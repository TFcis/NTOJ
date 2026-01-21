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
