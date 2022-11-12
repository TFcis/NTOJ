import logging
import asyncio
from multiprocessing import Process

import asyncpg
from redis import asyncio as aioredis
import tornado.ioloop
import tornado.netutil
import tornado.process
import tornado.httpserver
import tornado.web
import tornado.log
import tornado.options

import config
from inform import InformService, InformSub
from req import Service
from user import UserService
from acct import AcctHandler, SignHandler
from pro import ProService, ProHandler, ProStaticHandler, ProTagsHandler, SubmitHandler, ProsetHandler
from pro import ChalHandler, ChalListHandler, ChalSubHandler, ChalStateHandler
from judge import JudgeServerClusterService
from chal import ChalService
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
from index import IndexHandler, AbouotHandler, InfoHandler, OnlineCounterHandler

async def materialized_view_task():
    db = await asyncpg.connect(database=config.DBNAME_OJ, user=config.DBUSER_OJ, password='322752278227', host='localhost')
    rs = await aioredis.Redis(host='localhost', port=6379, db=1)
    p = rs.pubsub()
    await p.subscribe('materialized_view_req')

    async def _update():
        ret = await rs.incr('materialized_view_counter') - 1
        await db.execute('REFRESH MATERIALIZED VIEW challenge_state;')
        return ret

    counter = await _update()
    async for msg in p.listen():
        if msg['type'] != 'message':
            continue

        ind = int(msg['data'])
        if ind <= counter:
            continue

        counter = await _update()

if __name__ == "__main__":
    httpsock = tornado.netutil.bind_sockets(5500)
    def run_materialized_view_task():
        try:
            loop = asyncio.new_event_loop()
            task = loop.create_task(materialized_view_task())
            loop.run_forever()

        finally:
            task.cancel()
            loop.stop()
            loop.close()

    view_task_process = Process(target=run_materialized_view_task)
    view_task_process.start()

    # tornado.process.fork_processes(4)
    db = asyncio.get_event_loop().run_until_complete(asyncpg.create_pool(database=config.DBNAME_OJ, user=config.DBUSER_OJ,
                                                                            password='322752278227', host='localhost'))
    rs = aioredis.Redis(host='localhost', port=6379, db=1)

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
    Service.Judge    = JudgeServerClusterService(rs, config.JUDGE_SERVER_LIST)

    args = {
        'db' : db,
        'rs' : rs,
    }

    app = tornado.web.Application([
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
        ('/informsub',      InformSub,args),
        ('/chalstatesub',   ChalStateHandler, args),
        ('/online_count',   OnlineCounterHandler, args),
    ], autoescape='xhtml_escape', cookie_secret=config.COOKIE_SEC)

    tornado.log.enable_pretty_logging()

    tornado.options.parse_command_line()

    httpsrv = tornado.httpserver.HTTPServer(app, xheaders=True)
    httpsrv.add_sockets(httpsock)

    tornado.ioloop.IOLoop.current().run_sync(Service.Judge.start)

    try:
        tornado.ioloop.IOLoop.current().start()
    except:
        pass

    finally:
        view_task_process.kill()

        loop = asyncio.get_event_loop()
        loop.run_until_complete(db.close())
        loop.run_until_complete(rs.close())
        loop.run_until_complete(Service.Judge.disconnect_all_server())
        tornado.ioloop.IOLoop.current().stop()
        tornado.ioloop.IOLoop.current().close()
