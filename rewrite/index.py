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

                if (tmp := self.rs.get('someoneask')) != None:
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
        if (inform_list := self.rs.get('inform')) != None:
            inform_list = msgpack.unpackb(inform_list)

            #TODO: Performance test
            #TODO: sort轉移到set的時候
            inform_list.sort(key=lambda row: row['time'], reverse=True)
        else:
            inform_list = []

        await self.render('info', inform_list=inform_list)
