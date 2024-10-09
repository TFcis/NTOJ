import datetime

from services.board import BoardConst
from .util import AsyncTest, AccountContext


class BoardTest(AsyncTest):
    async def main(self):
        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.post('http://localhost:5501/manage/board/add', data={
                'reqtype': 'add',
                'name': 'board1',
                'status': BoardConst.STATUS_ONLINE,
                'start': self.get_isoformat(datetime.datetime.now() - datetime.timedelta(days=7)),
                'end': self.get_isoformat(datetime.datetime.now() + datetime.timedelta(days=7)),
                'pro_list': '1, 2',
                'acct_list': '1',
            })
            self.assertEqual(res.text, 'S')

            html = self.get_html('http://localhost:5501/manage/board', admin_session)
            self.assertEqual(len(html.select('tr')[1:]), 1)
            tr0 = html.select('tr')[1]
            self.assertEqual(tr0.select('td')[0].text.strip(), 'board1')
            self.assertEqual(tr0.select('td')[1].text.strip(), 'Online')

            html = self.get_html('http://localhost:5501/manage/board/update?boardid=1', admin_session)
            self.assertEqual(html.select_one('input#name').attrs.get('value').strip(), 'board1')
            self.assertIsNotNone(html.select('option')[0].attrs.get('selected'))
            self.assertEqual(html.select_one('input#datepickerStartInput').attrs.get('value'),
                             (datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%Y/%m/%d %H:%M'))
            self.assertEqual(html.select_one('input#datepickerEndInput').attrs.get('value'),
                             (datetime.datetime.now() + datetime.timedelta(days=7)).strftime('%Y/%m/%d %H:%M'))
            self.assertEqual(html.select_one('input#pro_list').attrs.get('value').strip(), '1,2')
            self.assertEqual(html.select_one('input#acct_list').attrs.get('value').strip(), '1')

            html = self.get_html('http://localhost:5501/board/1', admin_session)
            self.assertEqual(html.select('th._pro')[0].text, '1')
            self.assertEqual(html.select('th._pro')[1].text, '2')
            tr0 = html.select('tbody > tr')[0]
            self.assertEqual(tr0.select_one('td._rank').text.strip(), '1')
            self.assertEqual(tr0.select_one('td._acct').text.strip(), 'admin')
            self.assertEqual(tr0.select_one('td._score').text.strip(), '200 / 9')
            self.assertEqual(tr0.select('td._pro')[0].text, '100 / 8')
            self.assertEqual(tr0.select('td._pro')[0].attrs['class'][1], '_state-10')
            self.assertEqual(tr0.select('td._pro')[1].text, '100 / 1')
            self.assertEqual(tr0.select('td._pro')[1].attrs['class'][1], '_state-10')

            # board list
            html = self.get_html('http://localhost:5501/board', admin_session)
            self.assertEqual(len(html.select('tr')[1:]), 1)
            self.assertEqual(html.select('tr')[1:][0].select('td')[1].text.strip(), 'Online')

            res = admin_session.post('http://localhost:5501/manage/board/update', data={
                'reqtype': 'update',
                'board_id': 1,
                'name': 'board1',
                'status': BoardConst.STATUS_ONLINE,
                'start': self.get_isoformat(datetime.datetime.now() - datetime.timedelta(days=14)),
                'end': self.get_isoformat(datetime.datetime.now() - datetime.timedelta(days=7)),
                'pro_list': '1, 2',
                'acct_list': '1',
            })
            self.assertEqual(res.text, 'S')

            html = self.get_html('http://localhost:5501/board', admin_session)
            self.assertEqual(len(html.select('tr')[1:]), 1)
            self.assertEqual(html.select('tr')[1:][0].select('td')[1].text.strip(), 'Over')
            html = self.get_html('http://localhost:5501/board/1', admin_session)
            self.assertEqual(html.select('th._pro')[0].text, '1')
            self.assertEqual(html.select('th._pro')[1].text, '2')
            tr0 = html.select('tbody > tr')[0]
            self.assertEqual(tr0.select_one('td._rank').text.strip(), '1')
            self.assertEqual(tr0.select_one('td._acct').text.strip(), 'admin')
            self.assertEqual(tr0.select_one('td._score').text.strip(), '0 / 0')
            self.assertEqual(tr0.select('td._pro')[0].text.strip(), '')
            self.assertEqual(tr0.select('td._pro')[1].text.strip(), '')

            res = admin_session.post('http://localhost:5501/manage/board/update', data={
                'reqtype': 'remove',
                'board_id': 1,
            })
            self.assertEqual(res.text, 'S')

            res = admin_session.get('http://localhost:5501/board/1')
            self.assertEqual(res.text, 'Enoext')
