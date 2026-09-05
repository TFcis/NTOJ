import datetime

from handlers.base import RequestHandler, reqenv, require_permission, ActionDispatcher
from handlers.contests.base import contest_require_permission
from services.chal import Compiler
from services.contest_access import ContestPermission
from services.user import UserConst
from services.contests import (
    ContestConst,
    ContestService,
    ContestMode,
    RegMode,
    UserStatus,
    ProblemScoreType,
)

contest_manage_general_dispatcher = ActionDispatcher()
contest_manage_desc_edit_dispatcher = ActionDispatcher()
contest_manage_add_dispatcher = ActionDispatcher()


class ContestManageDashHandler(RequestHandler):
    @reqenv
    @contest_require_permission(ContestPermission.ADMIN)
    async def get(self):
        await self.render(
            "contests/manage/dash", f"{self.contest.name} - Manage", page="dash", contest_id=self.contest.contest_id
        )


class ContestManageGeneralHandler(RequestHandler):
    @reqenv
    @contest_require_permission(ContestPermission.ADMIN)
    async def get(self):
        await self.render(
            "contests/manage/general",
            f"{self.contest.name} - General Settings",
            page="general",
            contest_id=self.contest.contest_id,
            contest=self.contest,
        )

    @contest_manage_general_dispatcher.action("update")
    async def update_action(self):
        name = self.get_argument("name")

        contest_mode = ContestMode(int(self.get_argument("contest_mode")))
        contest_start = self.get_argument("contest_start")
        contest_end = self.get_argument("contest_end")

        reg_mode = RegMode(int(self.get_argument("reg_mode")))
        reg_end = self.get_argument("reg_end")

        allow_compilers = self.get_arguments("allow_compilers[]")
        is_public_scoreboard = self.get_argument("is_public_scoreboard") == "true"
        allow_view_other_page = self.get_argument("allow_view_other_page") == "true"
        hide_admin = self.get_argument("hide_admin") == "true"
        enable_system_test = self.get_argument("enable_system_test", default="false") == "true"
        try:
            submission_cd_time = int(self.get_argument("submission_cd_time"))
            if submission_cd_time < 0:
                submission_cd_time = 1 if contest_mode == ContestMode.ACM else 30

        except ValueError:
            submission_cd_time = 1 if contest_mode == ContestMode.ACM else 30

        try:
            freeze_scoreboard_period = int(
                self.get_argument("freeze_scoreboard_period")
            )
            if freeze_scoreboard_period < 0:
                freeze_scoreboard_period = 0

        except ValueError:
            freeze_scoreboard_period = 0

        try:
            penalty_value = int(self.get_argument("penalty_value", default="20"))
            if penalty_value < 0:
                penalty_value = 20

        except ValueError:
            penalty_value = 20

        allow_compilers = set(
            map(
                lambda x: Compiler(int(x)),
                filter(
                    lambda compiler: int(compiler) in Compiler._value2member_map_,
                    allow_compilers,
                ),
            )
        )

        err, contest_start = trantime(contest_start)
        if err:
            return self.error(err)
        err, contest_end = trantime(contest_end)
        if err:
            return self.error(err)
        err, reg_end = trantime(reg_end)
        if err:
            return self.error(err)

        self.contest.name = name

        self.contest.contest_mode = contest_mode
        if contest_end <= contest_start:
            return self.error(("Eparam", "Contest end time should be later than start time"))
        self.contest.contest_start = contest_start
        self.contest.contest_end = contest_end

        # NOTE: when registration mode change from approval to free, we should approval all account which waiting approval
        if (
            self.contest.reg_mode is RegMode.REG_APPROVAL
            and reg_mode is RegMode.FREE_REG
        ):
            for acct_id, v in list(self.contest.user_list.items()):
                if v["status"] == UserStatus.REQUESTED:
                    self.contest.user_list[acct_id]["status"] = UserStatus.APPROVED
                elif v["status"] == UserStatus.REJECTED:
                    self.contest.user_list.pop(acct_id)

        elif (
            self.contest.reg_mode is RegMode.REG_APPROVAL
            and reg_mode is RegMode.INVITED
        ):
            for acct_id, v in list(self.contest.user_list.items()):
                if v["status"] in (UserStatus.REQUESTED, UserStatus.REJECTED):
                    self.contest.user_list.pop(acct_id)

        self.contest.reg_mode = reg_mode
        if reg_mode is RegMode.INVITED:
            self.contest.reg_end = contest_end
        else:
            self.contest.reg_end = reg_end

        self.contest.allow_compilers = allow_compilers
        self.contest.is_public_scoreboard = is_public_scoreboard
        self.contest.allow_view_other_page = allow_view_other_page
        self.contest.hide_admin = hide_admin
        self.contest.submission_cd_time = submission_cd_time
        self.contest.penalty_value = penalty_value
        self.contest.enable_system_test = enable_system_test
        self.refresh_contest_context()
        if self.contest.freeze_scoreboard_period != freeze_scoreboard_period:
            self.contest.freeze_scoreboard_period = freeze_scoreboard_period
            if self.contest_session.is_started():
                await self.rs.delete(f"contest_{self.contest.contest_id}_scores")

        new_score_type = ProblemScoreType.ICPC if contest_mode == ContestMode.ACM else ProblemScoreType.IOI2017
        for pro_id in self.contest.pro_list:
            self.contest.pro_list[pro_id]["score_type"] = new_score_type

        await ContestService.inst.update_contest(self.acct, self.contest)

        await self.add_log(
            f"{self.acct.name} updated general settings of contest '{self.contest.name}'",
            "contest.manage.update.general",
            {
                "name": name,
                "contest_mode": contest_mode.value,
                "contest_start": contest_start,
                "contest_end": contest_end,
                "reg_mode": reg_mode.value,
                "reg_end": reg_end,
                "allow_compilers": [c.value for c in allow_compilers],
                "is_public_scoreboard": is_public_scoreboard,
                "allow_view_other_page": allow_view_other_page,
                "hide_admin": hide_admin,
                "submission_cd_time": submission_cd_time,
                "freeze_scoreboard_period": freeze_scoreboard_period,
            },
        )

        return self.error(("S", ""))

    @reqenv
    @contest_require_permission(ContestPermission.ADMIN)
    async def post(self):
        reqtype = self.get_argument("reqtype")
        return await contest_manage_general_dispatcher.dispatch(self, reqtype)


