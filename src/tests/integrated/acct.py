from decimal import Decimal
import hashlib
import requests
import datetime

from services.chal import ChalConst
from services.user import UserService
from services.rate import RateService
import config

from .util import AsyncTest, AccountContext
from tornado.websocket import websocket_connect
from tornado.httpclient import HTTPRequest


class SignTest(AsyncTest):
    async def main(self):
        with AccountContext('admin@test', 'testtest') as admin_session:
            admin_session.post('manage/holiday', data={
                'reqtype': 'add',
                'new_start': datetime.datetime.now().astimezone(config.TIMEZONE).strftime('%Y/%m/%d %H:%M'),
                'new_end': (datetime.datetime.now().astimezone(config.TIMEZONE) + datetime.timedelta(hours=2)).strftime('%Y/%m/%d %H:%M'),
                'is_weekday': '1',
            })
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

        # signin block by wrong password
        res = requests.post('http://localhost:5501/be/sign', data={
            'reqtype': 'signin',
            'mail': 'admin@test',
            'pw': 'test',
        })
        self.assertAPIReturnValue(res.text, ('Esign', 'Login failed'))

        # signin block by ip
        err, acct = await UserService.inst.info_acct(1)
        self.assertIsNone(err)
        assert acct
        acct.specific_ip = '192.168.11.10'
        await UserService.inst.update_acct(acct)

        res = requests.post('http://localhost:5501/be/sign', data={
            'reqtype': 'signin',
            'mail': 'admin@test',
            'pw': 'testtest',
        })
        self.assertAPIReturnValue(res.text, ('Esignip', 'Login failed'))

        err, acct = await UserService.inst.info_acct(1)
        self.assertIsNone(err)
        assert acct
        acct.specific_ip = ''
        await UserService.inst.update_acct(acct)


class AcctPageTest(AsyncTest):
    async def main(self):
        with AccountContext('admin@test', 'testtest') as admin_session:
            err, acct = await UserService.inst.info_acct(1)
            self.assertIsNone(err)
            assert acct

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


    class WebSocketLogoutTest(AsyncTest):
        async def main(self):
            # Test that sign-out publishes logout event and closes websocket
            with AccountContext('admin@test', 'testtest') as user_session:
                cookie_value = user_session.cookies.get('id')
                headers = {"Cookie": f"id={cookie_value}"}

                # connect websocket with same cookie
                ws = await websocket_connect(HTTPRequest("ws://localhost:5501/be/ws", headers=headers))

                # sign out - this should publish logout event and close websocket
                user_session.post('sign', data={"reqtype": "signout"})

                # read_message should return None after the server closes the connection
                msg = await ws.read_message()
                ws.close()
                self.assertIsNone(msg)

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
