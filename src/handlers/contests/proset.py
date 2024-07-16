import tornado

from handlers.base import reqenv, RequestHandler
from handlers.contests.base import contest_require_permission
from services.pro import ProService, ProConst
from services.rate import RateService


class ContestProsetHandler(RequestHandler):
    @reqenv
    @contest_require_permission('all')
    async def get(self):
        try:
            pageoff = int(self.get_argument('pageoff'))
        except tornado.web.HTTPError:
            pageoff = 0

        if not self.contest.is_running() and not self.contest.is_admin(self.acct):
            prolist = []

        else:
            _, acct_rates = await RateService.inst.map_rate_acct(self.acct, contest_id=self.contest.contest_id)
            _, prolist = await ProService.inst.list_pro(self.acct, is_contest=True)

            # TODO: Move this to services
            statemap = {}
            async with self.db.acquire() as con:
                result = await con.fetch(
                    f"""
                        SELECT "problem"."pro_id",
                        MIN("challenge_state"."state") AS "state"
                        FROM "challenge"
                        INNER JOIN "challenge_state"
                        ON "challenge"."chal_id" = "challenge_state"."chal_id" AND "challenge"."acct_id" = $1 AND "challenge"."contest_id" = $2
                        INNER JOIN "problem"
                        ON "challenge"."pro_id" = "problem"."pro_id"
                        WHERE "problem"."status" = {ProConst.STATUS_CONTEST}
                        GROUP BY "problem"."pro_id"
                        ORDER BY "pro_id" ASC;
                    """,
                    self.acct.acct_id,
                    self.contest.contest_id,
                )

                statemap = {pro_id: state for pro_id, state in result}
            prolist = list(filter(lambda pro: pro['pro_id'] in self.contest.pro_list, prolist))
            for pro in prolist:
                pro_id = pro["pro_id"]
                pro["state"] = statemap.get(pro_id)

            def get_score(pro):
                pro['score'] = 0
                if pro['pro_id'] in acct_rates:
                    pro['score'] += acct_rates[pro['pro_id']]['rate']

                return pro

            prolist = list(map(get_score, prolist))

        pro_total_cnt = len(prolist)
        prolist = prolist[pageoff: pageoff + 40]

        await self.render('contests/proset', contest=self.contest,
                          prolist=prolist, pro_total_cnt=pro_total_cnt, pageoff=pageoff)
