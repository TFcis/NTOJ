import datetime
from collections import defaultdict

from msgpack import packb, unpackb

from services.pro import ProConst
from services.chal import ChalConst
from services.user import Account
from services.contests import UserStatus


class RateService:
    def __init__(self, db, rs) -> None:
        self.db = db
        self.rs = rs
        RateService.inst = self

    async def get_pro_ac_rate(self, pro_id, contest_id: int = 0):
        # problem submission ac rate

        contest_user_filter_sql = ''
        if contest_id:
            contest_user_filter_sql = f'''
            INNER JOIN
                "contest_users"
            ON "contest_users"."contest_id" = $2 AND
               "contest_users"."acct_id" = "challenge"."acct_id" AND
               "contest_users"."status" = {UserStatus.APPROVED}

            '''

        ALL_CHAL_SQL = f"""
        SELECT COUNT(*) FROM "challenge" INNER JOIN "account" ON "challenge"."acct_id" = "account"."acct_id"
        INNER JOIN "total_result"
        ON "challenge"."chal_id" = "total_result"."chal_id"
        {contest_user_filter_sql}
        WHERE "challenge"."pro_id" = $1 AND "challenge"."contest_id" = $2;
        """
        AC_CHAL_SQL = f"""
        SELECT COUNT(*) FROM "challenge" INNER JOIN "account" ON "challenge"."acct_id" = "account"."acct_id"
        INNER JOIN "total_result"
        ON "challenge"."chal_id" = "total_result"."chal_id"
        {contest_user_filter_sql}
        WHERE "challenge"."pro_id" = $1 AND "challenge"."contest_id" = $2 AND "total_result"."state" = {ChalConst.STATE_AC};
        """

        # problem user ac rate
        USER_ALL_CHAL_SQL = f"""
        SELECT COUNT(*) FROM (SELECT DISTINCT "account"."acct_id" FROM "challenge" INNER JOIN "account" ON "challenge"."acct_id" = "account"."acct_id"
        INNER JOIN "total_result"
        ON "challenge"."chal_id" = "total_result"."chal_id"
        {contest_user_filter_sql}
        WHERE "challenge"."pro_id" = $1 AND "challenge"."contest_id" = $2) as user_cnt;
        """
        USER_AC_CHAL_SQL = f"""
        SELECT COUNT(*) FROM (SELECT DISTINCT "account"."acct_id" FROM "challenge" INNER JOIN "account" ON "challenge"."acct_id" = "account"."acct_id"
        INNER JOIN "total_result"
        ON "challenge"."chal_id" = "total_result"."chal_id"
        {contest_user_filter_sql}
        WHERE "challenge"."pro_id" = $1 AND "challenge"."contest_id" = $2 AND "total_result"."state" = {ChalConst.STATE_AC}) as user_cnt;
        """

        key = "pro_rate"
        key2 = f"pro_id_{pro_id}_contest_id_{contest_id}"
        pro_id = int(pro_id)

        if (rate_data := await self.rs.hget(key, key2)) is None:
            async with self.db.acquire() as con:
                all_chal_cnt = await con.fetchrow(ALL_CHAL_SQL, pro_id, contest_id)
                all_chal_cnt = all_chal_cnt['count']

                ac_chal_cnt = await con.fetchrow(AC_CHAL_SQL, pro_id, contest_id)
                ac_chal_cnt = ac_chal_cnt['count']

                user_all_chal_cnt = await con.fetchrow(USER_ALL_CHAL_SQL, pro_id, contest_id)
                user_all_chal_cnt = user_all_chal_cnt['count']

                user_ac_chal_cnt = await con.fetchrow(USER_AC_CHAL_SQL, pro_id, contest_id)
                user_ac_chal_cnt = user_ac_chal_cnt['count']

            rate_data = {
                'all_chal_cnt': all_chal_cnt,
                'ac_chal_cnt': ac_chal_cnt,
                'user_all_chal_cnt': user_all_chal_cnt,
                'user_ac_chal_cnt': user_ac_chal_cnt,
            }
            await self.rs.hset(key, key2, packb(rate_data))

        else:
            rate_data = unpackb(rate_data)

        return None, rate_data

    async def refresh_pro_ac_rate(self, pro_id: int, contest_id: int = 0):
        await self.rs.hdel('pro_rate', f'pro_id_{pro_id}_contest_id_{contest_id}')
        return None, None

    async def map_rate_acct(
            self, acct: Account, contest_id: int = 0, starttime='1970-01-01 00:00:00.000',
            endtime='2100-01-01 00:00:00.000'
    ):
        if isinstance(starttime, str):
            starttime = datetime.datetime.fromisoformat(starttime)

        if isinstance(endtime, str):
            endtime = datetime.datetime.fromisoformat(endtime)

        allow_statuses = ProConst.PRO_STATUS_NORMAL_USER
        if contest_id != 0:
            allow_statuses = ProConst.PRO_STATUS_CONTEST_USER
        elif acct.is_kernel():
            allow_statuses = ProConst.PRO_STATUS_KERNEL_USER

        async with self.db.acquire() as con:
            result = await con.fetch(
                f'''
                    SELECT "challenge"."pro_id",
                    ROUND(MAX("total_result"."rate"), (SELECT rate_precision FROM problem WHERE pro_id = challenge.pro_id)) AS "score",
                    COUNT("total_result") AS "count",
                    MIN("total_result"."state") as "state"
                    FROM "challenge"
                    INNER JOIN "total_result"
                    ON "challenge"."chal_id" = "total_result"."chal_id" AND "challenge"."acct_id" = $1
                    INNER JOIN "problem"
                    ON "challenge"."pro_id" = "problem"."pro_id" AND "problem"."status" IN ({",".join(map(str, allow_statuses))})
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

    async def map_rate(self, contest_id: int = 0, starttime='1970-01-01 00:00:00.000', endtime='2100-01-01 00:00:00.000'):
        if isinstance(starttime, str):
            starttime = datetime.datetime.fromisoformat(starttime)

        if isinstance(endtime, str):
            endtime = datetime.datetime.fromisoformat(endtime)

        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    SELECT "challenge"."acct_id", "challenge"."pro_id",
                    ROUND(MAX("total_result"."rate"), (SELECT rate_precision FROM problem WHERE pro_id = challenge.pro_id)) AS "rate",
                    COUNT("total_result") AS "count",
                    MIN("total_result"."state") AS "state"
                    FROM "challenge"
                    INNER JOIN "total_result"
                    ON "challenge"."chal_id" = "total_result"."chal_id"
                    INNER JOIN "problem"
                    ON "challenge"."pro_id" = "problem"."pro_id"
                    WHERE "challenge"."timestamp" >= $1 AND "challenge"."timestamp" <= $2 AND "challenge"."contest_id" = $3
                    GROUP BY "challenge"."acct_id", "challenge"."pro_id";
                ''',
                starttime,
                endtime,
                contest_id,
            )

        statemap = defaultdict(dict)
        for acct_id, pro_id, rate, count, state in result:
            statemap[acct_id][pro_id] = {'rate': rate, 'count': count, 'state': state}

        return None, statemap
