import json
import time
import zlib

from handlers.base import ActionDispatcher, RequestHandler, reqenv, require_permission
from services.chal import ChalConst, ChalService, Compiler
from services.judge import JudgeServerClusterService
from services.pro import ProService, ProConst, ProType
from services.user import UserService, UserConst
from services.contests import UserStatus


submit_dispatcher = ActionDispatcher()


class ProblemSubmitHandler(RequestHandler):
    def parse_submission(self):
        return self.get_argument("code")

    def prepare_submission(self, code, compiler_type: Compiler, pro):
        return code

    @reqenv
    async def get(self):
        try:
            try:
                pro_id = int(self.get_argument("pro_id"))
            except ValueError:
                return self.error(("Eparam", "Invalid problem ID"))

            try:
                contest_id = int(self.get_argument("contest_id", default="0"))
            except ValueError:
                return self.error(("Eparam", "Invalid contest ID"))

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

            if pro.problem_type != self.problem_type:
                return self.error(("Eparam", "Invalid problem type for this handler"))

            assert isinstance(pro.config.spec_config, self.config_type)
            spec_config = pro.config.spec_config

            allow_compilers = spec_config.allow_compilers

            # If in contest, filter by contest's allowed compilers
            if contest_id != 0:
                from services.contests import ContestService

                err, contest = await ContestService.inst.get_contest(contest_id)
                if not err and contest is not None:
                    allow_compilers = allow_compilers.intersection(
                        contest.allow_compilers
                    )

            await self.render(
                self.template,
                f"Submit - {pro.name}",
                pro=pro,
                allow_compilers=allow_compilers,
                contest_id=contest_id,
                problem_name=self.problem_name,
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

        try:
            pro_id = int(self.get_argument("pro_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem ID"))

        try:
            code = self.parse_submission()
        except (ValueError, TypeError):
            return self.error(("Eparam", "Invalid submitted source files"))
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

        try:
            code = self.prepare_submission(code, compiler_type, pro)
        except (ValueError, TypeError):
            return self.error(("Eparam", "Invalid submitted source files"))

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

        await self.add_log(
            f"Submit solution to problem #{pro_id} (challenge #{chal_id})",
            "contest.submit" if contest_id != 0 else "pro.submit",
            {
                "pro_id": pro_id,
                "chal_id": chal_id,
                "compiler_type": compiler_type.value,
                "contest_id": contest_id,
            },
        )

        await self.rs.hdel('rate', str(self.acct.acct_id))

        self.error(("S", chal_id))

    @submit_dispatcher.action("rechal")
    async def rechal_submission(self):
        allow_statuses = ProConst.PRO_STATUS_NORMAL_USER

        if self.contest:
            allow_statuses = ProConst.PRO_STATUS_CONTEST_USER

        try:
            chal_id = int(self.get_argument('chal_id'))
        except ValueError:
            return self.error(("Eparam", "Invalid challenge id"))

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

        await self.add_log(
            f"Rejudge challenge #{chal_id} for problem #{pro_id}",
            "contest.rechal" if self.contest else "pro.rechal",
            {
                "chal_id": chal_id,
                "pro_id": pro_id,
                "contest_id": self.contest.contest_id if self.contest else 0,
            },
        )

        await self.rs.hdel('rate', str(chal.acct_id))

        self.error(("S", chal_id))

    async def _is_allow_submit(self, code: str | dict[str, str], compiler_type: Compiler, pro):
        # TODO: extract this to util?
        pro_id = pro.pro_id

        assert isinstance(pro.config.spec_config, self.config_type)
        allow_compilers = pro.config.spec_config.allow_compilers

        submit_cd_time = 30
        contest = self.contest
        if contest:
            allow_compilers = allow_compilers.intersection(contest.allow_compilers)
            submit_cd_time = contest.submission_cd_time

        if isinstance(code, str):
            code_parts = [code]
        elif isinstance(code, dict) and code and all(
            isinstance(filename, str) and isinstance(content, str)
            for filename, content in code.items()
        ):
            code_parts = list(code.values())
        else:
            return ("Eparam", "Invalid submitted source files")

        if any(len(content.strip()) == 0 for content in code_parts):
            return ("Eempty", "Submitted code should not be empty")

        if any(len(content) > ProConst.CODE_MAX for content in code_parts):
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
            serialized_code = (
                code
                if isinstance(code, str)
                else json.dumps(code, sort_keys=True, separators=(",", ":"))
            )
            crc32 = str(zlib.crc32(serialized_code.encode("utf-8")))

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
