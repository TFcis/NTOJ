import asyncio

from handlers.base import reqenv, RequestHandler, ActionDispatcher
from handlers.contests.base import contest_require_permission
from services.chal import ChalConst, ChalService
from services.contests import ContestService, ProblemScoreType,  ChallengeResultStyle
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

        await self.render(
            "contests/manage/pro",
            page="pro",
            contest_id=self.contest.contest_id,
            contest=self.contest,
            pro_list=pro_list,
        )

    @contest_manage_pro_dispatcher.action("add")
    async def add_action(self):
        pro_id = int(self.get_argument("pro_id"))
        score_type = int(self.get_argument("score_type", default=ProblemScoreType.IOI2017))

        if self.contest.is_pro(pro_id):
            return self.error(("Eexist", f"Problem(#{pro_id}) is already in contest"))

        if score_type not in (ProblemScoreType.IOI2013, ProblemScoreType.IOI2017):
            return self.error(("Eparam", "Invalid score type"))

        self.contest.pro_list[pro_id] = {
            "score_type": ProblemScoreType(score_type),
            "challenge_style": ChallengeResultStyle.FULL
        }

        await ContestService.inst.update_contest(
            self.acct, self.contest, prolist_updated=True
        )
        # await self.rs.delete(f"contest_{self.contest.contest_id}_scores")
        return self.error(
            ("S", f"Problem(#{pro_id}) successfully added to problem list.")
        )

    @contest_manage_pro_dispatcher.action("remove")
    async def remove_action(self):
        pro_id = int(self.get_argument("pro_id"))

        if not self.contest.is_pro(pro_id):
            return self.error(("Enoext", f"Problem(#{pro_id}) not in contest"))

        self.contest.pro_list.pop(pro_id)

        await ContestService.inst.update_contest(
            self.acct, self.contest, prolist_updated=True
        )
        await self.rs.hdel(f"contest_{self.contest.contest_id}_scores", str(pro_id))
        return self.error(
            ("S", f"Problem(#${pro_id}) successfully removed from problem list.")
        )

    @contest_manage_pro_dispatcher.action("multi_add")
    async def multi_add_action(self):
        pro_id = self.get_argument("pro_id")
        pro_id = parse_str_to_list(pro_id)
        score_type = int(self.get_argument("score_type", default=ProblemScoreType.IOI2017))

        if score_type not in (ProblemScoreType.IOI2013, ProblemScoreType.IOI2017):
            return self.error(("Eparam", "Invalid score type"))

        for p_id in pro_id:
            self.contest.pro_list[p_id] = {
                "score_type": ProblemScoreType(score_type),
                "challenge_style": ChallengeResultStyle.FULL
            }

        await ContestService.inst.update_contest(
            self.acct, self.contest, prolist_updated=True
        )
        # await self.rs.delete(f"contest_{self.contest.contest_id}_scores")
        return self.error(
            ("S", f"Problems(#{pro_id}) successfully added to problem list.")
        )

    @contest_manage_pro_dispatcher.action("multi_remove")
    async def multi_remove_action(self):
        pro_id = self.get_argument("pro_id")
        pro_list = parse_str_to_list(pro_id)

        for pro_id in pro_list:
            try:
                self.contest.pro_list.pop(pro_id)
                await self.rs.hdel(f"contest_{self.contest.contest_id}_scores", str(pro_id))
            except KeyError:
                continue

        await ContestService.inst.update_contest(
            self.acct, self.contest, prolist_updated=True
        )
        return self.error(
            ("S", f"Problems(#${pro_id}) successfully removed from problem list.")
        )

    async def _rejudge_challenges(self, pro_id: int, rechals: list, include_system_test: bool = False):
        """Helper method to rejudge a list of challenges.

        Args:
            pro_id: Problem ID
            rechals: List of (chal_id, compiler_type) tuples
            include_system_test: Whether to include system test testdatas
        """
        err, pro = await ProService.inst.get_pro(
            pro_id, ProConst.PRO_STATUS_CONTEST_USER
        )
        if err:
            return

        for chal_id, compiler_type in rechals:
            await ChalService.inst.reset_chal(chal_id)
            await ChalService.inst.emit_chal(
                chal_id,
                pro.config,
                compiler_type,
                ChalConst.CONTEST_REJUDGE_PRI,
                pro.problem_type,
                skip_nonac=False,
                include_system_test=include_system_test,
            )

    @contest_manage_pro_dispatcher.action("rechal")
    async def rechal_action(self):
        pro_id = int(self.get_argument("pro_id"))

        if not JudgeServerClusterService.inst.is_server_online():
            return self.error(("Ejudge", "No judge available"))

        err, _ = await ProService.inst.get_pro(
            pro_id, ProConst.PRO_STATUS_CONTEST_USER
        )
        if err:
            return self.error(err)


        if not self.contest.enable_system_test:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    """
                        SELECT chal_id, compiler_type FROM challenge
                        WHERE contest_id = $1 AND pro_id = $2;
                    """,
                    self.contest.contest_id,
                    pro_id,
                )
            await asyncio.create_task(
                self._rejudge_challenges(pro_id, result, include_system_test=True)
            )
        else:
            admin_chals = []
            normal_chals = []
            async with self.db.acquire() as con:
                result = await con.fetch(
                    """
                        SELECT acct_id, chal_id, compiler_type FROM challenge
                        WHERE contest_id = $1 AND pro_id = $2;
                    """,
                    self.contest.contest_id,
                    pro_id,
                )

            for acct_id, chal_id, compiler_type in result:
                if self.contest.is_admin(acct_id=acct_id):
                    admin_chals.append((chal_id, compiler_type))
                else:
                    normal_chals.append((chal_id, compiler_type))

            await asyncio.create_task(
                self._rejudge_challenges(pro_id, admin_chals, include_system_test=True)
            )
            await asyncio.create_task(
                self._rejudge_challenges(pro_id, normal_chals, include_system_test=self.contest.is_end())
            )

        return self.error(("S", f"Problem(#{pro_id}) is rechallenging."))

    @contest_manage_pro_dispatcher.action("update_score_type")
    async def update_score_type_action(self):
        pro_id = int(self.get_argument("pro_id"))
        score_type = int(self.get_argument("score_type"))

        if not self.contest.is_pro(pro_id):
            return self.error(("Enoext", f"Problem(#{pro_id}) not in contest"))

        if score_type not in (ProblemScoreType.IOI2013, ProblemScoreType.IOI2017):
            return self.error(("Eparam", "Invalid score type"))

        self.contest.pro_list[pro_id]["score_type"] = ProblemScoreType(score_type)

        await ContestService.inst.update_contest(
            self.acct, self.contest, prolist_updated=True
        )
        await self.rs.hdel(f"contest_{self.contest.contest_id}_scores", str(pro_id))
        return self.error(("S", "Score type updated successfully."))

    @contest_manage_pro_dispatcher.action("update_challenge_style")
    async def update_challenge_style_action(self):
        from services.contests import ChallengeResultStyle
        pro_id = int(self.get_argument("pro_id"))
        challenge_style = int(self.get_argument("challenge_style"))

        if not self.contest.is_pro(pro_id):
            return self.error(("Enoext", f"Problem(#{pro_id}) not in contest"))

        if challenge_style not in (ChallengeResultStyle.FULL, ChallengeResultStyle.STATE_COUNT,
                                   ChallengeResultStyle.SUBTASK_ONLY, ChallengeResultStyle.TOTAL_ONLY):
            return self.error(("Eparam", "Invalid challenge style"))

        self.contest.pro_list[pro_id]["challenge_style"] = ChallengeResultStyle(challenge_style)

        await ContestService.inst.update_contest(
            self.acct, self.contest, prolist_updated=True
        )
        return self.error(("S", "Challenge style updated successfully."))

    @contest_manage_pro_dispatcher.action("public")
    async def public_action(self):
        pro_id = int(self.get_argument("pro_id"))
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

    @contest_manage_pro_dispatcher.action("system_test")
    async def system_test_action(self):
        """Start system test for all AC challenges for a specific problem.

        System test will rejudge all AC challenges with full testdatas including
        those tagged as 'system-test'.
        """
        pro_id = int(self.get_argument("pro_id"))

        if not self.contest.is_pro(pro_id):
            return self.error(("Enoext", f"Problem(#{pro_id}) not in contest"))

        if not self.contest.enable_system_test:
            return self.error(("Econf", "System test is not enabled for this contest"))

        if not self.contest.is_end():
            return self.error(("Etime", "Contest must be over to start system test"))

        if not JudgeServerClusterService.inst.is_server_online():
            return self.error(("Ejudge", "No judge available"))

        err, pro = await ProService.inst.get_pro(
            pro_id, ProConst.PRO_STATUS_CONTEST_USER
        )
        if err:
            return self.error(err)

        async with self.db.acquire() as con:
            result = await con.fetch(
                """
                    SELECT challenge.chal_id, challenge.compiler_type
                    FROM challenge
                    INNER JOIN total_result ON challenge.chal_id = total_result.chal_id
                    WHERE challenge.contest_id = $1
                    AND challenge.pro_id = $2
                    AND total_result.state = $3;
                """,
                self.contest.contest_id,
                pro_id,
                ChalConst.STATE_AC,
            )

        if len(result) == 0:
            return self.error(("Enoext", "No AC challenges found for system test"))

        await asyncio.create_task(
            self._rejudge_challenges(pro_id, result, include_system_test=True)
        )
        return self.error(("S", f"System test started for {len(result)} AC challenges on Problem(#{pro_id})."))

    @reqenv
    @contest_require_permission("admin")
    async def post(self):
        # TODO: update problem score type
        # TODO: frontend: drag problem to change order
        reqtype = self.get_argument("reqtype")
        return await contest_manage_pro_dispatcher.dispatch(self, reqtype)
