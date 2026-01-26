import sys
import datetime

import unittest
from unittest.mock import AsyncMock, MagicMock
from unittest.mock import patch

from services.holiday import HolidayService
sys.modules["config"].TIMEZONE = datetime.timezone(datetime.timedelta(hours=8))
import config

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
        self.fake_rs.set = AsyncMock()

        self.service = HolidayService(self.fake_db, rs=self.fake_rs)

    async def test_start_lt_now(self):
        self.fake_conn.fetchrow.return_value = {
            "start": datetime.datetime.fromtimestamp(1769118000.0, tz=config.TIMEZONE), 
            "end": datetime.datetime.fromtimestamp(1769118100.0, tz=config.TIMEZONE)
        }
        now = datetime.datetime.fromtimestamp(1769118050.0)
        with patch('datetime.datetime') as mock_now:
            mock_now.now.return_value = now
            res = await self.service.is_weekday_now()
        self.fake_conn.fetchrow.assert_awaited_once()
        self.assertTrue(res)
        calls = self.fake_rs.set.await_args_list
        self.assertEqual(len(calls), 2) # set valid time and the result
        self.assertEqual(calls[0][0][1], 1769118100) # valid time
        self.assertEqual(calls[1][0][1], 1)       # result

    async def test_start_eq_now(self):
        self.fake_conn.fetchrow.return_value = {
            "start": datetime.datetime.fromtimestamp(1769118000.0, tz=config.TIMEZONE), 
            "end": datetime.datetime.fromtimestamp(1769118100.0, tz=config.TIMEZONE)
        }
        now = datetime.datetime.fromtimestamp(1769118000.0)
        with patch('datetime.datetime') as mock_now:
            mock_now.now.return_value = now
            res = await self.service.is_weekday_now()
        self.fake_conn.fetchrow.assert_awaited_once()
        self.assertTrue(res)
        calls = self.fake_rs.set.await_args_list
        self.assertEqual(len(calls), 2) # set valid time and the result
        self.assertEqual(calls[0][0][1], 1769118100) # valid time
        self.assertEqual(calls[1][0][1], 1)       # result

    async def test_start_gt_now(self):
        self.fake_conn.fetchrow.return_value = {
            "start": datetime.datetime.fromtimestamp(1769118000.0, tz=config.TIMEZONE), 
            "end": datetime.datetime.fromtimestamp(1769118100.0, tz=config.TIMEZONE)
        }
        now = datetime.datetime.fromtimestamp(1769117050.0)
        with patch('datetime.datetime') as mock_now:
            mock_now.now.return_value = now
            res = await self.service.is_weekday_now()
        self.fake_conn.fetchrow.assert_awaited_once()
        self.assertFalse(res)
        calls = self.fake_rs.set.await_args_list
        self.assertEqual(len(calls), 2) # set valid time and the result
        self.assertEqual(calls[0][0][1], 1769118000.0) # valid time
        self.assertEqual(calls[1][0][1], 0)       # result

    async def test_no_row(self):
        self.fake_conn.fetchrow.return_value = None
        res = await self.service.is_weekday_now()
        self.fake_conn.fetchrow.assert_awaited_once()
        self.assertFalse(res)
        calls = self.fake_rs.set.await_args_list
        self.assertEqual(len(calls), 2) # set valid time and the result
        self.assertEqual(calls[1][0][1], 0)       # result

    async def test_no_val(self):
        self.fake_conn.fetchrow.return_value = {}
        res = await self.service.is_weekday_now()
        self.fake_conn.fetchrow.assert_awaited_once()
        self.assertFalse(res)
        calls = self.fake_rs.set.await_args_list
        self.assertEqual(len(calls), 2) # set valid time and the result
        self.assertEqual(calls[1][0][1], 0)       # result

    async def test_cache_hit(self):
        self.fake_rs.get.side_effect = [b'1769118100', b'1']
        now = datetime.datetime.fromtimestamp(1769118050.0)
        with patch('datetime.datetime') as mock_now:
            mock_now.now.return_value = now
            res = await self.service.is_weekday_now()
        self.fake_conn.fetchrow.assert_not_awaited()
        self.assertTrue(res)

    async def test_cache_expired(self):
        self.fake_rs.get.side_effect = [b'1769117000', b'1']
        self.fake_conn.fetchrow.return_value = {
            "start": datetime.datetime.fromtimestamp(1769118000.0,tz=config.TIMEZONE), 
            "end": datetime.datetime.fromtimestamp(1769118100.0, tz=config.TIMEZONE)
        }
        now = datetime.datetime.fromtimestamp(1769117050.0)
        with patch('datetime.datetime') as mock_now:
            mock_now.now.return_value = now
            res = await self.service.is_weekday_now()
        self.fake_conn.fetchrow.assert_awaited_once()
        self.assertFalse(res)
        calls = self.fake_rs.set.await_args_list
        self.assertEqual(len(calls), 2) # set valid time and the result
        self.assertEqual(calls[0][0][1], 1769118000.0) # valid time
        self.assertEqual(calls[1][0][1], 0)       # result
