from handlers.base import RequestHandler, reqenv, require_permission
from services.group import GroupService
from services.log import LogService

from services.user import UserConst, UserService


class ManageAcctHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self, page=None):
        if page is None:
            _, acctlist = await UserService.inst.list_acct(UserConst.ACCTTYPE_KERNEL, True)
            await self.render('manage/acct/acct-list', page='acct', acctlist=acctlist)

        elif page == 'update':
            acct_id = int(self.get_argument('acctid'))

            _, acct = await UserService.inst.info_acct(acct_id)
            glist = await GroupService.inst.list_group()
            group = await GroupService.inst.group_of_acct(acct_id)
            await self.render('manage/acct/update', page='acct', acct=acct, glist=glist, group=group)

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self, page=None):
        reqtype = self.get_argument('reqtype')

        if page == 'update' and reqtype == 'update':
            acct_id = int(self.get_argument('acct_id'))
            acct_type = int(self.get_argument('acct_type'))
            clas = int(self.get_argument('class'))
            group = str(self.get_argument('group'))
            err, acct = await UserService.inst.info_acct(acct_id)

            if err:
                await LogService.inst.add_log(
                    f"{self.acct.name}(#{self.acct.acct_id}) had been send a request to update the account #{acct_id} but not found",
                    'manage.acct.update.failure')
                self.error(err)
                return

            await LogService.inst.add_log(
                f"{self.acct.name}(#{self.acct.acct_id}) had been send a request to update the account {acct.name}(#{acct.acct_id})",
                'manage.acct.update')

            err, _ = await UserService.inst.update_acct(acct_id, acct_type, clas, acct.name, acct.photo, acct.cover)
            if err:
                self.error(err)
                return

            _ = await GroupService.inst.set_acct_group(acct_id, group)
            self.finish('S')
