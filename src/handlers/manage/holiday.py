from handlers.base import ActionDispatcher, RequestHandler, reqenv, require_permission
from services.user import UserConst

holiday_dispatcher = ActionDispatcher()

class ManageHolidayHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
        await self.render("manage/holiday", page="holiday")

