from enum import IntEnum
import datetime
from dataclasses import dataclass
import requests

@dataclass(slots=True)
class DayRange:
    start: datetime.datetime
    end: datetime.datetime

class DayPriority(IntEnum):
    NONE = 0
    GOV = 1
    SCHOOL = 2
    MANUAL = 3

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
                    WHERE $1 >= "start" AND $1 < "end" AND "is_weekday" = TRUE
                ''',
                int(timestamp),
            )
        return res[0]['cnt'] != 0

    async def is_weekday_now(self):
        timestamp = datetime.datetime.now().timestamp()
        valid_time = await self.rs.get('weekday_valid_time')
        is_weekday = await self.rs.get('is_weekday')
        if valid_time and timestamp < valid_time:
            return is_weekday

        async with self.db.acquire() as con:
            res = await con.fetchrow(
                '''
                    SELECT MIN("start") AS start, MIN("end") AS end FROM "weekdays"
                    WHERE ("start" >= $1 OR "end" >= $1) AND "is_weekday" = TRUE
                ''',
                int(timestamp),
            )
        if not res or not res[0]['start'] or not res[0]['end']:
            await self.rs.set('weekday_valid_time', timestamp + 30*86400) # valid for one month
            await self.rs.set('is_weekday', False)
            return False

        start = res[0]['start']
        end = res[0]['end']
        await self.rs.set('weekday_valid_time', min(start, end))
        await self.rs.set('is_weekday', end <= start)
        return end <= start

    async def fetch_gov_data(self):

        async def add_weekdays(dt, days):
            # Add 'days' weekdays after dt
            for d in range(1, days + 1):
                # weekday from 7 a.m. to 4 p.m.
                start = dt + datetime.timedelta(days=d,hours=7)
                end = dt + datetime.timedelta(days=d,hours=16)
                await self.add_days(DayRange(start=start, end=end), True, DayPriority.GOV)
        
        BASE_API_URL = 'https://data.taipei/api/v1/dataset/0dcbcfcf-f7a1-4664-a810-82c01cb524e0?scope=resourceAquire'
        offset = await self._get_offset()
        resp = requests.get(f'{BASE_API_URL}&offset={offset}&limit=1000')
        if resp.status_code != 200:
            return ('Eio', f'Failed to fetch holiday data: HTTP {resp.status_code}')

        data = resp.json()
        last_holiday = data['result']['results'][0]['date']
        last_holiday = datetime.datetime.strptime(last_holiday, '%Y%m%d')

        WINTER = DayRange(datetime.datetime(last_holiday.year, 1, 21), datetime.datetime(last_holiday.year, 2, 10, 23, 59))
        SUMMER = DayRange(datetime.datetime(last_holiday.year, 7, 1), datetime.datetime(last_holiday.year, 8, 29, 23, 59))
        for idx, item in enumerate(data['result']['results']):
            dt = datetime.datetime.strptime(item['date'], '%Y%m%d')

            if dt.year > WINTER.start.year:
                # New year, reset vacation periods
                WINTER = DayRange(datetime.datetime(dt.year, 1, 21), datetime.datetime(dt.year, 2, 10, 23, 59))
                SUMMER = DayRange(datetime.datetime(dt.year, 7, 1), datetime.datetime(dt.year, 8, 29, 23, 59))

            if dt <= last_holiday:
                continue

            if WINTER.start <= dt <= WINTER.end:
                await add_weekdays(last_holiday, (WINTER.start - last_holiday).days - 1)
                last_holiday = WINTER.end
                await self.add_days(WINTER, False, DayPriority.GOV)
                continue
            if SUMMER.start <= dt <= SUMMER.end:
                await add_weekdays(last_holiday, (SUMMER.start - last_holiday).days - 1)
                last_holiday = SUMMER.end
                await self.add_days(SUMMER, False, DayPriority.GOV)
                continue

            is_holiday = item['is_holiday'] == '是' \
                         or (item['holidaycategory'] in ('星期六、星期日', '補假', '放假之紀念日及節日'))
            if is_holiday:
                await add_weekdays(last_holiday, (dt - last_holiday).days - 1)
                if item['holidaycategory'] != '星期六、星期日':
                    # Only add non-weekend holidays
                    holiday = DayRange(dt, dt + datetime.timedelta(hours=23, minutes=59))
                    await self.add_days(holiday, False, DayPriority.GOV)
                    continue
                last_holiday = dt
            elif idx == len(data['result']['results']) - 1:
                # This is last data
                await add_weekdays(last_holiday, (dt - last_holiday).days)

        new_offset = data['result']['results'][-1]['_id'] - 1
        await self.rs.set('weekday_fetch_offset', new_offset)
        if new_offset != offset:
            async with self.db.acquire() as con:
                await con.execute(
                    '''
                        UPDATE "weekdays_fetch_status" SET "offset" = $1:
                    ''',
                    new_offset,
                )

        return None

    async def fetch_shool_data(self):
        BASE_API_URL = 'https://clients6.google.com/calendar/v3/calendars/library@gm.tnfsh.tn.edu.tw/events?calendarId=library%40gm.tnfsh.tn.edu.tw&singleEvents=true&eventTypes=default&eventTypes=focusTime&eventTypes=outOfOffice&timeZone=Asia%2FTaipei&maxAttendees=1&maxResults=250&sanitizeHtml=true&key=AIzaSyBNlYH01_9Hc5S1J9vuFmu2nUqBZJNAXxs&%24unique=gc237'

        now = datetime.datetime.now()
        now_6months = now + datetime.timedelta(days=180)
        resp = requests.get(f'{BASE_API_URL}&timeMin={now.strftime("%Y-%m-%dT00:00:00+08:00")}&timeMax={now_6months.strftime("%Y-%m-%dT23:59:59+08:00")}')
        if resp.status_code != 200:
            return ('Eio', f'Failed to fetch school holiday data: HTTP {resp.status_code}')

        data = resp.json()

        holidays = [
            item for item in data['items'] if '放假' in item['summary']
        ]

        for item in holidays:
            start_str = item['start'].get('dateTime', item['start'].get('date'))
            end_str = item['end'].get('dateTime', item['end'].get('date'))

            start_dt = datetime.datetime.fromisoformat(start_str)
            end_dt = datetime.datetime.fromisoformat(end_str)

            await self.add_days(DayRange(start=start_dt, end=end_dt), False, DayPriority.SCHOOL)

        return None

    async def get_days(self, range: DayRange):
        await self.fetch_gov_data()
        await self.fetch_shool_data()
        async with self.db.acquire() as con:
            res = await con.fetch(
                '''
                    SELECT "start", "end", "is_weekday" FROM "weekdays" 
                    WHERE $1 <= "end" OR "start" <= $2
                    ORDER BY "start" ASC
                ''',
                int(range.start.timestamp()),
                int(range.end.timestamp()),
            )
        result = [
            {
                'range': DayRange(
                    start=datetime.datetime.fromtimestamp(row['start']),
                    end=datetime.datetime.fromtimestamp(row['end']),
                ),
                'is_weekday': row['is_weekday']
            } for row in res
        ]
        return None, result

    async def add_days(self, new: DayRange, is_weekday: bool=True, pri: DayPriority=DayPriority.MANUAL):
        '''
            Add the days time range.
            Overwrite existing ranges with lower priority.
        '''
        new_start = int(new.start.timestamp())
        new_end = int(new.end.timestamp())

        async with self.db.acquire() as con:
            # Try to merge with existing ranges of same priority
            res = await con.fetch(
                '''
                    SELECT "start" FROM "weekdays"
                    WHERE "start" < $1 AND $1 <= "end" AND "priority" = $2;
                ''',
                new_start, pri
            )
            if res:
                new_start = res[0]['start']
            res = await con.fetch(
                '''
                    SELECT "end" FROM "weekdays"
                    WHERE "start" <= $1 AND $1 < "end" AND "priority" = $2;
                ''',
                new_end, pri
            )
            if res:
                new_end = res[0]['end']

        async with self.db.acquire() as con:
            res = await con.execute(
                '''
                    SELECT "start", "end" FROM "weekdays"
                    WHERE $1 < "end" AND "start" < $2 AND "priority" > $3;
                ''',
                new_start, new_end, pri
            )

        # Avoid higher priority ranges
        new_timestamps = [[new_start, new_end]]
        for row in res:
            start = row['start']
            end = row['end']

            if start <= new_timestamps[-1][0]:
                new_timestamps[-1][0] = end
            elif end >= new_timestamps[-1][1]:
                new_timestamps[-1][1] = start
            else:
                new_timestamps[-1][1] = start
                new_timestamps.append([end, new_end])

        async with self.db.acquire() as con:
            await con.executemany(
                '''
                    DELETE FROM "weekdays"
                    WHERE $1 <= "start" AND "end" <= $2;
                ''',
                [(ts[0], ts[1]) for ts in new_timestamps],
            )
            await con.executemany(
                '''
                    INSERT INTO "weekdays" ("start", "end", "priority", "is_weekday")
                    VALUES ($1, $2, $3, $4);
                ''',
                [(ts[0], ts[1], pri, is_weekday) for ts in new_timestamps],
            )

        # Invalidate cache
        await self.rs.set('weekday_valid_time', 0)
        return None

    async def delete_days(self, target: DayRange):
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
        await self.rs.set('weekday_valid_time', 0)
        return None

    async def delete_day_range(self, range: DayRange):
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
        await self.rs.set('weekday_valid_time', 0)
        return None

    async def _get_offset(self):
        offset = await self.rs.get('weekday_fetch_offset')
        if offset:
            return offset

        async with self.db.acquire() as con:
            res = await con.fetchrow(
                '''
                    SELECT "offset" FROM "weekdays_fetch_status"
                ''',
            )
        return res['offset']
