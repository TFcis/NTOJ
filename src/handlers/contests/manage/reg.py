from handlers.base import reqenv, RequestHandler, ActionDispatcher
from handlers.contests.base import contest_require_permission
from services.contests import ContestService, UserStatus
from services.user import UserService

contest_manage_reg_dispatcher = ActionDispatcher()


class ContestManageRegHandler(RequestHandler):
    @reqenv
    @contest_require_permission("admin")
    async def get(self):
        requested_list = []
        rejected_list = []

        for acct_id, v in self.contest.user_list.items():
            if v["status"] == UserStatus.REQUESTED:
                _, acct = await UserService.inst.info_acct(acct_id)
                requested_list.append(acct)
            elif v["status"] == UserStatus.REJECTED:
                _, acct = await UserService.inst.info_acct(acct_id)
                rejected_list.append(acct)

        await self.render(
            "contests/manage/reg",
            f"{self.contest.name} - Manage Registration",
            page="reg",
            contest_id=self.contest.contest_id,
            contest=self.contest,
            requested_list=requested_list,
            rejected_list=rejected_list,
        )

    @contest_manage_reg_dispatcher.action("approve")
    async def approval_action(self):
        acct_id = self.acct_id
        if acct_id not in self.contest.user_list:
            return self.error(
                ("Enoext", f"Account(#{acct_id}) is not registered in this contest")
            )
        old_status = self.contest.user_list[acct_id]["status"]
        if old_status not in (UserStatus.REQUESTED, UserStatus.REJECTED):
            return self.error(
                (
                    "Enoext",
                    f"Account(#{acct_id}) should be in the request or rejected status",
                )
            )

        self.contest.user_list[acct_id]["status"] = UserStatus.APPROVED

        # TODO: send notify to user

        await ContestService.inst.update_contest(
            self.acct, self.contest, userlist_updated=True
        )

        if old_status == UserStatus.REQUESTED:
            await self.add_log(
                f"{self.acct.name} approved registration request from account #{acct_id}",
                "contest.manage.reg.approval",
                {"target_acct_id": acct_id}
            )
            return self.error(("S", f"Approve account(#{acct_id}) successfully."))

        elif old_status == UserStatus.REJECTED:
            await self.add_log(
                f"{self.acct.name} approved rejected account #{acct_id}",
                "contest.manage.reg.approval",
                {"target_acct_id": acct_id}
            )
            return self.error(("S", f"Re-approve account(#{acct_id}) successfully."))

    @contest_manage_reg_dispatcher.action("reject")
    async def reject_action(self):
        acct_id = self.acct_id
        if not self.contest.member_is_status(acct_id, UserStatus.REQUESTED):
            return self.error(
                ("Enoext", f"Account(#{acct_id}) should be in the request status")
            )

        self.contest.user_list[acct_id]["status"] = UserStatus.REJECTED

        # TODO: send notify to user

        await ContestService.inst.update_contest(
            self.acct, self.contest, userlist_updated=True
        )

        await self.add_log(
            f"{self.acct.name} rejected registration request from account #{acct_id}",
            "contest.manage.reg.reject",
            {"target_acct_id": acct_id}
        )

        return self.error(("S", f"Reject account(#{acct_id}) successfully."))

    @reqenv
    @contest_require_permission("admin")
    async def post(self):
        reqtype = self.get_argument("reqtype")
        try:
            self.acct_id = int(self.get_argument("acct_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid account ID"))
        return await contest_manage_reg_dispatcher.dispatch(self, reqtype)
