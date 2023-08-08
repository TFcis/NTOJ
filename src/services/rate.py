import datetime

from msgpack import packb, unpackb

from services.user import UserConst
from services.chal import ChalConst


class RateService:
    def __init__(self, db, rs) -> None:
        self.db = db
        self.rs = rs
        RateService.inst = self

    async def get_acct_rate_and_chal_cnt(self, acct):
        kernel = (acct['acct_type'] == UserConst.ACCTTYPE_KERNEL)
        key = f'rate@kernel_{kernel}'
        acct_id = int(acct['acct_id'])

        if (rate_data := await self.rs.hget(key, acct_id)) == None:
            async with self.db.acquire() as con:
                all_chal_cnt = await con.fetchrow('SELECT COUNT(*) FROM "challenge" WHERE "acct_id" = $1', acct_id)
                all_chal_cnt = all_chal_cnt['count']

                ac_chal_cnt = await con.fetchrow(
                    '''
                        SELECT COUNT(*) FROM "challenge"
                        INNER JOIN "challenge_state"
                        ON "challenge"."chal_id" = "challenge_state"."chal_id"
                        AND "challenge_state"."state" = $1
                        WHERE "acct_id" = $2
                    ''',
                    ChalConst.STATE_AC, acct_id
                )
                ac_chal_cnt = ac_chal_cnt['count']

                result = await con.fetch(('SELECT '
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
                        '    WHERE "account"."acct_id" = $1 '
                        '    AND "test"."state" = $2 '
                        '    AND "account"."class" && "problem"."class" '
                        '    GROUP BY "test"."pro_id","test"."test_idx","problem"."expire"'
                        ') AS "valid_test" '
                        'ON "test_valid_rate"."pro_id" = "valid_test"."pro_id" '
                        'AND "test_valid_rate"."test_idx" = "valid_test"."test_idx";'),
                        acct_id, int(ChalConst.STATE_AC))
                if result.__len__() != 1:
                    return ('Eunk', None)

                if (rate := result[0]['rate']) == None:
                    rate = 0

                rate_data = {
                    'rate': rate,
                    'ac_cnt': ac_chal_cnt,
                    'all_cnt': all_chal_cnt,
                }
                await self.rs.hset(key, acct_id, packb(rate_data))
        else:
            rate_data = unpackb(rate_data)

        return (None, rate_data)

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

        async with self.db.acquire() as con:
            result = await con.fetch(
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
        async with self.db.acquire() as con:
            result = await con.fetch(
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
