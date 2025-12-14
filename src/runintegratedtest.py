import os
import sys
import traceback
import asyncio
import functools
import signal
import time
import subprocess
import multiprocessing

import asyncpg
import coverage
import tornado.httpserver
import tornado.ioloop
import tornado.netutil
import tornado.web
from redis import asyncio as aioredis

import config as TestConfig
import url as ur
from services.judge import JudgeServerClusterService
from services.service import services_init
from tests.integratedmain import test_main

MAX_WAIT_SECONDS_BEFORE_SHUTDOWN = 0


def sig_handler(server, db, rs, pool, cov, sig, frame):
    io_loop = tornado.ioloop.IOLoop.current()

    def stop_loop(deadline):
        now = time.time()
        if now < deadline and io_loop.time:
            print("Waiting for next tick")
            io_loop.add_timeout(now + 1, stop_loop, deadline)
        else:
            for task in asyncio.all_tasks():
                task.cancel()

            io_loop.add_callback(db.close)
            io_loop.add_callback(rs.aclose)
            io_loop.add_callback(pool.aclose)
            io_loop.add_callback(JudgeServerClusterService.inst.disconnect_all_server)
            io_loop.stop()

            print("Shutdown finally")

    def shutdown():
        print("Stopping http server")
        server.stop()
        cov.stop()
        cov.save()
        print("Will shutdown in %s seconds ...", MAX_WAIT_SECONDS_BEFORE_SHUTDOWN)
        stop_loop(time.time() + MAX_WAIT_SECONDS_BEFORE_SHUTDOWN)

    print("Caught signal: %s" % sig)
    io_loop.add_callback_from_signal(shutdown)


def m(event):
    cov = coverage.Coverage(data_file=f".coverage.{os.getpid()}", branch=True)
    cov.start()

    httpsock = tornado.netutil.bind_sockets(TestConfig.PORT)

    async def f():
        return await asyncpg.create_pool(database=TestConfig.DBNAME_OJ, user=TestConfig.DBUSER_OJ, password=TestConfig.DBPW_OJ, host=TestConfig.DBHOST_OJ)

    db2: asyncpg.Pool = tornado.ioloop.IOLoop.current().run_sync(f)
    pool2 = aioredis.ConnectionPool.from_url(
        f"redis://{TestConfig.REDIS_HOST}", db=TestConfig.REDIS_DB
    )
    rs2 = aioredis.Redis.from_pool(pool2)

    services_init(db2, rs2)
    app = tornado.web.Application(
        ur.get_url(db2, rs2, pool2),
        autoescape="xhtml_escape",
        cookie_secret=TestConfig.COOKIE_SEC,
    )

    httpsrv = tornado.httpserver.HTTPServer(app, xheaders=True)
    httpsrv.add_sockets(httpsock)

    tornado.ioloop.IOLoop.current().run_sync(JudgeServerClusterService.inst.start)

    signal.signal(
        signal.SIGINT,
        functools.partial(sig_handler, httpsrv, db2, rs2, pool2, cov),
    )
    signal.signal(
        signal.SIGTERM,
        functools.partial(sig_handler, httpsrv, db2, rs2, pool2, cov),
    )

    try:
        event.set()
        tornado.ioloop.IOLoop.current().start()
    except:
        pass

if __name__ == "__main__":
    testing_loop = asyncio.new_event_loop()
    if not os.path.exists('db-inited'):
        subprocess.run(
            [
                "/bin/bash",
                "tests/reinit.sh",
                TestConfig.DBNAME_OJ,
                TestConfig.DBHOST_OJ,
                TestConfig.DBUSER_OJ,
                TestConfig.DBPW_OJ,
            ]
        )
        with open('db-inited', 'w') as f:
            f.write('1')

    db: asyncpg.Pool = testing_loop.run_until_complete(
        asyncpg.create_pool(
            database=TestConfig.DBNAME_OJ,
            user=TestConfig.DBUSER_OJ,
            password=TestConfig.DBPW_OJ,
            host=TestConfig.DBHOST_OJ,
            loop=testing_loop,
        )
    )

    pool = aioredis.ConnectionPool.from_url(f"redis://{TestConfig.REDIS_HOST}", db=TestConfig.REDIS_DB)
    rs = aioredis.Redis.from_pool(pool)
    testing_loop.run_until_complete(rs.flushall())
    e = multiprocessing.Event()
    main_process = multiprocessing.Process(target=m, args=(e,))
    main_process.start()

    rc = 0
    while e.wait():
        services_init(db, rs)
        try:
            result = test_main(testing_loop)
            if result is None:
                rc = 1
            elif not result.wasSuccessful():
                rc = 1
        except Exception as exc:
            print("Exception while running tests:", exc)
            traceback.print_exception(exc)
            rc = 1
        main_process.terminate()
        # Wait for server to finish saving coverage and shutting down
        main_process.join(timeout=10)
        break

    sys.exit(rc)
