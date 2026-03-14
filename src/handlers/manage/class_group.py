from handlers.base import ActionDispatcher, RequestHandler, reqenv, require_permission
from services.class_group import ClassGroupService
from services.log import LogService
from services.user import UserConst, UserService

PERMISSION_DENIED_ERROR = ("Eacces", "Permission denied")

class_group_dispatcher = ActionDispatcher()


class ManageClassGroupHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self, page=None):
        if page is None:
            pageoff = int(self.get_argument("pageoff", default=0))
            year = self.get_argument("year", default=None)
            semester = self.get_argument("semester", default=None)
            class_number = self.get_argument("class_number", default=None)
            custom_name = self.get_argument("custom_name", default=None)

            year = int(year) if year else None
            semester = int(semester) if semester else None
            class_number = int(class_number) if class_number else None
            custom_name = custom_name.strip() if custom_name else None

            err, groups = await ClassGroupService.inst.list_class_groups(pageoff, 40, year, semester, class_number, custom_name)
            if err:
                return self.error(err)
            assert groups is not None

            total_cnt = await ClassGroupService.inst.count_class_groups(year, semester, class_number, custom_name)

            groups_with_range = []
            for group in groups:
                err, id_range = await ClassGroupService.inst.get_account_id_range(group.group_id)
                if err:
                    return self.error(err)
                groups_with_range.append({"group": group, "id_range": id_range})

            await self.render(
                "manage/class_group/list",
                page="class_group",
                groups=groups_with_range,
                pageoff=pageoff,
                total_cnt=total_cnt,
                filter_year=year,
                filter_semester=semester,
                filter_class_number=class_number,
                filter_custom_name=custom_name,
            )

        elif page == "add":
            await self.render("manage/class_group/add", page="class_group")

        elif page == "config":
            group_id = int(self.get_argument("groupid"))

            err, group = await ClassGroupService.inst.get_class_group(group_id)
            if err:
                return self.error(err)

            err, members = await ClassGroupService.inst.get_group_members(group_id)
            if err:
                return self.error(err)

            await self.render(
                "manage/class_group/config",
                page="class_group",
                group_id=group_id,
                group=group,
                members=members,
            )

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self, page=None):
        reqtype = self.get_argument("reqtype")
        return await class_group_dispatcher.dispatch(self, reqtype)

    @class_group_dispatcher.action("create")
    async def create_class_group(self):
        year = int(self.get_argument("year"))
        semester = int(self.get_argument("semester"))
        class_number = int(self.get_argument("class_number"))
        custom_name = self.get_argument("custom_name", default="").strip()
        ip_range_start = self.get_argument("ip_range_start", default="").strip()
        ip_range_end = self.get_argument("ip_range_end", default="").strip()

        if semester not in (1, 2):
            return self.error(("Einval", "Semester must be 1 or 2"))

        if ip_range_start and ip_range_end:
            err = ClassGroupService.inst._validate_ip_range(ip_range_start, ip_range_end)
            if err:
                return self.error(err)
        elif ip_range_start or ip_range_end:
            return self.error(("Einval", "Both ip_range_start and ip_range_end must be set together"))

        csv_file = self.request.files.get("csv_file")
        if csv_file:
            csv_content = csv_file[0]["body"]
            err, accounts_data = await ClassGroupService.inst.parse_csv(csv_content)
            if err:
                return self.error(err)
        else:
            accounts_data = []

        err, group_id = await ClassGroupService.inst.create_class_group(
            year, semester, class_number, custom_name, ip_range_start, ip_range_end
        )
        if err:
            return self.error(err)
        assert group_id

        if accounts_data:
            err, created_count = await ClassGroupService.inst.batch_create_accounts(
                group_id, accounts_data, ip_range_start, ip_range_end
            )
            if err:
                # If account creation fails, delete the just-created class group
                await ClassGroupService.inst.delete_class_group(group_id)
                return self.error(err)

        await LogService.inst.add_log(
            f"{self.acct.name}(#{self.acct.acct_id}) created class group #{group_id}",
            "manage.class_group.create",
            {"group_id": group_id, "year": year, "semester": semester, "class_number": class_number},
        )

        self.error(("S", group_id))

    @class_group_dispatcher.action("update")
    async def update_class_group(self):
        group_id = int(self.get_argument("group_id"))

        err, group = await ClassGroupService.inst.get_class_group(group_id)
        if err:
            return self.error(err)
        assert group

        group.year = int(self.get_argument("year"))
        group.semester = int(self.get_argument("semester"))
        group.class_number = int(self.get_argument("class_number"))
        group.custom_name = self.get_argument("custom_name", default="").strip()
        group.ip_range_start = self.get_argument("ip_range_start", default="").strip()
        group.ip_range_end = self.get_argument("ip_range_end", default="").strip()

        if group.semester not in (1, 2):
            return self.error(("Einval", "Semester must be 1 or 2"))

        if group.ip_range_start and group.ip_range_end:
            is_valid, error_msg = ClassGroupService.inst._validate_ip(group.ip_range_start)
            if not is_valid:
                return self.error(("Einval", f"Invalid start IP: {error_msg}"))

            is_valid, error_msg = ClassGroupService.inst._validate_ip(group.ip_range_end)
            if not is_valid:
                return self.error(("Einval", f"Invalid end IP: {error_msg}"))
        elif group.ip_range_start or group.ip_range_end:
            return self.error(("Einval", "Both ip_range_start and ip_range_end must be set together"))

        # if not (101 <= group.class_number <= 319):
        #     return self.error(("Einval", "Class number must be between 101 and 319"))

        err = await ClassGroupService.inst.update_class_group(group)
        if err:
            return self.error(err)

        await LogService.inst.add_log(
            f"{self.acct.name}(#{self.acct.acct_id}) updated class group #{group_id}",
            "manage.class_group.update",
            {"group_id": group_id},
        )

        self.error(("S", ""))

    @class_group_dispatcher.action("delete")
    async def delete_class_group(self):
        group_id = int(self.get_argument("group_id"))

        err = await ClassGroupService.inst.delete_class_group(group_id)
        if err:
            return self.error(err)

        await LogService.inst.add_log(
            f"{self.acct.name}(#{self.acct.acct_id}) deleted class group #{group_id}",
            "manage.class_group.delete",
            {"group_id": group_id},
        )

        self.error(("S", ""))

    @class_group_dispatcher.action("add_member_manual")
    async def add_member_manual(self):
        group_id = int(self.get_argument("group_id"))
        email = self.get_argument("email").strip()
        name = self.get_argument("name").strip()
        password = self.get_argument("password").strip()
        specific_ip = self.get_argument("specific_ip", default="").strip()

        err, group = await ClassGroupService.inst.get_class_group(group_id)
        if err:
            return self.error(err)
        assert group

        if specific_ip:
            is_valid, error_msg = ClassGroupService.inst._validate_ip(specific_ip)
            if not is_valid:
                return self.error(("Einval", f"Invalid IP: {error_msg}"))
        elif group.ip_login_enabled:
            # IP login restriction is active — ensure the new member gets an IP
            if group.ip_range_start and group.ip_range_end:
                err, auto_ip = await ClassGroupService.inst.get_next_available_ip(group_id)
                if err:
                    return self.error(err)
                assert auto_ip is not None
                specific_ip = auto_ip
            else:
                return self.error(("Einval", "IP login is enabled for this group but no IP range is configured; provide a specific_ip"))

        err, acct_id = await UserService.inst.sign_up(email, password, name)
        if err:
            return self.error(err)
        assert acct_id

        if specific_ip:
            err, acct = await UserService.inst.info_acct(acct_id)
            if err:
                return self.error(err)
            assert acct
            acct.specific_ip = specific_ip
            err, _ = await UserService.inst.update_acct(acct)
            if err:
                return self.error(err)

        err = await ClassGroupService.inst.add_member(group_id, acct_id)
        if err:
            return self.error(err)

        await LogService.inst.add_log(
            f"{self.acct.name}(#{self.acct.acct_id}) added account #{acct_id} to class group #{group_id}",
            "manage.class_group.add_member",
            {"group_id": group_id, "acct_id": acct_id},
        )

        self.error(("S", acct_id))

    @class_group_dispatcher.action("add_member_csv")
    async def add_member_csv(self):
        group_id = int(self.get_argument("group_id"))

        err, group = await ClassGroupService.inst.get_class_group(group_id)
        if err:
            return self.error(err)
        assert group

        csv_file = self.request.files.get("csv_file")
        if not csv_file:
            return self.error(("Einval", "No CSV file uploaded"))

        csv_content = csv_file[0]["body"]
        err, accounts_data = await ClassGroupService.inst.parse_csv(csv_content)
        if err:
            return self.error(err)
        assert accounts_data

        err, created_count = await ClassGroupService.inst.batch_create_accounts(
            group_id, accounts_data, group.ip_range_start, group.ip_range_end
        )
        if err:
            return self.error(err)

        await LogService.inst.add_log(
            f"{self.acct.name}(#{self.acct.acct_id}) added {created_count} accounts to class group #{group_id} via CSV",
            "manage.class_group.add_member_csv",
            {"group_id": group_id, "count": created_count},
        )

        self.error(("S", created_count))

    @class_group_dispatcher.action("remove_member")
    async def remove_member(self):
        group_id = int(self.get_argument("group_id"))
        acct_id = int(self.get_argument("acct_id"))

        err = await ClassGroupService.inst.remove_member(group_id, acct_id)
        if err:
            return self.error(err)

        await LogService.inst.add_log(
            f"{self.acct.name}(#{self.acct.acct_id}) removed account #{acct_id} from class group #{group_id}",
            "manage.class_group.remove_member",
            {"group_id": group_id, "acct_id": acct_id},
        )

        self.error(("S", ""))

    @class_group_dispatcher.action("set_ip_range")
    async def set_ip_range(self):
        group_id = int(self.get_argument("group_id"))
        ip_start = self.get_argument("ip_start").strip()
        ip_end = self.get_argument("ip_end").strip()

        is_valid, error_msg = ClassGroupService.inst._validate_ip(ip_start)
        if not is_valid:
            return self.error(("Einval", f"Invalid start IP: {error_msg}"))

        is_valid, error_msg = ClassGroupService.inst._validate_ip(ip_end)
        if not is_valid:
            return self.error(("Einval", f"Invalid end IP: {error_msg}"))

        err = await ClassGroupService.inst.set_ip_range(group_id, ip_start, ip_end)
        if err:
            return self.error(err)

        await LogService.inst.add_log(
            f"{self.acct.name}(#{self.acct.acct_id}) set IP range for class group #{group_id}",
            "manage.class_group.set_ip_range",
            {"group_id": group_id, "ip_start": ip_start, "ip_end": ip_end},
        )

        self.error(("S", ""))

    @class_group_dispatcher.action("enable_ip_login")
    async def enable_ip_login(self):
        group_id = int(self.get_argument("group_id"))
        enabled = self.get_argument("enabled") == "true"

        err = await ClassGroupService.inst.enable_ip_login(group_id, enabled)
        if err:
            return self.error(err)

        await LogService.inst.add_log(
            f"{self.acct.name}(#{self.acct.acct_id}) {'enabled' if enabled else 'disabled'} IP login for class group #{group_id}",
            "manage.class_group.toggle_ip_login",
            {"group_id": group_id, "enabled": enabled},
        )

        self.error(("S", ""))

    @class_group_dispatcher.action("remove_all_ip")
    async def remove_all_ip(self):
        group_id = int(self.get_argument("group_id"))

        err = await ClassGroupService.inst.remove_all_specific_ip(group_id)
        if err:
            return self.error(err)

        await LogService.inst.add_log(
            f"{self.acct.name}(#{self.acct.acct_id}) removed all specific IPs for class group #{group_id}",
            "manage.class_group.remove_all_ip",
            {"group_id": group_id},
        )

        self.error(("S", ""))

    @class_group_dispatcher.action("update_member_ip")
    async def update_member_ip(self):
        group_id = int(self.get_argument("group_id"))
        acct_id = int(self.get_argument("acct_id"))
        new_ip = self.get_argument("new_ip").strip()

        if new_ip:
            is_valid, error_msg = ClassGroupService.inst._validate_ip(new_ip)
            if not is_valid:
                return self.error(("Einval", f"Invalid IP: {error_msg}"))

        err = await ClassGroupService.inst.update_member_ip(group_id, acct_id, new_ip)
        if err:
            return self.error(err)

        await LogService.inst.add_log(
            f"{self.acct.name}(#{self.acct.acct_id}) updated IP for account #{acct_id} in class group #{group_id}",
            "manage.class_group.update_member_ip",
            {"group_id": group_id, "acct_id": acct_id, "new_ip": new_ip},
        )

        self.error(("S", ""))
