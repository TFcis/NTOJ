from handlers.base import ActionDispatcher, RequestHandler, reqenv, require_permission
from services.pack import PackService
from services.user import UserConst


pack_dispatcher = ActionDispatcher()


class ManagePackHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        reqtype = self.get_argument("reqtype")
        return await pack_dispatcher.dispatch(self, reqtype)

    @pack_dispatcher.action("gettoken")
    async def get_pack_token(self):
        _, pack_token = await PackService.inst.gen_token()
        self.error(("S", pack_token))
