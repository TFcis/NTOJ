import datetime

from services.board import BoardConst
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
            self.assertAPIReturnSuccess(res.text)

            html = self.get_html('manage/board', admin_session)
            self.assertEqual(len(html.select('tr')[1:]), 1)
            tr0 = html.select('tr')[1]
            self.assertEqual(tr0.select('td')[0].text.strip(), 'board1')
            self.assertEqual(tr0.select('td')[1].text.strip(), 'Online')

            html = self.get_html('manage/board/update?boardid=1', admin_session)
            self.assertEqual(html.select_one('input#name').attrs.get('value').strip(), 'board1')
            self.assertIsNotNone(html.select('option')[0].attrs.get('selected'))
            self.assertEqual(html.select_one('input#datepickerStartInput').attrs.get('value'),
                             (now - datetime.timedelta(days=7)).strftime('%Y/%m/%d %H:%M'))
            self.assertEqual(html.select_one('input#datepickerEndInput').attrs.get('value'),
                             (now + datetime.timedelta(days=7)).strftime('%Y/%m/%d %H:%M'))
            self.assertEqual(html.select_one('input#pro_list').attrs.get('value').strip(), '1-2')
            self.assertEqual(html.select_one('input#acct_list').attrs.get('value').strip(), '1')

            html = self.get_html('board/1', admin_session)
            self.assertEqual(html.select('th._pro')[0].text, '1')
            self.assertEqual(html.select('th._pro')[1].text, '2')
            tr0 = html.select('tbody > tr')[0]
            self.assertEqual(tr0.attrs['style'], '--bs-table-bg: #123456;')
            self.assertEqual(tr0.select_one('td._rank').text.strip(), '1')
            self.assertEqual(tr0.select_one('td._acct').text.strip(), 'admin')
            self.assertEqual(tr0.select_one('td._score').text.strip(), '200 / 9')
            self.assertEqual(tr0.select('td._pro')[0].text, '100 / 8')
            self.assertEqual(tr0.select('td._pro')[0].attrs['class'][1], '_state-10')
            self.assertEqual(tr0.select('td._pro')[1].text, '100 / 1')
            self.assertEqual(tr0.select('td._pro')[1].attrs['class'][1], '_state-10')

            # board list
            html = self.get_html('board', admin_session)
            trs = html.select('tr')
            self.assertEqual(trs[0].select('th')[2].text.strip(), 'Expire Status')
            self.assertEqual(trs[0].select('th')[3].text.strip(), 'Public Status')
            self.assertEqual(len(trs[1:]), 1)
            self.assertEqual(trs[1:][0].select('td')[1].text.strip(), 'Online')
            self.assertEqual(trs[1:][0].select('td')[2].text.strip(), 'Public')

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

            html = self.get_html('board', admin_session)
            trs = html.select('tr')
            self.assertEqual(len(trs[1:]), 1)
            self.assertEqual(trs[1:][0].select('td')[1].text.strip(), 'Over')
            self.assertEqual(trs[1:][0].select('td')[2].text.strip(), 'Hidden')

            with AccountContext('test1@test', 'test') as user_session:
                # only show STATUS_ONLINE board for normal user
                html = self.get_html('board', user_session)
                trs = html.select('tr')
                self.assertEqual(trs[0].select('th')[2].text.strip(), 'Expire Status')
                self.assertEqual(len(trs[0].select('th')), 3)
                self.assertEqual(len(trs[1:]), 0)

                res = user_session.get('board/1')
                self.assertAPIReturnValue(res.text, ('Eacces', 'Permission denied'))

            html = self.get_html('board/1', admin_session)
            self.assertEqual(html.select('th._pro')[0].text, '1')
            self.assertEqual(html.select('th._pro')[1].text, '2')
            tr0 = html.select('tbody > tr')[0]
            self.assertEqual(tr0.select_one('td._rank').text.strip(), '1')
            self.assertEqual(tr0.select_one('td._acct').text.strip(), 'admin')
            self.assertEqual(tr0.select_one('td._score').text.strip(), '0 / 0')
            self.assertEqual(tr0.select('td._pro')[0].text.strip(), '')
            self.assertEqual(tr0.select('td._pro')[1].text.strip(), '')

            res = admin_session.post('manage/board/update', data={
                'reqtype': 'remove',
                'board_id': 1,
            })
            self.assertAPIReturnSuccess(res.text)

            res = admin_session.get('board/1')
            self.assertAPIReturnValue(res.text, ('Enoext', 'Board not found'))
