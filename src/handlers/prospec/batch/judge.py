"""
Batch problem type judge configuration handler.
Handles Batch-specific judge settings like checker, grader, summary, etc.
"""
import json
import os

from handlers.base import RequestHandler, reqenv, require_permission
from services.chal import Compiler, COMPILER_INFOS
from services.log import LogService
from services.pro import ProService, ProConst, CheckerType, SummaryType, ProType
from services.user import UserConst


class BatchJudgeHandler(RequestHandler):
    """Handler for Batch problem type judge configuration."""

    @reqenv
    @require_permission([UserConst.ACCTTYPE_KERNEL])
    async def post(self):
        """Update Batch problem judge configuration."""
        from services.prospec.batch import BatchConfig

        ALLOW_STATUSES = ProConst.PRO_STATUS_FULL

        try:
            pro_id = int(self.get_argument('pro_id'))
            rate_precision = int(self.get_argument('rate_precision'))

            if rate_precision > ProConst.RATE_PRECISION_MAX or rate_precision < ProConst.RATE_PRECISION_MIN:
                return self.error(('Eparam', 'Invalid rate precision'))

            has_grader = self.get_argument('has_grader') == "true"
            userprog_compile_args = self.get_argument('userprog_compile_args')
            checker_type = int(self.get_argument('checker_type'))
            checker_compiler = self.get_argument('checker_compiler')
            if checker_compiler:
                checker_compiler = Compiler(int(checker_compiler))
            else:
                checker_compiler = None
            checker_compile_args = self.get_argument('checker_compile_args')

            summary_type = SummaryType(int(self.get_argument('summary_type')))
            summary_compiler = self.get_argument('summary_compiler')
            if summary_compiler:
                summary_compiler = Compiler(int(summary_compiler))
            else:
                summary_compiler = None
            summary_compile_args = self.get_argument('summary_compile_args')

            allow_compilers = self.get_arguments("allow_compilers[]")
            allow_compilers = set(map(
                lambda x: Compiler(int(x)),
                filter(lambda compiler: int(compiler) in Compiler._value2member_map_, allow_compilers)
            ))

            chalmeta = ''
            if checker_type == CheckerType.IOREDIR:
                chalmeta = self.get_argument('chalmeta')
                try:
                    json.loads(chalmeta)
                except json.JSONDecodeError:
                    return self.error(('Econf', 'Challenge metadata json syntax error'))

            err, pro = await ProService.inst.get_pro(pro_id, ALLOW_STATUSES)
            if err:
                return self.error(err)
            assert pro

            # Ensure this is a Batch problem
            if pro.problem_type != ProType.BATCH:
                return self.error(('Eparam', 'This handler only supports Batch problems'))

            config = pro.config
            assert config
            assert isinstance(config.spec_config, BatchConfig)
            batch_config = config.spec_config

            # Setup grader directories if needed
            if has_grader:
                grader_path = os.path.join("problem", str(pro_id), "res", "grader")
                if not os.path.exists(grader_path):
                    os.mkdir(grader_path)

                used_grader = set()
                for compiler in allow_compilers:
                    grader_name = COMPILER_INFOS[compiler].grader_name
                    if grader_name in used_grader:
                        continue
                    grader_compiler_path = os.path.join(grader_path, grader_name)
                    if not os.path.exists(grader_compiler_path):
                        os.mkdir(grader_compiler_path)
                    used_grader.add(grader_name)

            batch_config.has_grader = has_grader
            batch_config.userprog_compile_args = userprog_compile_args

            # Setup checker directories if needed
            need_build_checkers = CheckerType.need_build_checkers()
            if checker_type in need_build_checkers:
                if not os.path.exists(f'problem/{pro_id}/res/checker'):
                    os.mkdir(f'problem/{pro_id}/res/checker')

            batch_config.checker_type = CheckerType(checker_type)
            batch_config.checker_compiler = checker_compiler
            batch_config.checker_compile_args = checker_compile_args

            # Setup summary directories if needed
            if summary_type == SummaryType.CUSTOM:
                if not os.path.exists(f'problem/{pro_id}/res/summary'):
                    os.mkdir(f'problem/{pro_id}/res/summary')

            batch_config.summary_type = summary_type
            batch_config.summary_compiler = summary_compiler
            batch_config.summary_compile_args = summary_compile_args
            batch_config.allow_compilers = {int(c) for c in allow_compilers}
            batch_config.chalmeta = chalmeta

            config.rate_precision = rate_precision

            await ProService.inst.update_pro_config(pro_id, ProType(pro.problem_type), config)
            await LogService.inst.add_log(
                f"{self.acct.name} has updated Batch problem #{pro_id} judge config",
                'manage.pro.update.judge.batch',
                {
                    'pro_id': pro_id,
                    'has_grader': has_grader,
                    'checker_type': checker_type,
                    'summary_type': summary_type,
                }
            )

            self.error(('S', ''))

        except Exception as e:
            import traceback
            traceback.print_exc()
            return self.error(('Eunk', f'Unknown error: {str(e)}'))
