from handlers.base import RequestHandler, reqenv
from services.contests import ContestService


class ContestListHandler(RequestHandler):
    @reqenv
    async def get(self):
        _, contest_list = await ContestService.inst.get_contest_list()
        await self.render('contests/contests-list', contests=contest_list, acct=self.acct)

    @reqenv
    async def post(self):
        pass
