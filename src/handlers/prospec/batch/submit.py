import time
import zlib

from handlers.base import ActionDispatcher, RequestHandler, reqenv, require_permission
from services.chal import ChalConst, ChalService, Compiler
from services.judge import JudgeServerClusterService
from services.pro import ProService, ProConst, ProType
from services.user import UserService, UserConst
from services.contests import UserStatus


submit_dispatcher = ActionDispatcher()


class BatchSubmitHandler(RequestHandler):
    @reqenv
    async def get(self):
        try:
            pro_id = int(self.get_argument("pro_id"))
            contest_id = int(self.get_argument("contest_id", default=0))

            allow_statuses = ProConst.PRO_STATUS_NORMAL_USER
            if contest_id != 0:
                allow_statuses = ProConst.PRO_STATUS_CONTEST_USER
            elif self.acct.is_kernel():
                allow_statuses = ProConst.PRO_STATUS_KERNEL_USER

            err, pro = await ProService.inst.get_pro(pro_id, allow_statuses)
            if err:
                return self.error(err)

            assert pro is not None
            assert pro.config is not None

            if pro.problem_type != ProType.BATCH:
                return self.error(("Eparam", "Invalid problem type for this handler"))

            from services.prospec.batch import BatchConfig

            assert isinstance(pro.config.spec_config, BatchConfig)
            batch_config = pro.config.spec_config

            allow_compilers = batch_config.allow_compilers

            # If in contest, filter by contest's allowed compilers
            if contest_id != 0:
                from services.contests import ContestService

                err, contest = await ContestService.inst.get_contest(contest_id)
                if not err and contest is not None:
                    allow_compilers = allow_compilers.intersection(
                        contest.allow_compilers
                    )

            await self.render(
                "prospec/batch/submit",
                pro=pro,
                allow_compilers=allow_compilers,
                contest_id=contest_id,
            )

        except Exception as e:
            import traceback

            traceback.print_exc()
            return self.error(("Eunk", f"Unknown error: {str(e)}"))

    @reqenv
    @require_permission([UserConst.ACCTTYPE_USER, UserConst.ACCTTYPE_KERNEL])
    async def post(self):
        can_submit = JudgeServerClusterService.inst.is_server_online()
        if not can_submit:
            return self.error(("Ejudge", "No available judge"))

        reqtype = self.get_argument("reqtype")
        return await submit_dispatcher.dispatch(self, reqtype)

    @submit_dispatcher.action("submit")
    async def submit_code(self):
        allow_statuses = ProConst.PRO_STATUS_NORMAL_USER
        contest_id = 0

        if self.contest:
            contest_id = self.contest.contest_id
            allow_statuses = ProConst.PRO_STATUS_CONTEST_USER

        pro_id = int(self.get_argument("pro_id"))
        code = self.get_argument("code")
        try:
            compiler_type = Compiler(int(self.get_argument("compiler_type")))
        except ValueError:
            return self.error(("Ecomp", "The compiler is not allowed"))

        if hasattr(self, "contest") and self.contest:
            priority = ChalConst.CONTEST_PRI
            if not self.contest.is_running() and not self.contest.is_admin(self.acct):
                return self.error(("Eacces", "Permission denied"))

            if not self.contest.is_pro(pro_id):
                return self.error(("Enoext", "Problem not in contest"))
        else:
            priority = ChalConst.NORMAL_PRI
            if self.acct.is_kernel():
                allow_statuses = ProConst.PRO_STATUS_KERNEL_USER

        err, pro = await ProService.inst.get_pro(pro_id, allow_statuses)
        if err:
            return self.error(err)

        if err := await self._is_allow_submit(code, compiler_type, pro):
            return self.error(err)

        if not pro.allow_submit:
            return self.error(("Eacces", "Problem did not allow submit"))

        err, chal_id = await ChalService.inst.add_chal(
            pro_id, self.acct.acct_id, contest_id, compiler_type, code, pro.problem_type
        )
        if err:
            return self.error(err)

        if self.acct.last_compiler != compiler_type:
            self.acct.last_compiler = compiler_type
            err, _ = await UserService.inst.update_acct(self.acct)
            if err:
                return self.error(err)

        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        # Only filter system-test if in contest AND contest has system test enabled
        # Contest Admin always runs full test (include system-test)
        include_system_test = True
        if self.contest and self.contest.enable_system_test:
            # Check if user is contest admin
            is_admin = self.contest.is_admin(self.acct)
            if not is_admin:
                include_system_test = False  # Regular users only run pretest during contest

        err, _ = await ChalService.inst.emit_chal(
            chal_id,
            pro.config,
            compiler_type,
            priority,
            pro.problem_type,
            skip_nonac=False,
            include_system_test=include_system_test,
        )
        if err:
            return self.error(err)

        if pro.status == ProConst.STATUS_ONLINE:
            await self.rs.publish("challist_sub", str(1))

        self.error(("S", chal_id))

    @submit_dispatcher.action("rechal")
    async def rechal_submission(self):
        allow_statuses = ProConst.PRO_STATUS_NORMAL_USER

        if self.contest:
            allow_statuses = ProConst.PRO_STATUS_CONTEST_USER

        chal_id = int(self.get_argument("chal_id"))
        if (
            (self.contest is None and self.acct.is_kernel())  # not in contest
            or (self.contest and self.contest.is_admin(self.acct))
        ):  # in contest
            if self.contest:
                priority = ChalConst.CONTEST_REJUDGE_PRI
            else:
                priority = ChalConst.NORMAL_REJUDGE_PRI
                allow_statuses = ProConst.PRO_STATUS_KERNEL_USER

            err, _ = await ChalService.inst.reset_chal(chal_id)
            err, chal = await ChalService.inst.get_chal(chal_id)

            pro_id = chal.pro_id
            compiler_type = chal.compiler_type
            err, pro = await ProService.inst.get_pro(pro_id, allow_statuses)
            if err:
                return self.error(err)
        else:
            return self.error(("Eunk", "Unknown error"))

        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        # Only filter system-test if in contest AND contest has system test enabled
        # Contest Admin always runs full test (include system-test)
        include_system_test = True
        if self.contest and self.contest.enable_system_test:
            # Check if user is contest admin
            is_admin = self.contest.is_admin(acct_id=chal.acct_id)
            if not is_admin:
                include_system_test = False  # Regular users only run pretest during contest

        err, _ = await ChalService.inst.emit_chal(
            chal_id,
            pro.config,
            compiler_type,
            priority,
            pro.problem_type,
            skip_nonac=False,
            include_system_test=include_system_test,
        )
        if err:
            return self.error(err)

        self.error(("S", chal_id))

    async def _is_allow_submit(self, code: str, compiler_type: Compiler, pro):
        # TODO: extract this to util?
        pro_id = pro.pro_id

        from services.prospec.batch import BatchConfig

        assert isinstance(pro.config.spec_config, BatchConfig)
        allow_compilers = pro.config.spec_config.allow_compilers

        submit_cd_time = 30
        contest = self.contest
        if contest:
            allow_compilers = allow_compilers.intersection(contest.allow_compilers)
            submit_cd_time = contest.submission_cd_time

        if len(code.strip()) == 0:
            return ("Eempty", "Submitted code should not be empty")

        if len(code) > ProConst.CODE_MAX:
            return ("Ecodemax", "Submitted code too long")

        if compiler_type not in allow_compilers:
            return ("Ecomp", "The compiler is not allowed")

        should_check_submit_cd = (
            contest is None
            and not self.acct.is_kernel()  # not in contest
            or contest
            and contest.member_is_status(self.acct, UserStatus.APPROVED)
        )

        name = ""
        crc32 = ""
        if contest:
            name = f"contest_{contest.contest_id}_acct_{self.acct.acct_id}_pro_{pro_id}_compiler_{compiler_type}"
            crc32 = str(zlib.crc32(code.encode("utf-8")))

            if await self.rs.sismember(name, crc32):
                return ("Esame", "Do not submit same code")

        if should_check_submit_cd:
            last_submit_name = f"last_submit_time_{self.acct.acct_id}"
            if (last_submit_time := (await self.rs.get(last_submit_name))) is None:
                if submit_cd_time:
                    await self.rs.set(
                        last_submit_name, int(time.time()), ex=submit_cd_time
                    )

            else:
                last_submit_time = int(str(last_submit_time)[2:-1])
                elapsed_time = int(time.time()) - last_submit_time
                if elapsed_time < submit_cd_time:
                    remaining_time = submit_cd_time - elapsed_time
                    remaining_time = max(remaining_time, 0)
                    return (
                        "Einternal",
                        f"Submit CD Time: {submit_cd_time} Secs, Remaining: {remaining_time} Secs",
                    )
                else:
                    await self.rs.set(last_submit_name, int(time.time()))

        if contest:
            await self.rs.sadd(name, crc32)
            await self.rs.expire(
                name, time=(contest.contest_end - contest.contest_start)
            )

        return None
