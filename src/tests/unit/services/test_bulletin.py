import unittest
import datetime
from unittest.mock import AsyncMock, MagicMock
from services.bulletin import BulletinService

class TestBulletinService(unittest.IsolatedAsyncioTestCase):
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

        self.service = BulletinService(self.fake_db, rs=None)

    async def test_list_bulletin(self):
        self.fake_conn.fetch.return_value = [
            (1, "Title1", datetime.datetime(2024, 1, 1, 10, 0), "Red", True, "Alice", 101),
            (2, "Title2", datetime.datetime(2024, 1, 2, 11, 0), "Blue", False, "Bob", 102),
        ]
        err, res = await self.service.list_bulletin()
        self.fake_conn.fetch.assert_awaited_once()
        self.assertIsNone(err)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["bulletin_id"], 1)
        self.assertEqual(res[1]["title"], "Title2")

    async def test_get_bulletin_found(self):
        dt = datetime.datetime(2024, 1, 1, 12, 0)
        self.fake_conn.fetch.return_value = [{
            "title": "TitleA",
            "content": "ContentA",
            "timestamp": dt,
            "name": "Alice",
            "color": "Green",
            "pinned": True,
            "acct_id": 101,
        }]
        err, meta = await self.service.get_bulletin(1)
        self.fake_conn.fetch.assert_awaited_once()
        self.assertIsNone(err)
        self.assertEqual(meta["title"], "TitleA")
        self.assertEqual(meta["content"], "ContentA")
        self.assertEqual(meta["name"], "Alice")
        self.assertEqual(meta["color"], "Green")
        self.assertTrue(meta["pinned"])
        self.assertEqual(meta["acct_id"], 101)

    async def test_get_bulletin_not_found(self):
        self.fake_conn.fetch.return_value = []
        err, meta = await self.service.get_bulletin(999)
        self.fake_conn.fetch.assert_awaited_once()
        self.assertIsNotNone(err)
        self.assertIsNone(meta)
        self.assertEqual(err, ('Enoext', BulletinService.BULLETIN_NOT_FOUND))

    async def test_add_bulletin_success(self):
        self.fake_conn.fetch.return_value = [{"bulletin_id": 10}]
        err, bulletin_id = await self.service.add_bulletin("Title", "Content", 101, color="Yellow", pinned=True)
        self.fake_conn.fetch.assert_awaited_once()
        self.assertIsNone(err)
        self.assertEqual(bulletin_id, 10)

    async def test_add_bulletin_fail(self):
        self.fake_conn.fetch.return_value = []
        err, bulletin_id = await self.service.add_bulletin("Title", "Content", 101)
        self.fake_conn.fetch.assert_awaited_once()
        self.assertIsNotNone(err)
        self.assertIsNone(bulletin_id)
        self.assertEqual(err[0], 'Eunk')

    async def test_edit_bulletin_success(self):
        self.fake_conn.fetch.return_value = [{"bulletin_id": 1}]
        err, _ = await self.service.edit_bulletin(1, "UpdTitle", "UpdContent", 101, "Red", False)
        self.fake_conn.fetch.assert_awaited_once()
        self.assertIsNone(err)

    async def test_edit_bulletin_fail(self):
        self.fake_conn.fetch.return_value = []
        err, _ = await self.service.edit_bulletin(999, "UpdTitle", "UpdContent", 101, "Red", False)
        self.fake_conn.fetch.assert_awaited_once()
        self.assertIsNotNone(err)
        self.assertIsNone(_)
        self.assertEqual(err[0], 'Eunk')

    async def test_del_bulletin_success(self):
        self.fake_conn.execute.return_value = "DELETE 1"
        err, _ = await self.service.del_bulletin(1)
        self.fake_conn.execute.assert_awaited_once()
        self.assertIsNone(err)

    async def test_del_bulletin_not_found(self):
        self.fake_conn.execute.return_value = "DELETE 0"
        err, _ = await self.service.del_bulletin(999)
        self.fake_conn.execute.assert_awaited_once()
        self.assertIsNotNone(err)
        self.assertIsNone(_)
        self.assertEqual(err, ('Enoext', BulletinService.BULLETIN_NOT_FOUND))

if __name__ == '__main__':
    unittest.main()
