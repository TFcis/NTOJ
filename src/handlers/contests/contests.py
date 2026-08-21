import datetime

from handlers.base import ActionDispatcher, RequestHandler, reqenv
from services.contests import ContestService


contest_info_dispatcher = ActionDispatcher()


class ContestInfoHandler(RequestHandler):
    @reqenv
    async def get(self):
        await self.render("contests/info", self.contest.name, contest=self.contest)

    @contest_info_dispatcher.action("start")
    async def start_action(self):
        if not self.contest_access.can_start:
            return self.error(("Eacces", "Contest cannot be started at this time"))

        err, session = await ContestService.inst.start_official_session(
            self.contest, self.acct
        )
        if err:
            return self.error(err)

        options = self.contest.user_list[self.acct.acct_id]
        options["session_id"] = session.session_id
        options["session_start"] = session.start_time
        options["session_end"] = session.end_time
        self.refresh_contest_context()
        await self.add_log(
            f"{self.acct.name} started contest '{self.contest.name}'",
            "contest.session.start",
        )
        return self.error(("S", ""))

    @reqenv
    async def post(self):
        return await contest_info_dispatcher.dispatch(
            self, self.get_argument("reqtype")
        )


class ContestListHandler(RequestHandler):
    @reqenv
    async def get(self):
        try:
            pageoff = int(self.get_argument("pageoff", default="0"))
            if pageoff < 0:
                pageoff = 0
        except ValueError:
            pageoff = 0

        _, contest_list = await ContestService.inst.get_contest_list()
        contest_list.sort(key=lambda contest: contest["contest_start"], reverse=True)
        contest_category = {
            "active": [],
            "upcoming": [],
            "permanent": [],
            "recent": [],
        }

        now = datetime.datetime.now(datetime.UTC)
        for contest in contest_list:
            if contest["contest_start"] <= now < contest["contest_end"]:
                contest_category["active"].append(contest)
            elif contest["contest_start"] > now:
                contest_category["upcoming"].append(contest)
            elif contest["contest_end"] < now:
                contest_category["recent"].append(contest)

        contest_category["active"].sort(
            key=lambda c: (c["contest_end"], c["contest_start"])
        )
        contest_category["upcoming"].sort(
            key=lambda c: (c["contest_start"], c["contest_end"])
        )
        contest_category["recent"].sort(
            key=lambda c: (c["contest_start"], c["contest_end"]), reverse=True
        )

        recent_length = len(contest_category["recent"])
        contest_category["recent"] = contest_category["recent"][pageoff : pageoff + 20]
        await self.render(
            "contests/contests-list",
            "Contests",
            contest_category=contest_category,
            pageoff=pageoff,
            recent_length=recent_length,
        )
