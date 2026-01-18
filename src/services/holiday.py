import datetime
from dataclasses import dataclass

@dataclass(slots=True, kw_only=True)
class DayRange:
    start: datetime.datetime
    end: datetime.datetime

class HolidayService:
    def __init__(self, db, rs) -> None:
        self.db = db
        self.rs = rs
        HolidayService.inst = self

    async def is_weekday(self, time: datetime.datetime):
        timestamp = time.timestamp()
        async with self.db.acquire() as con:
            res = await con.fetchrow(
                '''
                    SELECT COUNT(*) AS cnt FROM "weekdays"
                    WHERE $1 >= "start" AND $1 < "end"
                ''',
                int(timestamp),
            )
        return res[0]['cnt'] != 0

    async def is_weekday_now(self):
        timestamp = datetime.datetime.now().timestamp()
        valid_time = self.rs.get('weekday_valid_time', 0)
        is_weekday = self.rs.get('is_weekday', False)
        if timestamp < valid_time:
            return is_weekday

        async with self.db.acquire() as con:
            res = await con.fetchrow(
                '''
                    SELECT MIN("start") AS start, MIN("end") AS end FROM "weekdays"
                    WHERE "start" >= $1 OR "end" >= $1
                ''',
                int(timestamp),
            )
        if not res or not res[0]['start'] or not res[0]['end']:
            self.rs.set('weekday_valid_time', timestamp + 30*86400) # valid for one month
            self.rs.set('is_weekday', False)
            return False

        start = res[0]['start']
        end = res[0]['end']
        self.rs.set('weekday_valid_time', min(start, end))
        self.rs.set('is_weekday', end <= start)
        return end <= start

    async def get_weekdays(self) -> list[DayRange]:
        async with self.db.acquire() as con:
            res = await con.fetch(
                '''
                    SELECT "start", "end" FROM "weekdays" ORDER BY "start" ASC
                ''',
            )
        result = [
            DayRange(
                start=datetime.datetime.fromtimestamp(row['start']),
                end=datetime.datetime.fromtimestamp(row['end']),
            ) for row in res
        ]
        return result

    async def update_weekdays(self, old: DayRange|None, new: DayRange):
        '''
            Update the weekday time range.
            If old is None, insert new as a new range.
            If old is not None, update the existing range to new.
            Range that overlaps with new will be merged into new.
        '''
        new_timestamp = [int(new.start.timestamp()), int(new.end.timestamp())]

        async with self.db.acquire() as con:
            if not old or new.start < old.start:
                # Try to extend start earlier
                res = await con.fetch(
                    '''
                        SELECT "start" FROM "weekdays"
                        WHERE "start" <= $1 AND $1 <= "end";
                    ''',
                    new_timestamp[0],
                )
                if res:
                    new_timestamp[0] = res[0]['start']
            if not old or new.end > old.end:
                # Try to extend end later
                res = await con.fetch(
                    '''
                        SELECT "end" FROM "weekdays"
                        WHERE "start" <= $1 AND $1 <= "end";
                    ''',
                    new_timestamp[1],
                )
                if res:
                    new_timestamp[1] = res[0]['end']

            if old:
                res = await con.execute(
                    '''
                        UPDATE "weekdays" SET "start" = $1, "end" = $2
                        WHERE "start" = $3 AND "end" = $4;
                    ''',
                    new_timestamp[0],
                    new_timestamp[1],
                    int(old.start.timestamp()),
                    int(old.end.timestamp()),
                )
                if res == 'UPDATE 0':
                    return ('Enoext', 'Old weekday range not found')

            await con.execute(
                '''
                    DELETE FROM "weekdays"
                    WHERE $1 < "start" AND "end" < $2;
                ''',
                new_timestamp[0],
                new_timestamp[1],
            )

        # Invalidate cache
        self.rs.set('weekday_valid_time', 0)
        return None

    async def delete_weekday(self, target: DayRange):
        async with self.db.acquire() as con:
            res = await con.execute(
                '''
                    DELETE FROM "weekdays"
                    WHERE "start" = $1 AND "end" = $2;
                ''',
                int(target.start.timestamp()),
                int(target.end.timestamp()),
            )
            if res == 'DELETE 0':
                return ('Enoext', 'Target weekday range not found')

        # Invalidate cache
        self.rs.set('weekday_valid_time', 0)
        return None

    async def delete_weekday_range(self, range: DayRange):
        '''
            Remove all weekdays within the specified range.
            Overlapping ranges won't be affected.
        '''
        async with self.db.acquire() as con:
            await con.execute(
                '''
                    DELETE FROM "weekdays"
                    WHERE $1 <= "start" AND "end" <= $2;
                ''',
                int(range.start.timestamp()),
                int(range.end.timestamp()),
            )

        # Invalidate cache
        self.rs.set('weekday_valid_time', 0)
        return None
