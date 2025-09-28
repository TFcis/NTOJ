from handlers.base import RequestHandler, reqenv
from services.user import Account
from services.chal import ChalConst
from services.pro import ProConst, ProService

PERMISSION_DENIED_ERROR = (('Eacces', 'Permission denied'))

class ProRankHandler(RequestHandler):
    @reqenv
    async def get(self, pro_id):
        pageoff = int(self.get_argument('pageoff', default=0))
        pagenum = int(self.get_argument('pagenum', default=20))

        pro_id = int(pro_id)
        allow_statuses = ProConst.PRO_STATUS_NORMAL_USER
        if self.acct.is_kernel():
            allow_statuses = ProConst.PRO_STATUS_KERNEL_USER

        err, _ = await ProService.inst.get_pro(pro_id, allow_statuses)
        if err:
            return self.error(err)

        async with self.db.acquire() as con:
            result = await con.fetch(
                f'''
                SELECT *
                FROM (
                SELECT DISTINCT ON ("challenge"."acct_id")
                        "challenge"."chal_id",
                        "challenge"."acct_id",
                        "challenge"."timestamp",
                        "account"."name" AS "acct_name",
                        "account"."photo" AS "photo",
                        "total_result"."time",
                        "total_result"."memory",
                        ROUND("total_result"."rate", "problem"."rate_precision") AS rate

                    FROM "challenge"

                    INNER JOIN "problem"
                    ON "challenge"."pro_id" = "problem"."pro_id" AND "problem"."pro_id" = $1

                    INNER JOIN "account"
                    ON "challenge"."acct_id"="account"."acct_id"

                    INNER JOIN "total_result"
                    ON "challenge"."chal_id"="total_result"."chal_id"

                    WHERE "total_result"."state"={ChalConst.STATE_AC} AND "challenge"."contest_id" = 0

                    ORDER BY "challenge"."acct_id" ASC, "total_result"."rate" DESC,
                    "total_result"."time" ASC, "total_result"."memory" ASC,
                    "challenge"."timestamp" ASC
                ) temp
                ORDER BY "rate" DESC, "time" ASC, "memory" ASC,
                "timestamp" ASC, "acct_id" ASC OFFSET $2 LIMIT $3;
                '''
                ,
                pro_id,
                pageoff,
                pagenum,
            )

            total_cnt = await con.fetch(
                '''
                SELECT COUNT(*)
                FROM (
                SELECT DISTINCT challenge.acct_id
                FROM challenge
                INNER JOIN account ON challenge.acct_id=account.acct_id
                INNER JOIN total_result ON challenge.chal_id=total_result.chal_id
                WHERE challenge.pro_id=$1
                AND total_result.state=1
                ) temp;
                ''',
                pro_id,
            )
            total_cnt = total_cnt[0]['count']

        chal_list = []
        for rank, (chal_id, acct_id, timestamp, acct_name, photo, time, memory, rate) in enumerate(result):
            chal_list.append(
                {
                    'rank': rank + pageoff + 1,
                    'chal_id': chal_id,
                    'acct_id': acct_id,
                    'acct_name': acct_name,
                    'photo': photo,
                    'time': int(time),
                    'memory': int(memory),
                    'rate': rate,
                    'timestamp': timestamp,
                }
            )

        await self.render(
            'pro-rank', pro_id=pro_id, chal_list=chal_list, pageoff=pageoff, pagenum=pagenum, total_cnt=total_cnt
        )


class UserRankHandler(RequestHandler):
    @reqenv
    async def get(self):
        pageoff = int(self.get_argument('pageoff', default=0))
        pagenum = int(self.get_argument('pagenum', default=20))

        res = await self.db.fetch(
            f'''
            WITH accepted_tests_per_user AS (
                SELECT DISTINCT
                    c.acct_id, t.pro_id, t.subtask_id, t.rate
                FROM
                    "subtask_result" t
                INNER JOIN problem p
                    ON t.pro_id = p.pro_id
                INNER JOIN challenge c
                    ON t.chal_id = c.chal_id
                WHERE
                    p.status = {ProConst.STATUS_ONLINE}
                    AND t.state <= {ChalConst.STATE_PC}
            ), user_total_rate AS (
                SELECT
                    acct_id, SUM(accepted_tests_per_user.rate) AS rate
                FROM accepted_tests_per_user
                GROUP BY acct_id
            ), user_stats AS (
                SELECT
                    user_total_rate.acct_id,
                    user_total_rate.rate,
                    COUNT(DISTINCT c.pro_id) FILTER (WHERE cs.state = {ChalConst.STATE_AC}) AS ac_problem_count,
                    COUNT(*) FILTER (WHERE cs.state = {ChalConst.STATE_AC}) AS ac_challenge_count,
                    COUNT(*) AS all_challenge_count,
                    COUNT(*) FILTER (WHERE cs.state = 1)::float / NULLIF(COUNT(c.chal_id), 0) AS ac_ratio

                FROM
                    public.challenge c
                INNER JOIN
                    problem p ON p.pro_id = c.pro_id
                INNER JOIN
                    total_result cs ON c.chal_id = cs.chal_id
                INNER JOIN
                    user_total_rate ON user_total_rate.acct_id = c.acct_id
                WHERE
                    c.contest_id = 0 AND
                    p.status = {ProConst.STATUS_ONLINE}
                GROUP BY
                    user_total_rate.acct_id, user_total_rate.rate
            ), ranked_user_stats AS (
                SELECT
                    acct_id,
                    rate,
                    ac_problem_count,
                    ac_challenge_count,
                    all_challenge_count,
                    RANK() OVER (ORDER BY
                        rate DESC,
                        ac_problem_count DESC,
                        ac_ratio DESC
                    ) AS rank
                FROM
                    user_stats
            ), ranked_user_cnt AS (
                SELECT COUNT(*) AS total_cnt FROM ranked_user_stats
            )
            SELECT
                ranked_user_cnt.total_cnt,
                a.acct_id,
                a.name,
                a.photo,
                a.motto,
                ac_problem_count,
                rate,
                ac_challenge_count,
                all_challenge_count,
                rank
            FROM
                account a
            INNER JOIN ranked_user_stats
                ON ranked_user_stats.acct_id = a.acct_id
            JOIN ranked_user_cnt
                ON 1 = 1
            ORDER BY
                rank
            OFFSET $1 LIMIT $2;
            ''',
            pageoff, pagenum
        )

        acctlist = []
        total_cnt = 0
        for total_cnt, acct_id, name, photo, motto, ac_pro_cnt, total_rate, ac_cnt, all_cnt, rank in res:
            acct = Account(acct_id, -1, '', name, photo, '', motto, '', '', [])
            acct.rank = rank

            acct.rate_data = {
                'all_cnt': all_cnt,
                'ac_cnt': ac_cnt,
                'ac_pro_cnt': ac_pro_cnt,
            }
            acctlist.append(acct)

        await self.render('user-rank', acctlist=acctlist, pageoff=pageoff, pagenum=pagenum, total_cnt=total_cnt)
