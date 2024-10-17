import datetime

import tornado.web

from handlers.base import RequestHandler, reqenv
from services.user import UserConst, UserService, Account
from services.chal import ChalConst


class ProRankHandler(RequestHandler):
    @reqenv
    async def get(self, pro_id):
        tz = datetime.timezone(datetime.timedelta(hours=+8))
        pro_id = int(pro_id)

        try:
            pageoff = int(self.get_argument('pageoff'))

        except tornado.web.HTTPError:
            pageoff = 0

        try:
            pagenum = int(self.get_argument('pagenum'))

        except tornado.web.HTTPError:
            pagenum = 20

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
                        "challenge_state"."runtime",
                        "challenge_state"."memory",
                        ROUND("challenge_state"."rate", "problem"."rate_precision")

                    FROM "challenge"
                    INNER JOIN "account"
                    ON "challenge"."acct_id"="account"."acct_id"

                    INNER JOIN "challenge_state"
                    ON "challenge"."chal_id"="challenge_state"."chal_id"

                    INNER JOIN "problem"
                    ON "challenge"."pro_id" = $1

                    WHERE "challenge_state"."state"={ChalConst.STATE_AC}

                    ORDER BY "challenge"."acct_id" ASC, "challenge_state"."rate" ASC,
                    "challenge_state"."runtime" ASC, "challenge_state"."memory" ASC,
                    "challenge"."timestamp" ASC
                ) temp
                ORDER BY "runtime" ASC, "memory" ASC,
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
                INNER JOIN challenge_state ON challenge.chal_id=challenge_state.chal_id
                WHERE challenge.pro_id=$1
                AND challenge_state.state=1
                ) temp;
                ''',
                pro_id,
            )
            total_cnt = total_cnt[0]['count']

        chal_list = []
        for rank, (chal_id, acct_id, timestamp, acct_name, runtime, memory, rate) in enumerate(result):
            chal_list.append(
                {
                    'rank': rank + pageoff + 1,
                    'chal_id': chal_id,
                    'acct_id': acct_id,
                    'acct_name': acct_name,
                    'runtime': int(runtime),
                    'memory': int(memory),
                    'rate': rate,
                    'timestamp': timestamp.astimezone(tz),
                }
            )

        await self.render(
            'pro-rank', pro_id=pro_id, chal_list=chal_list, pageoff=pageoff, pagenum=pagenum, total_cnt=total_cnt
        )


class UserRankHandler(RequestHandler):
    @reqenv
    async def get(self):
        try:
            pageoff = int(self.get_argument('pageoff'))

        except tornado.web.HTTPError:
            pageoff = 0

        try:
            pagenum = int(self.get_argument('pagenum'))

        except tornado.web.HTTPError:
            pagenum = 20

        res = await self.db.fetch(
            f'''
                WITH user_stats AS (
                    SELECT
                        a.acct_id,
                        a.name,
                        a.photo,
                        a.motto,
                        COUNT(DISTINCT CASE WHEN cs.state = 1 THEN c.pro_id END) AS ac_problem_count,
                        SUM(CASE WHEN cs.state = 1 THEN cs.rate ELSE 0 END) AS total_problem_rate,
                        COUNT(CASE WHEN cs.state = 1 THEN 1 END) AS ac_challenge_count,
                        COUNT(c.chal_id) AS all_challenge_count,
                        COUNT(CASE WHEN cs.state = 1 THEN 1 END)::float / NULLIF(COUNT(c.chal_id), 0) AS ac_ratio

                    FROM
                        public.challenge c
                    INNER JOIN
                        public.challenge_state cs ON c.chal_id = cs.chal_id AND c.contest_id = 0
                    INNER JOIN
                        public.account a ON a.acct_id = c.acct_id
                    INNER JOIN
                        public.problem ON c.pro_id = problem.pro_id AND problem.status = 0
                    GROUP BY
                        a.acct_id
                )
                SELECT
                    acct_id,
                    name,
                    photo,
                    motto,
                    ac_problem_count,
                    total_problem_rate,
                    ac_challenge_count,
                    all_challenge_count,
                    RANK() OVER (ORDER BY
                        ac_problem_count DESC,
                        total_problem_rate DESC,
                        ac_ratio DESC
                    ) AS rank
                FROM
                    user_stats
                ORDER BY
                    rank
                OFFSET {pageoff} LIMIT {pagenum};
                ''')

        acctlist = []
        for acct_id, name, photo, motto, ac_pro_cnt, total_rate, ac_cnt, all_cnt, rank in res:
            acct = Account(acct_id, -1, '', name, photo, '', motto, '', [])
            acct.rank = rank
            acct.rate_data = {
                'all_cnt': all_cnt,
                'ac_cnt': ac_cnt,
                'ac_pro_cnt': ac_pro_cnt,
            }
            acctlist.append(acct)

        _, t_acctlist = await UserService.inst.list_acct(UserConst.ACCTTYPE_KERNEL)
        total_cnt = len(t_acctlist)

        await self.render('user-rank', acctlist=acctlist, pageoff=pageoff, pagenum=pagenum, total_cnt=total_cnt)
