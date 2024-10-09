import requests

from .util import AsyncTest, AccountContext


class SignTest(AsyncTest):
    async def main(self):
        res = requests.post('http://localhost:5501/sign', data={
            'reqtype': 'signin',
            'mail': 'admin@test',
            'pw': 'test',
        })
        self.assertEqual(res.text, 'Esign')

        # signup but failed
        res = requests.post('http://localhost:5501/sign', data={
            'reqtype': 'signup',
            'name': 'test1',
            'mail': 'test1@test',
            'pw': 'test',
        })
        self.assertEqual(res.text, 'Eexist')
        async with self.db.acquire() as con:
            result = await con.fetch("SELECT last_value FROM account_acct_id_seq;")
            self.assertEqual(result[0]['last_value'], 2)


class AcctPageTest(AsyncTest):
    async def main(self):
        with AccountContext('admin@test', 'testtest') as admin_session:
            html = self.get_html('http://localhost:5501/acct/1', admin_session)
            trs = html.select_one('form#profile').select('tr')
            self.assertEqual(html.select_one('div#summary > h1').text, 'admin')
            self.assertEqual(trs[0].select('td')[1].text, '200')
            self.assertEqual(trs[1].select('td')[1].text, '2')
            self.assertEqual(trs[2].select('td')[1].text.strip().replace('\n', ''), '33.3%(3/9)')

        with AccountContext('test1@test', 'test') as user_session:
            html = self.get_html('http://localhost:5501/acctedit/2', user_session)
            self.assertIsNotNone(html.select_one('form#profile'))
            self.assertIsNotNone(html.select_one('form#reset'))

            res = user_session.post('http://localhost:5501/acctedit', data={
                'reqtype': 'profile',
                'acct_id': 2,
                'name': 'test1',
                'photo': 'https://static.zerochan.net/Takakura.Anzu.full.1658390.jpg',
                'cover': 'https://wallpaper.forfun.com/fetch/eb/eb9a621bbe1ceeb38a4387153a4376eb.jpeg',
            })
            self.assertEqual(res.text, 'S')

            html = self.get_html('http://localhost:5501/acct/2', user_session)
            trs = html.select_one('form#profile').select('tr')
            self.assertEqual(html.select_one('div#summary > h1').text, 'test1')
            self.assertEqual(html.select_one('script#contjs').attrs.get('photo'),
                             'https://static.zerochan.net/Takakura.Anzu.full.1658390.jpg')
            self.assertEqual(html.select_one('script#contjs').attrs.get('cover'),
                             'https://wallpaper.forfun.com/fetch/eb/eb9a621bbe1ceeb38a4387153a4376eb.jpeg')

            self.assertEqual(trs[0].select('td')[1].text, '0')
            self.assertEqual(trs[1].select('td')[1].text, '0')
            self.assertEqual(trs[2].select('td')[1].text.strip().replace('\n', ''), '0.0%(0/1)')

            # test update profile permission
            res = user_session.post('http://localhost:5501/acctedit', data={
                'reqtype': 'profile',
                'acct_id': 1,
                'name': 'test1',
                'photo': 'https://static.zerochan.net/Takakura.Anzu.full.1658390.jpg',
                'cover': 'https://wallpaper.forfun.com/fetch/eb/eb9a621bbe1ceeb38a4387153a4376eb.jpeg',
            })
            self.assertEqual(res.text, 'Eacces')
            html = self.get_html('http://localhost:5501/acct/1', user_session)
            self.assertEqual(html.select_one('div#summary > h1').text, 'admin')
            self.assertNotEqual(html.select_one('script#contjs').attrs.get('photo'),
                                'https://static.zerochan.net/Takakura.Anzu.full.1658390.jpg')
            self.assertNotEqual(html.select_one('script#contjs').attrs.get('cover'),
                                'https://wallpaper.forfun.com/fetch/eb/eb9a621bbe1ceeb38a4387153a4376eb.jpeg')

            # test change password
            res = user_session.post('http://localhost:5501/acctedit', data={
                'reqtype': 'reset',
                'acct_id': 2,
                'old': 'test',
                'pw': 'testtest'
            })
            self.assertEqual(res.text, 'S')

            # test change password permission
            res = user_session.post('http://localhost:5501/acctedit', data={
                'reqtype': 'reset',
                'acct_id': 1,
                'old': 'test',
                'pw': 'testtest'
            })
            self.assertEqual(res.text, 'Eacces')

        res = requests.post('http://localhost:5501/sign', data={
            'reqtype': 'signin',
            'mail': 'test1@test',
            'pw': 'test',
        })
        self.assertEqual(res.text, 'Esign')

        # test admin change password
        with AccountContext('admin@test', 'testtest') as admin_session:
            html = self.get_html('http://localhost:5501/acctedit/2', admin_session)
            self.assertIsNone(html.select_one('form#profile'))
            self.assertIsNotNone(html.select_one('form#reset'))

            res = admin_session.post('http://localhost:5501/acctedit', data={
                'reqtype': 'reset',
                'acct_id': 2,
                'old': '',
                'pw': 'test'
            })
            self.assertEqual(res.text, 'S')

        with AccountContext('test1@test', 'test') as user_session:
            html = self.get_html('http://localhost:5501/index/', user_session)
            self.assertIsNone(html.select_one('li.manage'))
            self.assertEqual(html.select_one('script#indexjs').attrs.get('acct_id'), '2')
