import math
import datetime

from msgpack import packb, unpackb

from user import UserConst
from pro import ProConst
from req import Service

from dbg import dbg_print

class RateService:
    def __init__(self, db, rs) -> None:
        self.db = db
        self.rs = rs
        RateService.inst = self

    #TODO: performance test
    async def list_rate(self, acct=None, clas=None):
        kernel = (acct != None and acct['acct_type'] == UserConst.ACCTTYPE_KERNEL)

        key = f'rate@kernel_{kernel}'
        data = self.rs.hgetall(key)

        if len(data) > 0:
            acctlist = list()
            for acct in data.values():
                acctlist.append(unpackb(acct))

            acctlist.sort(key=lambda acct : acct['rate'], reverse=True)
            return (None, acctlist)

        if kernel == True:
            min_type = UserConst.ACCTTYPE_KERNEL
            max_status = ProConst.STATUS_HIDDEN

        else:
            min_type = UserConst.ACCTTYPE_USER
            max_status = ProConst.STATUS_ONLINE

        if clas != None:
            qclas = [clas]

        else:
            qclas = [1,2]

        result = await self.db.fetch(
            'select "sum"."acct_id",sum("sum"."rate") from ('
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
            '    where "problem"."class" && $1 '
            '    and "account"."class" && "problem"."class" '
            '    and "account"."acct_type" >= $2 '
            '    and "problem"."status" <= $3 '
            '    group by "challenge"."acct_id","challenge"."pro_id"'
            ') as "sum" '
            'group by "sum"."acct_id" order by "sum"."acct_id" asc;',
            qclas, min_type, max_status
        )

        ratemap = {}
        for acct_id, rate in result:
            ratemap[acct_id] = rate

        err, prolist = await Service.Pro.list_pro(acct=acct)
        promap = {}
        for pro in prolist:
            promap[pro['pro_id']] = pro['rate']

        err, tmplist = await Service.Acct.list_acct(min_type=min_type)
        acctlist = []
        for acct in tmplist:
            if acct['class'] not in qclas:
                continue

            acct_id = acct['acct_id']
            if acct_id in ratemap:
                acct['rate'] = math.floor(ratemap[acct_id])

            else:
                acct['rate'] = 0

            acctlist.append(acct)

        acctlist.sort(key=lambda acct : acct['rate'], reverse=True)
        pipe = self.rs.pipeline()
        for acct in acctlist:
            pipe.hset(key, acct['acct_id'], packb(acct))

        pipe.execute()

        return (None, acctlist)

    # async def list_state(self):
    #     result = await self.db.fetch(
    #         '''
    #             SELECT "challenge"."acct_id", "challenge"."pro_id", MIN("challenge_state"."state") AS "state"
    #             FROM "challenge"
    #             INNER JOIN "challenge_state"
    #             ON "challenge"."chal_id" = "challenge_state"."chal_id"
    #             GROUP BY "challenge"."acct_id", "challenge"."pro_id";
    #         '''
    #     )
    #
    #     statemap = {}
    #     for acct_id, pro_id, state in result:
    #         if acct_id not in statemap:
    #             statemap[acct_id] = {}
    #
    #         statemap[acct_id][pro_id] = state
    #
    #     return (None, statemap)

    async def map_rate_acct(self, acct, clas=None,
            starttime='1970-01-01 00:00:00.000', endtime='2100-01-01 00:00:00.000'):

        if clas != None:
            qclas = [clas]

        else:
            qclas = [1, 2]

        if type(starttime) == str:
            starttime = datetime.datetime.fromisoformat(starttime)

        if type(endtime) == str:
            endtime = datetime.datetime.fromisoformat(endtime)

        result = await self.db.fetch(
            '''
                SELECT "challenge"."pro_id", MAX("challenge_state"."rate") AS "score",
                COUNT("challenge_state") AS "count"
                FROM "challenge"
                INNER JOIN "challenge_state"
                ON "challenge"."chal_id" = "challenge_state"."chal_id" AND "challenge"."acct_id" = $1
                INNER JOIN "problem"
                ON "challenge"."pro_id" = "problem"."pro_id"
                WHERE ("problem"."class" && $2) AND ("challenge"."timestamp" >= $3 AND "challenge"."timestamp" <= $4)
                GROUP BY "challenge"."pro_id";
            ''',
            int(acct['acct_id']), qclas, starttime, endtime
        )

        statemap = {}
        for (pro_id, rate, count) in result:
            statemap[pro_id] = {
                'rate'  : rate,
                'count' : count,
            }

        return (None, statemap)

    async def map_rate(self, clas=None,
            starttime='1970-01-01 00:00:00.000', endtime='2100-01-01 00:00:00.000'):
        if clas != None:
            qclas = [clas]

        else:
            qclas = [1, 2]

        if type(starttime) == str:
            starttime = datetime.datetime.fromisoformat(starttime)

        if type(endtime) == str:
            endtime = datetime.datetime.fromisoformat(endtime)

        #TODO: performance test
        result = await self.db.fetch(
            '''
                SELECT "challenge"."acct_id", "challenge"."pro_id", MAX("challenge_state"."rate") AS "score",
                COUNT("challenge_state") AS "count"
                FROM "challenge"
                INNER JOIN "challenge_state"
                ON "challenge"."chal_id" = "challenge_state"."chal_id"
                INNER JOIN "problem"
                ON "challenge"."pro_id" = "problem"."pro_id"
                WHERE ("problem"."class" && $1) AND ("challenge"."timestamp" >= $2 AND "challenge"."timestamp" <= $3)
                GROUP BY "challenge"."acct_id", "challenge"."pro_id";
            ''',
            qclas, starttime, endtime
        )

        statemap = {}
        for acct_id, pro_id, rate, count in result:
            if acct_id not in statemap:
                statemap[acct_id] = {}

            statemap[acct_id][pro_id] = {
                'rate'  : rate,
                'count' : count
            }

        return (None, statemap)
