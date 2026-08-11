import unittest

from unittest.mock import AsyncMock, MagicMock, patch
from services.user import UserService, Account, UserConst, GUEST_ACCOUNT
from services.chal import Compiler
import time

class DummyReq:
    def __init__(self, id_val=None, cookie_val=None, remote_ip="127.0.0.1"):
        self._id_val = id_val
        self._cookie_val = cookie_val
        self.request = MagicMock()
        self.request.remote_ip = remote_ip

    def get_secure_cookie(self, key):
        if key == "id":
            return self._id_val
        return None

    def get_cookie(self, key):
        if key == "id":
            return self._cookie_val
        return None


class TestUserService(unittest.IsolatedAsyncioTestCase):
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
        self.service = UserService(self.fake_db, self.fake_rs)

    @patch("bcrypt.hashpw", return_value=b"hashedpw")
    @patch("bcrypt.gensalt", return_value=b"salt")
    async def test_sign_up_success(self, mock_gensalt, mock_hashpw):
        self.fake_conn.fetch.return_value = [{"acct_id": 123}]
        self.fake_rs.delete.return_value = None
        err, acct_id = await self.service.sign_up("test@mail.com", "pw123", "tester")
        self.fake_conn.fetch.assert_awaited_once()
        self.fake_rs.delete.assert_awaited_once_with("acctlist")
        self.assertIsNone(err)
        self.assertEqual(acct_id, 123)

    async def test_sign_up_mail_too_short(self):
        err, acct_id = await self.service.sign_up("", "pw123", "tester")
        self.assertIsNotNone(err)
        self.assertIsNone(acct_id)
        self.assertEqual(err[0], "Emailmin")

    async def test_sign_up_mail_too_long(self):
        mail = "a" * (UserConst.MAIL_MAX + 1)
        err, acct_id = await self.service.sign_up(mail, "pw123", "tester")
        self.assertIsNotNone(err)
        self.assertIsNone(acct_id)
        self.assertEqual(err[0], "Emailmax")

    async def test_sign_up_pw_too_short(self):
        err, acct_id = await self.service.sign_up("test@mail.com", "", "tester")
        self.assertIsNotNone(err)
        self.assertIsNone(acct_id)
        self.assertEqual(err[0], "Epwmin")

    async def test_sign_up_pw_too_long(self):
        pw = "a" * (UserConst.PW_MAX + 1)
        err, acct_id = await self.service.sign_up("test@mail.com", pw, "tester")
        self.assertIsNotNone(err)
        self.assertIsNone(acct_id)
        self.assertEqual(err[0], "Epwmax")

    async def test_sign_up_name_too_long(self):
        name = "a" * (UserConst.NAME_MAX + 1)
        err, acct_id = await self.service.sign_up("test@mail.com", "pw123", name)
        self.assertIsNotNone(err)
        self.assertIsNone(acct_id)
        self.assertEqual(err[0], "Enamemax")

    async def test_sign_up_name_too_short(self):
        err, acct_id = await self.service.sign_up("test@mail.com", "pw123", "")
        self.assertIsNotNone(err)
        self.assertIsNone(acct_id)
        self.assertEqual(err[0], "Enamemin")

    async def test_sign_in_success(self):
        self.fake_conn.fetch.return_value = [{"acct_id": 1, "password": "aGVsbG8=", "specific_ip": ""}]
        with patch("base64.b64decode", return_value=b"hashedpw"):
            with patch("bcrypt.hashpw", return_value=b"hashedpw"):
                err, acct_id = await self.service.sign_in("test@mail.com", "pw123")
        self.fake_conn.fetch.assert_awaited_once()
        self.assertIsNone(err)
        self.assertEqual(acct_id, 1)

    @patch("services.user.bcrypt.hashpw")
    @patch("services.user.asyncio.to_thread", new_callable=AsyncMock)
    async def test_sign_in_offloads_bcrypt(self, mock_to_thread, mock_hashpw):
        self.fake_conn.fetch.return_value = [
            {"acct_id": 1, "password": "aGVsbG8=", "specific_ip": ""}
        ]
        mock_to_thread.return_value = b"hello"

        err, acct_id = await self.service.sign_in("test@mail.com", "pw123")

        mock_to_thread.assert_awaited_once_with(mock_hashpw, b"pw123", b"hello")
        mock_hashpw.assert_not_called()
        self.assertIsNone(err)
        self.assertEqual(acct_id, 1)

    @patch("services.user.asyncio.to_thread", new_callable=AsyncMock)
    async def test_sign_in_rejects_wrong_password_after_offload(self, mock_to_thread):
        self.fake_conn.fetch.return_value = [
            {"acct_id": 1, "password": "aGVsbG8=", "specific_ip": ""}
        ]
        mock_to_thread.return_value = b"wrong-password-hash"

        err, acct_id = await self.service.sign_in("test@mail.com", "wrong")

        self.assertEqual(err[0], "Esign")
        self.assertIsNone(acct_id)

    async def test_sign_in_success_with_ip(self):
        self.fake_conn.fetch.return_value = [{"acct_id": 1, "password": "aGVsbG8=", "specific_ip": "192.168.11.10"}]
        with patch("base64.b64decode", return_value=b"hashedpw"):
            with patch("bcrypt.hashpw", return_value=b"hashedpw"):
                err, acct_id = await self.service.sign_in("test@mail.com", "pw123", "192.168.11.10")
        self.fake_conn.fetch.assert_awaited_once()
        self.assertIsNone(err)
        self.assertEqual(acct_id, 1)

    async def test_sign_in_fail_block_by_ip(self):
        self.fake_conn.fetch.return_value = [{"acct_id": 1, "password": "aGVsbG8=", "specific_ip": "192.168.11.10"}]
        err, acct_id = await self.service.sign_in("test@mail.com", "pw123", "127.0.0.1")
        self.fake_conn.fetch.assert_awaited_once()
        self.assertIsNotNone(err)
        self.assertIsNone(acct_id)
        self.assertEqual(err[0], "Esignip")

    async def test_sign_in_fail(self):
        self.fake_conn.fetch.return_value = []
        err, acct_id = await self.service.sign_in("test@mail.com", "pw123")
        self.fake_conn.fetch.assert_awaited_once()
        self.assertIsNotNone(err)
        self.assertIsNone(acct_id)
        self.assertEqual(err[0], "Esign")

    async def test_info_acct_guest(self):
        err, acct = await self.service.info_acct(None)
        self.assertIsNone(err)
        self.assertEqual(acct, GUEST_ACCOUNT)

    async def test_info_acct_found_in_cache(self):
        dummy_acct = Account(
            acct_id=2,
            acct_type=UserConst.ACCTTYPE_USER,
            mail="",
            name="tester",
            photo="",
            cover="",
            motto="",
            lastip="",
            last_compiler=Compiler.GCC,
            proclass_collection=[],
            specific_ip="",
        )
        self.fake_rs.get.return_value = MagicMock()
        with patch("pickle.loads", return_value=dummy_acct):
            err, acct = await self.service.info_acct(2)
        self.fake_rs.get.assert_awaited_once()
        self.assertIsNone(err)
        self.assertEqual(acct.name, "tester")

    async def test_info_acct_not_found(self):
        self.fake_rs.get.return_value = None
        self.fake_conn.fetch.return_value = []
        err, acct = await self.service.info_acct(999)
        self.fake_conn.fetch.assert_awaited_once()
        self.assertIsNotNone(err)
        self.assertIsNone(acct)
        self.assertEqual(err[0], "Enoext")

    async def test_update_pw_success(self):
        self.fake_conn.fetch.return_value = [{"password": "aGVsbG8="}]
        with patch("base64.b64decode", return_value=b"hashedpw"):
            with patch("bcrypt.hashpw") as hashpw_mock:
                with patch("bcrypt.gensalt", return_value=b"salt"):
                    # First call: check old password (should not match)
                    # Second call: update with new password (should hash new password)
                    # Patch hashpw for the second call
                    hashpw_mock.side_effect = [b"notmatch", b"newhashedpw"]
                    self.fake_conn.execute.return_value = None
                    err, _ = await self.service.update_pw(1, "oldpw", "newpw", True)
        self.fake_conn.fetch.assert_awaited_once()
        self.fake_conn.execute.assert_awaited_once()
        self.assertIsNone(err)

    async def test_update_pw_old_wrong(self):
        self.fake_conn.fetch.return_value = [{"password": "aGVsbG8="}]
        with (
            patch("base64.b64decode", return_value=b"hashedpw"),
            patch("bcrypt.hashpw", return_value=b"notmatch"),
        ):
            err, _ = await self.service.update_pw(1, "oldpw", "newpw", False)
        self.assertIsNotNone(err)
        self.assertEqual(err[0], "Epwold")

    async def test_info_sign_success(self):
        req = DummyReq(id_val="1", cookie_val="sesskey", remote_ip="192.168.1.1")
        with patch("services.user.unpackb", return_value={"time": time.time()}):
            self.fake_rs.get.return_value = None
            self.fake_conn.fetch.return_value = [{"acct_id": 1, "lastip": "127.0.0.1"}]
            with (
                patch.object(self.service, "rs", self.fake_rs),
                patch("services.log.LogService.inst.add_log", new_callable=AsyncMock),
            ):
                self.fake_conn.execute.return_value = None
                self.fake_rs.delete.return_value = None
                err, acct_id, ip = await self.service.info_sign(req)
        self.assertIsNone(err)
        self.assertEqual(acct_id, 1)
        self.assertEqual(ip, "192.168.1.1")

    async def test_info_sign_expired(self):
        req = DummyReq(id_val="1", cookie_val="sesskey")
        with patch("services.user.unpackb", return_value={"time": time.time() - 31 * 24 * 60 * 60}):
            err, acct_id, ip = await self.service.info_sign(req)
        self.assertEqual(err, "Esign")
        self.assertIsNone(acct_id)
        self.assertEqual(ip, "")

    async def test_info_sign_no_cookie(self):
        req = DummyReq(id_val=None, cookie_val=None)
        err, acct_id, ip = await self.service.info_sign(req)
        self.assertEqual(err, "Esign")
        self.assertIsNone(acct_id)
        self.assertEqual(ip, "")

    async def test_update_acct_success(self):
        acct = Account(
            acct_id=1,
            acct_type=UserConst.ACCTTYPE_USER,
            mail="",
            name="tester",
            photo="",
            cover="",
            motto="hello",
            lastip="",
            last_compiler=Compiler.GCC,
            proclass_collection=[],
            specific_ip="",
        )
        self.fake_conn.fetch.return_value = [{"acct_id": 1}]
        self.fake_rs.delete.return_value = None
        err, _ = await self.service.update_acct(acct)
        self.fake_conn.fetch.assert_awaited_once()
        self.fake_rs.delete.assert_any_await("account@1")
        self.fake_rs.delete.assert_any_await("acctlist")
        self.assertIsNone(err)

    async def test_update_acct_invalid_type(self):
        acct = Account(
            acct_id=1,
            acct_type=99,
            mail="",
            name="tester",
            photo="",
            cover="",
            motto="hello",
            lastip="",
            last_compiler=Compiler.GCC,
            proclass_collection=[],
            specific_ip="",
        )
        err, _ = await self.service.update_acct(acct)
        self.assertEqual(err[0], "Eparam")

    async def test_update_acct_name_too_short(self):
        acct = Account(
            acct_id=1,
            acct_type=UserConst.ACCTTYPE_USER,
            mail="",
            name="",
            photo="",
            cover="",
            motto="hello",
            lastip="",
            last_compiler=Compiler.GCC,
            proclass_collection=[],
            specific_ip="",
        )
        err, _ = await self.service.update_acct(acct)
        self.assertEqual(err[0], "Enamemin")

    async def test_update_acct_motto_too_long(self):
        acct = Account(
            acct_id=1,
            acct_type=UserConst.ACCTTYPE_USER,
            mail="",
            name="tester",
            photo="",
            cover="",
            motto="a" * (UserConst.MOTTO_MAX + 1),
            lastip="",
            last_compiler=Compiler.GCC,
            proclass_collection=[],
            specific_ip="",
        )
        err, _ = await self.service.update_acct(acct)
        self.assertEqual(err[0], "Emottomax")

    async def test_list_acct_success(self):
        self.fake_rs.hget.return_value = None
        self.fake_conn.fetch.return_value = [
            (1, UserConst.ACCTTYPE_USER, "tester", "test@mail.com", "127.0.0.1", ""),
            (2, UserConst.ACCTTYPE_USER, "tester2", "test2@mail.com", "127.0.0.2", ""),
        ]
        self.fake_rs.hset.return_value = None
        err, acctlist = await self.service.list_acct()
        self.fake_conn.fetch.assert_awaited_once()
        self.fake_rs.hset.assert_awaited_once()
        self.assertIsNone(err)
        self.assertEqual(len(acctlist), 2)
        self.assertEqual(acctlist[0].name, "tester")
        self.assertEqual(acctlist[1].name, "tester2")

    async def test_list_acct_from_cache(self):
        dummy_acctlist = [
            Account(
                acct_id=1,
                acct_type=UserConst.ACCTTYPE_USER,
                mail="",
                name="tester",
                photo="",
                cover="",
                motto="",
                lastip="127.0.0.1",
                last_compiler=Compiler.GCC,
                proclass_collection=[],
                specific_ip="",
            )
        ]
        self.fake_rs.hget.return_value = MagicMock()
        with patch("pickle.loads", return_value=dummy_acctlist):
            err, acctlist = await self.service.list_acct()
        self.fake_rs.hget.assert_awaited_once()
        self.assertIsNone(err)
        self.assertEqual(len(acctlist), 1)
        self.assertEqual(acctlist[0].name, "tester")

    async def test_info_sign_db_not_found(self):
        req = DummyReq(id_val="1", cookie_val="sesskey", remote_ip="192.168.1.1")
        with patch("services.user.unpackb", return_value={"time": time.time()}):
            self.fake_rs.get.return_value = None
            self.fake_conn.fetch.return_value = []
            with patch.object(self.service, "rs", self.fake_rs):
                err, acct_id, ip = await self.service.info_sign(req)
        self.assertEqual(err, "Esign")
        self.assertIsNone(acct_id)
        self.assertEqual(ip, "192.168.1.1")

    async def test_info_sign_db_update_lastip(self):
        req = DummyReq(id_val="1", cookie_val="sesskey", remote_ip="192.168.1.2")
        with patch("services.user.unpackb", return_value={"time": time.time()}):
            self.fake_rs.get.return_value = None
            self.fake_conn.fetch.return_value = [{"acct_id": 1, "lastip": "127.0.0.1"}]
            with (
                patch.object(self.service, "rs", self.fake_rs),
                patch.object(self.service, "db", self.fake_db),
                patch("services.log.LogService.inst.add_log", new_callable=AsyncMock) as mock_add_log,
            ):
                self.fake_conn.execute.return_value = None
                self.fake_rs.delete.return_value = None
                err, acct_id, ip = await self.service.info_sign(req)
        self.fake_conn.execute.assert_awaited_once()
        self.fake_rs.delete.assert_any_await("account@1")
        self.fake_rs.delete.assert_any_await("acctlist")
        mock_add_log.assert_awaited_once()
        self.assertIsNone(err)
        self.assertEqual(acct_id, 1)
        self.assertEqual(ip, "192.168.1.2")

if __name__ == "__main__":
    unittest.main()
