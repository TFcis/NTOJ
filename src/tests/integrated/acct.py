from decimal import Decimal
import hashlib
import requests

from services.chal import ChalConst
from services.user import UserService
from services.rate import RateService

from .util import AsyncTest, AccountContext


class SignTest(AsyncTest):
    async def main(self):
        res = requests.post('http://localhost:5501/be/sign', data={
            'reqtype': 'signin',
            'mail': 'admin@test',
            'pw': 'test',
        })
        self.assertAPIReturnValue(res.text, ('Esign', 'Login failed'))

        # signup but failed
        res = requests.post('http://localhost:5501/be/sign', data={
            'reqtype': 'signup',
            'name': 'test1',
            'mail': 'test1@test',
            'pw': 'test',
        })
        self.assertAPIReturnValue(res.text, ('Eexist', 'Account already exists'))
        async with UserService.inst.db.acquire() as con:
            result = await con.fetch("SELECT last_value FROM account_acct_id_seq;")
            self.assertEqual(result[0]['last_value'], 2)


class AcctPageTest(AsyncTest):
    async def main(self):
        with AccountContext('admin@test', 'testtest') as admin_session:
            err, acct = await UserService.inst.info_acct(1)
            self.assertIsNone(err)
            assert acct
            err, acctrate = await RateService.inst.get_acct_rate_and_chal_cnt(acct)
            self.assertEqual(acctrate, {'rate': Decimal('200'), 'ac_cnt': 3, 'all_cnt': 9})
            self.assertIsNone(err)

            err, ratemap = await RateService.inst.map_rate_acct(acct)
            self.assertEqual(sum(1 if v['state'] == ChalConst.STATE_AC else 0 for v in ratemap.values()), 2)
            self.assertIsNone(err)

        with AccountContext('test1@test', 'test') as user_session:
            res = user_session.post('acctedit', data={
                'reqtype': 'profile',
                'acct_id': 2,
                'name': 'test1',
                'photo': 'https://static.zerochan.net/Takakura.Anzu.full.1658390.jpg',
                'cover': 'https://wallpaper.forfun.com/fetch/eb/eb9a621bbe1ceeb38a4387153a4376eb.jpeg',
                'motto': 'motto test',
            })
            self.assertAPIReturnSuccess(res.text)
            err, acct = await UserService.inst.info_acct(2)
            self.assertIsNone(err)
            assert acct
            self.assertEqual(acct.name, 'test1')
            self.assertEqual(acct.photo, 'https://static.zerochan.net/Takakura.Anzu.full.1658390.jpg')
            self.assertEqual(acct.cover, 'https://wallpaper.forfun.com/fetch/eb/eb9a621bbe1ceeb38a4387153a4376eb.jpeg')
            self.assertEqual(acct.motto, 'motto test')

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
            err, acct = await UserService.inst.info_acct(1)
            self.assertIsNone(err)
            assert acct
            self.assertNotEqual(acct.photo, 'https://static.zerochan.net/Takakura.Anzu.full.1658390.jpg')
            self.assertNotEqual(acct.cover, 'https://wallpaper.forfun.com/fetch/eb/eb9a621bbe1ceeb38a4387153a4376eb.jpeg')
            self.assertNotEqual(acct.motto, 'motto test')

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

        res = requests.post('http://localhost:5501/be/sign', data={
            'reqtype': 'signin',
            'mail': 'test1@test',
            'pw': 'test',
        })
        self.assertAPIReturnValue(res.text, ('Esign', 'Login failed'))

        # test admin change password
        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.post('acctedit', data={
                'reqtype': 'reset',
                'acct_id': 2,
                'old': '',
                'pw': 'test'
            })
            self.assertAPIReturnSuccess(res.text)

        with AccountContext('test1@test', 'test') as user_session:
            pass

        # # TODO: session
        # with AccountContext('admin@test', 'testtest') as admin_session:
        #     html = self.get_html('acctedit/2', admin_session)
        #     self.assertIsNone(html.select_one('form#login-list'))
        #
        #     html = self.get_html('acctedit/1', admin_session)
        #     self.assertIsNotNone('form#login-list')
        #
        #     trs = html.select('#loginlist > tbody > tr')
        #     self.assertEqual(len(trs), 1)
        #
        #     self.assertIn('Current device', trs[0].select('td')[0].get_text().strip())
        #     self.assertEqual(trs[0].select('td')[3].select_one('button').attrs['hashed_session_key'],
        #                      hashlib.md5(admin_session.cookies['id'].strip('"').encode()).hexdigest())
        #
        #     with AccountContext('admin@test', 'testtest') as admin2_session:
        #         html = self.get_html('acctedit/1', admin_session)
        #         trs = html.select('#loginlist > tbody > tr')
        #         self.assertEqual(len(trs), 2)
        #
        #         res = admin_session.post('acctedit', data={
        #             'reqtype': 'remote-logout',
        #             'acct_id': 1,
        #             'hashed_session_key': hashlib.md5(admin2_session.cookies['id'].strip('"').encode()).hexdigest()
        #         })
        #         self.assertAPIReturnSuccess(res.text)
        #
        #         res = admin2_session.get('acctedit/1')
        #         self.assertIn("You don't have permission.", res.text.strip())
        #
        #         html = self.get_html('acctedit/1', admin_session)
        #         trs = html.select('#loginlist > tbody > tr')
        #         self.assertEqual(len(trs), 1)
