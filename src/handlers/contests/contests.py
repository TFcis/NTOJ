import datetime

from handlers.base import RequestHandler, reqenv
from services.contests import ContestService


class ContestInfoHandler(RequestHandler):
    @reqenv
    async def get(self):
        await self.render("contests/info", self.contest.name, contest=self.contest)


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
