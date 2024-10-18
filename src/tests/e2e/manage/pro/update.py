import os
import json

from tests.e2e.util import AsyncTest, AccountContext
from services.pro import ProConst


class ManageProUpdateTest(AsyncTest):
    async def main(self):
        with AccountContext("admin@test", "testtest") as admin_session:
            res = admin_session.post('http://localhost:5501/manage/pro/update', data={
                'reqtype': 'updatepro',
                'pro_id': 1,
                'name': 'GCDGCD',
                'tags': 'GCD',
                'status': ProConst.STATUS_HIDDEN,
                'allow_submit': "false",
                "is_makefile": "false",
                "check_type": ProConst.CHECKER_DIFF,
                "rate_precision": ProConst.RATE_PRECISION_MIN,
            })
            self.assertEqual(res.text, 'S')
            html = self.get_html('http://localhost:5501/manage/pro/update?proid=1', admin_session)
            self.assertIsNone(html.select_one('input.allow-submit').get('checked'))
            self.assertEqual(html.select_one('select.status > option[selected]').text, 'Hidden')
            self.assertEqual(int(html.select_one('select.status > option[selected]').get('value')), ProConst.STATUS_HIDDEN)

            res = admin_session.get('http://localhost:5501/pro/1')
            self.assertNotEqual(res.text, 'Eacces')

            html = self.get_html('http://localhost:5501/pro/1', admin_session)
            submit_button = html.select_one('a.btn')
            self.assertIn('btn-warning', submit_button.get('class'))
            self.assertEqual(submit_button.text, 'Cannot Submit')

            with AccountContext('test1@test', 'test') as user_session:
                res = user_session.get('http://localhost:5501/pro/1')
                self.assertEqual(res.text, 'Enoext')

                html = self.get_html('http://localhost:5501/proset', user_session)
                trs = html.select('#prolist > tbody > tr')
                self.assertEqual(trs[0].select('td')[0].text, '2')
                self.assertEqual(trs[0].select('td')[2].text.strip().replace('\n', ''), '猜數字')

                self.assertEqual(trs[1].select('td')[0].text, '3')
                self.assertEqual(trs[1].select('td')[2].text.strip().replace('\n', ''), 'Move')

                res = user_session.get('http://localhost:5501/submit/1')
                self.assertEqual(res.text, 'Enoext')

            res = admin_session.post('http://localhost:5501/manage/pro/update', data={
                'reqtype': 'updatepro',
                'pro_id': 1,
                'name': 'GCD',
                'status': ProConst.STATUS_OFFLINE,
                'tags': '',
                'allow_submit': 'true',
                'is_makefile': 'false',
                'check_type': ProConst.CHECKER_DIFF,
                "rate_precision": ProConst.RATE_PRECISION_MIN,
            })
            self.assertEqual(res.text, 'S')
            res = admin_session.get('http://localhost:5501/submit/1')
            self.assertEqual(res.text, 'Eacces')

            res = admin_session.get('http://localhost:5501/pro/1')
            self.assertEqual(res.text, 'Eacces')

            # html = self.get_html('http://localhost:5501/proset', admin_session)
            # trs = html.select('tr')[1:]
            # self.assertEqual(trs[0].select('td')[0].text, '2')
            # self.assertEqual(trs[0].select('td')[2].text.strip().replace('\n', ''), '猜數字')

            # self.assertEqual(trs[1].select('td')[0].text, '3')
            # self.assertEqual(trs[1].select('td')[2].text.strip().replace('\n', ''), 'Move')

            admin_session.post('http://localhost:5501/manage/pro/update', data={
                'reqtype': 'updatepro',
                'pro_id': 1,
                'name': 'GCD',
                'status': ProConst.STATUS_ONLINE,
                'tags': '',
                'allow_submit': 'true',
                'is_makefile': 'false',
                'check_type': ProConst.CHECKER_DIFF,
                "rate_precision": ProConst.RATE_PRECISION_MIN,
            })

            res = admin_session.post('http://localhost:5501/manage/pro/update', data={
                'reqtype': 'updatelimit',
                'pro_id': 1,
                'limits': json.dumps({
                })
            })
            self.assertEqual(res.text, 'Eparam')

            res = admin_session.post('http://localhost:5501/manage/pro/update', data={
                'reqtype': 'updatelimit',
                'pro_id': 1,
                'limits': json.dumps({
                    'default': {
                        'timelimit': 1000,
                        'memlimit': 65536,
                    },
                    'python3': {
                        'timelimit': 1500,
                        'memlimit': 65536
                    },
                    'gcc': {},
                    'g++': {
                        'timelimit': '',
                        'memlimit': '',
                    }
                })
            })
            self.assertEqual(res.text, 'S')

            html = self.get_html('http://localhost:5501/pro/1', admin_session)
            limit_table = html.select_one('table > tbody')
            trs = limit_table.select('tr')
            self.assertEqual(trs[0].select('td')[0].text.strip(), 'default')
            self.assertEqual(trs[0].select('td')[1].text.strip(), '1000')
            self.assertEqual(trs[0].select('td')[2].text.strip(), '65536')
            self.assertEqual(trs[1].select('td')[0].text.strip(), 'python3')
            self.assertEqual(trs[1].select('td')[1].text.strip(), '1500')
            self.assertEqual(trs[1].select('td')[2].text.strip(), '65536')

            chal_id = -1
            def callback():
                nonlocal chal_id
                chal_id = self.submit_problem(1, open('tests/static_file/code/tle.py').read(), 'python3', admin_session)

            await self.wait_for_judge_finish(callback)
            html = self.get_html(f'http://localhost:5501/chal/{chal_id}', admin_session)
            states_trs = html.select('table#test > tbody > tr')
            self.assertGreaterEqual(int(states_trs[0].select_one('td.runtime').text), 1000)
            self.assertGreaterEqual(int(states_trs[1].select_one('td.runtime').text), 1000)

            # TODO: we should check limits and file
            pack_token = self.get_upload_token(admin_session)
            file = open('tests/static_file/toj3.tar.xz', 'rb')
            await self.upload_file(file, os.path.getsize('tests/static_file/toj3.tar.xz'), pack_token)
            file.close()

            res = admin_session.post('http://localhost:5501/manage/pro/update', data={
                'reqtype': 'uploadpackage',
                'pro_id': 1,
                'pack_token': pack_token,
            })
            self.assertEqual(res.text, 'S')
