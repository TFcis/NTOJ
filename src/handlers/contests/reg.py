import datetime

from services.contests import RegMode, ContestService, UserStatus
from services.user import UserConst
from handlers.base import RequestHandler, reqenv, require_permission


class ContestRegHandler(RequestHandler):
    @reqenv
    @require_permission([UserConst.ACCTTYPE_USER, UserConst.ACCTTYPE_KERNEL])
    async def get(self):
        if not self.contest:
            return self.error(('Enoext', 'Contest not found'))

        if self.contest.is_admin(self.acct):
            return self.error(('Eacces', 'Contest admin do not need to register'))

        await self.render('contests/reg', contest=self.contest)

    @reqenv
    @require_permission([UserConst.ACCTTYPE_USER, UserConst.ACCTTYPE_KERNEL])
    async def post(self):
        reqtype = self.get_argument("reqtype")
        acct_id = self.acct.acct_id

        if reqtype == 'reg':
            if self.contest.is_admin(self.acct):
                return self.error(('Eacces', 'Contest admin do not need to register'))

            else:
                status = None
                if self.contest.reg_mode is RegMode.FREE_REG:
                    status = UserStatus.APPROVED

                elif self.contest.reg_mode is RegMode.REG_APPROVAL:
                    status = UserStatus.REQUESTED

                if acct_id in self.contest.user_list and self.contest.user_list[acct_id]['status'] == status:
                    return self.error(('Eexist', 'Already registered'))

            if datetime.datetime.now().replace(tzinfo=datetime.timezone(datetime.timedelta(hours=+8))) > self.contest.reg_end:
                return self.error(('Etime', 'Registration time has passed. Please remember to register earlier next time'))

            if self.contest.reg_mode is RegMode.INVITED:
                return self.error(('Eacces', 'Invited mode do not allow register'))

            elif self.contest.reg_mode is RegMode.FREE_REG:
                self.contest.user_list[acct_id] = {
                    "status": UserStatus.APPROVED
                }

            elif self.contest.reg_mode is RegMode.REG_APPROVAL:
                self.contest.user_list[acct_id] = {
                    "status": UserStatus.REQUESTED
                }

            await ContestService.inst.update_contest(self.acct, self.contest, userlist_updated=True)
            self.error(('S', 'Register Successfully'))

        elif reqtype == 'unreg':
            if self.contest.is_admin(self.acct):
                return self.error(('Eacces', 'Contest admin do not need to register'))

            if self.contest.reg_mode is RegMode.INVITED:
                return self.error(('Eacces', 'Invited mode do not allow register'))

            if acct_id not in self.contest.user_list:
                return self.error(('Enoext', 'You have not registered yet' ))

            self.contest.user_list.pop(acct_id)

            await ContestService.inst.update_contest(self.acct, self.contest, userlist_updated=True)
            self.error(('S', 'Unregister Successfully'))

        else:
            self.error(('Eunk', 'Unknown error'))
