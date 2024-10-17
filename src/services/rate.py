import decimal
import datetime
from collections import defaultdict

from msgpack import packb, unpackb

from services.chal import ChalConst
from services.user import Account


class RateService:
    def __init__(self, db, rs) -> None:
        self.db = db
        self.rs = rs
        RateService.inst = self

    async def get_acct_rate_and_chal_cnt(self, acct: Account):
        key = 'rate'
        acct_id = acct.acct_id

        if (rate_data := await self.rs.hget(key, acct_id)) is None:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    f'''
                        SELECT
                            COUNT(*) AS all_chal_cnt,
                            COUNT(CASE WHEN challenge_state.state = {ChalConst.STATE_AC} THEN 1 END) AS ac_chal_cnt
                        FROM challenge
                        INNER JOIN challenge_state
                        ON challenge_state.chal_id = challenge.chal_id AND challenge.acct_id = $1
                    ''',
                    acct_id,
                )
                if len(result) != 1:
                    return 'Eunk', None
                result = result[0]

                ac_chal_cnt, all_chal_cnt = (
                    result['ac_chal_cnt'],
                    result['all_chal_cnt'],
                )

                result = await con.fetch(
                    '''
                        SELECT SUM(max_rate) AS total_rate
                        FROM (
                            SELECT MAX(cs.rate) AS max_rate
                            FROM public.account a
                            JOIN public.challenge c ON a.acct_id = c.acct_id
                            JOIN public.challenge_state cs ON c.chal_id = cs.chal_id
                            WHERE a.acct_id = $1
                            GROUP BY c.pro_id
                        ) AS subquery;
                    ''',
                    acct_id
                )
                if len(result) != 1:
                    return 'Eunk', None
                rate = result[0]['total_rate']
                if rate is None:
                    rate = 0

                rate_data = {
                    'rate': str(rate),
                    'ac_cnt': ac_chal_cnt,
                    'all_cnt': all_chal_cnt,
                }
                await self.rs.hset(key, acct_id, packb(rate_data))
        else:
            rate_data = unpackb(rate_data)

        rate_data['rate'] = decimal.Decimal(rate_data['rate'])

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
                'user_ac_chal_cnt': user_ac_chal_cnt,
            }
            await self.rs.hset(key, pro_id, packb(rate_data))

        else:
            rate_data = unpackb(rate_data)

        return None, rate_data

    async def map_rate_acct(
            self, acct: Account, contest_id: int = 0, starttime='1970-01-01 00:00:00.000',
            endtime='2100-01-01 00:00:00.000'
    ):
        from services.pro import ProConst
        if isinstance(starttime, str):
            starttime = datetime.datetime.fromisoformat(starttime)

        if isinstance(endtime, str):
            endtime = datetime.datetime.fromisoformat(endtime)

        problem_status_sql = ''
        if contest_id != 0:
            problem_status_sql = f'AND "problem"."status" = {ProConst.STATUS_CONTEST}'
        elif acct.is_kernel():
            problem_status_sql = f'AND "problem"."status" <= {ProConst.STATUS_HIDDEN} AND "problem"."status" != {ProConst.STATUS_CONTEST}'
        else:
            problem_status_sql = f'AND "problem"."status" <= {ProConst.STATUS_ONLINE} AND "problem"."status" != {ProConst.STATUS_CONTEST}'

        async with self.db.acquire() as con:
            result = await con.fetch(
                f'''
                    SELECT "challenge"."pro_id",
                    ROUND(MAX("challenge_state"."rate"), (SELECT rate_precision FROM problem WHERE pro_id = challenge.pro_id)) AS "score",
                    COUNT("challenge_state") AS "count",
                    MIN("challenge_state"."state") as "state"
                    FROM "challenge"
                    INNER JOIN "challenge_state"
                    ON "challenge"."chal_id" = "challenge_state"."chal_id" AND "challenge"."acct_id" = $1
                    INNER JOIN "problem"
                    ON "challenge"."pro_id" = "problem"."pro_id" {problem_status_sql}
                    WHERE "challenge"."contest_id" = $2 AND "challenge"."timestamp" >= $3 AND "challenge"."timestamp" <= $4
                    GROUP BY "challenge"."pro_id";
                ''',
                acct.acct_id,
                contest_id,
                starttime,
                endtime,
            )

        statemap = {}
        for pro_id, rate, count, state in result:
            statemap[pro_id] = {
                'rate': rate,
                'count': count,
                'state': state,
            }

        return None, statemap

    async def map_rate(self, starttime='1970-01-01 00:00:00.000', endtime='2100-01-01 00:00:00.000'):
        if isinstance(starttime, str):
            starttime = datetime.datetime.fromisoformat(starttime)

        if isinstance(endtime, str):
            endtime = datetime.datetime.fromisoformat(endtime)

        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    SELECT "challenge"."acct_id", "challenge"."pro_id",
                    ROUND(MAX("challenge_state"."rate"), (SELECT rate_precision FROM problem WHERE pro_id = challenge.pro_id)) AS "rate",
                    COUNT("challenge_state") AS "count"
                    FROM "challenge"
                    INNER JOIN "challenge_state"
                    ON "challenge"."chal_id" = "challenge_state"."chal_id"
                    INNER JOIN "problem"
                    ON "challenge"."pro_id" = "problem"."pro_id"
                    WHERE "challenge"."timestamp" >= $1 AND "challenge"."timestamp" <= $2
                    GROUP BY "challenge"."acct_id", "challenge"."pro_id";
                ''',
                starttime,
                endtime,
            )

        statemap = defaultdict(dict)
        for acct_id, pro_id, rate, count in result:
            statemap[acct_id][pro_id] = {'rate': rate, 'count': count}

        return None, statemap
