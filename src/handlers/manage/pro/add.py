from handlers.base import ActionDispatcher, RequestHandler, reqenv, require_permission
from services.log import LogService
from services.pro import ProService
from services.user import UserConst

add_dispatcher = ActionDispatcher()


class ManageProAddHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
        await self.render("manage/pro/add", "Add Problem", page="pro")

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        reqtype = self.get_argument("reqtype")
        return await add_dispatcher.dispatch(self, reqtype)

    @add_dispatcher.action("addpro")
    async def add_pro(self):
        name = self.get_argument("name")
        try:
            status = int(self.get_argument("status"))
        except ValueError:
            return self.error(("Eparam", "Invalid status"))
        mode = self.get_argument("mode")

        pack_token = None
        if mode == "upload":
            pack_token = self.get_argument("pack_token")

        err, pro_id = await ProService.inst.add_pro(name, status)
        await self.add_log(
            f"{self.acct.name} has sent a request to add the problem #{pro_id}",
            "manage.pro.add.pro",
            {"acct_id": self.acct.acct_id},
        )
        if err:
            return self.error(err)

        if mode == "upload" and pack_token:
            err, _ = await ProService.inst.unpack_pro(pro_id, pack_token)
            if err:
                return self.error(err)

        self.error(("S", pro_id))
