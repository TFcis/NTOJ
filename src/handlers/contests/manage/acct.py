from handlers.base import reqenv, RequestHandler, ActionDispatcher
from handlers.contests.base import contest_require_permission
from services.contests import ContestService, UserStatus
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
            f"{self.contest.name} - Manage Accounts",
            page="acct",
            contest_id=self.contest.contest_id,
            acct_list=acct_list,
            admin_list=admin_list,
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

        _, _ = await ContestService.inst.update_contest(
            self.acct, self.contest, userlist_updated=True
        )

        if list_type == "normal" or (
            list_type == "admin" and not self.contest.hide_admin
        ):
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

        success_list = [acct_id for acct_id in acct_list if acct_id in self.contest.user_list and acct_id != self.contest.contest_creator]

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

    @reqenv
    @contest_require_permission("admin")
    async def post(self):
        reqtype = self.get_argument("reqtype")
        return await contest_manage_acct_dispatcher.dispatch(self, reqtype)
