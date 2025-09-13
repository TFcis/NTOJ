import unittest

from unittest.mock import AsyncMock, MagicMock, patch
from services.user import UserService, Account, UserConst, GUEST_ACCOUNT
from services.chal import Compiler

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

    async def test_sign_in_success(self):
        self.fake_conn.fetch.return_value = [{"acct_id": 1, "password": "aGVsbG8="}]
        with patch("base64.b64decode", return_value=b"hashedpw"):
            with patch("bcrypt.hashpw", return_value=b"hashedpw"):
                err, acct_id = await self.service.sign_in("test@mail.com", "pw123")
        self.fake_conn.fetch.assert_awaited_once()
        self.assertIsNone(err)
        self.assertEqual(acct_id, 1)

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
            last_compiler=Compiler.GPP,
            proclass_collection=[],
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
        with (
            patch("base64.b64decode", return_value=b"hashedpw"),
            patch("bcrypt.hashpw", side_effect=[b"notmatch", b"newhashedpw"]),
            patch("bcrypt.gensalt", return_value=b"salt"),
        ):
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


if __name__ == "__main__":
    unittest.main()
