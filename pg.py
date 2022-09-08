import random
import datetime
import psycopg2
# add by tobiichi3227, 2022/9/8
from psycopg2 import extensions as psycopg2_extensions
# end
from collections import deque
from tornado.stack_context import wrap
from tornado.ioloop import IOLoop
from tornado.concurrent import return_future

class WrapCursor:
    def __init__(self, db, cur):
        self._db = db
        self._cur = cur
        self._oldcur = None
        self._init_member()

    def __iter__(self):
        return self._cur

    @return_future
    def execute(self, sql, param=None, callback=None):
        def _cb(err=None):
            if err != None:
                raise err

            self.arraysize = self._cur.arraysize
            self.itersize = self._cur.itersize
            self.rowcount = self._cur.rowcount
            self.rownumber = self._cur.rownumber
            self.lastrowid = self._cur.lastrowid
            self.query = self._cur.query
            self.statusmessage = self._cur.statusmessage

            callback()

        self._db._execute(self._cur, sql, param, _cb)

    @return_future
    def begin(self, callback):
        def _cur_cb(cur, err=None):
            if err != None:
                self._db._end_tran(cur)
                raise err

            self._db._execute(cur, 'BEGIN;', callback=lambda err : _exec_cb(cur, err))

        def _exec_cb(cur, err=None):
            if err != None:
                self._db._end_tran(cur)
                raise err

            self._oldcur = self._cur
            self._cur = cur

            callback()

        assert(self._oldcur == None)

        self._db._begin_tran(_cur_cb)

    @return_future
    def commit(self, callback):
        def _cb(err = None):
            if err != None:
                raise err

            self._db._end_tran(self._cur)
            self._cur = self._oldcur
            self._oldcur = None

            callback()

        assert(self._oldcur != None)

        self._db._execute(self._cur, 'COMMIT;', callback = _cb)

    @return_future
    def rollback(self, callback):
        def _cb(err=None):
            if err != None:
                raise err

            self._db._end_tran(self._cur)
            self._cur = self._oldcur
            self._oldcur = None

            callback()

        assert(self._oldcur != None)

        self._db._execute(self._cur, 'ROLLBACK;', callback=_cb)

    def _init_member(self):
        self.fetchone = self._cur.fetchone
        self.fetchmany = self._cur.fetchmany
        self.fetchall = self._cur.fetchall
        self.scroll = self._cur.scroll
        self.cast = self._cur.cast
        self.tzinfo_factory = self._cur.tzinfo_factory

        self.arraysize = 0
        self.itersize = 0
        self.rowcount = 0
        self.rownumber = 0
        self.lastrowid = None
        self.query = ''
        self.statusmessage = ''

