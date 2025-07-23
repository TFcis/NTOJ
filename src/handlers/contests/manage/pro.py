import asyncio

from handlers.base import reqenv, RequestHandler
from handlers.contests.base import contest_require_permission
from services.chal import ChalConst, ChalService
from services.contests import ContestService, ProblemScoreType
from services.judge import JudgeServerClusterService
from services.pro import ProService, ProConst
from utils.numeric import parse_list_str


class ContestManageProHandler(RequestHandler):
    @reqenv
    @contest_require_permission('admin')
    async def get(self):
        pro_list = []
        for pro_id in self.contest.pro_list.keys():
            err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_CONTEST_USER)
            if err:
                continue
            pro_list.append(pro)

        await self.render('contests/manage/pro', page='pro', contest_id=self.contest.contest_id,
                          contest=self.contest, pro_list=pro_list)

    @reqenv
    @contest_require_permission('admin')
    async def post(self):
        # TODO: update problem score type
        # TODO: frontend: drag problem to change order
        reqtype = self.get_argument('reqtype')
        pro_id = self.get_argument('pro_id')
        prolist_updated = False

        if reqtype == "add":
            pro_id = int(pro_id)

            if self.contest.is_pro(pro_id):
                return self.error(('Eexist', f'Problem(#{pro_id}) is already in contest'))

            self.contest.pro_list[pro_id] = {
                "score_type": ProblemScoreType.IOI2017.value
            }

            await ContestService.inst.update_contest(self.acct, self.contest, prolist_updated=True)
            self.error(('S', f'Problem(#{pro_id}) successfully added to problem list.'))
            prolist_updated = True

        elif reqtype == "remove":
            pro_id = int(pro_id)

            if not self.contest.is_pro(pro_id):
                return self.error(('Enoext', f'Problem(#{pro_id}) not in contest'))

            self.contest.pro_list.pop(pro_id)

            await ContestService.inst.update_contest(self.acct, self.contest, prolist_updated=True)
            self.error(('S', f'Problem(#${pro_id}) successfully removed from problem list.'))
            prolist_updated = True

        elif reqtype == "multi_add":
            pro_id = parse_list_str(pro_id)
            for p_id in pro_id:
                self.contest.pro_list[p_id] = {
                    "score_type": ProblemScoreType.IOI2017.value
                }

            await ContestService.inst.update_contest(self.acct, self.contest, prolist_updated=True)
            self.error(('S', f'Problems(#{pro_id}) successfully added to problem list.'))
            prolist_updated = True

        elif reqtype == "multi_remove":
            pro_list = parse_list_str(pro_id)

            for pro_id in pro_list:
                try:
                    self.contest.pro_list.pop(pro_id)
                except KeyError:
                    continue

            await ContestService.inst.update_contest(self.acct, self.contest, prolist_updated=True)
            self.error(('S', f'Problems(#${pro_id}) successfully removed from problem list.'))
            prolist_updated = True

        elif reqtype == "rechal":
            pro_id = int(pro_id)
            can_submit = JudgeServerClusterService.inst.is_server_online()
            if not can_submit:
                return self.error(('Ejudge', 'No judge available'))

            err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_CONTEST_USER)
            if err:
                return self.error(err)

            async with self.db.acquire() as con:
                result = await con.fetch(
                    f'''
                        SELECT "challenge"."chal_id", "challenge"."compiler_type" FROM "challenge"
                        INNER JOIN "challenge_state"
                        ON "challenge"."chal_id" = "challenge_state"."chal_id" AND "challenge"."contest_id" = {self.contest.contest_id}
                        WHERE "pro_id" = $1;
                    ''',
                    pro_id
                )

            # await LogService.inst.add_log(
            #         f"{self.acct.name} made a request to rejudge the problem #{pro_id} with {len(result)} chals",
            #         'manage.chal.rechal',
            #     )

            # TODO: send notify to user
            async def _rechal(rechals):
                for chal_id, comp_type in rechals:
                    _, _ = await ChalService.inst.reset_chal(chal_id)
                    _, _ = await ChalService.inst.emit_chal(
                        chal_id,
                        pro_id,
                        pro['testm_conf'],
                        comp_type,
                        ChalConst.CONTEST_REJUDGE_PRI,
                    )

            await asyncio.create_task(_rechal(rechals=result))
            self.error(('S', f'Problem(#{pro_id}) is rechallenging.'))

        elif reqtype == "public":
            pro_id = int(pro_id)
            if not self.contest.is_pro(pro_id):
                return self.error(('Enoext', f'Problem(#{pro_id}) not in contest'))

            if not self.contest.is_end():
                return self.error(('Etime', 'Contest is not over yet'))

            err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_CONTEST_USER)
            if err:
                return self.error(err)

            err, _ = await ProService.inst.update_pro(pro_id, pro['name'], ProConst.STATUS_ONLINE, pro['tags'])
            if err:
                return self.error(err)

            self.error(('S', ''))

        else:
            self.error(('Eunk', 'Unknown error'))
            return

        if prolist_updated:
            await self.rs.delete(f"contest_{self.contest.contest_id}_scores")
