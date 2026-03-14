import datetime
import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock

# TODO: Config should be refactored to be injectable
mock_config = types.SimpleNamespace(BASE_URL="/oj", TIMEZONE=datetime.timezone(datetime.timedelta(hours=+8)))
sys.modules["config"] = mock_config

from services.class_group import ClassGroup, ClassGroupService


class TestClassGroupModel(unittest.TestCase):
    def test_get_display_name_with_custom_name(self):
        group = ClassGroup(
            group_id=1,
            year=2025,
            semester=1,
            class_number=3,
            custom_name="數資班",
            ip_range_start="",
            ip_range_end="",
            ip_login_enabled=False,
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
        )

        self.assertEqual(group.get_display_name(), "2025學年 上學期 3班 - 數資班")

    def test_get_display_name_without_custom_name(self):
        group = ClassGroup(
            group_id=1,
            year=2025,
            semester=2,
            class_number=8,
            custom_name="",
            ip_range_start="",
            ip_range_end="",
            ip_login_enabled=False,
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
        )

        self.assertEqual(group.get_display_name(), "2025學年 下學期 8班")


class TestClassGroupServiceHelpers(unittest.TestCase):
    def setUp(self):
        self.service = ClassGroupService(db=MagicMock(), rs=AsyncMock())

    def test_build_filter_conditions_no_filters(self):
        where_clause, params, param_count = self.service._build_filter_conditions()

        self.assertEqual(where_clause, "TRUE")
        self.assertEqual(params, [])
        self.assertEqual(param_count, 1)

    def test_build_filter_conditions_with_all_filters(self):
        where_clause, params, param_count = self.service._build_filter_conditions(
            year=2025,
            semester=1,
            class_number=5,
            custom_name="資",
        )

        self.assertEqual(
            where_clause,
            '"year" = $1 AND "semester" = $2 AND "class_number" = $3 AND "custom_name" LIKE $4',
        )
        self.assertEqual(params, [2025, 1, 5, "%資%"])
        self.assertEqual(param_count, 5)

    def test_validate_ip_success(self):
        is_valid, err_msg = self.service._validate_ip("192.168.11.10")
        self.assertTrue(is_valid)
        self.assertIsNone(err_msg)

    def test_validate_ip_failure(self):
        is_valid, err_msg = self.service._validate_ip("999.1.1.1")
        self.assertFalse(is_valid)
        self.assertIsNotNone(err_msg)

    def test_validate_ip_range_success(self):
        err = self.service._validate_ip_range("192.168.11.10", "192.168.11.14")
        self.assertIsNone(err)

    def test_validate_ip_range_invalid_prefix(self):
        err = self.service._validate_ip_range("10.0.0.2", "10.0.0.20")
        self.assertEqual(err[0], "Einval")

    def test_validate_ip_range_different_subnet(self):
        err = self.service._validate_ip_range("192.168.10.2", "192.168.11.10")
        self.assertEqual(err[0], "Einval")

    def test_generate_ips_from_range_success(self):
        ips = self.service._generate_ips_from_range("192.168.11.10", "192.168.11.12")
        self.assertEqual(ips, ["192.168.11.10", "192.168.11.11", "192.168.11.12"])

    def test_generate_ips_from_range_invalid_order(self):
        with self.assertRaises(ValueError):
            self.service._generate_ips_from_range("192.168.11.12", "192.168.11.10")


class TestClassGroupServiceAsync(unittest.IsolatedAsyncioTestCase):
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

        self.service = ClassGroupService(self.fake_db, self.fake_rs)

    def _make_group(self, start_ip: str, end_ip: str) -> ClassGroup:
        now = datetime.datetime.now()
        return ClassGroup(
            group_id=1,
            year=2025,
            semester=1,
            class_number=3,
            custom_name="",
            ip_range_start=start_ip,
            ip_range_end=end_ip,
            ip_login_enabled=False,
            created_at=now,
            updated_at=now,
        )

    async def test_parse_csv_success(self):
        content = (
            "email,name,password,specific_ip\n"
            "s1@example.com,Student One,pass123,192.168.1.10\n"
            "s2@example.com,Student Two,pass456,\n"
        ).encode("utf-8")

        err, accounts = await self.service.parse_csv(content)

        self.assertIsNone(err)
        self.assertEqual(len(accounts), 2)
        self.assertEqual(accounts[0]["email"], "s1@example.com")
        self.assertEqual(accounts[0]["specific_ip"], "192.168.1.10")

    async def test_parse_csv_missing_required_columns(self):
        content = "email,name\na@example.com,Alice\n".encode("utf-8")

        err, accounts = await self.service.parse_csv(content)

        self.assertEqual(err[0], "Eformat")
        self.assertIsNone(accounts)

    async def test_parse_csv_invalid_specific_ip(self):
        content = (
            "email,name,password,specific_ip\n"
            "a@example.com,Alice,pw,999.168.1.1\n"
        ).encode("utf-8")

        err, accounts = await self.service.parse_csv(content)

        self.assertEqual(err[0], "Einval")
        self.assertIsNone(accounts)

    async def test_parse_csv_empty_file_after_header(self):
        content = "email,name,password\n".encode("utf-8")

        err, accounts = await self.service.parse_csv(content)

        self.assertEqual(err[0], "Eformat")
        self.assertIsNone(accounts)

    async def test_parse_csv_too_large(self):
        content = b"x" * 10

        err, accounts = await self.service.parse_csv(content, max_size=5)

        self.assertEqual(err[0], "Esize")
        self.assertIsNone(accounts)

    async def test_parse_csv_encoding_error(self):
        err, accounts = await self.service.parse_csv(b"\xff\xfe")

        self.assertEqual(err[0], "Eformat")
        self.assertIsNone(accounts)

    async def test_get_next_available_ip_returns_first_free_ip(self):
        self.service.get_class_group = AsyncMock(
            return_value=(None, self._make_group("192.168.1.10", "192.168.1.12"))
        )
        self.fake_conn.fetch.return_value = [{"specific_ip": "192.168.1.10"}]

        err, ip = await self.service.get_next_available_ip(1)

        self.assertIsNone(err)
        self.assertEqual(ip, "192.168.1.11")

    async def test_get_next_available_ip_no_range(self):
        self.service.get_class_group = AsyncMock(return_value=(None, self._make_group("", "")))

        err, ip = await self.service.get_next_available_ip(1)

        self.assertIsNone(err)
        self.assertIsNone(ip)
        self.fake_conn.fetch.assert_not_awaited()

    async def test_get_next_available_ip_group_error(self):
        self.service.get_class_group = AsyncMock(return_value=(("Enoext", "Class group not found"), None))

        err, ip = await self.service.get_next_available_ip(404)

        self.assertEqual(err[0], "Enoext")
        self.assertIsNone(ip)

    async def test_get_next_available_ip_range_exhausted(self):
        self.service.get_class_group = AsyncMock(
            return_value=(None, self._make_group("192.168.1.10", "192.168.1.10"))
        )
        self.fake_conn.fetch.return_value = [{"specific_ip": "192.168.1.10"}]

        err, ip = await self.service.get_next_available_ip(1)

        self.assertEqual(err[0], "Erange")
        self.assertIsNone(ip)

    async def test_get_next_available_ip_db_error(self):
        self.service.get_class_group = AsyncMock(
            return_value=(None, self._make_group("192.168.1.10", "192.168.1.12"))
        )
        self.fake_conn.fetch.side_effect = RuntimeError("db down")

        err, ip = await self.service.get_next_available_ip(1)

        self.assertEqual(err[0], "Eunk")
        self.assertIsNone(ip)
