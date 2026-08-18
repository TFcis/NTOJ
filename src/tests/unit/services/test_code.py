import os
import sys
import tempfile
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

# TODO: Config should be refactored to be injectable
mock_config = types.SimpleNamespace(lock_user_list=[], can_see_code_user=[])
sys.modules["config"] = mock_config

from services.code import CodeService
from services.chal import Compiler

class DummyAccount:
    def __init__(self, acct_id, name, kernel=False):
        self.acct_id = acct_id
        self.name = name
        self._kernel = kernel

    def is_kernel(self):
        return self._kernel


class DummyContest:
    def __init__(self, admins):
        self.admins = admins

    def is_admin(self, acct):
        return acct.acct_id in self.admins


class TestCodeService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fake_conn = AsyncMock()

        fake_tx_cm = MagicMock()
        fake_tx_cm.__aenter__ = AsyncMock(return_value=None)
        fake_tx_cm.__aexit__ = AsyncMock(return_value=None)
        self.fake_conn.transaction = MagicMock(return_value=fake_tx_cm)

        fake_acquire_cm = MagicMock()
        fake_acquire_cm.__aenter__ = AsyncMock(return_value=self.fake_conn)
        fake_acquire_cm.__aexit__ = AsyncMock(return_value=None)
        self.fake_db = MagicMock()
        self.fake_db.acquire = MagicMock(return_value=fake_acquire_cm)
        self.fake_rs = AsyncMock()
        self.service = CodeService(self.fake_db, self.fake_rs)

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="print('hello')".encode("utf-8"),
    )
    async def test_get_code_self(self, mock_file):
        self.fake_conn.fetch.return_value = [
            {
                "acct_id": 1,
                "pro_id": 2,
                "contest_id": 0,
                "compiler_type": Compiler.GPP,
            }
        ]
        acct = DummyAccount(1, "user1")
        self.fake_rs.get.return_value = None
        with patch("services.chal.Compiler", side_effect=lambda x: x):
            err, code, compiler_type = await self.service.get_code(123, acct, '192.168.11.10')
        self.fake_conn.fetch.assert_awaited_once()
        self.assertIsNone(err)
        self.assertIn("print('hello')", code)
        self.assertEqual(compiler_type, Compiler.GPP.value)
        mock_file.assert_called_once()

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="source".encode("utf-8"),
    )
    async def test_get_multiple_named_source_files(self, mock_file):
        self.fake_conn.fetch.return_value = [
            {
                "acct_id": 1,
                "pro_id": 2,
                "contest_id": 0,
                "compiler_type": Compiler.GPP,
            }
        ]
        acct = DummyAccount(1, "user1")
        self.fake_rs.get.return_value = None

        err, codes, compiler_type = await self.service.get_code(
            123,
            acct,
            "192.168.11.10",
            ["alice.cpp", "bob.cpp"],
        )

        self.assertIsNone(err)
        self.assertEqual(
            codes, {"alice.cpp": "source", "bob.cpp": "source"}
        )
        self.assertEqual(compiler_type, Compiler.GPP)
        self.assertEqual(mock_file.call_count, 2)

    async def test_get_code_rejects_path_traversal(self):
        self.fake_conn.fetch.return_value = [
            {
                "acct_id": 1,
                "pro_id": 2,
                "contest_id": 0,
                "compiler_type": Compiler.GPP,
            }
        ]
        acct = DummyAccount(1, "user1")
        self.fake_rs.get.return_value = None

        for filename in (
            "../secret.cpp",
            "/etc/passwd",
            "..\\secret.cpp",
            "nested/main.cpp",
            "main.cpp\x00ignored",
        ):
            with self.subTest(filename=filename):
                err, code, compiler_type = await self.service.get_code(
                    123,
                    acct,
                    "192.168.11.10",
                    [filename],
                )
                self.assertEqual(err, ("Eparam", "Invalid source filename"))
                self.assertIsNone(code)
                self.assertIsNone(compiler_type)

    async def test_get_code_rejects_symlink_outside_challenge_directory(self):
        self.fake_conn.fetch.return_value = [
            {
                "acct_id": 1,
                "pro_id": 2,
                "contest_id": 0,
                "compiler_type": Compiler.GPP,
            }
        ]
        acct = DummyAccount(1, "user1")
        self.fake_rs.get.return_value = None
        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tempdir:
            try:
                os.chdir(tempdir)
                os.makedirs("code/123")
                with open("secret.cpp", "w", encoding="utf-8") as secret:
                    secret.write("secret")
                os.symlink(
                    os.path.join(tempdir, "secret.cpp"),
                    "code/123/main.cpp",
                )

                err, code, compiler_type = await self.service.get_code(
                    123,
                    acct,
                    "192.168.11.10",
                    ["main.cpp"],
                )
            finally:
                os.chdir(original_cwd)

        self.assertEqual(err, ("Eparam", "Invalid source filename"))
        self.assertIsNone(code)
        self.assertIsNone(compiler_type)

    @patch("builtins.open", side_effect=FileNotFoundError)
    async def test_get_code_file_not_found(self, mock_file):
        self.fake_conn.fetch.return_value = [
            {
                "acct_id": 1,
                "pro_id": 2,
                "contest_id": 0,
                "compiler_type": Compiler.GPP,
            }
        ]
        acct = DummyAccount(1, "user1")
        self.fake_rs.get.return_value = None
        with patch("services.chal.Compiler", side_effect=lambda x: x):
            err, code, compiler_type = await self.service.get_code(123, acct, '192.168.11.10')
        self.assertIsNone(err)
        self.assertIn("ERROR", code)
        mock_file.assert_called_once()

    async def test_get_code_challenge_not_found(self):
        self.fake_conn.fetch.return_value = []
        acct = DummyAccount(1, "user1")
        err, code, compiler_type = await self.service.get_code(999, acct, '192.168.11.10')
        self.fake_conn.fetch.assert_awaited_once()
        self.assertIsNotNone(err)
        self.assertIsNone(code)
        self.assertIsNone(compiler_type)
        self.assertEqual(err[0], "Enoext")

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="int main(){}".encode("utf-8"),
    )
    async def test_get_code_kernel_can_see(self, mock_file):
        self.fake_conn.fetch.return_value = [
            {
                "acct_id": 2,
                "pro_id": 3,
                "contest_id": 0,
                "compiler_type": Compiler.GPP,
            }
        ]
        acct = DummyAccount(10, "admin", kernel=True)
        self.fake_rs.get.return_value = None
        from services.log import LogService

        LogService.inst = MagicMock()
        with (
            patch("services.chal.Compiler", side_effect=lambda x: x),
            patch("services.log.LogService.inst.add_log", new_callable=AsyncMock),
            patch(
                "services.code.config",
                new=MagicMock(lock_user_list=[10], can_see_code_user=[10]),
            ),
        ):
            err, code, compiler_type = await self.service.get_code(555, acct, '192.168.11.10')
        self.assertIsNone(err)
        self.assertIn("int main()", code)
        mock_file.assert_called_once()

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="int main(){}".encode("utf-8"),
    )
    async def test_get_code_contest_admin(self, mock_file):
        self.fake_conn.fetch.return_value = [
            {
                "acct_id": 2,
                "pro_id": 3,
                "contest_id": 42,
                "compiler_type": Compiler.GPP,
            }
        ]
        acct = DummyAccount(99, "contest_admin")
        dummy_contest = DummyContest([99])
        from services.contests import ContestService
        from services.log import LogService

        LogService.inst = MagicMock()
        ContestService.inst = MagicMock()
        with (
            patch("services.chal.Compiler", side_effect=lambda x: x),
            patch("services.log.LogService.inst.add_log", new_callable=AsyncMock),
            patch(
                "services.contests.ContestService.inst.get_contest",
                new_callable=AsyncMock,
            ) as mock_get_contest,
        ):
            mock_get_contest.return_value = (None, dummy_contest)
            err, code, compiler_type = await self.service.get_code(888, acct, '192.168.11.10')
        self.assertIsNone(err)
        self.assertIn("int main()", code)
        mock_file.assert_called_once()

    async def test_get_code_no_permission(self):
        self.fake_conn.fetch.return_value = [
            {
                "acct_id": 2,
                "pro_id": 3,
                "contest_id": 0,
                "compiler_type": Compiler.GPP,
            }
        ]
        acct = DummyAccount(77, "not_allowed", kernel=False)
        self.fake_rs.get.return_value = None
        with (
            patch("services.chal.Compiler", side_effect=lambda x: x),
            patch(
                "services.code.config",
                new=MagicMock(lock_user_list=[], can_see_code_user=[]),
            ),
        ):
            err, code, compiler_type = await self.service.get_code(123, acct, '192.168.11.10')
        self.assertIsNotNone(err)
        self.assertIsNone(code)
        self.assertIsNone(compiler_type)
        self.assertEqual(err[0], "Eacces")


if __name__ == "__main__":
    unittest.main()
