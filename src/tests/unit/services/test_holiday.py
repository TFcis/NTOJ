import unittest
from unittest.mock import AsyncMock, MagicMock
from services.holiday import HolidayService

class TestHolidayService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fake_conn = AsyncMock()

        fake_acquire_cm = MagicMock()
        fake_acquire_cm.__aenter__ = AsyncMock(return_value=self.fake_conn)
        fake_acquire_cm.__aexit__ = AsyncMock(return_value=None)

        self.fake_db = MagicMock()
        self.fake_db.acquire = MagicMock(return_value=fake_acquire_cm)
        self.fake_rs = AsyncMock()
        self.fake_rs.get = AsyncMock(return_value=None)

        self.service = HolidayService(self.fake_db, rs=self.fake_rs)

    async def test_start_lt_end(self):
        self.fake_conn.fetchrow.return_value = {"start": 1769118000, "end": 1769118100}
        res = await self.service.is_weekday_now()
        self.fake_conn.fetchrow.assert_awaited_once()
        self.assertFalse(res)

    async def test_start_gt_end(self):
        self.fake_conn.fetchrow.return_value = {"start": 1769118100, "end": 1769118000}
        res = await self.service.is_weekday_now()
        self.fake_conn.fetchrow.assert_awaited_once()
        self.assertTrue(res)

    async def test_start_eq_end(self):
        self.fake_conn.fetchrow.return_value = {"start": 1769118000, "end": 1769118000}
        res = await self.service.is_weekday_now()
        self.fake_conn.fetchrow.assert_awaited_once()
        self.assertTrue(res)

    async def test_no_row(self):
        self.fake_conn.fetchrow.return_value = None
        res = await self.service.is_weekday_now()
        self.fake_conn.fetchrow.assert_awaited_once()
        self.assertFalse(res)

    async def test_no_val(self):
        self.fake_conn.fetchrow.return_value = {}
        res = await self.service.is_weekday_now()
        self.fake_conn.fetchrow.assert_awaited_once()
        self.assertFalse(res)
