import math
import os
import logging
from multiprocessing import Process, shared_memory
import subprocess
import asyncio

import msgpack
import asyncpg
import redis
import tornado.ioloop
import tornado.netutil
import tornado.process
import tornado.httpserver
import tornado.web
from tornado.gen import coroutine
import tornado.log
import tornado.options

import config
from inform import InformService, InformSub
from req import RequestHandler, Service, reqenv
from user import UserService, UserConst
from acct import AcctHandler, SignHandler
from pro import ProService, ProHandler, ProStaticHandler, ProTagsHandler, SubmitHandler, ProsetHandler
from pro import ChalHandler, ChalListHandler, ChalSubHandler
from chal import ChalService, DokiDokiService
from rate import RateService
from contest import ContestService, BoardHandler
from manage import ManageHandler
from pack import PackService, PackHandler
from ques import QuestionService, QuestionHandler
# from api import ApiService, ApiHandler
from code import CodeService, CodeHandler
from rank import RankService, RankHandler
from auto import AutoService, AutoHandler
from group import GroupService
from log import LogService, LogHandler

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

def materialized_view_task():
    subprocess.run(['/bin/python3', 'viewtask.py'])

if __name__ == "__main__":
    # miyuki is my wife and sister 深雪わ私の妻です

    try:
        Service.doki = shared_memory.SharedMemory(create=True, size=2, name='doki_share_memory')
        Service.doki.buf[:] = bytearray([False, False])
        judge_doki = DokiDokiService()
        print(Service.doki.name)

        view_task_process = Process(target=materialized_view_task)
        view_task_process.start()

        def test():
            try:
                n_loop = asyncio.new_event_loop()
                n_loop.run_until_complete(judge_doki.collect_judge())
                n_loop.run_forever()

            finally:
                judge_doki.ws.close()
                judge_doki.doki.unlink()
                judge_doki.doki.close()
                n_loop.stop()
                n_loop.close()

        test_process = Process(target=test)
        test_process.start()

        httpsock = tornado.netutil.bind_sockets(5500)

        # tornado.process.fork_processes(4)

        db = asyncio.get_event_loop().run_until_complete(asyncpg.connect(database=config.DBNAME_OJ, user=config.DBUSER_OJ,
            password='322752278227', host='localhost'))
        rs = redis.StrictRedis(host='localhost', port=6379, db=1)

        Service.Acct     = UserService(db, rs)
        Service.Pro      = ProService(db, rs)
        Service.Chal     = ChalService(db, rs)
        Service.Contest  = ContestService(db, rs)
        Service.Question = QuestionService(db, rs)
        Service.Inform   = InformService(db, rs)
        Service.Pack     = PackService(db, rs)
        # Service.Api      = ApiService(db, rs)
        Service.Code     = CodeService(db, rs)
        Service.Rank     = RankService(db, rs)
        Service.Auto     = AutoService(db, rs)
        Service.Group    = GroupService(db, rs)
        Service.Log      = LogService(db, rs)
        Service.Rate     = RateService(db, rs)

        args = {
            'db' : db,
            'rs' : rs,
        }

        app = tornado.web.Application([
            # ('/', IndexHandler, args),
            ('/index',          IndexHandler, args),
            ('/info',           InfoHandler, args),
            ('/board',          BoardHandler, args),
            ('/sign',           SignHandler, args),
            ('/acct/(\d+)',     AcctHandler, args),
            ('/acct',           AcctHandler, args),
            ('/proset',         ProsetHandler, args),
            ('/pro/(\d+)/(.+)', ProStaticHandler,args),
            ('/pro/(\d+)',      ProHandler,args),
            ('/submit/(\d+)',   SubmitHandler,args),
            ('/submit',         SubmitHandler,args),
            ('/chal/(\d+)',     ChalHandler,args),
            ('/chal',           ChalListHandler,args),
            ('/chalsub',        ChalSubHandler,args),
            ('/manage/(.+)',    ManageHandler,args),
            ('/manage',         ManageHandler,args),
            ('/pack',           PackHandler,args),
            ('/about',          AbouotHandler, args),
            ('/question',       QuestionHandler,args),
            ('/set-tags',       ProTagsHandler,args),
            ('/log',            LogHandler,args),
            ('/rank/(\d+)',     RankHandler,args),
            ('/auto',           AutoHandler,args),
            ('/code',           CodeHandler,args),
            ('/informsub',   InformSub,args),
        ], autoescape='xhtml_escape', cookie_secret=config.COOKIE_SEC)

        access_log = logging.getLogger('tornado.access')
        tornado.log.enable_pretty_logging()

        tornado.options.parse_command_line()

        httpsrv = tornado.httpserver.HTTPServer(app, xheaders=True)
        httpsrv.add_sockets(httpsock)

        Service.doki.buf[0] = False
        tornado.ioloop.IOLoop.current().run_sync(Service.Chal.collect_judge)
        tornado.ioloop.IOLoop.current().start()
    finally:
        Service.doki.unlink()
        Service.Chal.inst.ws.close()
        view_task_process.terminate()
        view_task_process.close()
        test_process.terminate()
        test_process.close()
        tornado.ioloop.IOLoop.current().stop()
        tornado.ioloop.IOLoop.current().close()
