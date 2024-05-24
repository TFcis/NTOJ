import datetime

import tornado.web

from handlers.base import RequestHandler, reqenv
from services.user import UserService, UserConst
from services.rate import RateService


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
                'SELECT *'
                'FROM ('
                'SELECT DISTINCT ON ("challenge"."acct_id")'
                '"challenge"."chal_id",'
                '"challenge"."acct_id",'
                '"challenge"."timestamp",'
                '"account"."name" AS "acct_name",'
                '"challenge_state"."runtime",'
                '"challenge_state"."memory" '
                'FROM "challenge" '
                'INNER JOIN "account" '
                'ON "challenge"."acct_id"="account"."acct_id" '
                'LEFT JOIN "challenge_state" '
                'ON "challenge"."chal_id"="challenge_state"."chal_id" '
                'WHERE "account"."acct_type">= $1 AND "challenge"."pro_id"= $2 '
                'AND "challenge_state"."state"=1 '
                'ORDER BY "challenge"."acct_id" ASC, '
                '"challenge_state"."runtime" ASC, "challenge_state"."memory" ASC,'
                '"challenge"."timestamp" ASC, "challenge"."acct_id" ASC'
                ') temp '
                'ORDER BY "runtime" ASC, "memory" ASC,'
                '"timestamp" ASC, "acct_id" ASC OFFSET $3 LIMIT $4;',
                self.acct.acct_type, pro_id, pageoff, pagenum,
            )

            total_cnt = await con.fetch(
                '''
                SELECT COUNT(*)
                FROM (
                SELECT DISTINCT ON ("challenge"."acct_id")
                "challenge"."chal_id",
                FROM "challenge"
                INNER JOIN "account"
                ON "challenge"."acct_id"="account"."acct_id"
                LEFT JOIN "challenge_state"
                ON "challenge"."chal_id"="challenge_state"."chal_id"
                WHERE "account"."acct_type">= $1 AND "challenge"."pro_id"= $2
                AND "challenge_state"."state"=1
                ) AS temp;
                ''',
                self.acct.acct_type, pro_id,
            )
            total_cnt = total_cnt[0]['count']

            total_cnt = await con.fetch(
                '''
                SELECT COUNT(*)
                FROM (
                SELECT DISTINCT ON ("challenge"."acct_id")
                "challenge"."chal_id",
                FROM "challenge"
                INNER JOIN "account"
                ON "challenge"."acct_id"="account"."acct_id"
                LEFT JOIN "challenge_state"
                ON "challenge"."chal_id"="challenge_state"."chal_id"
                WHERE "account"."acct_type">= $1 AND "challenge"."pro_id"= $2
                AND "challenge_state"."state"=1
                ) AS temp;
                ''',
                self.acct.acct_type, pro_id,
            )
            total_cnt = total_cnt[0]['count']

        chal_list = []
        for rank, (chal_id, acct_id, timestamp, acct_name, runtime, memory) in enumerate(result):
            chal_list.append(
                {
                    'rank': rank + pageoff + 1,
                    'chal_id': chal_id,
                    'acct_id': acct_id,
                    'acct_name': acct_name,
                    'runtime': int(runtime),
                    'memory': int(memory),
                    'timestamp': timestamp.astimezone(tz),
                }
            )

        await self.render('pro-rank', pro_id=pro_id, chal_list=chal_list, pageoff=pageoff, pagenum=pagenum, total_cnt=total_cnt)

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

        err, acctlist = await UserService.inst.list_acct(UserConst.ACCTTYPE_KERNEL)
        if err:
            self.error(err)
            return

        err, ratemap = await RateService.inst.map_rate(clas=None)
        if err:
            self.error(err)
            return

        for acct in acctlist:
            err, t_acct = await UserService.inst.info_acct(acct.acct_id)
            if err:
                self.error(err)
                return

            err, rate_data = await RateService.inst.get_acct_rate_and_chal_cnt(acct)
            if err:
                self.error(err)
                return


            rate_data['ac_pro_cnt'] = sum(1 for r in ratemap[acct.acct_id].values() if r['rate'] == 100)
            acct.rate_data = rate_data
            acct.photo = t_acct.photo

        total_cnt = len(acctlist)
        acctlist.sort(key=lambda acct: (acct.rate_data['ac_pro_cnt'], acct.rate_data['ac_cnt'], acct.rate_data['all_cnt'], acct.rate_data['rate']), reverse=True)
        acctlist = acctlist[pageoff: pageoff + pagenum]
        for rank, acct in enumerate(acctlist):
            acct.rank = rank + 1 + pageoff

        await self.render('user-rank', acctlist=acctlist, pageoff=pageoff, pagenum=pagenum, total_cnt=total_cnt)