from handlers.base import reqenv, RequestHandler
from handlers.contests.base import contest_require_permission
from services.contests import ContestService
from services.user import UserService
from utils.numeric import parse_list_str


class ContestManageAcctHandler(RequestHandler):
    @reqenv
    @contest_require_permission('admin')
    async def get(self):
        admin_list = []
        acct_list = []
        for admin_id in self.contest.admin_list:
            _, acct = await UserService.inst.info_acct(admin_id)
            admin_list.append(acct)

        for acct_id in self.contest.acct_list:
            _, acct = await UserService.inst.info_acct(acct_id)
            acct_list.append(acct)

        await self.render('contests/manage/acct', page='acct',
                          contest_id=self.contest.contest_id, acct_list=acct_list, admin_list=admin_list)

    @reqenv
    @contest_require_permission('admin')
    async def post(self):
        reqtype = self.get_argument('reqtype')
        acct_id = self.get_argument('acct_id')
        list_type = self.get_argument('type')

        changed_list = None
        if list_type == "normal":
            changed_list = self.contest.acct_list
        elif list_type == "admin":
            changed_list = self.contest.admin_list

        if reqtype == "add":
            acct_id = int(acct_id)
            err, _ = await UserService.inst.info_acct(acct_id)
            if err:
                self.error(err)
                return

            if self.contest.is_member(acct_id=acct_id):
                self.error('Eexist')
                return

            if acct_id in changed_list:
                self.error('Eexist')
                return

            if acct_id in self.contest.reg_list:
                self.contest.reg_list.remove(acct_id)

            changed_list.append(acct_id)
            await ContestService.inst.update_contest(self.acct, self.contest)
            await self.finish('S')

        elif reqtype == "remove":
            acct_id = int(acct_id)

            if not self.contest.is_member(acct_id=acct_id):
                self.error('Enoext')
                return

            err, _ = await UserService.inst.info_acct(acct_id)
            if err:
                self.error(err)
                return

            if acct_id not in changed_list:
                self.error('Enoext')
                return

            # NOTE: Prevent admin remove self
            if self.acct.acct_id == acct_id and self.contest.is_admin(acct_id=acct_id):
                self.error('Eacces')
                return

            changed_list.remove(acct_id)
            await ContestService.inst.update_contest(self.acct, self.contest)
            await self.finish('S')

        elif reqtype == "multi_add":
            acct_list = []

            for a_id in parse_list_str(acct_id):
                if self.contest.is_member(acct_id=a_id):
                    continue

                err, _ = await UserService.inst.info_acct(a_id)
                if err:
                    continue

                acct_list.append(a_id)

                if a_id in self.contest.reg_list:
                    self.contest.reg_list.remove(a_id)

            acct_list = filter(lambda pro_id: pro_id not in changed_list, acct_list)
            changed_list.extend(acct_list)
            changed_list.sort()

            await ContestService.inst.update_contest(self.acct, self.contest)
            await self.finish('S')

        elif reqtype == "multi_remove":
            acct_list = parse_list_str(acct_id)

            acct_list = filter(lambda acct_id: self.contest.is_member(acct_id=acct_id), acct_list)
            changed_list = filter(lambda acct_id: acct_id not in acct_list, changed_list)

            # NOTE: Prevent admin remove self
            if self.acct.acct_id in changed_list and self.contest.is_admin(self.acct):
                changed_list.remove(self.acct.acct_id)

            changed_list.sort()

            await ContestService.inst.update_contest(self.acct, self.contest)
            await self.finish('S')

        else:
            self.error('Eunk')
