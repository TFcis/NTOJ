from req import Service
from req import RequestHandler
from req import reqenv
import tornado.web
import json
class ApiService:
    def __init__(self, db, rs):
        self.db = db
        self.rs = rs
        ApiService.inst = self

    def gen_json(self,_list):
        return json.dumps(_list)

class ApiHandler(RequestHandler):
    @reqenv
    def get(self):
        self.render('api')
        return

    @reqenv
    def post(self):
        reqtype = str(self.get_argument('reqtype'))
        if reqtype == 'AC':
            acct_id = int(self.get_argument('acct_id'))
            err, prolist = yield from Service.Pro.list_pro(acct=None, clas=1)
            err, ratemap = yield from Service.Rate.map_rate(clas=1)
            prolist2 = []
            for pro in prolist:
                pro_id = pro['pro_id']
                if acct_id in ratemap and pro_id in ratemap[acct_id]:
                    rate = ratemap[acct_id][pro_id]
                    if rate['rate'] >= 100:
                        prolist2.append(pro_id)
            self.finish(str(Service.Api.gen_json({'ac': prolist2})))
            return

        elif reqtype == 'NA':
            acct_id = int(self.get_argument('acct_id'))
            err, prolist = yield from Service.Pro.list_pro(acct=None, clas=1)
            err, ratemap = yield from Service.Rate.map_rate(clas=1)
            prolist2 = []
            for pro in prolist:
                pro_id = pro['pro_id']
                if acct_id in ratemap and pro_id in ratemap[acct_id]:
                    rate = ratemap[acct_id][pro_id]
                    if rate['rate'] < 100:
                        prolist2.append(pro_id)
            self.finish(str(Service.Api.gen_json({'na': prolist2})))
            return

        elif reqtype == 'INFO':
            acct_id = int(self.get_argument('acct_id'))
            err, acct = yield from Service.Acct.info_acct(acct_id)
            if err:
                self.finish(err)
                return

            cur = yield self.db.cursor()
            yield cur.execute(('SELECT '
                    'SUM("test_valid_rate"."rate" * '
                    '    CASE WHEN "valid_test"."timestamp" < "valid_test"."expire" '
                    '    THEN 1 ELSE '
                    '    (1 - (GREATEST(date_part(\'days\',justify_interval('
                    '    age("valid_test"."timestamp","valid_test"."expire") '
                    '    + \'1 days\')),-1)) * 0.15) '
                    '    END) '
                    'AS "rate" FROM "test_valid_rate" '
                    'INNER JOIN ('
                    '    SELECT "test"."pro_id","test"."test_idx",'
                    '    MIN("test"."timestamp") AS "timestamp","problem"."expire" '
                    '    FROM "test" '
                    '    INNER JOIN "account" '
                    '    ON "test"."acct_id" = "account"."acct_id" '
                    '    INNER JOIN "problem" '
                    '    ON "test"."pro_id" = "problem"."pro_id" '
                    '    WHERE "account"."acct_id" = %s '
                    '    AND "test"."state" = %s '
                    '    AND "account"."class" && "problem"."class" '
                    '    GROUP BY "test"."pro_id","test"."test_idx","problem"."expire"'
                    ') AS "valid_test" '
                    'ON "test_valid_rate"."pro_id" = "valid_test"."pro_id" '
                    'AND "test_valid_rate"."test_idx" = "valid_test"."test_idx";'),
                    (acct_id, Service.Chal.STATE_AC))
            if cur.rowcount != 1:
                self.finish('Unknown')
                return
            rate = cur.fetchone()[0]
            if rate == None:
                rate = 0
            self.finish(str(Service.Api.gen_json({'nick': acct['name'], 'score': rate})))
            return

