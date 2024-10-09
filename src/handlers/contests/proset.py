import tornado

from handlers.base import reqenv, RequestHandler
from handlers.contests.base import contest_require_permission
from services.pro import ProService
from services.rate import RateService


class ContestProsetHandler(RequestHandler):
    @reqenv
    @contest_require_permission('all')
    async def get(self):
        try:
            pageoff = int(self.get_argument('pageoff'))
        except tornado.web.HTTPError:
            pageoff = 0

        if not (self.contest.is_start() or self.contest.is_admin(self.acct)):
            prolist = []

        else:
            _, acct_rates = await RateService.inst.map_rate_acct(self.acct, contest_id=self.contest.contest_id)
            _, prolist = await ProService.inst.list_pro(self.acct, is_contest=True)

            prolist_order = {pro_id: idx for idx, pro_id in enumerate(self.contest.pro_list)}
            prolist = sorted(filter(lambda pro: pro['pro_id'] in self.contest.pro_list, prolist),
                                  key=lambda pro: prolist_order[pro['pro_id']])

            def get_score(pro):
                pro['score'] = 0
                pro['state'] = None
                if pro['pro_id'] in acct_rates:
                    pro['score'] += acct_rates[pro['pro_id']]['rate']
                    pro['state'] = acct_rates[pro['pro_id']]['state']

                return pro

            prolist = list(map(get_score, prolist))

        pro_total_cnt = len(prolist)
        prolist = prolist[pageoff: pageoff + 40]

        await self.render('contests/proset', contest=self.contest,
                          prolist=prolist, pro_total_cnt=pro_total_cnt, pageoff=pageoff)
