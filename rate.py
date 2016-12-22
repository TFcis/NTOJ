import msgpack
import math

from user import UserConst
from pro import ProConst
from req import RequestHandler
from req import reqenv
from req import Service

LEVEL_GAP = list()
for i in range(0,8):
    LEVEL_GAP.append(1 * 0.38 * i / 8)

for i in range(0,10):
    LEVEL_GAP.append(1 * 0.38 + (1 * 0.62 * i / 10))

LEVEL_NAME = [
    '無',
    '七級',
    '六級',
    '五級',
    '四級',
    '三級',
    '二級',
    '一級',
    '初段',
    '二段',
    '三段',
    '四段',
    '五段',
    '七段',
    '八段',
    '九段',
    '十段',
    '★皆伝★'
]

class RateService:
    def __init__(self,db,rs):
        self.db = db
        self.rs = rs

    def list_rate(self,acct = None,clas = None):
        if acct != None and acct['acct_type'] == UserConst.ACCTTYPE_KERNEL:
            kernel = True

        else:
            kernel = False
        
        key = 'rate@kernel_' + str(kernel)
        data = self.rs.hgetall(key)
        if len(data) > 0:
            acctlist = list()
            for acct in data.values():
                acctlist.append(msgpack.unpackb(acct,encoding = 'utf-8'))

            acctlist.sort(key = lambda acct : acct['rate'],reverse = True)
            return (None,acctlist)
        if kernel:
            min_type = UserConst.ACCTTYPE_KERNEL
            max_status = ProConst.STATUS_HIDDEN

        else:
            min_type = UserConst.ACCTTYPE_USER
            max_status = ProConst.STATUS_ONLINE
        
        if clas != None:
            qclas = [clas]

        else:
            qclas = [1,2]

        cur = yield self.db.cursor()
        yield cur.execute(('select "sum"."acct_id",sum("sum"."rate") from ('
            '    select "challenge"."acct_id","challenge"."pro_id",'
            '    max("challenge_state"."rate" * '
            '        case when "challenge"."timestamp" < "problem"."expire" '
            '        then 1 else '
            '        (1 - (greatest(date_part(\'days\',justify_interval('
            '        age("challenge"."timestamp","problem"."expire") '
            '        + \'1 days\')),-1)) * 0.15) '
            '        end) '
            '    as "rate" '
            '    from "challenge" '
            '    inner join "problem" '
            '    on "challenge"."pro_id" = "problem"."pro_id" '
            '    inner join "account" '
            '    on "challenge"."acct_id" = "account"."acct_id" '
            '    inner join "challenge_state" '
            '    on "challenge"."chal_id" = "challenge_state"."chal_id" '
            '    where "problem"."class" && %s '
            '    and "account"."class" && "problem"."class" '
            '    and "account"."acct_type" >= %s '
            '    and "problem"."status" <= %s '
            '    group by "challenge"."acct_id","challenge"."pro_id"'
            ') as "sum" '
            'group by "sum"."acct_id" order by "sum"."acct_id" asc;'),
            (qclas,min_type,max_status))

        ratemap = {}
        for acct_id,rate in cur:
            ratemap[acct_id] = rate

        '''
        yield cur.execute(('SELECT "rank"."acct_id","rank"."pro_id",'
            '(0.3 * power(0.66,("rank"."rank" - 1))) AS "weight" FROM ('
            '    SELECT "challenge"."acct_id","challenge"."pro_id",'
            '    row_number() OVER ('
            '        PARTITION BY "challenge"."pro_id" ORDER BY MIN('
            '        "challenge"."chal_id") ASC) AS "rank" '
            '    FROM "challenge" '
            '    INNER JOIN "problem" '
            '    ON "challenge"."pro_id" = "problem"."pro_id" '
            '    INNER JOIN "account" '
            '    ON "challenge"."acct_id" = "account"."acct_id" '
            '    INNER JOIN "challenge_state" '
            '    ON "challenge"."chal_id" = "challenge_state"."chal_id" '
            '    WHERE "account"."class" && "problem"."class" '
            '    AND "challenge_state"."state" = 1 '
            '    AND "account"."acct_type" = %s '
            '    AND "problem"."status" = %s '
            '    GROUP BY "challenge"."acct_id","challenge"."pro_id"'
            ') AS "rank" WHERE "rank"."rank" < 17;'),
            (UserConst.ACCTTYPE_USER,ProConst.STATUS_ONLINE))

        bonusmap = {}
        for acct_id,pro_id,weight in cur:
            ratemap[acct_id] += promap[pro_id] * float(weight)
        '''
     
        err,prolist = yield from Service.Pro.list_pro(acct = acct)
        promap = {}
        for pro in prolist:
            promap[pro['pro_id']] = pro['rate']

        err,tmplist = yield from Service.Acct.list_acct(min_type = min_type)
        acctlist = list()
        for acct in tmplist:
            if acct['class'] not in qclas:
                continue
            acct_id = acct['acct_id']
            if acct_id in ratemap:
                acct['rate'] = math.floor(ratemap[acct_id])

            else:
                acct['rate'] = 0

            acctlist.append(acct)

        acctlist.sort(key = lambda acct : acct['rate'],reverse = True)
        pipe = self.rs.pipeline()
        for acct in acctlist:
            pipe.hset(key,acct['acct_id'],msgpack.packb(acct))

        pipe.execute()

        return (None,acctlist)

    def list_state(self):
        cur = yield self.db.cursor()
        yield cur.execute(('SELECT "challenge"."acct_id","challenge"."pro_id",'
            'MIN("challenge_state"."state") AS "state" '
            'FROM "challenge" '
            'INNER JOIN "challenge_state" '
            'ON "challenge"."chal_id" = "challenge_state"."chal_id" '
            'GROUP BY "challenge"."acct_id","challenge"."pro_id";'))

        statemap = {}
        for acct_id,pro_id,state in cur:
            if acct_id not in statemap:
                statemap[acct_id] = {}
            
            statemap[acct_id][pro_id] = state
        
        return (None,statemap)
    
    def map_rate(self,clas = None,
            starttime = '1970-01-01 00:00:00.000',endtime = '2100-01-01 00:00:00.000'):
        if clas != None:
            qclas = [clas]

        else:
            qclas = [1,2]

        cur = yield self.db.cursor()
        yield cur.execute(('select "challenge"."acct_id","challenge"."pro_id",'
            'max("challenge_state"."rate") as "score",'
            'count("challenge_state") as "count" '
            'from "challenge" '
            'inner join "challenge_state" '
            'on "challenge"."chal_id" = "challenge_state"."chal_id" '
            'inner join "problem" '
            'on "challenge"."pro_id" = "problem"."pro_id" '
            'where ("problem"."class" && %s) '
            'AND ("challenge"."timestamp" >= %s AND "challenge"."timestamp" <= %s) '
            'group by "challenge"."acct_id","challenge"."pro_id";'),
            (qclas,starttime,endtime))

        statemap = {}
        for acct_id,pro_id,rate,count in cur:
            if acct_id not in statemap:
                statemap[acct_id] = {}
            
            statemap[acct_id][pro_id] = {
                'rate':rate,
                'count':count
            }
        
        return (None,statemap)


