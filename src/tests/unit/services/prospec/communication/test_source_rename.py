import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from services.chal import Compiler
from services.pro import ProType
from services.prospec.program import program_config_transaction


class TestSourceRenameTransaction(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(os.chdir, self.original_cwd)
        for chal_id in (1, 2):
            Path(f'code/{chal_id}').mkdir(parents=True)
            Path(f'code/{chal_id}/a.cpp').write_text(str(chal_id))
        self.con = AsyncMock()
        self.tx = MagicMock()
        self.con.transaction = MagicMock(return_value=self.tx)
        self.con.fetchrow.return_value = {
            'problem_type': int(ProType.COMMUNICATION),
            'config': json.dumps({'submission_format': ['a.%l']}),
        }
        self.con.fetch.return_value = [
            {'chal_id': n, 'compiler_type': Compiler.GPP} for n in (1, 2)
        ]
        self.config = SimpleNamespace(spec_config=SimpleNamespace(submission_format=['b.%l']))

    def transaction(self):
        return program_config_transaction(self.con, 10, ProType.COMMUNICATION, self.config)

    def assert_originals(self):
        for chal_id in (1, 2):
            self.assertEqual(Path(f'code/{chal_id}/a.cpp').read_text(), str(chal_id))
            self.assertFalse(Path(f'code/{chal_id}/b.cpp').exists())

    async def test_success_renames_all_challenges(self):
        async with self.transaction():
            pass
        for chal_id in (1, 2):
            self.assertEqual(Path(f'code/{chal_id}/b.cpp').read_text(), str(chal_id))
            self.assertFalse(Path(f'code/{chal_id}/a.cpp').exists())

    async def test_conflict_is_detected_before_any_rename(self):
        Path('code/2/b.cpp').write_text('existing')
        with patch('services.prospec.program.os.rename') as rename:
            with self.assertRaises(FileExistsError):
                async with self.transaction():
                    self.fail('must reject before updating config')
            rename.assert_not_called()
        self.assertEqual(Path('code/1/a.cpp').read_text(), '1')
        self.assertEqual(Path('code/2/b.cpp').read_text(), 'existing')

    async def test_later_filesystem_failure_restores_earlier_challenges(self):
        real_rename = os.rename
        def rename(source, target):
            if source == 'code/2/a.cpp':
                raise OSError('injected rename failure')
            real_rename(source, target)
        with patch('services.prospec.program.os.rename', side_effect=rename):
            with self.assertRaises(OSError):
                async with self.transaction():
                    pass
        self.assert_originals()

    async def test_database_failure_restores_sources(self):
        with self.assertRaises(RuntimeError):
            async with self.transaction():
                raise RuntimeError('database update failed')
        self.assert_originals()

    async def test_commit_failure_restores_sources(self):
        self.tx.__aexit__.side_effect = RuntimeError('commit failed')
        with self.assertRaises(RuntimeError):
            async with self.transaction():
                pass
        self.assert_originals()

    async def test_cancelled_update_restores_sources(self):
        with self.assertRaises(asyncio.CancelledError):
            async with self.transaction():
                raise asyncio.CancelledError()
        self.assert_originals()

    async def test_swapped_names_are_restored_on_failure(self):
        self.con.fetchrow.return_value['config'] = json.dumps({
            'submission_format': ['a.%l', 'b.%l'],
        })
        self.config.spec_config.submission_format = ['b.%l', 'a.%l']
        for chal_id in (1, 2):
            Path(f'code/{chal_id}/b.cpp').write_text('second')
        with self.assertRaises(RuntimeError):
            async with self.transaction():
                raise RuntimeError('database update failed')
        for chal_id in (1, 2):
            self.assertEqual(Path(f'code/{chal_id}/a.cpp').read_text(), str(chal_id))
            self.assertEqual(Path(f'code/{chal_id}/b.cpp').read_text(), 'second')

    async def test_missing_sources_are_not_created_or_moved_on_rollback(self):
        Path('code/2/a.cpp').unlink()
        Path('code/2/b.cpp').write_text('unrelated')
        with self.assertRaises(RuntimeError):
            async with self.transaction():
                raise RuntimeError('database update failed')
        self.assertFalse(Path('code/2/a.cpp').exists())
        self.assertEqual(Path('code/2/b.cpp').read_text(), 'unrelated')
        self.assertEqual(Path('code/1/a.cpp').read_text(), '1')
