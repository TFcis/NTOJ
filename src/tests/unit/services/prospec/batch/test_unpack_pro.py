"""Unit tests for BatchProblemSpec.unpack_pro method."""
import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from services.pro import ProType, Limit, SubtaskConfig, ProblemConfig, CheckerType, SummaryType
from services.prospec.batch import BatchProblemSpec, BatchConfig, BatchTestdata
from services.chal import Compiler


class TestBatchUnpackPro(unittest.IsolatedAsyncioTestCase):
    """Test BatchProblemSpec.unpack_pro method."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.spec = BatchProblemSpec()
        self.pro_id = 1

    def tearDown(self):
        """Clean up test directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _create_test_package(self, pro_id: int, config_data: dict):
        """Helper to create a test problem package."""
        pro_dir = os.path.join(self.test_dir, f'problem/{pro_id}')
        os.makedirs(pro_dir, exist_ok=True)

        # Write config file
        with open(os.path.join(pro_dir, 'conf.json'), 'w') as f:
            json.dump(config_data, f)

        # Create res/testdata directory
        testdata_dir = os.path.join(pro_dir, 'res', 'testdata')
        os.makedirs(testdata_dir, exist_ok=True)

        return pro_dir

    @patch('services.pro.ProService')
    @patch('services.pack.PackService')
    async def test_unpack_basic_problem(self, mock_pack_service, mock_pro_service):
        """Test unpacking a basic problem package."""
        config_data = {
            'timelimit': 1000,
            'memlimit': 262144,
            'metadata': '',
            'check': 'diff',
            'test': [
                {'data': ['1', '2'], 'weight': 100}
            ]
        }

        pro_dir = self._create_test_package(self.pro_id, config_data)

        # Mock PackService
        mock_pack_service.inst = MagicMock()
        mock_pack_service.inst.unpack = AsyncMock(return_value=(None, None))
        mock_pack_service.inst.clear = AsyncMock()

        # Mock ProService
        mock_pro_service.inst = MagicMock()
        mock_pro_service.inst.update_pro_config = AsyncMock()

        # Mock database and redis
        mock_db = MagicMock()
        mock_rs = MagicMock()
        mock_rs.delete = AsyncMock()

        # Change to test directory for the test
        original_cwd = os.getcwd()
        os.chdir(self.test_dir)

        try:
            err, _ = await self.spec.unpack_pro(mock_db, mock_rs, self.pro_id, 'test_token')

            self.assertIsNone(err)
            mock_pack_service.inst.unpack.assert_called_once()
            mock_pro_service.inst.update_pro_config.assert_called_once()
            mock_rs.delete.assert_called_once_with('prolist')
        finally:
            os.chdir(original_cwd)

    @patch('services.pack.PackService')
    async def test_unpack_invalid_json(self, mock_pack_service):
        """Test unpacking with invalid JSON config."""
        pro_dir = os.path.join(self.test_dir, f'problem/{self.pro_id}')
        os.makedirs(pro_dir, exist_ok=True)

        # Write invalid JSON
        with open(os.path.join(pro_dir, 'conf.json'), 'w') as f:
            f.write('{ invalid json')

        mock_pack_service.inst = MagicMock()
        mock_pack_service.inst.unpack = AsyncMock(return_value=(None, None))
        mock_pack_service.inst.clear = AsyncMock()

        mock_db = MagicMock()
        mock_rs = MagicMock()

        original_cwd = os.getcwd()
        os.chdir(self.test_dir)

        try:
            err, _ = await self.spec.unpack_pro(mock_db, mock_rs, self.pro_id, 'test_token')

            self.assertIsNotNone(err)
            self.assertEqual(err[0], 'Econf')
            self.assertIn('json syntax error', err[1].lower())
            mock_pack_service.inst.clear.assert_called_once()
        finally:
            os.chdir(original_cwd)

    @patch('services.pack.PackService')
    async def test_unpack_with_grader(self, mock_pack_service):
        """Test unpacking problem with grader."""
        config_data = {
            'compile': 'makefile',
            'timelimit': 1000,
            'memlimit': 262144,
            'metadata': '',
            'check': 'diff',
            'test': [
                {'data': ['1'], 'weight': 100}
            ]
        }

        pro_dir = self._create_test_package(self.pro_id, config_data)

        mock_pack_service.inst = MagicMock()
        mock_pack_service.inst.unpack = AsyncMock(return_value=(None, None))
        mock_pack_service.inst.clear = AsyncMock()

        mock_db = MagicMock()
        mock_rs = MagicMock()
        mock_rs.delete = AsyncMock()

        original_cwd = os.getcwd()
        os.chdir(self.test_dir)

        try:
            with patch('services.pro.ProService') as mock_pro_service:
                mock_pro_service.inst = MagicMock()
                mock_pro_service.inst.update_pro_config = AsyncMock()

                err, _ = await self.spec.unpack_pro(mock_db, mock_rs, self.pro_id, 'test_token')

                self.assertIsNone(err)

                # Check that the config was created with grader settings
                call_args = mock_pro_service.inst.update_pro_config.call_args
                _, _, proconfig = call_args[0]

                self.assertIsInstance(proconfig, ProblemConfig)
                self.assertIsInstance(proconfig.spec_config, BatchConfig)
                self.assertTrue(proconfig.spec_config.has_grader)
                # Only C++ compilers allowed for grader problems
                self.assertEqual(
                    proconfig.spec_config.allow_compilers,
                    {int(Compiler.CLANGPP), int(Compiler.GPP)}
                )
        finally:
            os.chdir(original_cwd)

    @patch('services.pack.PackService')
    async def test_unpack_with_custom_limits(self, mock_pack_service):
        """Test unpacking problem with custom compiler limits."""
        config_data = {
            'metadata': '',
            'check': 'diff',
            'limit': {
                'default': {
                    'timelimit': 1000,
                    'memlimit': 262144
                },
                'g++': {
                    'timelimit': 2000,
                    'memlimit': 524288
                }
            },
            'test': [
                {'data': ['1'], 'weight': 100}
            ]
        }

        pro_dir = self._create_test_package(self.pro_id, config_data)

        mock_pack_service.inst = MagicMock()
        mock_pack_service.inst.unpack = AsyncMock(return_value=(None, None))
        mock_pack_service.inst.clear = AsyncMock()

        mock_db = MagicMock()
        mock_rs = MagicMock()
        mock_rs.delete = AsyncMock()

        original_cwd = os.getcwd()
        os.chdir(self.test_dir)

        try:
            with patch('services.pro.ProService') as mock_pro_service:
                mock_pro_service.inst = MagicMock()
                mock_pro_service.inst.update_pro_config = AsyncMock()

                err, _ = await self.spec.unpack_pro(mock_db, mock_rs, self.pro_id, 'test_token')

                self.assertIsNone(err)

                # Check limits were parsed correctly
                call_args = mock_pro_service.inst.update_pro_config.call_args
                _, _, proconfig = call_args[0]

                self.assertIn('default', proconfig.limits)
                self.assertEqual(proconfig.limits['default'].time, 1000)
                self.assertEqual(proconfig.limits['default'].memory, 262144)

                # g++ was mapped to GPP compiler
                self.assertIn(int(Compiler.GPP), proconfig.limits)
        finally:
            os.chdir(original_cwd)

    @patch('services.pack.PackService')
    async def test_unpack_missing_default_limit(self, mock_pack_service):
        """Test unpacking fails when default limit is missing."""
        config_data = {
            'metadata': '',
            'check': 'diff',
            'limit': {
                'g++': {
                    'timelimit': 1000,
                    'memlimit': 262144
                }
            },
            'test': [
                {'data': ['1'], 'weight': 100}
            ]
        }

        pro_dir = self._create_test_package(self.pro_id, config_data)

        mock_pack_service.inst = MagicMock()
        mock_pack_service.inst.unpack = AsyncMock(return_value=(None, None))
        mock_pack_service.inst.clear = AsyncMock()

        mock_db = MagicMock()
        mock_rs = MagicMock()

        original_cwd = os.getcwd()
        os.chdir(self.test_dir)

        try:
            err, _ = await self.spec.unpack_pro(mock_db, mock_rs, self.pro_id, 'test_token')

            self.assertIsNotNone(err)
            self.assertEqual(err[0], 'Econf')
            self.assertIn('default', err[1].lower())
        finally:
            os.chdir(original_cwd)

    @patch('services.pack.PackService')
    async def test_unpack_cleans_up_on_failure(self, mock_pack_service):
        """Test that problem directory is cleaned up on failure."""
        config_data = {
            'metadata': '',
            'check': 'diff',
            # Missing required fields to trigger error
            'test': []
        }

        pro_dir = self._create_test_package(self.pro_id, config_data)

        mock_pack_service.inst = MagicMock()
        mock_pack_service.inst.unpack = AsyncMock(return_value=(None, None))
        mock_pack_service.inst.clear = AsyncMock()

        mock_db = MagicMock()
        mock_rs = MagicMock()

        original_cwd = os.getcwd()
        os.chdir(self.test_dir)

        try:
            err, _ = await self.spec.unpack_pro(mock_db, mock_rs, self.pro_id, 'test_token')

            # Should return error
            self.assertIsNotNone(err)

            # Should clean up pack token
            mock_pack_service.inst.clear.assert_called_once_with('test_token')

            # Problem directory should be removed on failure
            self.assertFalse(os.path.exists(pro_dir))
        finally:
            os.chdir(original_cwd)

    @patch('services.pack.PackService')
    async def test_unpack_creates_testdata_correctly(self, mock_pack_service):
        """Test that testdata is created correctly from config."""
        config_data = {
            'timelimit': 1000,
            'memlimit': 262144,
            'metadata': '',
            'check': 'diff',
            'test': [
                {'data': ['1', '2'], 'weight': 50},
                {'data': ['3'], 'weight': 50}
            ]
        }

        pro_dir = self._create_test_package(self.pro_id, config_data)

        mock_pack_service.inst = MagicMock()
        mock_pack_service.inst.unpack = AsyncMock(return_value=(None, None))
        mock_pack_service.inst.clear = AsyncMock()

        mock_db = MagicMock()
        mock_rs = MagicMock()
        mock_rs.delete = AsyncMock()

        original_cwd = os.getcwd()
        os.chdir(self.test_dir)

        try:
            with patch('services.pro.ProService') as mock_pro_service:
                mock_pro_service.inst = MagicMock()
                mock_pro_service.inst.update_pro_config = AsyncMock()

                err, _ = await self.spec.unpack_pro(mock_db, mock_rs, self.pro_id, 'test_token')

                self.assertIsNone(err)

                # Check testdata and subtasks
                call_args = mock_pro_service.inst.update_pro_config.call_args
                _, _, proconfig = call_args[0]

                # Should have 3 unique testdatas (1, 2, 3)
                self.assertEqual(len(proconfig.testdatas), 3)

                # Should have 2 subtasks
                self.assertEqual(len(proconfig.subtask_configs), 2)

                # Check subtask 0 has testdatas 1 and 2
                subtask0 = proconfig.subtask_configs[0]
                self.assertEqual(subtask0.rate, 50)
                self.assertEqual(len(subtask0.testdatas), 2)

                # Check subtask 1 has testdata 3
                subtask1 = proconfig.subtask_configs[1]
                self.assertEqual(subtask1.rate, 50)
                self.assertEqual(len(subtask1.testdatas), 1)
        finally:
            os.chdir(original_cwd)
if __name__ == '__main__':
    unittest.main()
