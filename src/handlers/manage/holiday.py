import datetime

from handlers.base import ActionDispatcher, RequestHandler, reqenv, require_permission
from services.user import UserConst
from services.holiday import HolidayService, DayRange

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
        query_range = DayRange(
            datetime.datetime(year,month,1) - datetime.timedelta(days=7), 
            datetime.datetime(year,month,1) + datetime.timedelta(days=41)
        )
        err, res = await HolidayService.inst.get_days(query_range)
        if err:
            return self.error(err)

        RED = '#ff5555'
        GREEN = '#50fa7b'
        events = [
            {
                'calendarId': str(day['range'].start.timestamp()),
                'title': f'{day['range'].start.strftime("%H:%M")} - {day['range'].end.strftime("%H:%M")}',
                'start': day['range'].start.isoformat(),
                'end': day['range'].end.isoformat(),
                'backgroundColor': GREEN if day['is_weekday'] else RED,
                
            }
            for day in res
        ]
        self.error(('S',events))

    @holiday_dispatcher.action("update")
    async def update_holiday(self):
        old_start = self.get_argument("old_start")
        old_end = self.get_argument("old_end")
        new_start = self.get_argument("new_start")
        new_end = self.get_argument("new_end")
        is_weekday = self.get_argument("is_weekday") == '1'

        try:
            old_start = datetime.datetime.strptime(old_start, '%Y/%m/%d %H:%M')
            old_end = datetime.datetime.strptime(old_end, '%Y/%m/%d %H:%M')
            start = datetime.datetime.strptime(new_start, '%Y/%m/%d %H:%M')
            end = datetime.datetime.strptime(new_end, '%Y/%m/%d %H:%M')
        except ValueError:
            return self.error(('Eparam', 'Invalid date format'))

        if start >= end:
            return self.error(('Eparam', 'Start time must be before end time'))

        old_range = DayRange(old_start, old_end)
        new_range= DayRange(start, end)
        err = await HolidayService.inst.delete_days(old_range)
        if err:
            return self.error(err)
        err = await HolidayService.inst.add_days(new_range, is_weekday)
        if err:
            return self.error(err)

        self.error(('S', ''))

    @holiday_dispatcher.action("delete")
    async def delete_holiday(self):
        start = self.get_argument("old_start")
        end = self.get_argument("old_end")

        try:
            start = datetime.datetime.strptime(start, '%Y/%m/%d %H:%M')
            end = datetime.datetime.strptime(end, '%Y/%m/%d %H:%M')
        except ValueError:
            return self.error(('Eparam', 'Invalid date format'))

        del_range = DayRange(start, end)
        err = await HolidayService.inst.delete_days(del_range)
        if err:
            return self.error(err)

        self.error(('S', ''))
