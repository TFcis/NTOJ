from handlers.base import ActionDispatcher, RequestHandler, reqenv, require_permission
from handlers.contests.base import contest_require_permission
from services.chal import ChalService
from services.judge import JudgeServerClusterService
from services.pro import ProService, ProConst
from services.user import UserConst

PERMISSION_DENIED_ERROR = ("Eacces", "Permission denied")

submit_dispatcher = ActionDispatcher()


class SubmitHandler(RequestHandler):
    @reqenv
    @require_permission([UserConst.ACCTTYPE_USER, UserConst.ACCTTYPE_KERNEL])
    @contest_require_permission("all")
    async def get(self, pro_id=None):
        if pro_id is None:
            return self.error(("Enoext", "Missing parameter pro_id"))

        pro_id = int(pro_id)

        allow_statuses = ProConst.PRO_STATUS_NORMAL_USER
        if self.contest:
            if not self.contest.is_running() and not self.contest.is_admin(self.acct):
                return self.error(PERMISSION_DENIED_ERROR)

            if not self.contest.is_pro(pro_id):
                return self.error(("Enoext", "Problem not in contest"))

            allow_statuses = ProConst.PRO_STATUS_CONTEST_USER
        else:
            if self.acct.is_kernel():
                allow_statuses = ProConst.PRO_STATUS_KERNEL_USER

        err, pro = await ProService.inst.get_pro(pro_id, allow_statuses)
        if err:
            return self.error(err)

        can_submit = JudgeServerClusterService.inst.is_server_online()
        if not can_submit:
            self.finish('<h1 style="color: red;">All Judge Server Offline</h1>')
            return

        if not pro.allow_submit:
            return self.error(("Eacces", "Problem did not allow submit"))

        # Dispatch to problem type-specific submit page
        from services.pro import ProType

        if pro.problem_type == ProType.BATCH:
            from services.prospec.batch import BatchConfig

            assert isinstance(pro.config.spec_config, BatchConfig)
            allow_compilers = pro.config.spec_config.allow_compilers
            if self.contest:
                allow_compilers = allow_compilers.intersection(
                    self.contest.allow_compilers
                )

            await self.render(
                "prospec/batch/submit",
                pro=pro,
                allow_compilers=allow_compilers,
                contest_id=self.contest.contest_id if self.contest else 0,
                user=self.acct,
            )
        elif pro.problem_type == ProType.COMMUNICATION:
            # Future: Communication submit page
            return self.error(
                ("Enotsupport", "Communication problem type not yet supported")
            )
        elif pro.problem_type == ProType.TWOSTEP:
            # Future: TwoStep submit page
            return self.error(("Enotsupport", "TwoStep problem type not yet supported"))
        elif pro.problem_type == ProType.OUTPUTONLY:
            # Future: OutputOnly submit page
            return self.error(
                ("Enotsupport", "OutputOnly problem type not yet supported")
            )
        else:
            return self.error(("Eparam", "Invalid problem type"))

    @reqenv
    @require_permission([UserConst.ACCTTYPE_USER, UserConst.ACCTTYPE_KERNEL])
    @contest_require_permission("all")
    async def post(self):
        """Handle problem submission - dispatch to type-specific handler."""
        can_submit = JudgeServerClusterService.inst.is_server_online()
        if not can_submit:
            return self.error(("Ejudge", "No available judge"))

        reqtype = self.get_argument("reqtype")
        return await submit_dispatcher.dispatch(self, reqtype)

    async def _dispatch_to_problem_handler(self, pro_id: int):
        # Get problem to determine type
        allow_statuses = ProConst.PRO_STATUS_NORMAL_USER
        if self.contest:
            allow_statuses = ProConst.PRO_STATUS_CONTEST_USER
        elif self.acct.is_kernel():
            allow_statuses = ProConst.PRO_STATUS_KERNEL_USER

        err, pro = await ProService.inst.get_pro(pro_id, allow_statuses)
        if err:
            return self.error(err)

        # Dispatch to problem type-specific handler
        from services.pro import ProType

        if pro.problem_type == ProType.BATCH:
            from handlers.prospec.batch.submit import BatchSubmitHandler

            handler = BatchSubmitHandler(
                self.application, self.request, db=self.db, rs=self.rs
            )
            handler.acct = self.acct
            handler.contest = self.contest
            handler._transforms = []
            return await handler.post()
        elif pro.problem_type == ProType.COMMUNICATION:
            return self.error(
                ("Enotsupport", "Communication problem type not yet supported")
            )
        elif pro.problem_type == ProType.TWOSTEP:
            return self.error(("Enotsupport", "TwoStep problem type not yet supported"))
        elif pro.problem_type == ProType.OUTPUTONLY:
            return self.error(
                ("Enotsupport", "OutputOnly problem type not yet supported")
            )
        else:
            return self.error(("Eparam", "Invalid problem type"))

    @submit_dispatcher.action("submit")
    async def submit_problem(self):
        pro_id = int(self.get_argument("pro_id"))
        return await self._dispatch_to_problem_handler(pro_id)

    @submit_dispatcher.action("rechal")
    async def rejudge_challenge(self):
        chal_id = int(self.get_argument("chal_id"))
        err, chal = await ChalService.inst.get_chal(chal_id)
        if err:
            return self.error(err)
        pro_id = chal.pro_id
        return await self._dispatch_to_problem_handler(pro_id)
