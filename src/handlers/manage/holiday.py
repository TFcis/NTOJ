import datetime

from handlers.base import ActionDispatcher, RequestHandler, reqenv, require_permission
from services.user import UserConst
from services.holiday import HolidayService, TimeSlot
import config

holiday_dispatcher = ActionDispatcher()

class ManageHolidayHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
        if self.get_argument("action", None) == "events":
            await self._get_events()
            return
        await self.render("manage/holiday", page="holiday")

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self, page=None):
        reqtype = self.get_argument("reqtype")
        return await holiday_dispatcher.dispatch(self, reqtype)

    async def _get_events(self):
        '''
            Return json data of the requested month
        '''
        year = int(self.get_argument("year"))
        month = int(self.get_argument("month"))
        MAX_DAYS_SHOW = 42 # TUI calendar shows 6 weeks in month view
        base_date = datetime.datetime(year, month, 1, tzinfo=config.TIMEZONE)
        query_range = TimeSlot(
            base_date - datetime.timedelta(days=7), 
            base_date + datetime.timedelta(days=MAX_DAYS_SHOW-1)
        )
        err, res = await HolidayService.inst.get_time_slots(query_range)
        if err:
            return self.error(err)

        RED = '#ff5555'
        GREEN = '#50fa7b'
        events = [
            {
                'calendarId': str(day['range'].start.timestamp()),
                'title': f'{day['range'].start.astimezone(config.TIMEZONE).strftime("%H:%M")} - {
                            day['range'].end.astimezone(config.TIMEZONE).strftime("%H:%M")}',
                'start': day['range'].start.astimezone(config.TIMEZONE).isoformat(),
                'end': day['range'].end.astimezone(config.TIMEZONE).isoformat(),
                'backgroundColor': GREEN if day['is_weekday'] else RED,
                
            }
            for day in res
        ]
        self.error(('S',events))

    @holiday_dispatcher.action("add")
    async def add_holiday(self):
        start = self.get_argument("new_start")
        end = self.get_argument("new_end")
        is_weekday = self.get_argument("is_weekday") == '1'

        try:
            start = datetime.datetime.strptime(start, '%Y/%m/%d %H:%M')
            start = start.replace(tzinfo=config.TIMEZONE)
            end = datetime.datetime.strptime(end, '%Y/%m/%d %H:%M')
            end = end.replace(tzinfo=config.TIMEZONE)
        except ValueError:
            return self.error(('Eparam', 'Invalid date format'))

        if start >= end:
            return self.error(('Eparam', 'Start time must be before end time'))

        new_slot = TimeSlot(start, end)
        err = await HolidayService.inst.add_time_slot(new_slot, is_weekday)
        if err:
            return self.error(err)

        self.error(('S', ''))

    @holiday_dispatcher.action("update")
    async def update_holiday(self):
        old_start = self.get_argument("old_start")
        old_end = self.get_argument("old_end")
        new_start = self.get_argument("new_start")
        new_end = self.get_argument("new_end")
        is_weekday = self.get_argument("is_weekday") == '1'

        try:
            old_start = datetime.datetime.strptime(old_start, '%Y/%m/%d %H:%M')
            old_start = old_start.replace(tzinfo=config.TIMEZONE)
            old_end = datetime.datetime.strptime(old_end, '%Y/%m/%d %H:%M')
            old_end = old_end.replace(tzinfo=config.TIMEZONE)
            start = datetime.datetime.strptime(new_start, '%Y/%m/%d %H:%M')
            start = start.replace(tzinfo=config.TIMEZONE)
            end = datetime.datetime.strptime(new_end, '%Y/%m/%d %H:%M')
            end = end.replace(tzinfo=config.TIMEZONE)
        except ValueError:
            return self.error(('Eparam', 'Invalid date format'))

        if start >= end:
            return self.error(('Eparam', 'Start time must be before end time'))

        old_slot = TimeSlot(old_start, old_end)
        new_slot = TimeSlot(start, end)
        err = await HolidayService.inst.delete_time_slot(old_slot)
        if err:
            return self.error(err)
        err = await HolidayService.inst.add_time_slot(new_slot, is_weekday)
        if err:
            return self.error(err)

        self.error(('S', ''))

    @holiday_dispatcher.action("delete")
    async def delete_holiday(self):
        start = self.get_argument("old_start")
        end = self.get_argument("old_end")

        try:
            start = datetime.datetime.strptime(start, '%Y/%m/%d %H:%M')
            start = start.replace(tzinfo=config.TIMEZONE)
            end = datetime.datetime.strptime(end, '%Y/%m/%d %H:%M')
            end = end.replace(tzinfo=config.TIMEZONE)
        except ValueError:
            return self.error(('Eparam', 'Invalid date format'))

        del_slot = TimeSlot(start, end)
        err = await HolidayService.inst.delete_time_slot(del_slot)
        if err:
            return self.error(err)

        self.error(('S', ''))