class ScbdHandler(RequestHandler):
    def _get_level(self,ratio):
        l = 0
        r = len(LEVEL_GAP) - 1
        level = 0

        while l <= r:
            mid = (l + r) // 2
            if ratio < LEVEL_GAP[mid]:
                r = mid - 1

            else:
                level = mid
                l = mid + 1

        return level

    @reqenv
    def get(self):
        err,acctlist = yield from Service.Rate.list_rate()
        err,prolist = yield from Service.Pro.list_pro()
        err,statemap = yield from Service.Rate.list_state()

        cur = yield self.db.cursor()
        yield cur.execute(('select '
                '"account"."acct_id",'
                'sum("test_valid_rate"."rate") AS "rate" '
                'from "test_valid_rate" '
                'join "problem" '
                'on "test_valid_rate"."pro_id" = "problem"."pro_id" '
                'join "account" '
                'on "problem"."class" && "account"."class" '
                'where "account"."acct_type" = %s '
                'and "problem"."status" = %s '
                'group by "account"."acct_id";'),
                (UserConst.ACCTTYPE_USER,ProConst.STATUS_ONLINE))

        fullmap = {}
        for acct_id,rate in cur:
            fullmap[acct_id] = rate

        for acct in acctlist:
            acct_id = acct['acct_id']
            if acct_id in fullmap:
                fullrate = fullmap[acct_id]
                acct['level'] = self._get_level(acct['rate'] / fullrate)

            else:
                acct['level'] = None

        alglist = list()
        langlist = list()
        for pro in prolist:
            clas = pro['class']
            if clas == 2:
                alglist.append(pro)

            elif clas == 1:
                langlist.append(pro)

        self.render('scbd',
                acctlist = acctlist,
                alglist = alglist,
                langlist = langlist,
                statemap = statemap)
        return
