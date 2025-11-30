from handlers.base import RequestHandler, reqenv, require_permission
from services.log import LogService
from services.pro import ProService, ProConst
from services.user import UserConst

ALLOW_STATUSES = [ProConst.STATUS_ONLINE, ProConst.STATUS_CONTEST, ProConst.STATUS_HIDDEN]


class ManageProAddHandler(RequestHandler):
    """Handler for adding new problems"""
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
        """Render add problem page"""
        await self.render('manage/pro/add', page='pro')

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        """Handle add problem request"""
        reqtype = self.get_argument('reqtype')

        if reqtype == 'addpro':
            name = self.get_argument('name')
            status = int(self.get_argument('status'))
            mode = self.get_argument('mode')

            pack_token = None
            if mode == "upload":
                pack_token = self.get_argument('pack_token')

            err, pro_id = await ProService.inst.add_pro(name, status)
            await LogService.inst.add_log(
                f"{self.acct.name} has sent a request to add the problem #{pro_id}",
                'manage.pro.add.pro',
                {'acct_id': self.acct.acct_id}
            )
            if err:
                return self.error(err)

            if mode == "upload" and pack_token:
                err, _ = await ProService.inst.unpack_pro(pro_id, pack_token)
                if err:
                    return self.error(err)

            self.error(('S', pro_id))
