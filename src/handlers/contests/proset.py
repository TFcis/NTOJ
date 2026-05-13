from handlers.base import reqenv, RequestHandler
from services.pro import ProConst, ProService
from services.rate import RateService


class ContestProsetHandler(RequestHandler):
    @reqenv
    async def get(self):
        try:
            pageoff = int(self.get_argument("pageoff", default="0"))
            if pageoff < 0:
                pageoff = 0
        except ValueError:
            return self.error(("Eparam", "Invalid page offset"))

        show_ac_ratio = False
        if not self.contest.is_start() and not self.contest.is_admin(self.acct):
            return self.error(('Eacces', 'Permission denied'))

        elif self.contest.is_running() and not self.contest.is_member(self.acct):
            return self.error(('Eacces', 'Permission denied'))

        else:
            _, acct_rates = await RateService.inst.map_rate_acct(self.acct, contest_id=self.contest.contest_id)
            _, prolist = await ProService.inst.list_pro(ProConst.PRO_STATUS_CONTEST_USER)

            prolist_order = {pro_id: idx for idx, pro_id in enumerate(self.contest.pro_list.keys())}
            prolist = sorted(filter(lambda pro: self.contest.is_pro(pro.pro_id), prolist),
                                  key=lambda pro: prolist_order[pro.pro_id])

            score_map: dict[int, dict] = {}
            for pro in prolist:
                pro_id = pro.pro_id
                score_map[pro_id] = {'score': 0, 'state': None}
                if pro_id in acct_rates:
                    score_map[pro_id]['score'] += acct_rates[pro.pro_id]['rate']
                    score_map[pro_id]['state'] = acct_rates[pro.pro_id]['state']

            if self.contest.is_public_scoreboard or self.contest.is_admin(self.acct):
                show_ac_ratio = True
                for pro in prolist:
                    _, rate = await RateService.inst.get_pro_ac_rate(pro.pro_id, contest_id=self.contest.contest_id)
                    score_map[pro.pro_id]['rate_data'] = rate

        pro_total_cnt = len(prolist)
        prolist = prolist[pageoff: pageoff + 40]

        await self.render('contests/proset', contest=self.contest, show_ac_ratio=show_ac_ratio,
                          prolist=prolist, pro_total_cnt=pro_total_cnt, score_map=score_map, pageoff=pageoff)
