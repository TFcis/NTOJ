import msgpack

from handlers.base import RequestHandler, reqenv
from services.contests import ContestService
from services.ques import QuestionService


class IndexHandler(RequestHandler):
    @reqenv
    async def get(self, page: str):
        is_in_contest = False
        contest_manage = False
        contest_id = 0

        reply = False
        ask_cnt = 0

        if page.startswith('contests'):
            is_in_contest = True
            try:
                contest_id = int(page.split('/')[1])
            except:
                is_in_contest = False

            if contest_id != 0:
                _, contest = await ContestService.inst.get_contest(contest_id)
                if contest.is_admin(self.acct):
                    contest_manage = True

        if self.acct.is_kernel():
            _, _, ask_cnt = await QuestionService.inst.get_asklist()

        elif not self.acct.is_guest():
            reply = await QuestionService.inst.have_reply(self.acct.acct_id)

        await self.render('index', ask_cnt=ask_cnt, reply=reply,
                          is_in_contest=is_in_contest, contest_manage=contest_manage, contest_id=contest_id)



class AbouotHandler(RequestHandler):
    @reqenv
    async def get(self):
        await self.render('about')


class OnlineCounterHandler(RequestHandler):
    @reqenv
    async def get(self):
        if (cnt := (await self.rs.get('online_counter'))) is None:
            cnt = 0
        else:
            cnt = cnt.decode('utf-8')

        set_cnt = await self.rs.scard('online_counter_set')

        self.finish(f"<h1>{cnt}</h1> <br> <h1>{set_cnt}</h1>")


class DevInfoHandler(RequestHandler):
    @reqenv
    async def get(self):
        await self.render('dev-info')
