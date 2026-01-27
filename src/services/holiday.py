from enum import IntEnum
import datetime
from dataclasses import dataclass
import ssl
from zoneinfo import ZoneInfo

import aiohttp

import config


@dataclass(slots=True)
class TimeSlot:
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
        async with self.db.acquire() as con:
            res = await con.fetchrow(
                '''
                    SELECT COUNT(*) AS cnt FROM "weekdays"
                    WHERE $1 >= "start" AND $1 < "end" AND "is_weekday" = TRUE
                ''',
                time
            )
        return res['cnt'] != 0

    async def is_weekday_now(self):
        now = datetime.datetime.now().astimezone(config.TIMEZONE)
        valid_time = await self.rs.get('weekday_valid_time')
        is_weekday = await self.rs.get('is_weekday')
        if valid_time and is_weekday and now.timestamp() < float(valid_time.decode()):
            return is_weekday == b'1'

        async with self.db.acquire() as con:
            res = await con.fetchrow(
                '''
                    SELECT "start", "end" FROM "weekdays"
                    WHERE "end" > $1 AND "is_weekday" = TRUE ORDER BY "start" ASC LIMIT 1
                ''',
                now,
            )
        if not res or not res['start'] or not res['end']:
            await self.rs.set('weekday_valid_time', now.timestamp() + 30*86400) # valid for one month
            await self.rs.set('is_weekday', 0)
            return False

        is_weekday = (res['start'] <= now)
        valid_time = res['end'] if is_weekday else res['start']
        await self.rs.set('weekday_valid_time', valid_time.timestamp())
        await self.rs.set('is_weekday', int(is_weekday))
        return is_weekday

    async def fetch_gov_data(self):

        async def add_weekdays(dt, days):
            # Add 'days' weekdays after dt
            for d in range(1, days + 1):
                # weekday from 7 a.m. to 4 p.m.
                start = dt + datetime.timedelta(days=d,hours=8)
                end = dt + datetime.timedelta(days=d,hours=16)
                await self.add_time_slot(TimeSlot(start=start, end=end), True, DayPriority.GOV)
        
        BASE_API_URL = 'https://data.taipei/api/v1/dataset/0dcbcfcf-f7a1-4664-a810-82c01cb524e0?scope=resourceAquire'
        offset = await self._get_offset()

        # Fix for "Missing Subject Key Identifier" when accessing data.taipei
        ctx = ssl.create_default_context()
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
        connector = aiohttp.TCPConnector(ssl=ctx)

        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(f'{BASE_API_URL}&offset={offset}&limit=1000') as resp:
                if resp.status != 200:
                    return ('Eio', f'Failed to fetch holiday data: HTTP {resp.status}')
                data = await resp.json()

        TW_ZONE = ZoneInfo('Asia/Taipei')
        last_holiday = data['result']['results'][0]['date']
        last_holiday = datetime.datetime.strptime(last_holiday, '%Y%m%d')
        last_holiday = last_holiday.replace(tzinfo=TW_ZONE)

        WINTER = TimeSlot(datetime.datetime(last_holiday.year, 1, 21, tzinfo=TW_ZONE), datetime.datetime(last_holiday.year, 2, 10, 23, 59, tzinfo=TW_ZONE))
        SUMMER = TimeSlot(datetime.datetime(last_holiday.year, 7, 1, tzinfo=TW_ZONE), datetime.datetime(last_holiday.year, 8, 29, 23, 59, tzinfo=TW_ZONE))
        for idx, item in enumerate(data['result']['results']):
            dt = datetime.datetime.strptime(item['date'], '%Y%m%d')
            dt = dt.replace(tzinfo=TW_ZONE)

            if dt.year > WINTER.start.year:
                # New year, reset vacation periods
                WINTER = TimeSlot(datetime.datetime(dt.year, 1, 21, tzinfo=TW_ZONE), datetime.datetime(dt.year, 2, 10, 23, 59, tzinfo=TW_ZONE))
                SUMMER = TimeSlot(datetime.datetime(dt.year, 7, 1, tzinfo=TW_ZONE), datetime.datetime(dt.year, 8, 29, 23, 59, tzinfo=TW_ZONE))

            if dt <= last_holiday:
                continue

            if WINTER.start <= dt <= WINTER.end:
                await add_weekdays(last_holiday, (WINTER.start - last_holiday).days - 1)
                last_holiday = WINTER.end - datetime.timedelta(hours=23, minutes=59)
                await self.add_time_slot(WINTER, False, DayPriority.GOV)
                continue
            if SUMMER.start <= dt <= SUMMER.end:
                await add_weekdays(last_holiday, (SUMMER.start - last_holiday).days - 1)
                last_holiday = SUMMER.end - datetime.timedelta(hours=23, minutes=59)
                await self.add_time_slot(SUMMER, False, DayPriority.GOV)
                continue

            is_holiday = item['isholiday'] == '是' \
                         and (item['holidaycategory'] in ('星期六、星期日', '補假', '放假之紀念日及節日'))
            if is_holiday:
                await add_weekdays(last_holiday, (dt - last_holiday).days - 1)
                if item['holidaycategory'] != '星期六、星期日':
                    # Only add non-weekend holidays
                    holiday = TimeSlot(dt, dt + datetime.timedelta(hours=23, minutes=59))
                    await self.add_time_slot(holiday, False, DayPriority.GOV)
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
                        UPDATE "weekdays_fetch_status" SET "offset" = $1;
                    ''',
                    new_offset,
                )

        return None

    async def fetch_shool_data(self):
        BASE_API_URL = 'https://clients6.google.com/calendar/v3/calendars/library@gm.tnfsh.tn.edu.tw/events?calendarId=library%40gm.tnfsh.tn.edu.tw&singleEvents=true&eventTypes=default&eventTypes=focusTime&eventTypes=outOfOffice&timeZone=Asia%2FTaipei&maxAttendees=1&maxResults=250&sanitizeHtml=true&key=AIzaSyBNlYH01_9Hc5S1J9vuFmu2nUqBZJNAXxs&%24unique=gc237'

        now = datetime.datetime.now().astimezone(ZoneInfo('Asia/Taipei'))
        six_month_later = now + datetime.timedelta(days=180)
        async with aiohttp.ClientSession() as session:
            async with session.get(f'{BASE_API_URL}&timeMin={now.strftime("%Y-%m-%dT00:00:00+08:00")}&timeMax={six_month_later.strftime("%Y-%m-%dT23:59:59+08:00")}') as resp:
                if resp.status != 200:
                    return ('Eio', f'Failed to fetch school holiday data: HTTP {resp.status}')
                data = await resp.json()

        holidays = [
            item for item in data['items'] if '放假' in item['summary']
        ]

        for item in holidays:
            start_str = item['start'].get('dateTime', item['start'].get('date'))
            end_str = item['end'].get('dateTime', item['end'].get('date'))

            start_dt = datetime.datetime.fromisoformat(start_str)
            end_dt = datetime.datetime.fromisoformat(end_str)

            await self.add_time_slot(TimeSlot(start=start_dt, end=end_dt), False, DayPriority.SCHOOL)

        return None

    async def get_time_slots(self, range: TimeSlot):
        last_fetch = await self.rs.get('weekday_last_fetch')
        if not last_fetch or float(last_fetch.decode()) + 86400 < datetime.datetime.now().timestamp():
            await self.fetch_gov_data()
            await self.fetch_shool_data()
            await self.rs.set('weekday_last_fetch', datetime.datetime.now().timestamp())
        async with self.db.acquire() as con:
            res = await con.fetch(
                '''
                    SELECT "start", "end", "is_weekday" FROM "weekdays" 
                    WHERE NOT ("end" < $1 OR $2 <= "start")
                    ORDER BY "start" ASC
                ''',
                range.start,
                range.end,
            )
        result = [
            {
                'range': TimeSlot(
                    start=row['start'].astimezone(config.TIMEZONE),
                    end=row['end'].astimezone(config.TIMEZONE)
                ),
                'is_weekday': row['is_weekday']
            } for row in res
        ]
        return None, result

    async def add_time_slot(self, new: TimeSlot, is_weekday: bool=True, pri: DayPriority=DayPriority.MANUAL):
        '''
            Add the given time slot as weekday/non-weekday with the given priority.
            Overwrite existing ranges with lower priority.
        '''
        async with self.db.acquire() as con:
            # Try to merge with existing ranges of same priority
            res = await con.fetch(
                '''
                    SELECT "start" FROM "weekdays"
                    WHERE "start" < $1 AND $1 <= "end" AND "priority" = $2 AND "is_weekday" = $3;
                ''',
                new.start, pri, is_weekday
            )
            if res:
                new.start = res[0]['start']
            res = await con.fetch(
                '''
                    SELECT "end" FROM "weekdays"
                    WHERE "start" <= $1 AND $1 < "end" AND "priority" = $2 AND "is_weekday" = $3;
                ''',
                new.end, pri, is_weekday
            )
            if res:
                new_end = res[0]['end']

            res = await con.fetch(
                '''
                    SELECT "start", "end" FROM "weekdays"
                    WHERE NOT ("end" <= $1 OR $2 <= "start") AND "priority" > $3;
                ''',
                new.start, new.end, pri
            )

        if res and res[0]['start'] <= new.start and new.end <= res[0]['end']:
            # Fully covered by higher priority range
            return None

        # Avoid higher priority ranges
        new_slots = [[new.start, new.end]]
        for row in res:
            start = row['start']
            end = row['end']

            if start <= new_slots[-1][0]:
                new_slots[-1][0] = end
            elif end >= new_slots[-1][1]:
                new_slots[-1][1] = start
            else:
                if start == new_slots[-1][0]:
                    new_slots[-1][0] = end
                    continue
                new_slots[-1][1] = start
                new_slots.append([end, new.end])

        if new_slots[-1][0] >= new_slots[-1][1]:
            new_slots.pop()

        async with self.db.acquire() as con:
            await con.executemany(
                '''
                    DELETE FROM "weekdays"
                    WHERE $1 <= "start" AND "end" <= $2;
                ''',
                [(ts[0], ts[1]) for ts in new_slots],
            )
            await con.executemany(
                '''
                    INSERT INTO "weekdays" ("start", "end", "priority", "is_weekday")
                    VALUES ($1, $2, $3, $4);
                ''',
                [(ts[0], ts[1], pri, is_weekday) for ts in new_slots],
            )

            res = await con.fetch(
                '''
                    SELECT "end", "priority", "is_weekday" FROM "weekdays"
                    WHERE "start" < $1 AND $2 < "end" AND "priority" <= $3;
                ''',
                new.start, new.end, pri
            )
            if res:
                # Split existing range
                await con.execute(
                    '''
                        UPDATE "weekdays" SET "end" = $1
                        WHERE "start" < $1 AND $2 < "end" AND "priority" <= $3;
                    ''',
                    new.start, new.end, pri
                )
                await con.execute(
                    '''
                        INSERT INTO "weekdays" ("start", "end", "priority", "is_weekday")
                        VALUES ($1, $2, $3, $4);
                    ''',
                    new.end, res[0]['end'] , res[0]['priority'], res[0]['is_weekday']
                )

            await con.execute(
                '''
                    UPDATE "weekdays" SET "start" = $1
                    WHERE ("start" < $1 AND $1 < "end") AND "priority" <= $2;
                ''',
                new.end, pri
            )
            await con.execute(
                '''
                    UPDATE "weekdays" SET "end" = $1
                    WHERE ("start" < $1 AND $1 < "end") AND "priority" <= $2;
                ''',
                new.start, pri
            )

        # Invalidate cache
        await self.rs.set('weekday_valid_time', 0)
        return None

    async def delete_time_slot(self, target: TimeSlot):
        async with self.db.acquire() as con:
            res = await con.execute(
                '''
                    DELETE FROM "weekdays"
                    WHERE "start" = $1 AND "end" = $2;
                ''',
                target.start,
                target.end,
            )
            if res == 'DELETE 0':
                return ('Enoext', 'Target weekday range not found')

        # Invalidate cache
        await self.rs.set('weekday_valid_time', 0)
        return None

    async def delete_range(self, range: TimeSlot):
        '''
            Remove all time slots within the specified range.
            Overlapping ranges won't be affected.
        '''
        async with self.db.acquire() as con:
            await con.execute(
                '''
                    DELETE FROM "weekdays"
                    WHERE $1 <= "start" AND "end" <= $2;
                ''',
                range.start,
                range.end,
            )

        # Invalidate cache
        await self.rs.set('weekday_valid_time', 0)
        return None

    async def _get_offset(self) -> int:
        offset = await self.rs.get('weekday_fetch_offset')
        if offset:
            return int(offset.decode())

        async with self.db.acquire() as con:
            res = await con.fetchrow(
                '''
                    SELECT "offset" FROM "weekdays_fetch_status"
                ''',
            )
        return res['offset']
