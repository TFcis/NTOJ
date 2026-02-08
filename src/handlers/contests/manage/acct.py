from handlers.base import reqenv, RequestHandler, ActionDispatcher
from handlers.contests.base import contest_require_permission
from services.contests import ContestService, UserStatus, ContestMode
from services.user import UserService
from utils.numeric import parse_str_to_list

contest_manage_acct_dispatcher = ActionDispatcher()

class ContestManageAcctHandler(RequestHandler):
    @reqenv
    @contest_require_permission("admin")
    async def get(self):
        admin_list = []
        acct_list = []
        for acct_id, v in self.contest.user_list.items():
            _, acct = await UserService.inst.info_acct(acct_id)
            if v["status"] == UserStatus.ADMIN:
                admin_list.append(acct)
            elif v["status"] == UserStatus.APPROVED:
                acct_list.append(acct)

        await self.render(
            "contests/manage/acct",
            page="acct",
            contest_id=self.contest.contest_id,
            contest=self.contest,
            acct_list=acct_list,
            admin_list=admin_list,
        )

    @contest_manage_acct_dispatcher.action("add")
    async def add_action(self):
        acct_id = int(self.get_argument("acct_id"))
        list_type = self.get_argument("type")

        if acct_id == self.contest.contest_creator:
            return self.error(("Eexist", "Contest creator already exists"))

        status = None
        if list_type == "normal":
            status = UserStatus.APPROVED
        elif list_type == "admin":
            status = UserStatus.ADMIN
        else:
            return self.error(("Eparam", "Invalid list type"))

        self.contest.user_list[acct_id] = {
            "status": status,
        }

        await ContestService.inst.update_contest(
            self.acct, self.contest, userlist_updated=True
        )

        if self.contest.contest_mode == ContestMode.RANDOM_SET and status != UserStatus.ADMIN:
            await ContestService.inst.allocate_new_accounts(self.contest)

        if list_type == "normal" or (
            list_type == "admin" and not self.contest.hide_admin
        ):
            await self.rs.delete(f"contest_{self.contest.contest_id}_scores")

        return self.error(
            (
                "S",
                f"Account(#{acct_id}) successfully added to user list with {status.name}.",
            )
        )

    @contest_manage_acct_dispatcher.action("remove")
    async def remove_action(self):
        acct_id = int(self.get_argument("acct_id"))
        list_type = self.get_argument("type")

        if acct_id == self.contest.contest_creator:
            return self.error(("Eacces", "Cannot remove contest creator"))

        if acct_id not in self.contest.user_list:
            return self.error(("Enoext", "User is not in contest"))

        self.contest.user_list.pop(acct_id)

        if self.contest.contest_mode == ContestMode.RANDOM_SET and acct_id in self.contest.acct_pro_list:
            self.contest.acct_pro_list.pop(acct_id)

        await ContestService.inst.update_contest(
            self.acct, self.contest, userlist_updated=True
        )

        if list_type == "normal" or (
            list_type == "admin" and not self.contest.hide_admin
        ):
            if self.contest.contest_mode == ContestMode.RANDOM_SET:
                await self.rs.hdel(f"contest_{self.contest.contest_id}_randomset_scoreboard", *[f'{acct_id}_{pro_order}' for pro_order in range(len(self.contest.pro_sets))])
            else:
                await self.rs.delete(f"contest_{self.contest.contest_id}_scores")


        return self.error(
            ("S", f"Account(#{acct_id} successfully removed from user list.")
        )

    @contest_manage_acct_dispatcher.action("multi_add")
    async def multi_add_action(self):
        acct_id = self.get_argument("acct_id")
        list_type = self.get_argument("type")

        status = None
        if list_type == "normal":
            status = UserStatus.APPROVED
        elif list_type == "admin":
            status = UserStatus.ADMIN
        else:
            return self.error(("Eparam", "Invalid list type"))

        acct_list = parse_str_to_list(acct_id)

        for a_id in acct_list:
            if a_id == self.contest.contest_creator:
                continue

            self.contest.user_list[a_id] = {
                "status": status,
            }

        await ContestService.inst.update_contest(
            self.acct, self.contest, userlist_updated=True
        )

        if self.contest.contest_mode == ContestMode.RANDOM_SET and status != UserStatus.ADMIN:
            await ContestService.inst.allocate_new_accounts(self.contest)

        if list_type == "normal" or (
            list_type == "admin" and not self.contest.hide_admin
        ):
            await self.rs.delete(f"contest_{self.contest.contest_id}_scores")

        return self.error(
            (
                "S",
                f"Accounts({acct_list}) successfully added to user list with {status.name}.",
            )
        )

    @contest_manage_acct_dispatcher.action("multi_remove")
    async def multi_remove_action(self):
        acct_id = self.get_argument("acct_id")
        list_type = self.get_argument("type")

        acct_list = parse_str_to_list(acct_id)

        for a_id in acct_list:
            if a_id == self.contest.contest_creator:
                continue
            try:
                self.contest.user_list.pop(a_id)
                if self.contest.contest_mode == ContestMode.RANDOM_SET and a_id in self.contest.acct_pro_list:
                    self.contest.acct_pro_list.pop(a_id)
            except KeyError:
                continue

        await ContestService.inst.update_contest(
            self.acct, self.contest, userlist_updated=True
        )

        if list_type == "normal" or (
            list_type == "admin" and not self.contest.hide_admin
        ):
            if self.contest.contest_mode == ContestMode.RANDOM_SET:
                async with self.rs.pipeline() as pipe:
                    for a_id in acct_list:
                        for pro_order in range(len(self.contest.pro_sets)):
                            await pipe.hdel(f"contest_{self.contest.contest_id}_randomset_scoreboard", f'{a_id}_{pro_order}')
                    await pipe.execute()
            else:
                await self.rs.delete(f"contest_{self.contest.contest_id}_scores")

        return self.error(
            ("S", f"Accounts(#{acct_list} successfully removed from user list.")
        )

    @contest_manage_acct_dispatcher.action("reallocate_account_pro_set")
    async def reallocate_account_pro_set_action(self):
        acct_id = int(self.get_argument("acct_id"))
        pro_set_idx = int(self.get_argument("pro_set_idx"))
        if self.contest.is_running():
            return self.error(("Etime", "Cannot reallocate problem set during contest running"))

        err, _ = await ContestService.inst.reallocate_randomset_account_pro_set(
            self.contest, acct_id, pro_set_idx
        )
        if err:
            return self.error(err)

        return self.error(("S", f"Successfully reallocated problem set {pro_set_idx} for account {acct_id}."))

    @contest_manage_acct_dispatcher.action("reallocate_all_accounts_pro_set")
    async def reallocate_all_accounts_pro_set_action(self):
        if self.contest.is_running():
            return self.error(("Etime", "Cannot reallocate problem set during contest running"))

        pro_set_idx = int(self.get_argument("pro_set_idx"))

        err, _ = await ContestService.inst.reallocate_randomset_all_accounts_pro_set(
            self.contest, pro_set_idx
        )
        if err:
            return self.error(err)

        return self.error(("S", f"Successfully reallocated problem set {pro_set_idx} for all accounts."))

    @contest_manage_acct_dispatcher.action("reallocate_account_all_pro_sets")
    async def reallocate_account_all_pro_sets_action(self):
        if self.contest.is_running():
            return self.error(("Etime", "Cannot reallocate problem set during contest running"))

        acct_id = int(self.get_argument("acct_id"))

        err, _ = await ContestService.inst.reallocate_randomset_account_all_pro_sets(
            self.contest, acct_id
        )
        if err:
            return self.error(err)

        return self.error(("S", f"Successfully reallocated all problem sets for account {acct_id}."))

    @contest_manage_acct_dispatcher.action("reallocate_all_accounts_all_pro_sets")
    async def reallocate_all_accounts_all_pro_sets_action(self):
        if self.contest.is_running():
            return self.error(("Etime", "Cannot reallocate problem set during contest running"))

        err, _ = await ContestService.inst.reallocate_randomset_all_accounts_all_pro_sets(
            self.contest
        )
        if err:
            return self.error(err)

        return self.error(("S", "Successfully reallocated all problem sets for all accounts."))

    @reqenv
    @contest_require_permission("admin")
    async def post(self):
        reqtype = self.get_argument("reqtype")
        return await contest_manage_acct_dispatcher.dispatch(self, reqtype)
