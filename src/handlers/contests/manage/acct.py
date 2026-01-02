from handlers.base import reqenv, RequestHandler, ActionDispatcher
from handlers.contests.base import contest_require_permission
from services.contests import ContestService, UserStatus
from services.user import UserService
from utils.numeric import parse_str_to_list

from ipaddress import IPv4Address, AddressValueError

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
            acct_list=acct_list,
            admin_list=admin_list,
            start_ip=str(self.contest.ip_range[0]),
            end_ip=str(self.contest.ip_range[1])
        )

    @contest_manage_acct_dispatcher.action("add")
    async def add_action(self):
        acct_id = int(self.get_argument("acct_id"))
        list_type = self.get_argument("type")

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

        if acct_id not in self.contest.user_list:
            return self.error(("Enoext", "User is not in contest"))

        self.contest.user_list.pop(acct_id)
        await ContestService.inst.update_contest(
            self.acct, self.contest, userlist_updated=True
        )

        if list_type == "normal" or (
            list_type == "admin" and not self.contest.hide_admin
        ):
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
            self.contest.user_list[a_id] = {
                "status": status,
            }

        await ContestService.inst.update_contest(
            self.acct, self.contest, userlist_updated=True
        )

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
            try:
                self.contest.user_list.pop(a_id)
            except KeyError:
                continue

        await ContestService.inst.update_contest(
            self.acct, self.contest, userlist_updated=True
        )

        if list_type == "normal" or (
            list_type == "admin" and not self.contest.hide_admin
        ):
            await self.rs.delete(f"contest_{self.contest.contest_id}_scores")

        return self.error(
            ("S", f"Accounts(#{acct_list} successfully removed from user list.")
        )

    @contest_manage_acct_dispatcher.action("update_ip")
    async def update_ip_action(self):
        start_ip = self.get_argument("start_ip")
        end_ip = self.get_argument("end_ip")

        try:
            start_ip = IPv4Address(start_ip)
            end_ip = IPv4Address(end_ip)
        except AddressValueError:
            return self.error(("Eparam", "Invalid IP address format."))

        if start_ip > end_ip:
            return ('Eparam', 'Invalid IP range'), None

        self.contest.ip_range = (start_ip, end_ip)
        await ContestService.inst.update_contest(
            self.acct, self.contest
        )

        return self.error(
            ("S", f"Contest IP range successfully updated.")
        )

    @reqenv
    @contest_require_permission("admin")
    async def post(self):
        reqtype = self.get_argument("reqtype")
        return await contest_manage_acct_dispatcher.dispatch(self, reqtype)
