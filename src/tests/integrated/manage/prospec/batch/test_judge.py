"""Integration tests for Batch problem judge configuration."""
import json

from tests.integrated.util import AsyncTest, AccountContext
from services.pro import ProService, ProConst, CheckerType, SummaryType
from services.chal import Compiler


class BatchJudgeTest(AsyncTest):
    """Test Batch problem judge configuration (checker, grader, summary)."""

    async def main(self):
        with AccountContext("admin@test", "testtest") as admin_session:
            # Test updatejudge - basic configuration
            res = admin_session.post('manage/pro/updatejudge', data={
                'pro_id': 1,
                'rate_precision': 2,
                'has_grader': 'false',
                'userprog_compile_args': '',
                'checker_type': CheckerType.DIFF,
                'checker_compiler': '',
                'checker_compile_args': '',
                'summary_type': SummaryType.GROUPMIN,
                'summary_compiler': '',
                'summary_compile_args': '',
                'allow_compilers[]': [Compiler.GCC, Compiler.GPP, Compiler.PYTHON3],
            })
            self.assertAPIReturnSuccess(res.text)

            err, pro = await ProService.inst.get_pro(1, ProConst.PRO_STATUS_FULL)
            self.assertIsNone(err)
            assert pro
            assert pro.config
            from services.prospec.batch import BatchConfig
            assert isinstance(pro.config.spec_config, BatchConfig)

            batch_config = pro.config.spec_config
            self.assertFalse(batch_config.has_grader)
            self.assertEqual(batch_config.checker_type, CheckerType.DIFF)
            self.assertEqual(batch_config.summary_type, SummaryType.GROUPMIN)
            self.assertEqual(batch_config.allow_compilers, {Compiler.GCC, Compiler.GPP, Compiler.PYTHON3})
            self.assertEqual(pro.config.rate_precision, 2)

            # Test updatejudge - with grader
            res = admin_session.post('manage/pro/updatejudge', data={
                'pro_id': 1,
                'rate_precision': 2,
                'has_grader': 'true',
                'userprog_compile_args': '-std=c++17 -O2',
                'checker_type': CheckerType.DIFF,
                'checker_compiler': '',
                'checker_compile_args': '',
                'summary_type': SummaryType.GROUPMIN,
                'summary_compiler': '',
                'summary_compile_args': '',
                'allow_compilers[]': [Compiler.GPP],
            })
            self.assertAPIReturnSuccess(res.text)

            err, pro = await ProService.inst.get_pro(1, ProConst.PRO_STATUS_FULL)
            self.assertIsNone(err)
            assert pro
            batch_config = pro.config.spec_config
            self.assertTrue(batch_config.has_grader)
            self.assertEqual(batch_config.userprog_compile_args, '-std=c++17 -O2')

            # Test updatejudge - with custom summary
            res = admin_session.post('manage/pro/updatejudge', data={
                'pro_id': 1,
                'rate_precision': 2,
                'has_grader': 'false',
                'userprog_compile_args': '',
                'checker_type': CheckerType.DIFF,
                'checker_compiler': '',
                'checker_compile_args': '',
                'summary_type': SummaryType.CUSTOM,
                'summary_compiler': Compiler.PYTHON3,
                'summary_compile_args': '',
                'allow_compilers[]': [Compiler.PYTHON3],
            })
            self.assertAPIReturnSuccess(res.text)

            err, pro = await ProService.inst.get_pro(1, ProConst.PRO_STATUS_FULL)
            self.assertIsNone(err)
            assert pro
            batch_config = pro.config.spec_config
            self.assertEqual(batch_config.summary_type, SummaryType.CUSTOM)
            self.assertEqual(batch_config.summary_compiler, Compiler.PYTHON3)

            # Test updatejudge - invalid rate precision
            res = admin_session.post('manage/pro/updatejudge', data={
                'pro_id': 1,
                'rate_precision': 10,  # Invalid: too high
                'has_grader': 'false',
                'userprog_compile_args': '',
                'checker_type': CheckerType.DIFF,
                'checker_compiler': '',
                'checker_compile_args': '',
                'summary_type': SummaryType.GROUPMIN,
                'summary_compiler': '',
                'summary_compile_args': '',
                'allow_compilers[]': [Compiler.GPP],
            })
            self.assertAPIReturnValue(res.text, ('Eparam', 'Invalid rate precision'))

            # Reset to default configuration
            res = admin_session.post('manage/pro/updatejudge', data={
                'pro_id': 1,
                'rate_precision': 2,
                'has_grader': 'false',
                'userprog_compile_args': '',
                'checker_type': CheckerType.DIFF,
                'checker_compiler': '',
                'checker_compile_args': '',
                'summary_type': SummaryType.GROUPMIN,
                'summary_compiler': '',
                'summary_compile_args': '',
                'allow_compilers[]': [Compiler.GCC, Compiler.GPP, Compiler.PYTHON3],
            })
            self.assertAPIReturnSuccess(res.text)
