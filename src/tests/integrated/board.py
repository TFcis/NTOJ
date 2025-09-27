import datetime

from services.board import BoardService, BoardConst
from .util import AsyncTest, AccountContext


class BoardTest(AsyncTest):
    async def main(self):
        now = datetime.datetime.now()
        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.post('manage/board/add', data={
                'reqtype': 'add',
                'name': 'board1',
                'status': BoardConst.STATUS_ONLINE,
                'start': self.get_isoformat(now - datetime.timedelta(days=7)),
                'end': self.get_isoformat(now + datetime.timedelta(days=7)),
                'pro_list': '1, 2',
                'acct_list': '1',
            })
            print(self.get_isoformat(now - datetime.timedelta(days=7)))
            self.assertAPIReturnSuccess(res.text)

            err, boardlist = await BoardService.inst.get_boardlist()
            self.assertIsNone(err)
            self.assertEqual(len(boardlist), 1)
            self.assertEqual(boardlist[0]['name'], 'board1')
            self.assertEqual(boardlist[0]['status'], BoardConst.STATUS_ONLINE)
            # self.assertEqual(boardlist[0]['start'], (now - datetime.timedelta(days=7)).replace(tzinfo=datetime.timezone.utc))
            # self.assertEqual(boardlist[0]['end'], (now + datetime.timedelta(days=7)).replace(tzinfo=datetime.timezone.utc))

            err, board = await BoardService.inst.get_board(1)
            self.assertIsNone(err)
            assert board
            self.assertEqual(board['name'], 'board1')
            self.assertEqual(board['status'], BoardConst.STATUS_ONLINE)
            # self.assertEqual(board['start'], (now - datetime.timedelta(days=7)).replace(tzinfo=datetime.timezone.utc))
            # self.assertEqual(board['end'], (now + datetime.timedelta(days=7)).replace(tzinfo=datetime.timezone.utc))
            self.assertEqual(board['pro_list'], [1, 2])
            self.assertEqual(board['acct_list'], [1])

            res = admin_session.post('manage/board/update', data={
                'reqtype': 'update',
                'board_id': 1,
                'name': 'board1',
                'status': BoardConst.STATUS_HIDDEN,
                'start': self.get_isoformat(now - datetime.timedelta(days=14)),
                'end': self.get_isoformat(now - datetime.timedelta(days=7)),
                'pro_list': '1, 2',
                'acct_list': '1',
            })
            self.assertAPIReturnSuccess(res.text)

            err, board = await BoardService.inst.get_board(1)
            self.assertIsNone(err)
            assert board
            self.assertEqual(board['name'], 'board1')
            self.assertEqual(board['status'], BoardConst.STATUS_HIDDEN)
            # self.assertEqual(board['start'], (now - datetime.timedelta(days=14)).replace(tzinfo=datetime.timezone.utc))
            # self.assertEqual(board['end'], (now - datetime.timedelta(days=7)).replace(tzinfo=datetime.timezone.utc))
            self.assertEqual(board['pro_list'], [1, 2])
            self.assertEqual(board['acct_list'], [1])

            res = admin_session.post('manage/board/update', data={
                'reqtype': 'remove',
                'board_id': 1,
            })
            self.assertAPIReturnSuccess(res.text)
            err, board = await BoardService.inst.get_board(1)
            self.assertEqual(err, ('Enoext', 'Board not found'))
