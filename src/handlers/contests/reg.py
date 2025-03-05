import datetime

from services.contests import RegMode, ContestService, UserStatus
from services.user import UserConst
from handlers.base import RequestHandler, reqenv, require_permission


class ContestRegHandler(RequestHandler):
    @reqenv
    @require_permission([UserConst.ACCTTYPE_USER, UserConst.ACCTTYPE_KERNEL])
    async def get(self):
        if not self.contest:
            self.error('Enoext')
            return

        if self.contest.is_admin(self.acct):
            self.error('Eacces')
            return

        await self.render('contests/reg', contest=self.contest)

    @reqenv
    @require_permission([UserConst.ACCTTYPE_USER, UserConst.ACCTTYPE_KERNEL])
    async def post(self):
        reqtype = self.get_argument("reqtype")
        acct_id = self.acct.acct_id

        if reqtype == 'reg':
            if self.contest.is_admin(self.acct):
                self.error('Eacces')
                return

            else:
                status = None
                if self.contest.reg_mode is RegMode.FREE_REG:
                    status = UserStatus.APPROVED

                elif self.contest.reg_mode is RegMode.REG_APPROVAL:
                    status = UserStatus.REQUESTED

                if acct_id in self.contest.user_list and self.contest.user_list[acct_id]['status'] == status:
                    self.error('Eexist')
                    return

            if datetime.datetime.now().replace(tzinfo=datetime.timezone(datetime.timedelta(hours=+8))) > self.contest.reg_end:
                self.error('Etime')
                return

            if self.contest.reg_mode is RegMode.INVITED:
                self.error('Eacces')
                return

            elif self.contest.reg_mode is RegMode.FREE_REG:
                self.contest.user_list[acct_id] = {
                    "status": UserStatus.APPROVED
                }

            elif self.contest.reg_mode is RegMode.REG_APPROVAL:
                self.contest.user_list[acct_id] = {
                    "status": UserStatus.REQUESTED
                }

            await ContestService.inst.update_contest(self.acct, self.contest, userlist_updated=True)
            self.finish('S')

        elif reqtype == 'unreg':
            if self.contest.is_admin(self.acct):
                self.error('Eacces')
                return

            if self.contest.reg_mode is RegMode.INVITED:
                self.error('Eacces')
                return

            if acct_id not in self.contest.user_list:
                self.error('Enoext')
                return

            self.contest.user_list.pop(acct_id)

            await ContestService.inst.update_contest(self.acct, self.contest, userlist_updated=True)
            self.finish('S')

        else:
            self.error('Eunk')
