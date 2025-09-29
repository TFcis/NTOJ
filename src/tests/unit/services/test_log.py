import unittest
import datetime
import json
from unittest.mock import AsyncMock, MagicMock
from services.log import LogService, _Encoder


class TestLogService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fake_conn = AsyncMock()

        fake_acquire_cm = MagicMock()
        fake_acquire_cm.__aenter__ = AsyncMock(return_value=self.fake_conn)
        fake_acquire_cm.__aexit__ = AsyncMock(return_value=None)

        self.fake_db = MagicMock()
        self.fake_db.acquire = MagicMock(return_value=fake_acquire_cm)

        self.service = LogService(self.fake_db, rs=None)

    async def test_add_log_with_dict_params(self):
        self.fake_conn.fetch.return_value = [{"log_id": 123}]

        params = {"key": "value"}
        err, log_id = await self.service.add_log("Test message", "info", params)

        self.fake_conn.fetch.assert_awaited_once()
        self.assertIsNone(err)
        self.assertEqual(log_id, 123)
        called_params = self.fake_conn.fetch.call_args[0][3]
        self.assertIsInstance(called_params, str)
        loaded_params = json.loads(called_params)
        self.assertEqual(loaded_params["key"], "value")

    async def test_add_log_with_none_params(self):
        self.fake_conn.fetch.return_value = [{"log_id": 456}]

        err, log_id = await self.service.add_log("Another message", "error", None)

        self.fake_conn.fetch.assert_awaited_once()
        self.assertIsNone(err)
        self.assertEqual(log_id, 456)
        called_params = self.fake_conn.fetch.call_args[0][3]
        self.assertIsNone(called_params)

    async def test_view_log_found(self):
        timestamp = datetime.datetime(
            2024, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc
        )
        self.fake_conn.fetch.return_value = [
            {
                "log_id": 789,
                "message": "Log message",
                "timestamp": timestamp,
                "params": '{"key": "value"}',
            }
        ]

        err, log = await self.service.view_log(789)

        self.fake_conn.fetch.assert_awaited_once()
        self.assertIsNone(err)
        self.assertEqual(log["log_id"], 789)
        self.assertEqual(log["message"], "Log message")
        self.assertEqual(log["timestamp"], timestamp)
        self.assertEqual(json.loads(log["params"])["key"], "value")

    async def test_view_log_not_found(self):
        self.fake_conn.fetch.return_value = []

        err, log = await self.service.view_log(999)

        self.fake_conn.fetch.assert_awaited_once()
        self.assertIsNotNone(err)
        self.assertIsNone(log)
        self.assertEqual(err, ("Enoext", "Log not found"))

    async def test_list_log_no_type(self):
        self.fake_conn.fetch.side_effect = [
            [
                (
                    1,
                    "Msg1",
                    datetime.datetime(
                        2024, 1, 1, 10, 0, 0, tzinfo=datetime.timezone.utc
                    ),
                ),
                (
                    2,
                    "Msg2",
                    datetime.datetime(
                        2024, 1, 1, 11, 0, 0, tzinfo=datetime.timezone.utc
                    ),
                ),
            ],
            [{"count": 2}],
        ]

        err, ret = await self.service.list_log(0, 10)
        logs = ret["loglist"]
        count = ret["lognum"]

        self.fake_conn.fetch.assert_called()
        self.assertEqual(self.fake_conn.fetch.call_count, 2)
        self.assertIsNone(err)
        self.assertEqual(len(logs), 2)
        self.assertEqual(len(logs), count)
        self.assertEqual(logs[0]["log_id"], 1)
        self.assertEqual(logs[1]["log_id"], 2)
        self.assertEqual(logs[0]["message"], "Msg1")
        self.assertEqual(logs[1]["message"], "Msg2")

    async def test_get_log_types(self):
        self.fake_conn.fetch.side_effect = [
            [
                {"type": "info"},
                {"type": "error"},
            ]
        ]
        err, types = await self.service.get_log_type()
        self.assertIsNone(err)

        self.fake_conn.fetch.assert_awaited_once()
        self.assertEqual(types, ["info", "error"])

    def test_encoder_datetime(self):
        dt = datetime.datetime(2024, 6, 1, 12, 0, tzinfo=datetime.timezone.utc)
        encoded = json.dumps({"dt": dt}, cls=_Encoder)
        self.assertIn("+00:00", encoded)


if __name__ == "__main__":
    unittest.main()

