from decimal import Decimal

from msgpack import unpackb

from handlers.base import reqenv, RequestHandler
from services.pro import ProConst, ProService
from services.rate import RateService
from services.contests import ContestMode

PERMISSION_DENIED_ERROR = ('Eacces', 'Permission denied')

class ContestProsetHandler(RequestHandler):
    async def randomset_proset(self, pageoff: int):
        if not self.contest.is_member(self.acct):
            return self.error(PERMISSION_DENIED_ERROR)

        scoreboard_key = f'contest_{self.contest.contest_id}_randomset_scoreboard'
        randomset_prolist = self.contest.get_prolist_from_acct_by_ip(self.acct)
        if randomset_prolist is None:
            return self.error(('Etodo', 'TODO: Assign problem set for out of range IP not implemented. Call Yushiuan9499.'))
        randomset_prolist_set = set(randomset_prolist)

        prolist_order = {pro_id: idx for idx, pro_id in enumerate(randomset_prolist)}
        _, prolist = await ProService.inst.list_pro(ProConst.PRO_STATUS_CONTEST_USER)
        prolist = sorted(filter(lambda pro: pro.pro_id in randomset_prolist_set, prolist),
                                key=lambda pro: prolist_order[pro.pro_id])

        keys = [f'{self.acct.acct_id}_{pro_order}' for pro_order in range(len(prolist))]
        score_values = await self.rs.hmget(scoreboard_key, keys)

        score_map: dict[int, dict] = {}
        for pro_order, pro in enumerate(prolist):
            score_map[pro.pro_id] = {'score': Decimal('0'), 'state': None}
            assert 0 <= pro_order < len(score_values)

            best_record = score_values[pro_order]
            if best_record is not None:
                best_record = unpackb(best_record)
                score_map[pro.pro_id]['score'] += Decimal(best_record['score'])
                score_map[pro.pro_id]['state'] = best_record['state']

        pro_total_cnt = len(prolist)
        prolist = prolist[pageoff: pageoff + 40]

        pro_idx_map = {pro_id: idx for idx, pro_id in enumerate(randomset_prolist)}
        await self.render('contests/proset', contest=self.contest, show_ac_ratio=False,
                          prolist=prolist, pro_idx_map=pro_idx_map, pro_total_cnt=pro_total_cnt, score_map=score_map, pageoff=pageoff)


    @reqenv
    async def get(self):
        pageoff = int(self.get_argument('pageoff', default=0))

        show_ac_ratio = False

        if not self.contest.is_member(self.acct):
            return self.error(PERMISSION_DENIED_ERROR)

        if not self.contest.is_start() and not self.contest.is_admin(self.acct):
            return self.error(PERMISSION_DENIED_ERROR)

        elif self.contest.is_running() and not self.contest.is_member(self.acct):
            return self.error(PERMISSION_DENIED_ERROR)

        else:
            if self.contest.contest_mode == ContestMode.RANDOM_SET and not self.contest.is_admin(self.acct):
                return await self.randomset_proset(pageoff)

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

            if self.contest.contest_mode == ContestMode.RANDOM_SET:
                pro_idx_map = {pro_id: idx for idx, pro_set in enumerate(self.contest.pro_sets) for pro_id in pro_set}
            else:
                pro_idx_map = {pro_id: idx for idx, pro_id in enumerate(self.contest.pro_list.keys())}

        pro_total_cnt = len(prolist)
        prolist = prolist[pageoff: pageoff + 40]

        await self.render('contests/proset', contest=self.contest, show_ac_ratio=show_ac_ratio,
                          prolist=prolist, pro_idx_map=pro_idx_map, pro_total_cnt=pro_total_cnt, score_map=score_map, pageoff=pageoff)
