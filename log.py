import os
import json
import msgpack
import tornado.web
import tornado.gen
import tornadoredis
import datetime
from req import reqenv
from req import RequestHandler
#from user import UserConst
#from user import UserService
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter
from req import Service
# from chal import ChalService

class LogService:
    def __init__(self,db,rs):
        self.db = db
        self.rs = rs
        LogService.inst = self
    def add_log(self,message):
        message = str(message)
        cur = yield self.db.cursor()
        yield cur.execute(('INSERT INTO "log" '
            '("message") '
            'VALUES (%s) RETURNING "log_id";'),[message])
        log_id = cur.fetchone()[0]
        return (None,log_id)
    def list_log(self,off,num):
        #self.add_log('list log')
        cur = yield self.db.cursor()
        yield cur.execute(('SELECT '
            '"log"."log_id",'
            '"log"."message",'
            '"log"."timestamp"'
            'FROM "log" '
            'ORDER BY "log"."timestamp" DESC OFFSET %s LIMIT %s;'),
            [off,num])
        loglist = list()
        for (log_id,message,timestamp) in cur:
           loglist.append({
                'log_id':log_id,
                'message':message,
                'timestamp':timestamp
           })

        yield cur.execute('SELECT COUNT(*) FROM "log" ;')
        lognum = cur.fetchone()[0]
#        lognum = 0
        return (None,{'loglist':loglist,'lognum':lognum})

class LogHandler(RequestHandler):
    @reqenv
    def get(self):
        #yield from LogService.inst.add_log('list log')
        from user import UserConst
        if self.acct['acct_type'] != UserConst.ACCTTYPE_KERNEL:
            self.finish('Eacces')
            return
        try:
            off = int(self.get_argument('off'))

        except tornado.web.HTTPError:
            off = 0

        err,log = yield from LogService.inst.list_log(off,50)
        if err:
            self.finish(err)
            return
        self.render('loglist',
                pageoff = off,
                lognum = log['lognum'],
                loglist = log['loglist'])
        return

