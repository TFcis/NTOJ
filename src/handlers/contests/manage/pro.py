import asyncio

from handlers.base import reqenv, RequestHandler, ActionDispatcher
from handlers.contests.base import contest_require_permission
from services.chal import ChalConst, ChalService
from services.contests import ContestService, ProblemScoreType, ContestMode
from services.judge import JudgeServerClusterService
from services.pro import ProService, ProConst
from utils.numeric import parse_str_to_list

contest_manage_pro_dispatcher = ActionDispatcher()


class ContestManageProHandler(RequestHandler):
    @reqenv
    @contest_require_permission("admin")
    async def get(self):
        pro_list = []
        for pro_id in self.contest.pro_list.keys():
            err, pro = await ProService.inst.get_pro(
                pro_id, ProConst.PRO_STATUS_CONTEST_USER
            )
            if err:
                continue
            pro_list.append(pro)

        if self.contest.contest_mode == ContestMode.RANDOM_SET:
            await self.render(
                "contests/manage/rand-pro",
                page="pro",
                contest_id=self.contest.contest_id,
                contest=self.contest,
                pro_sets=self.contest.pro_sets
            )
        else:
            await self.render(
                "contests/manage/pro",
                page="pro",
                contest_id=self.contest.contest_id,
                contest=self.contest,
                pro_list=pro_list,
            )

    @contest_manage_pro_dispatcher.action("add")
    async def add_action(self):
        if self.contest.contest_mode == ContestMode.RANDOM_SET:
            return self.error(('Emod', 'Cannot add problems to random set contests'))

        try:
            pro_id = int(self.get_argument("pro_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem ID"))

        if self.contest.is_pro(pro_id):
            return self.error(("Eexist", f"Problem(#{pro_id}) is already in contest"))

        err, _ = await ProService.inst.get_pro(
            pro_id, ProConst.PRO_STATUS_CONTEST_USER
        )
        if err:
            return self.error(err)

        self.contest.pro_list[pro_id] = {"score_type": ProblemScoreType.IOI2017}

        await ContestService.inst.update_contest(
            self.acct, self.contest, prolist_updated=True
        )
        await self.rs.delete(f"contest_{self.contest.contest_id}_scores")
        return self.error(
            ("S", f"Problem(#{pro_id}) successfully added to problem list.")
        )

    @contest_manage_pro_dispatcher.action("remove")
    async def remove_action(self):
        if self.contest.contest_mode == ContestMode.RANDOM_SET:
            return self.error(('Emod', 'Cannot remove problems from random set contests'))

        try:
            pro_id = int(self.get_argument("pro_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem ID"))

        if not self.contest.is_pro(pro_id):
            return self.error(("Enoext", f"Problem(#{pro_id}) not in contest"))

        self.contest.pro_list.pop(pro_id)

        await ContestService.inst.update_contest(
            self.acct, self.contest, prolist_updated=True
        )
        await self.rs.delete(f"contest_{self.contest.contest_id}_scores")
        return self.error(
            ("S", f"Problem(#${pro_id}) successfully removed from problem list.")
        )

    @contest_manage_pro_dispatcher.action("multi_add")
    async def multi_add_action(self):
        if self.contest.contest_mode == ContestMode.RANDOM_SET:
            return self.error(('Emod', 'Cannot add problems to random set contests'))

        proid_list = self.get_argument("pro_id")
        proid_list = parse_str_to_list(proid_list)
        for pro_id in proid_list:
            err, _ = await ProService.inst.get_pro(
                pro_id, ProConst.PRO_STATUS_CONTEST_USER
            )
            if err:
                continue
            self.contest.pro_list[pro_id] = {"score_type": ProblemScoreType.IOI2017}

        await ContestService.inst.update_contest(
            self.acct, self.contest, prolist_updated=True
        )
        await self.rs.delete(f"contest_{self.contest.contest_id}_scores")
        return self.error(
            ("S", f"Problems(#{proid_list}) successfully added to problem list.")
        )

    @contest_manage_pro_dispatcher.action("multi_remove")
    async def multi_remove_action(self):
        if self.contest.contest_mode == ContestMode.RANDOM_SET:
            return self.error(('Emod', 'Cannot remove problems from random set contests'))

        pro_id = self.get_argument("pro_id")
        pro_list = parse_str_to_list(pro_id)

        for pro_id in pro_list:
            try:
                self.contest.pro_list.pop(pro_id)
            except KeyError:
                continue

        await ContestService.inst.update_contest(
            self.acct, self.contest, prolist_updated=True
        )
        await self.rs.delete(f"contest_{self.contest.contest_id}_scores")
        return self.error(
            ("S", f"Problems(#${pro_id}) successfully removed from problem list.")
        )

    @contest_manage_pro_dispatcher.action("rechal")
    async def rechal_action(self):
        try:
            pro_id = int(self.get_argument("pro_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem ID"))

        can_submit = JudgeServerClusterService.inst.is_server_online()
        if not can_submit:
            return self.error(("Ejudge", "No judge available"))

        err, pro = await ProService.inst.get_pro(
            pro_id, ProConst.PRO_STATUS_CONTEST_USER
        )
        if err:
            return self.error(err)

        async with self.db.acquire() as con:
            result = await con.fetch(
                """
                    SELECT chal_id, compiler_type FROM challenge
                    WHERE contest_id = $1 AND pro_id = $2;
                """,
                self.contest.contest_id,
                pro_id,
            )

        # await LogService.inst.add_log(
        #         f"{self.acct.name} made a request to rejudge the problem #{pro_id} with {len(result)} chals",
        #         'manage.chal.rechal',
        #     )

        # TODO: send notify to user
        async def _rechal(rechals):
            err, pro = await ProService.inst.get_pro(
                pro_id, ProConst.PRO_STATUS_CONTEST_USER
            )
            if err:
                return
            for chal_id, compiler_type in rechals:
                _, _ = await ChalService.inst.reset_chal(chal_id)
                _, _ = await ChalService.inst.emit_chal(
                    chal_id,
                    pro.config,
                    compiler_type,
                    ChalConst.CONTEST_REJUDGE_PRI,
                    pro.problem_type,
                    skip_nonac=False,
                )

        await asyncio.create_task(_rechal(rechals=result))
        return self.error(("S", f"Problem(#{pro_id}) is rechallenging."))

    @contest_manage_pro_dispatcher.action("public")
    async def public_action(self):
        try:
            pro_id = int(self.get_argument("pro_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem ID"))

        if not self.contest.is_pro(pro_id):
            return self.error(("Enoext", f"Problem(#{pro_id}) not in contest"))

        if not self.contest.is_end():
            return self.error(("Etime", "Contest is not over yet"))

        err, pro = await ProService.inst.get_pro(
            pro_id, ProConst.PRO_STATUS_CONTEST_USER
        )
        if err:
            return self.error(err)

        pro.status = ProConst.STATUS_ONLINE
        err, _ = await ProService.inst.update_pro(pro)
        if err:
            return self.error(err)

        return self.error(("S", ""))

    @contest_manage_pro_dispatcher.action("add_set")
    async def add_set_action(self):
        '''
            Add a problem set in random set mode
            pro_id should be a list of problem ids separated by comma
        '''
        if self.contest.contest_mode != ContestMode.RANDOM_SET:
            return self.error(('Emod', 'Cannot add problem set to non-random set contests'))

        pro_ids = self.get_argument("pro_id")
        pro_ids = parse_str_to_list(pro_ids)

        if len(pro_ids) < 1:
            return self.error(('Eparam', 'Problem set must contain at least one problem'))

        pro_set = [(pro_id, ProblemScoreType.IOI2017) for pro_id in pro_ids]

        err, _ = await ContestService.inst.add_pro_set(self.contest, pro_set)
        if err:
            return self.error(err)

        return self.error(("S", "Add new problem set successfully"))

    @contest_manage_pro_dispatcher.action("remove_set")
    async def remove_set_action(self):
        '''
            Remove a problem set in random set mode
            pro_id is the problem set index
        '''
        if self.contest.contest_mode != ContestMode.RANDOM_SET:
            return self.error(('Emod', 'Cannot remove problem set from non-random set contests'))

        pro_set_idx = int(self.get_argument("pro_id"))
        if pro_set_idx < 0 or pro_set_idx > len(self.contest.pro_sets) - 1:
            return self.error(('Eparam', 'Problem set index out of range'))

        err, _ = await ContestService.inst.remove_pro_set(self.contest, pro_set_idx)
        if err:
            return self.error(err)

        return self.error(("S", f"Remove problem set #{pro_set_idx} successfully"))

    @contest_manage_pro_dispatcher.action("update_order")
    async def update_order_action(self):
        '''
            Update problem order in random set mode
            pro_id is a comma separated list of new problem set indices
        '''
        if self.contest.contest_mode != ContestMode.RANDOM_SET:
            return self.error(('Emod', 'Cannot update problem order in non-random set contests'))

        new_idxs = self.get_argument("pro_id")
        new_idxs = parse_str_to_list(new_idxs)

        pro_set_len = len(self.contest.pro_sets)

        if len(new_idxs) != pro_set_len or sorted(new_idxs) != list(range(pro_set_len)):
            return self.error(('Eparam', 'Invalid new indexes for problem sets'))

        err, _ = await ContestService.inst.reorder_pro_set(self.contest, new_idxs)
        if err:
            return self.error(err)

        return self.error(("S", f"Update problem set order successfully"))

    @reqenv
    @contest_require_permission("admin")
    async def post(self):
        # TODO: update problem score type
        # TODO: frontend: drag problem to change order
        reqtype = self.get_argument("reqtype")
        return await contest_manage_pro_dispatcher.dispatch(self, reqtype)
