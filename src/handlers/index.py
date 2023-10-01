import msgpack

from services.user import UserConst
from services.ques import QuestionService
from services.judge import JudgeServerClusterService
from handlers.base import RequestHandler, reqenv


class IndexHandler(RequestHandler):
    @reqenv
    async def get(self):
        manage = False
        reply = False
        ask_cnt = 0

        if self.acct['acct_type'] == UserConst.ACCTTYPE_GUEST:
            name = ''

        else:
            name = self.acct['name']

            if self.acct['acct_type'] == UserConst.ACCTTYPE_KERNEL:
                manage = True
                _, _, ask_cnt = await QuestionService.inst.get_asklist()

            else:
                reply = await QuestionService.inst.have_reply(self.acct['acct_id'])

        await self.render('index', name=name, manage=manage, ask_cnt=ask_cnt, reply=reply)
        return


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
        return


class DevInfoHandler(RequestHandler):
    @reqenv
    async def get(self):
        await self.render('dev-info')
        return
