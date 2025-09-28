import unittest
import datetime
from unittest.mock import AsyncMock, MagicMock
from services.board import BoardService, BoardConst

class TestBoardService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.fake_conn = AsyncMock()

        fake_acquire_cm = MagicMock()
        fake_acquire_cm.__aenter__ = AsyncMock(return_value=self.fake_conn)
        fake_acquire_cm.__aexit__ = AsyncMock(return_value=None)

        self.fake_db = MagicMock()
        self.fake_db.acquire = MagicMock(return_value=fake_acquire_cm)

        self.service = BoardService(self.fake_db, rs=None)

    async def test_get_boardlist(self):
        self.fake_conn.fetch.return_value = [
            {"board_id": 1, "name": "A", "status": 0, "start": datetime.datetime(2024, 1, 1, 8, 0), "end": datetime.datetime(2024, 1, 2, 8, 0)},
            {"board_id": 2, "name": "B", "status": 1, "start": datetime.datetime(2024, 2, 1, 8, 0), "end": datetime.datetime(2024, 2, 2, 8, 0)},
        ]
        err, res = await self.service.get_boardlist()
        self.fake_conn.fetch.assert_awaited_once()
        self.assertIsNone(err)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["board_id"], 1)
        self.assertEqual(res[1]["name"], "B")

    async def test_get_board_found(self):
        start = datetime.datetime(2024, 1, 1, 8, 0)
        end = datetime.datetime(2024, 1, 2, 8, 0)
        self.fake_conn.fetchrow.return_value = {
            "name": "BoardA",
            "status": BoardConst.STATUS_ONLINE,
            "start": start,
            "end": end,
            "pro_list": [1, 2],
            "acct_list": [3, 4],
        }
        err, meta = await self.service.get_board(1)
        self.fake_conn.fetchrow.assert_awaited_once()
        self.assertIsNone(err)
        self.assertIsNotNone(meta)
        self.assertEqual(meta["name"], "BoardA")
        self.assertEqual(meta["status"], BoardConst.STATUS_ONLINE)
        self.assertEqual(meta["pro_list"], [1, 2])
        self.assertEqual(meta["acct_list"], [3, 4])
        self.assertEqual(meta["start"], start)
        self.assertEqual(meta["end"], end)

    async def test_get_board_not_found(self):
        self.fake_conn.fetchrow.return_value = None
        err, meta = await self.service.get_board(999)
        self.fake_conn.fetchrow.assert_awaited_once()
        self.assertIsNotNone(err)
        self.assertIsNone(meta)
        self.assertEqual(err, ('Enoext', BoardService.BOARD_NOT_FOUND))

    async def test_add_board_success(self):
        self.fake_conn.fetch.return_value = [{"board_id": 10}]
        err, board_id = await self.service.add_board("NewBoard", 0, datetime.datetime(2024, 1, 1), datetime.datetime(2024, 1, 2), [2, 1], [4, 3])
        self.fake_conn.fetch.assert_awaited_once()
        self.assertIsNone(err)
        self.assertEqual(board_id, 10)

    async def test_add_board_fail(self):
        self.fake_conn.fetch.return_value = []
        err, board_id = await self.service.add_board("NewBoard", 0, datetime.datetime(2024, 1, 1), datetime.datetime(2024, 1, 2), [], [])
        self.fake_conn.fetch.assert_awaited_once()
        self.assertIsNotNone(err)
        self.assertIsNone(board_id)
        self.assertEqual(err[0], 'Eunk')

    async def test_update_board_success(self):
        self.fake_conn.fetch.return_value = [{"board_id": 1}]
        err, _ = await self.service.update_board(1, "Upd", 1, datetime.datetime(2024, 1, 1), datetime.datetime(2024, 1, 2), [1], [2])
        self.fake_conn.fetch.assert_awaited_once()
        self.assertIsNone(err)

    async def test_update_board_not_found(self):
        self.fake_conn.fetch.return_value = []
        err, _ = await self.service.update_board(999, "Upd", 1, datetime.datetime(2024, 1, 1), datetime.datetime(2024, 1, 2), [], [])
        self.fake_conn.fetch.assert_awaited_once()
        self.assertIsNotNone(err)
        self.assertEqual(err, ('Enoext', BoardService.BOARD_NOT_FOUND))

    async def test_remove_board_success(self):
        self.fake_conn.execute.return_value = "DELETE 1"
        err, _ = await self.service.remove_board(1)
        self.fake_conn.execute.assert_awaited_once()
        self.assertIsNone(err)

    async def test_remove_board_not_found(self):
        self.fake_conn.execute.return_value = "DELETE 0"
        err, _ = await self.service.remove_board(999)
        self.fake_conn.execute.assert_awaited_once()
        self.assertIsNotNone(err)
        self.assertEqual(err, ('Enoext', BoardService.BOARD_NOT_FOUND))

if __name__ == '__main__':
    unittest.main()
