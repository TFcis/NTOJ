import datetime

from services.contests import RegMode, ContestService, UserStatus
from services.user import UserConst
from handlers.base import RequestHandler, reqenv, require_permission, ActionDispatcher

contest_reg_dispatcher = ActionDispatcher()


class ContestRegHandler(RequestHandler):
    @reqenv
    @require_permission([UserConst.ACCTTYPE_USER, UserConst.ACCTTYPE_KERNEL])
    async def get(self):
        if not self.contest:
            return self.error(("Enoext", "Contest not found"))

        if self.contest.is_admin(self.acct):
            return self.error(("Eacces", "Contest admin do not need to register"))

        await self.render("contests/reg", contest=self.contest)

    @contest_reg_dispatcher.action("reg")
    async def register_action(self):
        acct_id = self.acct.acct_id

        if self.contest.is_admin(self.acct):
            return self.error(("Eacces", "Contest admin do not need to register"))

        status = None
        if self.contest.reg_mode is RegMode.FREE_REG:
            status = UserStatus.APPROVED
        elif self.contest.reg_mode is RegMode.REG_APPROVAL:
            status = UserStatus.REQUESTED
        elif self.contest.reg_mode is RegMode.PASSWORD:
            status = UserStatus.APPROVED

        if (
            acct_id in self.contest.user_list
            and self.contest.user_list[acct_id]["status"] == status
        ):
            return self.error(("Eexist", "Already registered"))

        if datetime.datetime.now(datetime.UTC) > self.contest.reg_end:
            return self.error(
                (
                    "Etime",
                    "Registration time has passed. Please remember to register earlier next time",
                )
            )

        if self.contest.reg_mode is RegMode.INVITED:
            return self.error(("Eacces", "Invited mode do not allow register"))

        elif self.contest.reg_mode is RegMode.PASSWORD:
            password = self.get_argument("password", "")
            if password != self.contest.contest_password:
                return self.error(("Eacces", "Invalid password"))

            self.contest.user_list[acct_id] = {"status": UserStatus.APPROVED}

        elif self.contest.reg_mode is RegMode.FREE_REG:
            self.contest.user_list[acct_id] = {"status": UserStatus.APPROVED}

        elif self.contest.reg_mode is RegMode.REG_APPROVAL:
            self.contest.user_list[acct_id] = {"status": UserStatus.REQUESTED}

        await ContestService.inst.update_contest(
            self.acct, self.contest, userlist_updated=True
        )
        return self.error(("S", "Register Successfully"))

    @contest_reg_dispatcher.action("unreg")
    async def unregister_action(self):
        acct_id = self.acct.acct_id

        if self.contest.is_admin(self.acct):
            return self.error(("Eacces", "Contest admin do not need to register"))

        if self.contest.reg_mode is RegMode.INVITED:
            return self.error(("Eacces", "Invited mode do not allow register"))

        if self.contest.reg_mode is RegMode.PASSWORD:
            return self.error(("Eacces", "Password mode do not allow unregister"))

        if acct_id not in self.contest.user_list:
            return self.error(("Enoext", "You have not registered yet"))

        self.contest.user_list.pop(acct_id)

        await ContestService.inst.update_contest(
            self.acct, self.contest, userlist_updated=True
        )
        return self.error(("S", "Unregister Successfully"))

    @reqenv
    @require_permission([UserConst.ACCTTYPE_USER, UserConst.ACCTTYPE_KERNEL])
    async def post(self):
        reqtype = self.get_argument("reqtype")
        return await contest_reg_dispatcher.dispatch(self, reqtype)
