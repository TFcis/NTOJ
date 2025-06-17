import hashlib
import requests

from .util import AsyncTest, AccountContext


class SignTest(AsyncTest):
    async def main(self):
        res = requests.post('http://localhost:5501/sign', data={
            'reqtype': 'signin',
            'mail': 'admin@test',
            'pw': 'test',
        })
        self.assertAPIReturnValue(res.text, ('Esign', 'Login failed'))

        # signup but failed
        res = requests.post('http://localhost:5501/sign', data={
            'reqtype': 'signup',
            'name': 'test1',
            'mail': 'test1@test',
            'pw': 'test',
        })
        self.assertAPIReturnValue(res.text, ('Eexist', 'Account already exists'))
        async with self.db.acquire() as con:
            result = await con.fetch("SELECT last_value FROM account_acct_id_seq;")
            self.assertEqual(result[0]['last_value'], 2)


class AcctPageTest(AsyncTest):
    async def main(self):
        with AccountContext('admin@test', 'testtest') as admin_session:
            html = self.get_html('acct/1', admin_session)
            trs = html.select_one('form#profile').select('tr')
            self.assertEqual(html.select_one('div#summary > h1').text, 'admin')
            self.assertEqual(trs[0].select('td')[1].text, '200')
            self.assertEqual(trs[1].select('td')[1].text, '2')
            self.assertEqual(trs[2].select('td')[1].text.strip().replace('\n', ''), '33.3%(3/9)')

        with AccountContext('test1@test', 'test') as user_session:
            html = self.get_html('acctedit/2', user_session)
            self.assertIsNotNone(html.select_one('form#profile'))
            self.assertIsNotNone(html.select_one('form#reset'))

            res = user_session.post('acctedit', data={
                'reqtype': 'profile',
                'acct_id': 2,
                'name': 'test1',
                'photo': 'https://static.zerochan.net/Takakura.Anzu.full.1658390.jpg',
                'cover': 'https://wallpaper.forfun.com/fetch/eb/eb9a621bbe1ceeb38a4387153a4376eb.jpeg',
                'motto': 'motto test',
            })
            self.assertAPIReturnSuccess(res.text)

            html = self.get_html('acct/2', user_session)
            trs = html.select_one('form#profile').select('tr')
            self.assertEqual(html.select_one('div#summary > h1').text, 'test1')
            self.assertEqual(html.select_one('script#contjs').attrs.get('photo'),
                             'https://static.zerochan.net/Takakura.Anzu.full.1658390.jpg')
            self.assertEqual(html.select_one('script#contjs').attrs.get('cover'),
                             'https://wallpaper.forfun.com/fetch/eb/eb9a621bbe1ceeb38a4387153a4376eb.jpeg')
            self.assertEqual(html.select_one('p').text, 'motto test')

            self.assertEqual(trs[0].select('td')[1].text, '0')
            self.assertEqual(trs[1].select('td')[1].text, '0')
            self.assertEqual(trs[2].select('td')[1].text.strip().replace('\n', ''), '0.0%(0/1)')

            # test update profile permission
            res = user_session.post('acctedit', data={
                'reqtype': 'profile',
                'acct_id': 1,
                'name': 'test1',
                'photo': 'https://static.zerochan.net/Takakura.Anzu.full.1658390.jpg',
                'cover': 'https://wallpaper.forfun.com/fetch/eb/eb9a621bbe1ceeb38a4387153a4376eb.jpeg',
                'motto': 'motto test',
            })
            self.assertAPIReturnValue(res.text , ('Eacces', 'Permission denied'))
            html = self.get_html('acct/1', user_session)
            self.assertEqual(html.select_one('div#summary > h1').text, 'admin')
            self.assertNotEqual(html.select_one('script#contjs').attrs.get('photo'),
                                'https://static.zerochan.net/Takakura.Anzu.full.1658390.jpg')
            self.assertNotEqual(html.select_one('script#contjs').attrs.get('cover'),
                                'https://wallpaper.forfun.com/fetch/eb/eb9a621bbe1ceeb38a4387153a4376eb.jpeg')
            self.assertNotEqual(html.select_one('p').text, 'motto test')

            # test change password
            res = user_session.post('acctedit', data={
                'reqtype': 'reset',
                'acct_id': 2,
                'old': 'test',
                'pw': 'testtest'
            })
            self.assertAPIReturnSuccess(res.text)

            # test change password permission
            res = user_session.post('acctedit', data={
                'reqtype': 'reset',
                'acct_id': 1,
                'old': 'test',
                'pw': 'testtest'
            })
            self.assertAPIReturnValue(res.text , ('Eacces', 'Permission denied'))

        res = requests.post('http://localhost:5501/sign', data={
            'reqtype': 'signin',
            'mail': 'test1@test',
            'pw': 'test',
        })
        self.assertAPIReturnValue(res.text, ('Esign', 'Login failed'))

        # test admin change password
        with AccountContext('admin@test', 'testtest') as admin_session:
            html = self.get_html('acctedit/2', admin_session)
            self.assertIsNone(html.select_one('form#profile'))
            self.assertIsNotNone(html.select_one('form#reset'))

            res = admin_session.post('acctedit', data={
                'reqtype': 'reset',
                'acct_id': 2,
                'old': '',
                'pw': 'test'
            })
            self.assertAPIReturnSuccess(res.text)

        with AccountContext('test1@test', 'test') as user_session:
            html = self.get_html('index/', user_session)
            self.assertIsNone(html.select_one('li.manage'))
            self.assertEqual(html.select_one('script#indexjs').attrs.get('acct_id'), '2')

        # test session
        with AccountContext('admin@test', 'testtest') as admin_session:
            html = self.get_html('acctedit/2', admin_session)
            self.assertIsNone(html.select_one('form#login-list'))

            html = self.get_html('acctedit/1', admin_session)
            self.assertIsNotNone('form#login-list')

            trs = html.select('#loginlist > tbody > tr')
            self.assertEqual(len(trs), 1)

            self.assertIn('Current device', trs[0].select('td')[0].get_text().strip())
            self.assertEqual(trs[0].select('td')[3].select_one('button').attrs['hashed_session_key'],
                             hashlib.md5(admin_session.cookies['id'].strip('"').encode()).hexdigest())

            with AccountContext('admin@test', 'testtest') as admin2_session:
                html = self.get_html('acctedit/1', admin_session)
                trs = html.select('#loginlist > tbody > tr')
                self.assertEqual(len(trs), 2)

                res = admin_session.post('acctedit', data={
                    'reqtype': 'remote-logout',
                    'acct_id': 1,
                    'hashed_session_key': hashlib.md5(admin2_session.cookies['id'].strip('"').encode()).hexdigest()
                })
                self.assertAPIReturnSuccess(res.text)

                res = admin2_session.get('acctedit/1')
                self.assertIn("You don't have permission.", res.text.strip())

                html = self.get_html('acctedit/1', admin_session)
                trs = html.select('#loginlist > tbody > tr')
                self.assertEqual(len(trs), 1)
