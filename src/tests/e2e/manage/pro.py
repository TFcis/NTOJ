import json
import os

from services.chal import ChalConst
from services.pro import ProConst
from tests.e2e.util import AsyncTest, AccountContext


class ManageProTest(AsyncTest):
    # TODO: separate to each function
    async def main(self):
        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.post('http://localhost:5501/manage/pro/update', data={
                'reqtype': 'updatelimit',
                'pro_id': 1,
                'timelimit': 2000,
                'memlimit': 65536,
            })
            self.assertEqual(res.text, 'S')

            html = self.get_html('http://localhost:5501/pro/1', admin_session)
            self.assertEqual(html.select_one('input#tags').attrs.get('value'), '')
            self.assertEqual(html.select('tbody > tr')[0].select('td')[1].text, '2000 ms')
            self.assertEqual(html.select('tbody > tr')[1].select('td')[1].text, '65536 KB')

            html = self.get_html('http://localhost:5501/manage/pro/update?proid=1', admin_session)
            self.assertEqual(html.select_one('input.timelimit').attrs.get('value'), '2000')
            self.assertEqual(html.select_one('input.memlimit').attrs.get('value'), '65536')

            # test testcase preview
            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'preview',
                'pro_id': 1,
                'idx': 1,
                'type': 'out'
            })
            self.assertEqual(json.loads(res.text), open('tests/static_file/toj3.1.out.correct').read())
            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'preview',
                'pro_id': 1,
                'idx': 2,
                'type': 'out'
            })
            self.assertEqual(res.text, 'Efile')

            # update testcase
            pack_token = self.get_upload_token(admin_session)
            file_path = 'tests/static_file/toj3.1.out.incorrect'
            file_size = os.path.getsize(file_path)
            with open(file_path, 'rb') as f:
                await self.upload_file(f, file_size, pack_token)

            res = admin_session.post('http://localhost:5501/manage/pro/updatetests', data={
                'reqtype': 'updatesingletestcase',
                'pro_id': 1,
                'idx': 1,
                'type': 'out',
                'pack_token': pack_token,
            })
            self.assertEqual(res.text, 'S')

            res = admin_session.post('http://localhost:5501/manage/pro/updatetests', data={
                'reqtype': 'preview',
                'pro_id': 1,
                'idx': 1,
                'type': 'out'
            })
            self.assertEqual(json.loads(res.text), open('tests/static_file/toj3.1.out.incorrect').read())

            # rejudge
            def callback():
                admin_session.post('http://localhost:5501/submit', data={
                    'reqtype': 'rechal',
                    'chal_id': 1
                })

            await self.wait_for_judge_finish(callback)
            states = self.get_chal_state(chal_id=1, session=admin_session)
            self.assertEqual(states[0], ChalConst.STATE_WA)
            self.assertEqual(states[1], ChalConst.STATE_AC)

            # reset testcase
            pack_token = self.get_upload_token(admin_session)
            file_path = 'tests/static_file/toj3.1.out.correct'
            file_size = os.path.getsize(file_path)
            with open(file_path, 'rb') as f:
                await self.upload_file(f, file_size, pack_token)
            res = admin_session.post('http://localhost:5501/manage/pro/updatetests', data={
                'reqtype': 'updatesingletestcase',
                'pro_id': 1,
                'idx': 1,
                'type': 'out',
                'pack_token': pack_token,
            })
            self.assertEqual(res.text, 'S')

            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'preview',
                'pro_id': 1,
                'idx': 1,
                'type': 'out'
            })
            self.assertEqual(json.loads(res.text), open('tests/static_file/toj3.1.out.correct').read())

            def callback():
                admin_session.post('http://localhost:5501/submit', data={
                    'reqtype': 'rechal',
                    'chal_id': 1
                })

            await self.wait_for_judge_finish(callback)
            states = self.get_chal_state(chal_id=1, session=admin_session)
            self.assertEqual(states[0], ChalConst.STATE_AC)
            self.assertEqual(states[1], ChalConst.STATE_AC)

            res = admin_session.post('http://localhost:5501/manage/pro/update', data={
                'reqtype': 'updatepro',
                'pro_id': 1,
                'name': 'GCD',
                'status': ProConst.STATUS_HIDDEN,
                'pack_type': '1',
                'pack_token': '',
                'tags': '',
                'allow_submit': 'false',
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
                trs = html.select('tr')[1:]
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
                'pack_type': '1',
                'pack_token': '',
                'tags': '',
                'allow_submit': 'true',
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
            #
            # self.assertEqual(trs[1].select('td')[0].text, '3')
            # self.assertEqual(trs[1].select('td')[2].text.strip().replace('\n', ''), 'Move')

            admin_session.post('http://localhost:5501/manage/pro/update', data={
                'reqtype': 'updatepro',
                'pro_id': 1,
                'name': 'GCD',
                'status': ProConst.STATUS_ONLINE,
                'pack_type': '1',
                'pack_token': '',
                'tags': '',
                'allow_submit': 'true',
            })

            # test rechal
            # test reg corner case
