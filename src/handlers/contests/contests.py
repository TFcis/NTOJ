from handlers.base import RequestHandler, reqenv
from services.contests import ContestService


class ContestInfoHandler(RequestHandler):
    @reqenv
    async def get(self):
        await self.render('contests/info', contest=self.contest)


class ContestListHandler(RequestHandler):
    @reqenv
    async def get(self):
        _, contest_list = await ContestService.inst.get_contest_list()
        await self.render('contests/contests-list', contests=contest_list)
