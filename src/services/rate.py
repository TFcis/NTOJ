import datetime
from collections import defaultdict

from msgpack import packb, unpackb

from services.user import Account
from services.chal import ChalConst


class RateService:
    def __init__(self, db, rs) -> None:
        self.db = db
        self.rs = rs
        RateService.inst = self

    async def get_acct_rate_and_chal_cnt(self, acct: Account):
        kernel = acct.is_kernel()
        key = f'rate@kernel_{kernel}'
        acct_id = acct.acct_id

        if (rate_data := await self.rs.hget(key, acct_id)) is None:
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
                if len(result) != 1:
                    return 'Eunk', None

                if (rate := result[0]['rate']) is None:
                    rate = 0

                rate_data = {
                    'rate': rate,
                    'ac_cnt': ac_chal_cnt,
                    'all_cnt': all_chal_cnt,
                }
                await self.rs.hset(key, acct_id, packb(rate_data))
        else:
            rate_data = unpackb(rate_data)

        return None, rate_data

    async def get_pro_ac_rate(self, pro_id):
        # problem submission ac rate
        ALL_CHAL_SQL = """
        SELECT COUNT(*) FROM "challenge" INNER JOIN "account" ON "challenge"."acct_id" = "account"."acct_id"
        LEFT JOIN "challenge_state"
        ON "challenge"."chal_id" = "challenge_state"."chal_id"
        WHERE "challenge"."pro_id" = $1;
        """
        AC_CHAL_SQL = f"""
        SELECT COUNT(*) FROM "challenge" INNER JOIN "account" ON "challenge"."acct_id" = "account"."acct_id"
        LEFT JOIN "challenge_state"
        ON "challenge"."chal_id" = "challenge_state"."chal_id"
        WHERE "challenge"."pro_id" = $1 AND "challenge_state"."state" = {ChalConst.STATE_AC};
        """

        # problem user ac rate
        USER_ALL_CHAL_SQL = """
        SELECT COUNT(*) FROM (SELECT DISTINCT "account"."acct_id" FROM "challenge" INNER JOIN "account" ON "challenge"."acct_id" = "account"."acct_id"
        LEFT JOIN "challenge_state"
        ON "challenge"."chal_id" = "challenge_state"."chal_id"
        WHERE "challenge"."pro_id" = $1) as user_cnt;
        """
        USER_AC_CHAL_SQL = f"""
        SELECT COUNT(*) FROM (SELECT DISTINCT "account"."acct_id" FROM "challenge" INNER JOIN "account" ON "challenge"."acct_id" = "account"."acct_id"
        LEFT JOIN "challenge_state"
        ON "challenge"."chal_id" = "challenge_state"."chal_id"
        WHERE "challenge"."pro_id" = $1 AND "challenge_state"."state" = {ChalConst.STATE_AC}) as user_cnt;
        """

        key = "pro_rate"
        pro_id = int(pro_id)

        if (rate_data := await self.rs.hget(key, str(pro_id))) is None:
            async with self.db.acquire() as con:
                all_chal_cnt = await con.fetchrow(ALL_CHAL_SQL, pro_id)
                all_chal_cnt = all_chal_cnt['count']

                ac_chal_cnt = await con.fetchrow(AC_CHAL_SQL, pro_id)
                ac_chal_cnt = ac_chal_cnt['count']

                user_all_chal_cnt = await con.fetchrow(USER_ALL_CHAL_SQL, pro_id)
                user_all_chal_cnt = user_all_chal_cnt['count']

                user_ac_chal_cnt = await con.fetchrow(USER_AC_CHAL_SQL, pro_id)
                user_ac_chal_cnt = user_ac_chal_cnt['count']

            rate_data = {
                'all_chal_cnt': all_chal_cnt,
                'ac_chal_cnt': ac_chal_cnt,
                'user_all_chal_cnt': user_all_chal_cnt,
                'user_ac_chal_cnt': user_ac_chal_cnt
            }
            await self.rs.hset(key, pro_id, packb(rate_data))

        else:
            rate_data = unpackb(rate_data)

        return None, rate_data

    async def map_rate_acct(self, acct: Account, clas=None,
                            starttime='1970-01-01 00:00:00.000', endtime='2100-01-01 00:00:00.000'):

        if clas is not None:
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
                acct.acct_id, qclas, starttime, endtime
            )

        statemap = {}
        for (pro_id, rate, count) in result:
            statemap[pro_id] = {
                'rate': rate,
                'count': count,
            }

        return None, statemap

    async def map_rate(self, clas=None,
                       starttime='1970-01-01 00:00:00.000', endtime='2100-01-01 00:00:00.000'):
        if clas is not None:
            qclas = [clas]

        else:
            qclas = [1, 2]

        if isinstance(starttime, str):
            starttime = datetime.datetime.fromisoformat(starttime)

        if isinstance(endtime, str):
            endtime = datetime.datetime.fromisoformat(endtime)

        # TODO: performance test
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

        statemap = defaultdict(dict)
        for acct_id, pro_id, rate, count in result:
            statemap[acct_id][pro_id] = {
                'rate': rate,
                'count': count
            }

        return None, statemap
