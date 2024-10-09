from tests.e2e.util import AsyncTest, AccountContext


class PublicProClassTest(AsyncTest):
    async def main(self):
        with AccountContext('admin@test', 'testtest') as admin_session:
            # add proclass
            res = admin_session.post('http://localhost:5501/manage/proclass/add', data={
                'reqtype': 'add',
                'name': 'test',
                'list': '1'
            })
            self.assertEqual(res.text, '1')

            html = self.get_html('http://localhost:5501/manage/proclass/update?pubclassid=1', admin_session)
            self.assertEqual(html.select_one('input#name').attrs.get('value'), 'test')
            self.assertEqual(html.select_one('input#list').attrs.get('value'), '1')

            html = self.get_html('http://localhost:5501/proset?pubclass_id=1', admin_session)
            trs = html.select('tr')[1:]
            self.assertEqual(len(trs), 1)

            res = admin_session.post('http://localhost:5501/manage/proclass/update', data={
                'reqtype': 'update',
                'pubclass_id': 1,
                'name': 'test',
                'list': '1, 2'
            })
            self.assertEqual(res.text, 'S')

            html = self.get_html('http://localhost:5501/manage/proclass/update?pubclassid=1', admin_session)
            self.assertEqual(html.select_one('input#name').attrs.get('value'), 'test')
            self.assertEqual(html.select_one('input#list').attrs.get('value'), '1, 2')

            html = self.get_html('http://localhost:5501/proset?pubclass_id=1', admin_session)
            trs = html.select('tr')[1:]
            self.assertEqual(len(trs), 2)

            res = admin_session.post('http://localhost:5501/manage/proclass/update', data={
                'reqtype': 'remove',
                'pubclass_id': 1,
            })
            self.assertEqual(res.text, 'S')

            res = admin_session.get('http://localhost:5501/proset?pubclass_id=1')
            self.assertEqual(res.text, 'Enoext')
