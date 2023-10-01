from handlers.base import RequestHandler, reqenv, require_permission

from services.user import UserConst


class ManageContestHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
        pass
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        pass
