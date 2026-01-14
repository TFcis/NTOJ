import decimal
import datetime
from collections import defaultdict

from msgpack import packb, unpackb

from services.chal import ChalConst
from services.user import Account
from services.contests import UserStatus
from services.pro import ProConst


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
                            COUNT(CASE WHEN cs.state = {ChalConst.STATE_AC} THEN 1 END) AS ac_chal_cnt
                        FROM
                            challenge c
                        INNER JOIN problem
                            ON c.pro_id = problem.pro_id
                        INNER JOIN total_result cs
                            ON c.chal_id = cs.chal_id
                        WHERE
                            c.acct_id = $1 AND
                            problem.status = {ProConst.STATUS_ONLINE} AND
                            c.contest_id = 0;
                    ''',
                    acct_id,
                )
                if len(result) != 1:
                    return ('Eunk', 'Unknown error'), None
                result = result[0]

                ac_chal_cnt, all_chal_cnt = (
                    result['ac_chal_cnt'],
                    result['all_chal_cnt'],
                )

                result = await con.fetch(
                    f'''
                    WITH accepted_tests AS (
                        SELECT DISTINCT
                            c.acct_id, t.pro_id, t.subtask_id, t.rate
                        FROM
                            subtask_result t
                        INNER JOIN problem p
                            ON t.pro_id = p.pro_id
                        INNER JOIN challenge c
                            ON t.chal_id = c.chal_id AND c.contest_id = 0
                        WHERE
                            p.status = {ProConst.STATUS_ONLINE}
                            AND t.state IN ({ChalConst.STATE_AC}, {ChalConst.STATE_PC})
                            AND c.acct_id = $1
                    )
                    SELECT
                        SUM(at.rate) AS total_rate
                    FROM
                        accepted_tests at;
                    ''',
                    acct_id
                )
                if len(result) != 1:
                    return ('Eunk', 'Unknown error'), None
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

    async def get_pro_topcoder(self, pro_id: int) -> tuple[None, int | None]:
        """
        Get the top coder for a given problem ID based on challenge performance.

        The topcoder is determined from non-contest (`contest_id = 0`) accepted (`state = AC`) challenges
        by selecting each user's best challenge, ranked primarily by:
        - highest rate
        - lowest time
        - lowest memory usage
        - earliest chal_id (tie-breaker)
        This algorithm same as `ProRankHandler`.

        The best among all users is then selected as the topcoder.

        This result is cached in Redis (under the hash key 'pro_topcoder') to avoid repeated database queries.

        Args:
            pro_id (int): The problem ID to retrieve topcoder for.

        Returns:
            Tuple[None, Optional[int]]: A tuple where the first element is always None (reserved for Error),
            and the second element is either:
                - topcoder account id.
                - None, if no valid submission was found.
        """

        if (topcoder := await self.rs.hget('pro_topcoder', str(pro_id))) is None:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    f'''
                    SELECT temp2.acct_id
                    FROM (
                        SELECT *
                        FROM (
                            SELECT DISTINCT ON ("challenge"."acct_id")
                                "challenge"."chal_id",
                                "challenge"."acct_id",
                                "total_result"."time",
                                "total_result"."memory",
                                "total_result"."rate"

                                FROM "challenge"

                                INNER JOIN "total_result"
                                ON "challenge"."chal_id"="total_result"."chal_id"

                                WHERE "total_result"."state"={ChalConst.STATE_AC} AND "challenge"."contest_id"=0 AND "challenge"."pro_id"=$1

                                ORDER BY "challenge"."acct_id" ASC, "total_result"."rate" DESC,
                                "total_result"."time" ASC, "total_result"."memory" ASC,
                                "challenge"."chal_id" ASC
                        ) temp

                        ORDER BY "rate" DESC, "time" ASC, "memory" ASC,
                        "chal_id" ASC, "acct_id" ASC LIMIT 1
                        ) temp2

                    INNER JOIN "account"
                    ON temp2."acct_id"="account"."acct_id";
                    ''',
                    pro_id,
                )
            if len(result) == 0:
                topcoder = None
            else:
                topcoder = result[0]['acct_id']
            await self.rs.hset('pro_topcoder', str(pro_id), packb(topcoder))
            return None, topcoder
        else:
            return None, unpackb(topcoder)

    async def map_rate_acct(
            self, acct: Account, contest_id: int = 0, starttime='1970-01-01 00:00:00.000',
            endtime='2100-01-01 00:00:00.000'
    ):
        from services.pro import ProConst
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
