import json
import datetime

import tornado.web

from req import RequestHandler, reqenv

from dbg import dbg_print

class LogService:
    def __init__(self, db, rs) -> None:
        self.db = db
        self.rs = rs
        LogService.inst = self

    async def add_log(self, message, log_type=None, params=None):
        if isinstance(params, dict):
            params = json.dumps(params, ensure_ascii=False)

        message = str(message)

        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    INSERT INTO "log"
                    ("message", "type", "params")
                    VALUES ($1, $2, $3) RETURNING "log_id";
                ''',
                message, log_type, params
            )
        return (None, result[0]['log_id'])

    async def list_log(self, off, num, log_type=None):
        tz = datetime.timezone(datetime.timedelta(hours=+8))
        async with self.db.acquire() as con:
            if log_type == None:
                result = await con.fetch(
                    '''
                        SELECT "log"."log_id", "log"."message", "log"."timestamp"
                        FROM "log"
                        ORDER BY "log"."timestamp" DESC OFFSET $1 LIMIT $2;
                    ''',
                    off, num
                )

                count = await con.fetch('SELECT COUNT(*) FROM "log"')
                count = count[0]['count']

            else:
                result = await con.fetch(
                    '''
                        SELECT "log"."log_id", "log"."message", "log"."timestamp"
                        FROM "log"
                        WHERE "log"."type" = $1
                        ORDER BY "log"."timestamp" DESC OFFSET $2 LIMIT $3;
                    ''',
                    log_type, off, num
                )

                count = await con.fetch('SELECT COUNT(*) FROM "log" WHERE "log"."type" = $1', log_type)
                count = count[0]['count']

            loglist = []
            for (log_id, message, timestamp) in result:
                loglist.append({
                    'log_id'    : log_id,
                    'message'   : message,
                    'timestamp' : timestamp.astimezone(tz).isoformat(timespec="seconds"),
                })

        return (None, {'loglist': loglist, 'lognum': count})

    async def get_log_type(self):
        async with self.db.acquire() as con:
            result = await con.fetch('SELECT DISTINCT "type" FROM "log"')

            log_type = []
            for type in result:
                log_type.append(type['type'])

        return (None, log_type)

class LogHandler(RequestHandler):
    @reqenv
    async def get(self):
        from user import UserConst
        if self.acct['acct_type'] != UserConst.ACCTTYPE_KERNEL:
            self.error('Eacces')
            return

        try:
            off = int(self.get_argument('off'))
        except tornado.web.HTTPError:
            off = 0

        try:
            logtype = str(self.get_argument('logtype'))
        except tornado.web.HTTPError:
            logtype = None

        err, logtype_list = await LogService.inst.get_log_type()

        err, log = await LogService.inst.list_log(off, 50, logtype)
        if err:
            self.error(err)
            return

        await self.render('loglist', pageoff=off, lognum=log['lognum'], loglist=log['loglist'], logtype_list=logtype_list, cur_logtype=logtype)
        return

