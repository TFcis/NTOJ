from handlers.base import reqenv, RequestHandler
from handlers.contests.base import contest_require_permission
from services.contests import ContestService, UserStatus
from services.user import UserService


class ContestManageRegHandler(RequestHandler):
    @reqenv
    @contest_require_permission('admin')
    async def get(self):
        reg_list = []

        for acct_id, v in self.contest.user_list.items():
            if v['status'] in [UserStatus.REJECTED, UserStatus.REQUESTED]:
                _, acct = await UserService.inst.info_acct(acct_id)
                reg_list.append(acct)


        await self.render('contests/manage/reg', page='reg',
                          contest_id=self.contest.contest_id, contest=self.contest, reg_list=reg_list)

    @reqenv
    @contest_require_permission('admin')
    async def post(self):
        reqtype = self.get_argument('reqtype')

        if reqtype == 'approval':
            acct_id = int(self.get_argument('acct_id'))

            if not self.contest.member_is_status(acct_id, UserStatus.REQUESTED):
                self.error('Enoext')
                return

            self.contest.user_list[acct_id]['status'] = UserStatus.APPROVED

            # TODO: send notify to user

            await ContestService.inst.update_contest(self.acct, self.contest, userlist_updated=True)
            await self.finish('S')

        elif reqtype == 'reject':
            acct_id = int(self.get_argument('acct_id'))

            if not self.contest.member_is_status(acct_id, UserStatus.REQUESTED):
                self.error('Enoext')
                return

            self.contest.user_list[acct_id]['status'] = UserStatus.REJECTED

            # TODO: send notify to user

            await ContestService.inst.update_contest(self.acct, self.contest, userlist_updated=True)
            await self.finish('S')

        else:
            self.error('Eunk')
