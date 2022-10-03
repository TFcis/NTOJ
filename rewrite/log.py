import json

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

        result = await self.db.fetch(
            '''
                INSERT INTO "log"
                ("message", "type", "params")
                VALUES ($1, $2, $3) RETURNING "log_id";
            ''',
            message, log_type, params
        )
        return (None, result[0]['log_id'])

    async def list_log(self, off, num):
        result = await self.db.fetch(
            '''
                SELECT "log"."log_id", "log"."message", "log"."timestamp"
                FROM "log"
                ORDER BY "log"."timestamp" DESC OFFSET $1 LIMIT $2;
            ''',
            off, num
        )

        loglist = []
        for (log_id, message, timestamp) in result:
            loglist.append({
                'log_id'    : log_id,
                'message'   : message,
                'timestamp' : timestamp,
            })

        result = await self.db.fetch('SELECT COUNT(*) FROM "log"')

        return (None, { 'loglist': loglist, 'lognum': result[0]['count'] })

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

        err, log = await LogService.inst.list_log(off, 50)
        if err:
            self.error(err)
            return

        await self.render('loglist', pageoff=off, lognum=log['lognum'], loglist=log['loglist'])
        return