class AsyncPG:
    def __init__(self, dbname, dbuser, dbpasswd, dbtz='+0'):

        self.INITCONN_SHARE = 4
        self.INITCONN_FREE = 16
        self.OPER_CURSOR = 0
        self.OPER_EXECUTE = 1

        self._ioloop = IOLoop.instance()
        self._dbname = dbname
        self._dbuser = dbuser
        self._dbpasswd = dbpasswd
        self._dbschema = 'public'
        self._dbtz = dbtz
        self._share_connpool = []
        self._free_connpool = []
        self._conn_fdmap = {}

        class _InfDateAdapter:
            def __init__(self, wrapped):
                self.wrapped = wrapped

            def getquoted(self):
                if self.wrapped == datetime.datetime.max:
                    return b"'infinity'::date"
                elif self.wrapped == datetime.datetime.min:
                    return b"'-infinity'::date"
                else:
                    # modify by tobiichi3227, 2022/9/8
                    return psycopg2_extensions.TimestampFromPy(self.wrapped).getquoted()

                    # return psycopg2.extensions.TimestampFromPy(
                    #         self.wrapped).getquoted()
                    # end

        # modify by tobiichi3227, 2022/9/8
        # psycopg2.extensions.register_adapter(datetime.datetime, _InfDateAdapter)
        psycopg2_extensions.register_adapter(datetime.datetime, _InfDateAdapter)
        # end

        for i in range(self.INITCONN_SHARE):
            conn = self._create_conn()
            self._share_connpool.append(conn)

            self._ioloop.add_handler(conn[0], self._dispatch, IOLoop.ERROR)

            conn[2] = True
            self._ioloop.add_callback(self._dispatch, conn[0], 0)

        for i in range(self.INITCONN_FREE):
            conn = self._create_conn()
            self._free_connpool.append(conn)

            self._ioloop.add_handler(conn[0],self._dispatch, IOLoop.ERROR)

            conn[2] = True
            self._ioloop.add_callback(self._dispatch, conn[0], 0)

    @return_future
    def cursor(self, callback):
        def _cb(cur, err=None):
            if err != None:
                raise err

            callback(WrapCursor(self, cur))

        self._cursor(callback=_cb)

    def _cursor(self, conn=None, callback=None):
        def _cb(err=None):
            if err != None:
                callback(None, err)

            callback(conn[4].cursor())

        if conn == None:
            conn = self._share_connpool[
                    random.randrange(len(self._share_connpool))]

        conn[1].append((self.OPER_CURSOR, None, wrap(_cb)))

        if conn[2] == False:
            conn[2] = True
            self._ioloop.add_callback(self._dispatch, conn[0], 0)

    def _execute(self, cur, sql, param=(), callback=None):
        conn = self._conn_fdmap[cur.connection.fileno()]

        conn[1].append((self.OPER_EXECUTE, (cur, sql, param), wrap(callback)))

        if conn[2] == False:
            conn[2] = True
            self._ioloop.add_callback(self._dispatch, conn[0], 0)

    def _begin_tran(self, callback):
        if len(self._free_connpool) == 0:
            conn = self._create_conn()
            self._ioloop.add_handler(conn[0], self._dispatch, IOLoop.ERROR)

        else:
            conn = self._free_connpool.pop()

        self._cursor(conn, callback)

    def _end_tran(self, cur):
        conn = self._conn_fdmap[cur.connection.fileno()]

        if len(self._free_connpool) < self.INITCONN_FREE:
            self._free_connpool.append(conn)

        else:
            self._close_conn(conn)

    def _create_conn(self):
        # modify by tobiichi3227, 2022/9/8
        # dbconn = psycopg2.connect(database=self._dbname,
        #                         user=self._dbuser,
        #                         password=self._dbpasswd,
        #                         async=1,
        #                         options=(
        #                             '-c search_path=%s '
        #                             '-c timezone=%s'
        #                         ) % (self._dbschema,self._dbtz))

        dbconn = psycopg2.connect(dbname=self._dbname, user=self._dbuser, password=self._dbpasswd, async_=True,
                options=('-c search_path=%s '
                         '-c timezone=%s') % (self._dbschema, self._dbtz))
        # end

        conn = [dbconn.fileno(), deque(), False, None, dbconn]
        self._conn_fdmap[conn[0]] = conn

        return conn

    def _close_conn(self, conn):
        self._conn_fdmap.pop(conn[0],None)
        self._ioloop.remove_handler(conn[0])
        conn[4].close()

    def _dispatch(self, fd, evt):
        err = None

        try:
            conn = self._conn_fdmap[fd]

        except KeyError:
            self._ioloop.remove_handler(fd)
            return

        try:
            stat = conn[4].poll()

        except Exception as e:
            err = e

        # modify by tobiichi3227, 2022/9/8

        if err != None or stat == psycopg2_extensions.POLL_OK:
            self._ioloop.update_handler(fd, IOLoop.ERROR)

        elif stat == psycopg2_extensions.POLL_READ:
            self._ioloop.update_handler(fd, IOLoop.READ | IOLoop.ERROR)
            return

        elif stat == psycopg2_extensions.POLL_WRITE:
            self._ioloop.update_handler(fd, IOLoop.WRITE | IOLoop.ERROR)
            return

        # if err != None or stat == psycopg2.extensions.POLL_OK:
        #     self._ioloop.update_handler(fd,IOLoop.ERROR)
        #
        # elif stat == psycopg2.extensions.POLL_READ:
        #     self._ioloop.update_handler(fd,IOLoop.READ | IOLoop.ERROR)
        #     return
        #
        # elif stat == psycopg2.extensions.POLL_WRITE:
        #     self._ioloop.update_handler(fd,IOLoop.WRITE | IOLoop.ERROR)
        #     return
        # end

        cb = conn[3]
        if cb != None:
            conn[3] = None
            cb(err)

        else:
            try:
                oper,data,cb = conn[1].popleft()

            except IndexError:
                conn[2] = False
                return

            try:
                if oper == self.OPER_CURSOR:
                    conn[3] = cb

                elif oper == self.OPER_EXECUTE:
                    cur, sql, param = data
                    cur.execute(sql, param)
                    conn[3] = cb

            except Exception as e:
                conn[3] = None
                cb(e)

        self._ioloop.add_callback(self._dispatch, fd, 0)
