import tornado

from handlers.base import reqenv, RequestHandler
from services.pro import ProService
from services.rate import RateService


class ContestProsetHandler(RequestHandler):
    @reqenv
    async def get(self):
        try:
            pageoff = int(self.get_argument('pageoff'))
        except tornado.web.HTTPError:
            pageoff = 0

        show_ac_ratio = False
        if not self.contest.is_start() and not self.contest.is_admin(self.acct):
            return self.error(('Eacces', 'Permission denied'))

        elif self.contest.is_running() and not self.contest.is_member(self.acct):
            return self.error(('Eacces', 'Permission denied'))

        else:
            _, acct_rates = await RateService.inst.map_rate_acct(self.acct, contest_id=self.contest.contest_id)
            _, prolist = await ProService.inst.list_pro(self.acct, is_contest=True)

            prolist_order = {pro_id: idx for idx, pro_id in enumerate(self.contest.pro_list.keys())}
            prolist = sorted(filter(lambda pro: self.contest.is_pro(pro['pro_id']), prolist),
                                  key=lambda pro: prolist_order[pro['pro_id']])

            def get_score(pro):
                pro['score'] = 0
                pro['state'] = None
                if pro['pro_id'] in acct_rates:
                    pro['score'] += acct_rates[pro['pro_id']]['rate']
                    pro['state'] = acct_rates[pro['pro_id']]['state']

                return pro

            prolist = list(map(get_score, prolist))

            if self.contest.is_public_scoreboard or self.contest.is_admin(self.acct):
                show_ac_ratio = True
                for pro in prolist:
                    _, rate = await RateService.inst.get_pro_ac_rate(pro['pro_id'], contest_id=self.contest.contest_id)
                    pro['rate_data'] = rate

        pro_total_cnt = len(prolist)
        prolist = prolist[pageoff: pageoff + 40]

        await self.render('contests/proset', contest=self.contest, show_ac_ratio=show_ac_ratio,
                          prolist=prolist, pro_total_cnt=pro_total_cnt, pageoff=pageoff)
