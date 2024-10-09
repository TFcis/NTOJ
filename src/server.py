import asyncio
import functools
import signal
import time
from multiprocessing import Process

import asyncpg
import tornado.httpserver
import tornado.ioloop
import tornado.log
import tornado.netutil
import tornado.options
import tornado.process
import tornado.web
from redis import asyncio as aioredis

import config
import url as ur
from services.judge import JudgeServerClusterService
from services.service import services_init

MAX_WAIT_SECONDS_BEFORE_SHUTDOWN = 3


def sig_handler(server, db, rs, pool, sig, frame):
    io_loop = tornado.ioloop.IOLoop.current()

    def stop_loop(deadline):
        now = time.time()
        if now < deadline and io_loop.time:
            print('Waiting for next tick')
            io_loop.add_timeout(now + 1, stop_loop, deadline)
        else:
            view_task_process.kill()

            for task in asyncio.all_tasks():
                task.cancel()

            io_loop.run_in_executor(func=db.close, executor=None)
            io_loop.run_in_executor(func=rs.aclose, executor=None)
            io_loop.run_in_executor(func=pool.aclose, executor=None)
            io_loop.run_in_executor(func=JudgeServerClusterService.inst.disconnect_all_server, executor=None)
            io_loop.stop()

            print('Shutdown finally')

    def shutdown():
        print('Stopping http server')
        server.stop()
        print('Will shutdown in %s seconds ...', MAX_WAIT_SECONDS_BEFORE_SHUTDOWN)
        stop_loop(time.time() + MAX_WAIT_SECONDS_BEFORE_SHUTDOWN)

    print('Caught signal: %s' % sig)
    io_loop.add_callback_from_signal(shutdown)


async def materialized_view_task():
    db = await asyncpg.connect(
        database=config.DBNAME_OJ, user=config.DBUSER_OJ, password=config.DBPW_OJ, host='localhost'
    )
    rs = await aioredis.Redis(host='localhost', port=6379, db=config.REDIS_DB)
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
    httpsock = tornado.netutil.bind_sockets(config.PORT)

    def run_materialized_view_task():
        signal.signal(signal.SIGINT, lambda _, __: loop.stop())
        signal.signal(signal.SIGTERM, lambda _, __: loop.stop())
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
    pool = aioredis.ConnectionPool.from_url("redis://localhost", db=config.REDIS_DB)
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

    signal.signal(signal.SIGINT, functools.partial(sig_handler, httpsrv, db, rs, pool))
    signal.signal(signal.SIGTERM, functools.partial(sig_handler, httpsrv, db, rs, pool))

    try:
        tornado.ioloop.IOLoop.current().start()
    except:
        pass
