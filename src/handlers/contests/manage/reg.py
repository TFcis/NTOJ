from handlers.base import reqenv, RequestHandler
from handlers.contests.base import contest_require_permission
from services.contests import ContestService
from services.user import UserService


class ContestManageRegHandler(RequestHandler):
    @reqenv
    @contest_require_permission('admin')
    async def get(self):
        reg_list = []

        for acct_id in self.contest.reg_list:
            err, acct = await UserService.inst.info_acct(acct_id)
            if err:
                continue

            reg_list.append(acct)

        await self.render('contests/manage/reg', page='reg',
                          contest_id=self.contest.contest_id, contest=self.contest, reg_list=reg_list)

    @reqenv
    @contest_require_permission('admin')
    async def post(self):
        reqtype = self.get_argument('reqtype')

        if reqtype == 'approval':
            acct_id = int(self.get_argument('acct_id'))

            if acct_id not in self.contest.reg_list:
                self.error('Enoext')
                return
            elif self.contest.is_member(acct_id=acct_id):
                self.error('Eexist')
                return

            self.contest.reg_list.remove(acct_id)
            self.contest.acct_list.append(acct_id)
            self.contest.reg_list.sort()
            self.contest.acct_list.sort()

            # TODO: send notify to user

            await ContestService.inst.update_contest(self.acct, self.contest)
            await self.finish('S')

        elif reqtype == 'reject':
            acct_id = int(self.get_argument('acct_id'))

            if acct_id not in self.contest.reg_list:
                self.error('Enoext')
                return
            elif self.contest.is_member(acct_id=acct_id):
                self.error('Eexist')
                return

            self.contest.reg_list.remove(acct_id)
            self.contest.reg_list.sort()

            # TODO: send notify to user

            await ContestService.inst.update_contest(self.acct, self.contest)
            await self.finish('S')

        else:
            self.error('Eunk')
