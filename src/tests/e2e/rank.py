from tests.e2e.util import AsyncTest, AccountContext


class UserRankTest(AsyncTest):
    async def main(self):
        with AccountContext('admin@test', 'testtest') as admin_session:
            html = self.get_html('http://localhost:5501/users', admin_session)
            first = html.select_one('tbody > tr')
            self.assertEqual(first.attrs['class'][0], 'rank-gold')
            self.assertEqual(first.select('td')[2].text, 'admin')
            self.assertEqual(first.select('td')[3].text, '2')
            self.assertEqual(first.select('td')[4].text.strip().replace('\n', ''), '33.33%(3/9)')


class ProRankTest(AsyncTest):
    async def main(self):
        with AccountContext('admin@test', 'testtest') as admin_session:
            html = self.get_html('http://localhost:5501/rank/1', admin_session)
            first = html.select_one('tbody > tr')
            self.assertEqual(first.attrs['class'][0], 'rank-gold')
            self.assertEqual(first.select('td')[2].text, 'admin')
