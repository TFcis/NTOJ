"""Unit tests for BatchProblemSpec.emit_chal() method."""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from services.pro import CheckerType, SummaryType, ProblemConfig, Limit, SubtaskConfig
from services.prospec.batch import BatchProblemSpec, BatchConfig, BatchTestdata
from services.chal import Compiler, ChalConst


class TestBatchProblemSpecEmitChal(unittest.IsolatedAsyncioTestCase):
    """Test BatchProblemSpec.emit_chal() method."""

    def setUp(self):
        """Set up test fixtures."""
        self.spec = BatchProblemSpec()
        self.fake_db = AsyncMock()
        self.fake_rs = AsyncMock()

        # Create a basic BatchConfig
        self.batch_config = BatchConfig(
            chalmeta='',
            userprog_compile_args='-std=c++17',
            checker_type=CheckerType.DIFF,
            checker_compiler=None,
            checker_compile_args='',
            summary_type=SummaryType.GROUPMIN,
            summary_compiler=None,
            summary_compile_args='',
            has_grader=False,
            allow_compilers={Compiler.GPP},
        )

        # Create a ProblemConfig with subtasks and testdatas
        self.problem_config = ProblemConfig(
            limits={
                'default': Limit(time=1000, memory=262144, output=65536),
                str(int(Compiler.GPP)): Limit(time=2000, memory=524288, output=65536),
            },
            subtask_configs={
                1: SubtaskConfig(
                    subtask_id=1,
                    testdatas=[
                        BatchTestdata(testdata_id=1, inputfile='1.in', outputfile='1.out'),
                        BatchTestdata(testdata_id=2, inputfile='2.in', outputfile='2.out'),
                    ],
                    dependency_subtasks=set(),
                    rate=50,
                ),
                2: SubtaskConfig(
                    subtask_id=2,
                    testdatas=[
                        BatchTestdata(testdata_id=3, inputfile='3.in', outputfile='3.out'),
                    ],
                    dependency_subtasks={1},
                    rate=50,
                ),
            },
            testdatas={
                1: BatchTestdata(testdata_id=1, inputfile='1.in', outputfile='1.out'),
                2: BatchTestdata(testdata_id=2, inputfile='2.in', outputfile='2.out'),
                3: BatchTestdata(testdata_id=3, inputfile='3.in', outputfile='3.out'),
            },
            rate_precision=2,
            spec_config=self.batch_config,
        )

    @patch('services.judge.JudgeServerClusterService')
    @patch('os.path.isfile')
    async def test_emit_chal_success(self, mock_isfile, mock_judge_service):
        """Test successful challenge emission."""
        mock_isfile.return_value = True
        mock_judge_instance = MagicMock()
        mock_judge_instance.send = AsyncMock()
        mock_judge_service.inst = mock_judge_instance

        err, result = await self.spec.emit_chal(
            db=self.fake_db,
            rs=self.fake_rs,
            chal_id=100,
            pro_id=1,
            acct_id=42,
            contest_id=0,
            compiler_type=Compiler.GPP,
            config=self.problem_config,
            priority=ChalConst.NORMAL_PRI,
            skip_nonac=False,
        )

        # Should succeed
        self.assertIsNone(err)
        self.assertIsNone(result)

        # Verify database updates
        self.assertEqual(self.fake_db.execute.call_count, 3)

        # Check total_result update
        call_args = self.fake_db.execute.call_args_list[0]
        self.assertIn('UPDATE total_result SET state', call_args[0][0])
        self.assertEqual(call_args[0][1], ChalConst.STATE_JUDGE)
        self.assertEqual(call_args[0][2], 100)

        # Check subtask_result update
        call_args = self.fake_db.execute.call_args_list[1]
        self.assertIn('UPDATE subtask_result SET state', call_args[0][0])

        # Check testdata_result update
        call_args = self.fake_db.execute.call_args_list[2]
        self.assertIn('UPDATE testdata_result SET state', call_args[0][0])

        # Verify judge server was called
        mock_judge_instance.send.assert_awaited_once()
        send_args = mock_judge_instance.send.call_args[0][0]

        self.assertEqual(send_args['chal_id'], 100)
        self.assertEqual(send_args['pro_id'], 1)
        self.assertEqual(send_args['acct_id'], 42)
        self.assertEqual(send_args['contest_id'], 0)
        self.assertEqual(send_args['priority'], ChalConst.NORMAL_PRI)
        self.assertFalse(send_args['skip_nonac'])
        self.assertFalse(send_args['has_grader'])
        self.assertEqual(send_args['userprog_compiler'], Compiler.GPP)
        self.assertEqual(send_args['userprog_compile_args'], '-std=c++17')
        self.assertEqual(send_args['checker_type'], CheckerType.DIFF)

    @patch('services.judge.JudgeServerClusterService')
    @patch('os.path.isfile')
    async def test_emit_chal_with_subtask_dependencies(self, mock_isfile, mock_judge_service):
        """Test challenge emission with subtask dependencies."""
        mock_isfile.return_value = True
        mock_judge_instance = MagicMock()
        mock_judge_instance.send = AsyncMock()
        mock_judge_service.inst = mock_judge_instance

        await self.spec.emit_chal(
            db=self.fake_db,
            rs=self.fake_rs,
            chal_id=100,
            pro_id=1,
            acct_id=42,
            contest_id=0,
            compiler_type=Compiler.GPP,
            config=self.problem_config,
            priority=ChalConst.NORMAL_PRI,
        )

        send_args = mock_judge_instance.send.call_args[0][0]
        subtasks = send_args['subtasks']

        # Verify subtask structure
        self.assertEqual(len(subtasks), 2)

        # First subtask has no dependencies
        subtask1 = next(s for s in subtasks if s['id'] == 1)
        self.assertEqual(subtask1['score'], 50)
        self.assertEqual(subtask1['testdatas'], [1, 2])
        self.assertEqual(subtask1['dependency_subtasks'], [])

        # Second subtask depends on first
        subtask2 = next(s for s in subtasks if s['id'] == 2)
        self.assertEqual(subtask2['score'], 50)
        self.assertEqual(subtask2['testdatas'], [3])
        self.assertEqual(subtask2['dependency_subtasks'], [1])

    @patch('services.judge.JudgeServerClusterService')
    @patch('os.path.isfile')
    async def test_emit_chal_uses_compiler_specific_limit(self, mock_isfile, mock_judge_service):
        """Test that emit_chal uses compiler-specific limits when available."""
        mock_isfile.return_value = True
        mock_judge_instance = MagicMock()
        mock_judge_instance.send = AsyncMock()
        mock_judge_service.inst = mock_judge_instance

        await self.spec.emit_chal(
            db=self.fake_db,
            rs=self.fake_rs,
            chal_id=100,
            pro_id=1,
            acct_id=42,
            contest_id=0,
            compiler_type=Compiler.GPP,  # Has specific limit
            config=self.problem_config,
            priority=ChalConst.NORMAL_PRI,
        )

        send_args = mock_judge_instance.send.call_args[0][0]
        limit = send_args['limit']

        # Should use GPP-specific limit (2000ms, 524288kib)
        self.assertEqual(limit['time'], 2000 * 10**6)  # Convert to nanoseconds
        self.assertEqual(limit['memory'], 524288 * 1024)  # Convert to bytes
        self.assertEqual(limit['output'], 65536 * 1024)  # Convert to bytes

    @patch('services.judge.JudgeServerClusterService')
    @patch('os.path.isfile')
    async def test_emit_chal_uses_default_limit(self, mock_isfile, mock_judge_service):
        """Test that emit_chal falls back to default limit."""
        mock_isfile.return_value = True
        mock_judge_instance = MagicMock()
        mock_judge_instance.send = AsyncMock()
        mock_judge_service.inst = mock_judge_instance

        await self.spec.emit_chal(
            db=self.fake_db,
            rs=self.fake_rs,
            chal_id=100,
            pro_id=1,
            acct_id=42,
            contest_id=0,
            compiler_type=Compiler.PYTHON3,  # No specific limit
            config=self.problem_config,
            priority=ChalConst.NORMAL_PRI,
        )

        send_args = mock_judge_instance.send.call_args[0][0]
        limit = send_args['limit']

        # Should use default limit (1000ms, 262144kib)
        self.assertEqual(limit['time'], 1000 * 10**6)
        self.assertEqual(limit['memory'], 262144 * 1024)

    @patch('services.chal.ChalService')
    @patch('os.path.isfile')
    async def test_emit_chal_missing_source_file(self, mock_isfile, mock_chal_service):
        """Test emit_chal when source file doesn't exist."""
        mock_isfile.return_value = False
        mock_chal_instance = MagicMock()
        mock_chal_instance.update_total_result = AsyncMock()
        mock_chal_instance.update_subtask_result = AsyncMock()
        mock_chal_instance.update_testdata_result = AsyncMock()
        mock_chal_service.inst = mock_chal_instance

        err, result = await self.spec.emit_chal(
            db=self.fake_db,
            rs=self.fake_rs,
            chal_id=100,
            pro_id=1,
            acct_id=42,
            contest_id=0,
            compiler_type=Compiler.GPP,
            config=self.problem_config,
            priority=ChalConst.NORMAL_PRI,
        )

        # Should still succeed but mark as error
        self.assertIsNone(err)

        # Verify error results were set
        mock_chal_instance.update_total_result.assert_awaited_once()
        total_result = mock_chal_instance.update_total_result.call_args[0][1]
        self.assertEqual(total_result.state, ChalConst.STATE_ERR)

        # Should update all subtasks
        self.assertEqual(mock_chal_instance.update_subtask_result.call_count, 2)

        # Should update all testdatas
        self.assertEqual(mock_chal_instance.update_testdata_result.call_count, 3)

    @patch('services.judge.JudgeServerClusterService')
    @patch('os.path.isfile')
    async def test_emit_chal_with_custom_checker(self, mock_isfile, mock_judge_service):
        """Test emit_chal with custom checker configuration."""
        mock_isfile.return_value = True
        mock_judge_instance = MagicMock()
        mock_judge_instance.send = AsyncMock()
        mock_judge_service.inst = mock_judge_instance

        # Update config with custom checker
        self.batch_config.checker_type = CheckerType.TOJ
        self.batch_config.checker_compiler = Compiler.GPP
        self.batch_config.checker_compile_args = '-O2 -std=c++17'

        await self.spec.emit_chal(
            db=self.fake_db,
            rs=self.fake_rs,
            chal_id=100,
            pro_id=1,
            acct_id=42,
            contest_id=0,
            compiler_type=Compiler.GPP,
            config=self.problem_config,
            priority=ChalConst.NORMAL_PRI,
        )

        send_args = mock_judge_instance.send.call_args[0][0]

        self.assertEqual(send_args['checker_type'], CheckerType.TOJ)
        self.assertEqual(send_args['checker_compiler'], Compiler.GPP)
        self.assertEqual(send_args['checker_compile_args'], '-O2 -std=c++17')

    @patch('services.judge.JudgeServerClusterService')
    @patch('os.path.isfile')
    async def test_emit_chal_with_skip_nonac(self, mock_isfile, mock_judge_service):
        """Test emit_chal with skip_nonac enabled."""
        mock_isfile.return_value = True
        mock_judge_instance = MagicMock()
        mock_judge_instance.send = AsyncMock()
        mock_judge_service.inst = mock_judge_instance

        await self.spec.emit_chal(
            db=self.fake_db,
            rs=self.fake_rs,
            chal_id=100,
            pro_id=1,
            acct_id=42,
            contest_id=0,
            compiler_type=Compiler.GPP,
            config=self.problem_config,
            priority=ChalConst.NORMAL_PRI,
            skip_nonac=True,
        )

        send_args = mock_judge_instance.send.call_args[0][0]
        self.assertTrue(send_args['skip_nonac'])


if __name__ == '__main__':
    unittest.main()
