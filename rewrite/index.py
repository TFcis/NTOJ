import msgpack

from user import UserConst
from ques import QuestionService
from req import RequestHandler, reqenv

class IndexHandler(RequestHandler):
    @reqenv
    async def get(self):
        manage = False
        ask = False
        reply = False

        if self.acct['acct_id'] == UserConst.ACCTID_GUEST:
            name = ''

        else:
            name = self.acct['name']

            if self.acct['acct_type'] == UserConst.ACCTTYPE_KERNEL:
                manage = True

                if (tmp := (await self.rs.get('someoneask'))) != None:
                    if msgpack.unpackb(tmp) == True:
                        ask = True

            else:
                reply = await QuestionService.inst.have_reply(self.acct['acct_id'])

        await self.render('index', name=name, manage=manage, ask=ask, reply=reply)
        return

class AbouotHandler(RequestHandler):
    @reqenv
    async def get(self):
        await self.render('about')

class InfoHandler(RequestHandler):
    @reqenv
    async def get(self):
        if (inform_list := (await self.rs.get('inform'))) != None:
            inform_list = msgpack.unpackb(inform_list)
        else:
            inform_list = []

        await self.render('info', inform_list=inform_list)

class OnlineCounterHandler(RequestHandler):
    @reqenv
    async def get(self):
        if (cnt := (await self.rs.get('online_counter'))) == None:
            cnt = 0
        else:
            cnt = cnt.decode('utf-8')

        set_cnt = await self.rs.scard('online_counter_set')

        self.finish(f"<h1>{cnt}</h1> <br> <h1>{set_cnt}</h1>")
        return
