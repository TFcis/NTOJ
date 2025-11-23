"""Unit tests for BatchProblemSpec.add_chal() method."""
import os
import shutil
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from services.pro import CheckerType, SummaryType, ProblemConfig, Limit, SubtaskConfig, Testdata
from services.prospec.batch import BatchProblemSpec, BatchConfig
from services.chal import Compiler


class TestBatchProblemSpecAddChal(unittest.IsolatedAsyncioTestCase):
    """Test BatchProblemSpec.add_chal() method."""

    def setUp(self):
        """Set up test fixtures."""
        self.spec = BatchProblemSpec()

        # Create temporary directory for code storage
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        os.makedirs('code', exist_ok=True)

        # Mock database connection
        self.fake_conn = AsyncMock()
        self.fake_conn.fetch = AsyncMock()
        self.fake_conn.execute = AsyncMock()
        self.fake_conn.executemany = AsyncMock()

        fake_acquire_cm = MagicMock()
        fake_acquire_cm.__aenter__ = AsyncMock(return_value=self.fake_conn)
        fake_acquire_cm.__aexit__ = AsyncMock(return_value=None)

        self.fake_db = MagicMock()
        self.fake_db.acquire = MagicMock(return_value=fake_acquire_cm)
        self.fake_rs = AsyncMock()

        # Create basic configuration
        self.batch_config = BatchConfig(
            chalmeta='',
            userprog_compile_args='',
            checker_type=CheckerType.DIFF,
            checker_compiler=None,
            checker_compile_args='',
            summary_type=SummaryType.GROUPMIN,
            summary_compiler=None,
            summary_compile_args='',
            has_grader=False,
            allow_compilers={Compiler.GPP},
        )

        self.problem_config = ProblemConfig(
            limits={
                'default': Limit(time=1000, memory=262144, output=65536),
            },
            subtask_configs={
                1: SubtaskConfig(
                    subtask_id=1,
                    testdatas=[
                        Testdata(testdata_id=1, inputfile='1.in', outputfile='1.out'),
                        Testdata(testdata_id=2, inputfile='2.in', outputfile='2.out'),
                    ],
                    dependency_subtasks=set(),
                    rate=100,
                ),
            },
            testdatas={
                1: Testdata(testdata_id=1, inputfile='1.in', outputfile='1.out'),
                2: Testdata(testdata_id=2, inputfile='2.in', outputfile='2.out'),
            },
            rate_precision=2,
            spec_config=self.batch_config,
        )

    def tearDown(self):
        """Clean up temporary directory."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_add_chal_success(self):
        """Test successful challenge creation."""
        # Mock database response
        self.fake_conn.fetch.return_value = [{'chal_id': 100}]

        code = '#include <iostream>\nint main() { return 0; }'

        err, chal_id = await self.spec.add_chal(
            db=self.fake_db,
            rs=self.fake_rs,
            pro_id=1,
            acct_id=42,
            contest_id=0,
            compiler_type=Compiler.GPP,
            code=code,
            config=self.problem_config,
        )

        # Should succeed
        self.assertIsNone(err)
        self.assertEqual(chal_id, 100)

        # Verify challenge was inserted
        insert_call = self.fake_conn.fetch.call_args[0]
        self.assertIn('INSERT INTO "challenge"', insert_call[0])
        self.assertEqual(insert_call[1], 1)  # pro_id
        self.assertEqual(insert_call[2], 42)  # acct_id
        self.assertEqual(insert_call[3], Compiler.GPP)  # compiler_type
        self.assertEqual(insert_call[4], 0)  # contest_id

    async def test_add_chal_creates_results(self):
        """Test that add_chal creates total, subtask, and testdata results."""
        self.fake_conn.fetch.return_value = [{'chal_id': 100}]

        code = 'print("Hello")'

        await self.spec.add_chal(
            db=self.fake_db,
            rs=self.fake_rs,
            pro_id=1,
            acct_id=42,
            contest_id=0,
            compiler_type=Compiler.PYTHON3,
            code=code,
            config=self.problem_config,
        )

        # Check total_result insert
        total_result_call = self.fake_conn.execute.call_args_list[0][0]
        self.assertIn('INSERT INTO total_result', total_result_call[0])
        self.assertEqual(total_result_call[1], 100)

        # Check subtask_result insert
        subtask_call = self.fake_conn.executemany.call_args_list[0]
        self.assertIn('INSERT INTO subtask_result', subtask_call[0][0])
        subtask_values = subtask_call[0][1]
        self.assertEqual(len(subtask_values), 1)  # One subtask
        self.assertEqual(subtask_values[0], (100, 1, 1))  # (chal_id, pro_id, subtask_id)

        # Check testdata_result insert
        testdata_call = self.fake_conn.executemany.call_args_list[1]
        self.assertIn('INSERT INTO testdata_result', testdata_call[0][0])
        testdata_values = testdata_call[0][1]
        self.assertEqual(len(testdata_values), 2)  # Two testdatas
        self.assertIn((100, 1, 1), testdata_values)
        self.assertIn((100, 1, 2), testdata_values)

    async def test_add_chal_creates_code_file(self):
        """Test that add_chal creates source code file with correct extension."""
        self.fake_conn.fetch.return_value = [{'chal_id': 100}]

        code = '#include <iostream>\nint main() { return 0; }'

        await self.spec.add_chal(
            db=self.fake_db,
            rs=self.fake_rs,
            pro_id=1,
            acct_id=42,
            contest_id=0,
            compiler_type=Compiler.GPP,
            code=code,
            config=self.problem_config,
        )

        # Verify code directory and file were created
        self.assertTrue(os.path.exists('code/100'))
        self.assertTrue(os.path.isfile('code/100/main.cpp'))

        # Verify file contents
        with open('code/100/main.cpp', 'r') as f:
            saved_code = f.read()
        self.assertEqual(saved_code, code)

    async def test_add_chal_different_compiler_extensions(self):
        """Test that different compilers use correct file extensions."""
        test_cases = [
            (Compiler.GCC, 'c'),
            (Compiler.GPP, 'cpp'),
            (Compiler.PYTHON3, 'py'),
            (Compiler.RUST, 'rs'),
            (Compiler.JAVA, 'java'),
        ]

        for idx, (compiler, expected_ext) in enumerate(test_cases):
            chal_id = 100 + idx
            self.fake_conn.fetch.return_value = [{'chal_id': chal_id}]

            code = f'// Test code for {compiler}'

            await self.spec.add_chal(
                db=self.fake_db,
                rs=self.fake_rs,
                pro_id=1,
                acct_id=42,
                contest_id=0,
                compiler_type=compiler,
                code=code,
                config=self.problem_config,
            )

            # Verify correct extension
            expected_path = f'code/{chal_id}/main.{expected_ext}'
            self.assertTrue(os.path.isfile(expected_path),
                          f'Expected file {expected_path} for compiler {compiler}')

    async def test_add_chal_with_multiple_subtasks(self):
        """Test add_chal with multiple subtasks."""
        self.fake_conn.fetch.return_value = [{'chal_id': 100}]

        # Add more subtasks
        self.problem_config.subtask_configs[2] = SubtaskConfig(
            subtask_id=2,
            testdatas=[
                Testdata(testdata_id=3, inputfile='3.in', outputfile='3.out'),
            ],
            dependency_subtasks={1},
            rate=0,
        )
        self.problem_config.testdatas[3] = Testdata(
            testdata_id=3, inputfile='3.in', outputfile='3.out'
        )

        code = 'int main() {}'

        await self.spec.add_chal(
            db=self.fake_db,
            rs=self.fake_rs,
            pro_id=1,
            acct_id=42,
            contest_id=0,
            compiler_type=Compiler.GPP,
            code=code,
            config=self.problem_config,
        )

        # Verify subtask inserts
        subtask_call = self.fake_conn.executemany.call_args_list[0]
        subtask_values = subtask_call[0][1]
        self.assertEqual(len(subtask_values), 2)  # Two subtasks

        # Verify testdata inserts
        testdata_call = self.fake_conn.executemany.call_args_list[1]
        testdata_values = testdata_call[0][1]
        self.assertEqual(len(testdata_values), 3)  # Three testdatas

    async def test_add_chal_database_error(self):
        """Test add_chal when database returns unexpected result."""
        # Return empty result (error case)
        self.fake_conn.fetch.return_value = []

        code = 'int main() {}'

        err, chal_id = await self.spec.add_chal(
            db=self.fake_db,
            rs=self.fake_rs,
            pro_id=1,
            acct_id=42,
            contest_id=0,
            compiler_type=Compiler.GPP,
            code=code,
            config=self.problem_config,
        )

        # Should return error
        self.assertIsNotNone(err)
        self.assertEqual(err, ('Eunk', 'Unknown error'))
        self.assertIsNone(chal_id)

    async def test_add_chal_unicode_code(self):
        """Test add_chal with Unicode characters in source code."""
        self.fake_conn.fetch.return_value = [{'chal_id': 100}]

        code = '// 測試中文註解\n#include <iostream>\nint main() { return 0; }'

        err, chal_id = await self.spec.add_chal(
            db=self.fake_db,
            rs=self.fake_rs,
            pro_id=1,
            acct_id=42,
            contest_id=0,
            compiler_type=Compiler.GPP,
            code=code,
            config=self.problem_config,
        )

        self.assertIsNone(err)

        # Verify Unicode was saved correctly
        with open('code/100/main.cpp', 'r', encoding='utf-8') as f:
            saved_code = f.read()
        self.assertEqual(saved_code, code)

    async def test_add_chal_in_contest(self):
        """Test add_chal for a contest submission."""
        self.fake_conn.fetch.return_value = [{'chal_id': 100}]

        code = 'int main() {}'

        err, chal_id = await self.spec.add_chal(
            db=self.fake_db,
            rs=self.fake_rs,
            pro_id=1,
            acct_id=42,
            contest_id=5,  # In contest
            compiler_type=Compiler.GPP,
            code=code,
            config=self.problem_config,
        )

        self.assertIsNone(err)

        # Verify contest_id was passed
        insert_call = self.fake_conn.fetch.call_args[0]
        self.assertEqual(insert_call[4], 5)  # contest_id


if __name__ == '__main__':
    unittest.main()
