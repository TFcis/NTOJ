import os
import asyncio
import functools
import signal
import time
import logging
import shutil

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

MAX_WAIT_SECONDS_BEFORE_SHUTDOWN = 0

logger = logging.getLogger("tornado.application")


def sig_handler(server, db, rs, pool, sig, frame):
    io_loop = tornado.ioloop.IOLoop.current()

    def stop_loop(deadline):
        now = time.time()
        if now < deadline and io_loop.time:
            print("Waiting for next tick")
            io_loop.add_timeout(now + 1, stop_loop, deadline)
        else:
            for task in asyncio.all_tasks():
                task.cancel()

            asyncio.create_task(db.close())
            asyncio.create_task(rs.aclose())
            asyncio.create_task(pool.aclose())
            asyncio.create_task(JudgeServerClusterService.inst.disconnect_all_server())
            io_loop.add_callback(io_loop.stop)

            print("Shutdown finally")

    def shutdown():
        logger.info("Stopping http server")
        server.stop()
        logger.info("Will shutdown in %s seconds ...", MAX_WAIT_SECONDS_BEFORE_SHUTDOWN)
        stop_loop(time.time() + MAX_WAIT_SECONDS_BEFORE_SHUTDOWN)

    print("Caught signal: %s" % sig)
    io_loop.add_callback_from_signal(shutdown)


def check_and_create_directory(path):
    """
    If the directory does not exist, create it. If it exists, check if it is writable.
    """
    try:
        os.mkdir(path)
    except FileExistsError:
        pass
    except OSError as e:
        logger.critical(f"Failed to create directory {path}: {e}", exc_info=True)
        exit(1)

    try:
        os.chmod(path, 0o755)
    except OSError as e:
        logger.critical(
            f"Failed to set permissions for directory {path}: {e}", exc_info=True
        )
        exit(1)

    try:
        with open(os.path.join(path, ".test"), "w") as f:
            f.write("test")
        os.remove(os.path.join(path, ".test"))
    except OSError as e:
        logger.critical(f"Failed to write to directory {path}: {e}", exc_info=True)
        exit(1)


if __name__ == "__main__":
    httpsock = tornado.netutil.bind_sockets(config.PORT)

    # tornado.process.fork_processes(4)
    async def get_db_connection_pool():
        return await asyncpg.create_pool(
            database=config.DBNAME_OJ,
            user=config.DBUSER_OJ,
            password=config.DBPW_OJ,
            host=config.DBHOST_OJ,
        )

    db: asyncpg.Pool = tornado.ioloop.IOLoop.current().run_sync(get_db_connection_pool)
    logger.info("Successfully connected to PostgreSQL")

    pool = aioredis.ConnectionPool.from_url(
        f"redis://{config.REDIS_HOST}", db=config.REDIS_DB
    )
    rs = aioredis.Redis.from_url(f"redis://{config.REDIS_HOST}", db=config.REDIS_DB)

    async def test_redis():
        try:
            await rs.ping()
        except Exception as e:
            logger.critical(f"Failed to connect to Redis: {e}", exc_info=True)
            exit(1)
        r = aioredis.Redis.from_pool(pool)
        try:
            await r.ping()
            await r.aclose()
        except Exception as e:
            logger.critical(f"Failed to connect to Redis with pool: {e}", exc_info=True)
            exit(1)

    tornado.ioloop.IOLoop.current().run_sync(test_redis)
    logger.info("Successfully connected to Redis")

    logger.info("Checking directories ...")
    check_and_create_directory("code")
    check_and_create_directory("problem")

    logger.info("Clearing tmp directory ...")
    shutil.rmtree("tmp", ignore_errors=True)
    check_and_create_directory("tmp")

    services_init(db, rs)
    app = tornado.web.Application(
        ur.get_url(db, rs, pool),
        autoescape="xhtml_escape",
        cookie_secret=config.COOKIE_SEC,
    )
    # NOTE: for dev
    # app = tornado.web.Application(ur.get_url(db, rs), autoescape='xhtml_escape', cookie_secret=config.COOKIE_SEC, debug=True, autoreload=True)

    tornado.log.enable_pretty_logging()

    tornado.options.parse_command_line()

    httpsrv = tornado.httpserver.HTTPServer(app, xheaders=True)
    httpsrv.add_sockets(httpsock)

    tornado.ioloop.IOLoop.current().run_sync(JudgeServerClusterService.inst.start)

    signal.signal(signal.SIGINT, functools.partial(sig_handler, httpsrv, db, rs, pool))
    signal.signal(signal.SIGTERM, functools.partial(sig_handler, httpsrv, db, rs, pool))
    signal.signal(signal.SIGQUIT, functools.partial(sig_handler, httpsrv, db, rs, pool))

    try:
        tornado.ioloop.IOLoop.current().start()
    except:
        pass
