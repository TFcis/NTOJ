from handlers.base import reqenv, RequestHandler
from handlers.contests.base import contest_require_permission
from services.contests import ContestService, UserStatus
from services.user import UserService
from utils.numeric import parse_list_str


class ContestManageAcctHandler(RequestHandler):
    @reqenv
    @contest_require_permission('admin')
    async def get(self):
        admin_list = []
        acct_list = []
        for acct_id, v in self.contest.user_list.items():
            _, acct = await UserService.inst.info_acct(acct_id)
            if v['status'] == UserStatus.ADMIN:
                admin_list.append(acct)
            elif v['status'] == UserStatus.APPROVED:
                acct_list.append(acct)

        await self.render('contests/manage/acct', page='acct',
                          contest_id=self.contest.contest_id, acct_list=acct_list, admin_list=admin_list)

    @reqenv
    @contest_require_permission('admin')
    async def post(self):
        reqtype = self.get_argument('reqtype')
        acct_id = self.get_argument('acct_id')
        list_type = self.get_argument('type')

        status = None
        if list_type == "normal":
            status = UserStatus.APPROVED
        elif list_type == "admin":
            status = UserStatus.ADMIN
        else:
            self.error('Eparam')
            return

        if reqtype == "add":
            acct_id = int(acct_id)
            self.contest.user_list[acct_id] = {
                "status": status,
            }

            await ContestService.inst.update_contest(self.acct, self.contest, userlist_updated=True)
            await self.finish('S')

        elif reqtype == "remove":
            acct_id = int(acct_id)
            if acct_id not in self.contest.user_list:
                self.error('Enoext')
                return

            self.contest.user_list.pop(acct_id)
            await ContestService.inst.update_contest(self.acct, self.contest, userlist_updated=True)
            await self.finish('S')

        elif reqtype == "multi_add":
            acct_list = []

            for a_id in parse_list_str(acct_id):
                self.contest.user_list[a_id] = {
                    "status": status,
                }

            await ContestService.inst.update_contest(self.acct, self.contest, userlist_updated=True)
            await self.finish('S')

        elif reqtype == "multi_remove":
            acct_list = parse_list_str(acct_id)

            for a_id in acct_list:
                try:
                    self.contest.user_list.pop(a_id)
                except KeyError:
                    continue

            await ContestService.inst.update_contest(self.acct, self.contest, userlist_updated=True)
            await self.finish('S')

        else:
            self.error('Eunk')
            return

        if list_type == "normal" or (list_type == "admin" and not self.contest.hide_admin):
            await self.rs.delete(f"contest_{self.contest.contest_id}_scores")
