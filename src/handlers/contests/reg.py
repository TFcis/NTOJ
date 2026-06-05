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
            return self.error(("Eacces", "Contest admin cannot register"))

        await self.render("contests/reg", f"{self.contest.name} - Registration", contest=self.contest)

    def check(self, action_name):
        if self.contest.is_admin(self.acct):
            return ("Eacces", f"Contest admin cannot {action_name}")

        if self.contest.reg_mode is RegMode.INVITED:
            return ("Eacces", f"Invited mode does not allow {action_name}")

    @contest_reg_dispatcher.action("reg")
    async def register_action(self):
        if error := self.check("register"):
            return self.error(error)

        if datetime.datetime.now(datetime.UTC) >= self.contest.reg_end:
            return self.error(
                (
                    "Etime",
                    "Registration time has passed. Please remember to register earlier next time",
                )
            )

        acct_id = self.acct.acct_id
        if self.contest.member_is_status(acct_id, UserStatus.REJECTED):
            assert self.contest.reg_mode is RegMode.REG_APPROVAL
            return self.error(
                ("Eacces", "Your registration has been rejected, you cannot register")
            )

        if self.contest.member_is_status(acct_id, UserStatus.REQUESTED):
            assert self.contest.reg_mode is RegMode.REG_APPROVAL
            return self.error(
                (
                    "Eacces",
                    "Your registration is in request status, please wait for approval",
                )
            )

        if self.contest.member_is_status(acct_id, UserStatus.APPROVED):
            return self.error(
                (
                    "Eexist",
                    "Your registration has been approved, you cannot register again",
                )
            )

        if self.contest.reg_mode is RegMode.FREE_REG:
            self.contest.user_list[acct_id] = {"status": UserStatus.APPROVED}

        elif self.contest.reg_mode is RegMode.REG_APPROVAL:
            self.contest.user_list[acct_id] = {"status": UserStatus.REQUESTED}

        await ContestService.inst.update_contest(
            self.acct, self.contest, userlist_updated=True
        )

        await self.add_log(
            f"{self.acct.name} registered for contest '{self.contest.name}'",
            "contest.user.register",
        )

        return self.error(("S", "Register Successfully"))

    @contest_reg_dispatcher.action("cancelreq")
    async def cancel_request_action(self):
        if error := self.check("cancel request"):
            return self.error(error)

        if datetime.datetime.now(datetime.UTC) >= self.contest.reg_end:
            return self.error(
                ("Etime", "Registration time has passed, you cannot cancel request now")
            )

        acct_id = self.acct.acct_id
        if acct_id not in self.contest.user_list:
            return self.error(("Enoext", "You have not registered yet"))

        if not self.contest.member_is_status(acct_id, UserStatus.REQUESTED):
            return self.error(
                (
                    "Eacces",
                    "Your registration is not in request status, you cannot cancel request",
                )
            )

        self.contest.user_list.pop(acct_id)
        await ContestService.inst.update_contest(
            self.acct, self.contest, userlist_updated=True
        )
        return self.error(("S", "Cancel Request Successfully"))

    @contest_reg_dispatcher.action("unreg")
    async def unregister_action(self):
        if error := self.check("unregister"):
            return self.error(error)

        if datetime.datetime.now(datetime.UTC) >= self.contest.contest_start:
            return self.error(
                ("Etime", "Contest has started, you cannot unregister now")
            )

        acct_id = self.acct.acct_id
        if acct_id not in self.contest.user_list:
            return self.error(("Enoext", "You have not registered yet"))

        if self.contest.member_is_status(acct_id, UserStatus.REJECTED):
            assert self.contest.reg_mode is RegMode.REG_APPROVAL
            return self.error(
                ("Eacces", "Your registration has been rejected, you cannot unregister")
            )
        elif self.contest.member_is_status(acct_id, UserStatus.REQUESTED):
            assert self.contest.reg_mode is RegMode.REG_APPROVAL
            return self.error(
                (
                    "Eacces",
                    "Your registration is in request status, you cannot unregister",
                )
            )

        self.contest.user_list.pop(acct_id)
        await ContestService.inst.update_contest(
            self.acct, self.contest, userlist_updated=True
        )

        await self.add_log(
            f"{self.acct.name} unregistered from contest '{self.contest.name}'",
            "contest.user.unregister"
        )

        return self.error(("S", "Unregister Successfully"))

    @reqenv
    @require_permission([UserConst.ACCTTYPE_USER, UserConst.ACCTTYPE_KERNEL])
    async def post(self):
        reqtype = self.get_argument("reqtype")
        return await contest_reg_dispatcher.dispatch(self, reqtype)