class ContestManageDescEditHandler(RequestHandler):
    @reqenv
    @contest_require_permission(ContestPermission.ADMIN)
    async def get(self):
        await self.render(
            "contests/manage/desc-edit",
            f"{self.contest.name} - Edit Description",
            page="desc",
            contest_id=self.contest.contest_id,
            contest=self.contest,
        )

    @contest_manage_desc_edit_dispatcher.action("update")
    async def update_action(self):
        desc = self.get_argument("desc")
        desc_type = self.get_argument("desc_type")

        if desc_type == "before":
            self.contest.desc_before_contest = desc

        elif desc_type == "during":
            self.contest.desc_during_contest = desc

        elif desc_type == "after":
            self.contest.desc_after_contest = desc

        else:
            return self.error(("Eunk", "Unknown error"))

        await ContestService.inst.update_contest(self.acct, self.contest)

        await self.add_log(
            f"{self.acct.name} updated contest '{self.contest.name}' description ({desc_type})",
            "contest.manage.update.desc",
            {"desc_type": desc_type}
        )

        return self.error(("S", ""))

    @reqenv
    @contest_require_permission(ContestPermission.ADMIN)
    async def post(self):
        reqtype = self.get_argument("reqtype")
        return await contest_manage_desc_edit_dispatcher.dispatch(self, reqtype)


class ContestManageAddHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
        await self.render("contests/manage/add", "Add Contest", page="add")

    @contest_manage_add_dispatcher.action("add")
    async def add_action(self):
        name = self.get_argument("name")
        if err := self.len_check(
            name, ContestConst.NAME_MIN, ContestConst.NAME_MAX, "Name"
        ):
            return self.error(err)

        _, contest_id = await ContestService.inst.add_default_contest(self.acct, name)

        await self.add_log(
            f"{self.acct.name} created a new contest '{name}'",
            "contest.manage.add",
            {"contest_id": contest_id}
        )

        return self.error(("S", contest_id))

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        reqtype = self.get_argument("reqtype")
        return await contest_manage_add_dispatcher.dispatch(self, reqtype)


def trantime(time):
    if time == "":
        time = None

    else:
        try:
            time = datetime.datetime.strptime(time, "%Y-%m-%dT%H:%M:%S.%fZ")
            time = time.replace(tzinfo=datetime.timezone.utc)

        except ValueError:
            return ("Eparam", "Invalid time"), None

    return None, time
