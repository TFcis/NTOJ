from handlers.base import reqenv, RequestHandler, ActionDispatcher
from handlers.contests.base import contest_require_permission
from services.class_group import ClassGroupService
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

        _, class_groups = await ClassGroupService.inst.list_class_groups(pagesize=200)

        await self.render(
            "contests/manage/acct",
            page="acct",
            contest_id=self.contest.contest_id,
            contest=self.contest,
            acct_list=acct_list,
            admin_list=admin_list,
            class_groups=class_groups or [],
        )

    @contest_manage_acct_dispatcher.action("add")
    async def add_action(self):
        try:
            acct_id = int(self.get_argument('acct_id'))
        except ValueError:
            return self.error(("Eparam", "Invalid account ID"))

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

        error_group, _ = await ContestService.inst.update_contest(
            self.acct, self.contest, userlist_updated=True
        )

        if error_group:
            return self.error(error_group[0])

        if self.contest.contest_mode == ContestMode.RANDOM_SET and status != UserStatus.ADMIN:
            await ContestService.inst.allocate_new_accounts(self.contest)

        if list_type == "normal" or (
            list_type == "admin" and not self.contest.hide_admin
        ):
            await self.rs.delete(f"contest_{self.contest.contest_id}_scores")

        await self.add_log(
            f"{self.acct.name} added account #{acct_id} to contest as {status.name}",
            "contest.manage.acct.add",
            {"target_acct_id": acct_id, "list_type": list_type, "status": status.name}
        )

        return self.error(
            (
                "S",
                f"Account(#{acct_id}) successfully added to user list with {status.name}.",
            )
        )

    @contest_manage_acct_dispatcher.action("remove")
    async def remove_action(self):
        try:
            acct_id = int(self.get_argument('acct_id'))
        except ValueError:
            return self.error(("Eparam", "Invalid account ID"))

        list_type = self.get_argument("type")

        if acct_id == self.contest.contest_creator:
            return self.error(("Eacces", "Cannot remove contest creator"))

        if acct_id not in self.contest.user_list:
            return self.error(("Enoext", "User is not in contest"))

        expected_status = None
        if list_type == "normal":
            expected_status = UserStatus.APPROVED
        elif list_type == "admin":
            expected_status = UserStatus.ADMIN
        else:
            return self.error(("Eparam", "Invalid list type"))

        current_status = self.contest.user_list[acct_id]["status"]
        if current_status != expected_status:
            return self.error((
                "Eacces",
                f"Cannot remove user with status {current_status.name} from {list_type} list"
            ))

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


        await self.add_log(
            f"{self.acct.name} removed account #{acct_id} from contest",
            "contest.manage.acct.remove",
            {"target_acct_id": acct_id, "list_type": list_type}
        )

        return self.error(
            ("S", f"Account(#{acct_id}) successfully removed from user list.")
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

        error_group, _ = await ContestService.inst.update_contest(
            self.acct, self.contest, userlist_updated=True
        )

        success_list = [aid for aid in acct_list if aid in self.contest.user_list and aid != self.contest.contest_creator]

        if self.contest.contest_mode == ContestMode.RANDOM_SET and status != UserStatus.ADMIN:
            await ContestService.inst.allocate_new_accounts(self.contest)

        if list_type == "normal" or (
            list_type == "admin" and not self.contest.hide_admin
        ):
            await self.rs.delete(f"contest_{self.contest.contest_id}_scores")

        if error_group:
            await self.add_log(
                f"{self.acct.name} batch added {len(acct_list)} accounts to contest as {status.name}",
                "contest.manage.acct.multi_add",
                {"acct_list": acct_list, "list_type": list_type, "status": status.name, "error": error_group}
            )
            error_msg = f"Successfully added: {success_list}. Errors: {', '.join([f'{code}: {msg}' for code, msg in error_group])}"
            return self.error(("S", error_msg))
        else:
            await self.add_log(
                f"{self.acct.name} batch added {len(acct_list)} accounts to contest as {status.name}",
                "contest.manage.acct.multi_add",
                {"acct_list": acct_list, "list_type": list_type, "status": status.name}
            )
            return self.error(
                (
                    "S",
                    f"Accounts {success_list} successfully added to user list with {status.name}.",
                )
            )

    @contest_manage_acct_dispatcher.action("multi_remove")
    async def multi_remove_action(self):
        acct_id = self.get_argument("acct_id")
        list_type = self.get_argument("type")

        expected_status = None
        if list_type == "normal":
            expected_status = UserStatus.APPROVED
        elif list_type == "admin":
            expected_status = UserStatus.ADMIN
        else:
            return self.error(("Eparam", "Invalid list type"))

        acct_list = parse_str_to_list(acct_id)
        error_group = []
        removed_list = []

        for a_id in acct_list:
            if a_id == self.contest.contest_creator:
                error_group.append(("Eacces", f"Cannot remove contest creator {a_id}"))
                continue
            try:
                self.contest.user_list.pop(a_id)
                if self.contest.contest_mode == ContestMode.RANDOM_SET and a_id in self.contest.acct_pro_list:
                    self.contest.acct_pro_list.pop(a_id)
            except KeyError:
                continue

            try:
                current_status = self.contest.user_list[a_id]["status"]
                if current_status != expected_status:
                    error_group.append((
                        "Eacces",
                        f"Cannot remove account {a_id} with status {current_status.name} from {list_type} list"
                    ))
                    continue
            except KeyError:
                error_group.append(("Enoext", f"Account {a_id} not in contest"))
                continue

            self.contest.user_list.pop(a_id)
            removed_list.append(a_id)

        update_errors, _ = await ContestService.inst.update_contest(
            self.acct, self.contest, userlist_updated=True
        )

        # Combine errors from validation and update
        if update_errors:
            error_group.extend(update_errors)

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

        if error_group:
            await self.add_log(
                f"{self.acct.name} batch removed {len(acct_list)} accounts from contest",
                "contest.manage.acct.multi_remove",
                {"acct_list": acct_list, "list_type": list_type, "error": error_group}
            )
            error_msg = f"Successfully removed: {removed_list}. Errors: {', '.join([f'{code}: {msg}' for code, msg in error_group])}"
            return self.error(("S", error_msg))
        else:
            await self.add_log(
                f"{self.acct.name} batch removed {len(acct_list)} accounts from contest",
                "contest.manage.acct.multi_remove",
                {"acct_list": acct_list, "list_type": list_type}
            )
            return self.error(
                ("S", f"Accounts {removed_list} successfully removed from user list.")
            )

    @contest_manage_acct_dispatcher.action("add_class_group")
    async def add_class_group_action(self):
        try:
            group_id = int(self.get_argument("group_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid group ID"))

        list_type = self.get_argument("type", default="normal")
        if list_type not in ("normal", "admin"):
            return self.error(("Eparam", "Invalid list type"))

        status = UserStatus.APPROVED if list_type == "normal" else UserStatus.ADMIN

        err, members = await ClassGroupService.inst.get_group_members(group_id)
        if err:
            return self.error(err)
        assert members is not None

        if not members:
            return self.error(("Enoext", "Class group has no members"))

        added = []
        for member in members:
            acct_id = member["acct_id"]
            if acct_id == self.contest.contest_creator:
                continue
            self.contest.user_list[acct_id] = {"status": status}
            added.append(acct_id)

        error_group, _ = await ContestService.inst.update_contest(
            self.acct, self.contest, userlist_updated=True
        )

        if self.contest.contest_mode == ContestMode.RANDOM_SET and status != UserStatus.ADMIN:
            await ContestService.inst.allocate_new_accounts(self.contest)

        if list_type == "normal" or (list_type == "admin" and not self.contest.hide_admin):
            await self.rs.delete(f"contest_{self.contest.contest_id}_scores")

        await self.add_log(
            f"{self.acct.name} added class group #{group_id} ({len(added)} accounts) to contest",
            "contest.manage.acct.add_class_group",
            {"group_id": group_id, "acct_list": added, "list_type": list_type},
        )

        if error_group:
            return self.error(("S", f"Added {len(added)} accounts from group #{group_id}. Errors: {error_group}"))
        return self.error(("S", f"Added {len(added)} accounts from class group #{group_id} as {status.name}."))

    @contest_manage_acct_dispatcher.action("remove_class_group")
    async def remove_class_group_action(self):
        try:
            group_id = int(self.get_argument("group_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid group ID"))

        list_type = self.get_argument("type", default="normal")
        if list_type not in ("normal", "admin"):
            return self.error(("Eparam", "Invalid list type"))

        expected_status = UserStatus.APPROVED if list_type == "normal" else UserStatus.ADMIN

        err, members = await ClassGroupService.inst.get_group_members(group_id)
        if err:
            return self.error(err)
        assert members is not None

        removed = []
        for member in members:
            acct_id = member["acct_id"]
            if acct_id == self.contest.contest_creator:
                continue
            entry = self.contest.user_list.get(acct_id)
            if entry is None or entry["status"] != expected_status:
                continue
            self.contest.user_list.pop(acct_id)
            if self.contest.contest_mode == ContestMode.RANDOM_SET and acct_id in self.contest.acct_pro_list:
                self.contest.acct_pro_list.pop(acct_id)
            removed.append(acct_id)

        await ContestService.inst.update_contest(
            self.acct, self.contest, userlist_updated=True
        )

        if list_type == "normal" or (list_type == "admin" and not self.contest.hide_admin):
            if self.contest.contest_mode == ContestMode.RANDOM_SET:
                async with self.rs.pipeline() as pipe:
                    for acct_id in removed:
                        for pro_order in range(len(self.contest.pro_sets)):
                            await pipe.hdel(f"contest_{self.contest.contest_id}_randomset_scoreboard", f'{acct_id}_{pro_order}')
                    await pipe.execute()
            else:
                await self.rs.delete(f"contest_{self.contest.contest_id}_scores")

        await self.add_log(
            f"{self.acct.name} removed class group #{group_id} ({len(removed)} accounts) from contest",
            "contest.manage.acct.remove_class_group",
            {"group_id": group_id, "acct_list": removed, "list_type": list_type},
        )

        return self.error(("S", f"Removed {len(removed)} accounts from class group #{group_id}."))

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
