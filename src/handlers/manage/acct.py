import tornado

from handlers.base import RequestHandler, reqenv, require_permission
from services.log import LogService
from services.user import UserConst, UserService


class ManageAcctHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self, page=None):
        if page is None:
            try:
                pageoff = int(self.get_argument('pageoff'))
            except tornado.web.HTTPError:
                pageoff = 0

            _, acctlist = await UserService.inst.list_acct(UserConst.ACCTTYPE_KERNEL, True)
            acct_total_cnt = len(acctlist)
            acctlist = acctlist[pageoff:pageoff + 40]
            await self.render('manage/acct/acct-list', page='acct', acctlist=acctlist,
                              pageoff=pageoff, acct_total_cnt=acct_total_cnt)

        elif page == 'update':
            acct_id = int(self.get_argument('acctid'))

            _, acct = await UserService.inst.info_acct(acct_id)
            await self.render('manage/acct/update', page='acct', acct=acct)

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self, page=None):
        reqtype = self.get_argument('reqtype')

        if page == 'update' and reqtype == 'update':
            acct_id = int(self.get_argument('acct_id'))
            acct_type = int(self.get_argument('acct_type'))
            err, acct = await UserService.inst.info_acct(acct_id)

            if err:
                await LogService.inst.add_log(
                    f"{self.acct.name}(#{self.acct.acct_id}) had been send a request to update the account #{acct_id} but not found",
                    'manage.acct.update.failure',
                )
                return self.error(err)

            await LogService.inst.add_log(
                f"{self.acct.name}(#{self.acct.acct_id}) had been send a request to update the account {acct.name}(#{acct.acct_id})",
                'manage.acct.update',
            )

            acct.acct_type = acct_type
            err, _ = await UserService.inst.update_acct(acct)
            if err:
                return self.error(err)

            self.error(('S', ''))
