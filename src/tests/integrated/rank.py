from tests.integrated.util import AsyncTest, AccountContext
from services.pro import ProConst, CheckerType


class UserRankTest(AsyncTest):
    async def main(self):
        with AccountContext('admin@test', 'testtest') as admin_session:
            html = self.get_html('users', admin_session)
            first = html.select_one('tbody > tr')
            self.assertEqual(first.attrs['class'][0], 'rank-gold')
            self.assertEqual(first.select('td')[2].text, 'admin') # username
            self.assertEqual(first.select('td')[3].text, '') # motto
            self.assertEqual(first.select('td')[4].text, '2') # ac count
            self.assertEqual(first.select('td')[5].text.strip().replace('\n', ''), '33.33%(3/9)') # ac ratio


class ProRankTest(AsyncTest):
    async def main(self):
        with AccountContext('admin@test', 'testtest') as admin_session:
            html = self.get_html('rank/1', admin_session)
            first = html.select_one('tbody > tr')
            self.assertEqual(first.attrs['class'][0], 'rank-gold')
            self.assertEqual(first.select('td')[2].text, 'admin')

            admin_session.post('manage/pro/update', data={
                'reqtype': 'updategeneral',
                'pro_id': 1,
                'name': 'GCD',
                'status': ProConst.STATUS_HIDDEN,
                'tags': '',
                'allow_submit': 'true',
            })

            with AccountContext('test1@test', 'test') as user_session:
                res = user_session.get('rank/1')
                self.assertAPIReturnValue(res.text, ('Eacces', 'Permission denied'))

            admin_session.post('manage/pro/update', data={
                'reqtype': 'updategeneral',
                'pro_id': 1,
                'name': 'GCD',
                'status': ProConst.STATUS_ONLINE,
                'tags': '',
                'allow_submit': 'true',
            })
