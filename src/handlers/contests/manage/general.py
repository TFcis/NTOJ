import datetime
import json

from handlers.base import RequestHandler, reqenv, require_permission
from handlers.contests.base import contest_require_permission
from services.chal import ChalConst
from services.user import UserConst
from services.contests import ContestService, ContestMode, RegMode


class ContestManageDashHandler(RequestHandler):
    @reqenv
    @contest_require_permission('admin')
    async def get(self):
        await self.render('contests/manage/dash', page='dash', contest_id=self.contest.contest_id)


class ContestManageGeneralHandler(RequestHandler):
    @reqenv
    @contest_require_permission('admin')
    async def get(self):
        await self.render('contests/manage/general', page='general', contest_id=self.contest.contest_id,
                          contest=self.contest)

    @reqenv
    @contest_require_permission('admin')
    async def post(self):
        reqtype = self.get_argument('reqtype')

        if reqtype == "update":
            name = self.get_argument("name")
            desc = self.get_argument("desc")

            contest_mode = ContestMode(int(self.get_argument("contest_mode")))
            contest_start = self.get_argument("contest_start")
            contest_end = self.get_argument("contest_end")

            reg_mode = RegMode(int(self.get_argument("reg_mode")))
            reg_end = self.get_argument("reg_end")

            allow_compilers = self.get_arguments("allow_compilers[]")
            is_public_scoreboard = self.get_argument("is_public_scoreboard") == "true"
            allow_view_other_page = self.get_argument("allow_view_other_page") == "true"
            hide_admin = self.get_argument("hide_admin") == "true"
            try:
                submission_cd_time = int(self.get_argument("submission_cd_time"))
                if submission_cd_time < 0:
                    submission_cd_time = 30

            except ValueError:
                submission_cd_time = 30

            try:
                freeze_scoreboard_period = int(self.get_argument("freeze_scoreboard_period"))
                if freeze_scoreboard_period < 0:
                    freeze_scoreboard_period = 0

            except ValueError:
                freeze_scoreboard_period = 0

            allow_compilers = list(filter(lambda compiler: compiler in ChalConst.ALLOW_COMPILERS, allow_compilers))

            err, contest_start = trantime(contest_start)
            if err:
                self.error(err)
                return
            err, contest_end = trantime(contest_end)
            if err:
                self.error(err)
                return
            err, reg_end = trantime(reg_end)
            if err:
                self.error(err)
                return

            self.contest.name = name
            self.contest.desc = desc

            self.contest.contest_mode = contest_mode
            self.contest.contest_start = contest_start
            self.contest.contest_end = contest_end

            # NOTE: when registration mode change from approval to free, we should approval all account which waiting approval
            if self.contest.reg_mode is RegMode.REG_APPROVAL and reg_mode is RegMode.FREE_REG:
                self.contest.acct_list.extend(self.contest.reg_list)

            self.contest.reg_mode = reg_mode
            self.contest.reg_end = reg_end

            self.contest.allow_compilers = allow_compilers
            self.contest.is_public_scoreboard = is_public_scoreboard
            self.contest.allow_view_other_page = allow_view_other_page
            self.contest.hide_admin = hide_admin
            self.contest.submission_cd_time = submission_cd_time
            self.contest.freeze_scoreboard_period = freeze_scoreboard_period

            await ContestService.inst.update_contest(self.acct, self.contest)

            self.finish('S')


class ContestManageDescEditHandler(RequestHandler):
    @reqenv
    @contest_require_permission('admin')
    async def get(self):
        await self.render('contests/manage/desc-edit', page='desc', contest_id=self.contest.contest_id,
                          contest=self.contest)

    @reqenv
    @contest_require_permission('admin')
    async def post(self):
        reqtype = self.get_argument('reqtype')

        if reqtype == "update":
            desc = self.get_argument('desc')
            desc_type = self.get_argument('desc_type')

            if desc_type == "before":
                self.contest.desc_before_contest = desc

            elif desc_type == "during":
                self.contest.desc_during_contest = desc

            elif desc_type == "after":
                self.contest.desc_after_contest = desc

            else:
                self.error('Eunk')

            await ContestService.inst.update_contest(self.acct, self.contest)

            await self.finish('S')


class ContestManageAddHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
        await self.render('contests/manage/add')

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        reqtype = self.get_argument('reqtype')

        if reqtype == "add":
            name = self.get_argument('name')

            _, contest_id = await ContestService.inst.add_default_contest(self.acct, name)
            await self.finish(json.dumps(contest_id))
        else:
            self.error('Eunk')


def trantime(time):
    if time == '':
        time = None

    else:
        try:
            time = datetime.datetime.strptime(time, '%Y-%m-%dT%H:%M:%S.%fZ')
            time = time.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=+8)))

        except ValueError:
            return 'Eparam', None

    return None, time
