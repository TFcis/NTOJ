import asyncio
from multiprocessing import Process

import asyncpg
import config
import tornado.httpserver
import tornado.ioloop
import tornado.log
import tornado.netutil
import tornado.options
import tornado.process
import tornado.web
from redis import asyncio as aioredis

import url as ur
from services.judge import JudgeServerClusterService
from services.service import services_init


async def materialized_view_task():
    db = await asyncpg.connect(
        database=config.DBNAME_OJ, user=config.DBUSER_OJ, password=config.DBPW_OJ, host='localhost'
    )
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
            loop.run_until_complete(materialized_view_task())
            loop.run_forever()

        finally:
            loop.stop()
            loop.close()

    view_task_process = Process(target=run_materialized_view_task)
    view_task_process.start()

    # tornado.process.fork_processes(4)
    db: asyncpg.Pool = asyncio.get_event_loop().run_until_complete(
        asyncpg.create_pool(database=config.DBNAME_OJ, user=config.DBUSER_OJ, password=config.DBPW_OJ, host='localhost')
    )
    pool = aioredis.ConnectionPool.from_url("redis://localhost", db=1)
    rs = aioredis.Redis.from_pool(pool)

    services_init(db, rs)
    app = tornado.web.Application(ur.get_url(db, rs, pool), autoescape='xhtml_escape', cookie_secret=config.COOKIE_SEC)
    # NOTE: for dev
    # app = tornado.web.Application(ur.get_url(db, rs), autoescape='xhtml_escape', cookie_secret=config.COOKIE_SEC, debug=True, autoreload=True)

    tornado.log.enable_pretty_logging()

    tornado.options.parse_command_line()

    httpsrv = tornado.httpserver.HTTPServer(app, xheaders=True)
    httpsrv.add_sockets(httpsock)

    tornado.ioloop.IOLoop.current().run_sync(JudgeServerClusterService.inst.start)

    try:
        tornado.ioloop.IOLoop.current().start()
    except:
        pass

    finally:
        view_task_process.kill()

        loop = asyncio.get_event_loop()
        loop.run_until_complete(db.close())
        loop.run_until_complete(rs.aclose())
        loop.run_until_complete(pool.aclose())
        loop.run_until_complete(JudgeServerClusterService.inst.disconnect_all_server())
        tornado.ioloop.IOLoop.current().stop()
        tornado.ioloop.IOLoop.current().close()
