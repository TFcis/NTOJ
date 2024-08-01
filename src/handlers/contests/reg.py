import datetime

from services.contests import RegMode, ContestService
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

        if reqtype == 'reg':
            if self.contest.is_admin(self.acct):
                self.error('Eexist')
                return

            else:
                if self.contest.reg_mode is RegMode.FREE_REG and self.acct.acct_id in self.contest.acct_list:
                    self.error('Eexist')
                    return

                elif self.contest.reg_mode is RegMode.REG_APPROVAL and self.acct.acct_id in self.contest.reg_list:
                    self.error('Eexist')
                    return

            if datetime.datetime.now().replace(tzinfo=datetime.timezone(datetime.timedelta(hours=+8))) > self.contest.reg_end:
                self.error('Etime')
                return

            if self.contest.reg_mode is RegMode.INVITED:
                self.error('Eacces')
                return

            elif self.contest.reg_mode is RegMode.FREE_REG:
                self.contest.acct_list.append(self.acct.acct_id)
                self.contest.acct_list.sort()

            elif self.contest.reg_mode is RegMode.REG_APPROVAL:
                self.contest.reg_list.append(self.acct.acct_id)
                self.contest.reg_list.sort()

            await ContestService.inst.update_contest(self.acct, self.contest)
            self.finish('S')

        elif reqtype == 'unreg':
            if self.contest.is_admin(self.acct):
                self.error('Eexist')
                return
            else:
                if self.contest.reg_mode is RegMode.FREE_REG and self.acct.acct_id not in self.contest.acct_list:
                    self.error('Eexist')
                    return

                elif self.contest.reg_mode is RegMode.REG_APPROVAL and self.acct.acct_id not in self.contest.reg_list:
                    self.error('Eexist')
                    return

            if self.contest.reg_mode is RegMode.INVITED:
                self.error('Eacces')
                return

            elif self.contest.reg_mode is RegMode.FREE_REG:
                self.contest.acct_list.remove(self.acct.acct_id)
                self.contest.acct_list.sort()

            elif self.contest.reg_mode is RegMode.REG_APPROVAL:
                if self.acct.acct_id in self.contest.reg_list:
                    changed_list = self.contest.reg_list
                else:
                    changed_list = self.contest.acct_list

                changed_list.remove(self.acct.acct_id)
                changed_list.sort()

            await ContestService.inst.update_contest(self.acct, self.contest)
            self.finish('S')

        else:
            self.error('Eunk')
