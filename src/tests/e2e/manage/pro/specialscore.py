import os
import json

from tests.e2e.util import AsyncTest, AccountContext
from services.chal import ChalConst
from services.pro import ProConst


class ManageProSpecialScoreTest(AsyncTest):
    async def _upload_file(self, filepath, session):
        pack_token = self.get_upload_token(session)
        with open(filepath, 'rb') as file:
            size = os.path.getsize(filepath)
            await self.upload_file(file, size, pack_token)

        return pack_token

    async def main(self):
        with AccountContext("admin@test", "testtest") as admin_session:
            res = admin_session.post('http://localhost:5501/manage/pro/add', data={
                'reqtype': 'addpro',
                'name': 'special score test',
                'status': ProConst.STATUS_ONLINE,
                'mode': 'manual',
            })
            self.assertEqual(res.text, '5')

            res = admin_session.post('http://localhost:5501/manage/pro/update', data={
                'reqtype': 'updatepro',
                'pro_id': 5,
                'name': 'special score test',
                'tags': '',
                'status': ProConst.STATUS_ONLINE,
                'allow_submit': "true",
                "is_makefile": "false",
                "check_type": ProConst.CHECKER_CMS,
                "rate_precision": 2,
            })
            self.assertEqual(res.text, 'S')

            res = admin_session.post('http://localhost:5501/manage/pro/update', data={
                'reqtype': 'updatelimit',
                'pro_id': 5,
                'limits': json.dumps({
                    'default': {
                        'timelimit': 1000,
                        'memlimit': 65536,
                    }
                })
            })
            self.assertEqual(res.text, 'S')

            res = admin_session.post('http://localhost:5501/manage/pro/updatetests', data={
                'reqtype': 'addtaskgroup',
                'pro_id': 5,
                'weight': 100, # NOTE: weight is not important, because we will be overwritten by the checker
            })
            self.assertEqual(res.text, 'S')

            # NOTE: In this case, the testcase is not important, but we need at least one testcase because without any test cases, the judge cannot function.
            inputfile_token = await self._upload_file('tests/static_file/toj3/3.in', admin_session)
            outputfile_token = await self._upload_file('tests/static_file/toj3/3.out', admin_session)
            res = admin_session.post('http://localhost:5501/manage/pro/updatetests', data={
                'reqtype': 'addsinglefile',
                'pro_id': 5,
                'filename': '1',
                'input_pack_token': inputfile_token,
                'output_pack_token': outputfile_token,
            })
            self.assertEqual(res.text, 'S')

            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'addsingletestcase',
                'pro_id': 5,
                'testcase': '1',
                'group': 0,
            })
            self.assertEqual(res.text, 'S')

            # NOTE: add checker
            pack_token = await self._upload_file('tests/static_file/special_score/res/check/check.cpp', admin_session)
            res = admin_session.post('http://localhost:5501/manage/pro/filemanager', data={
                'reqtype': 'addsinglefile',
                'pro_id': 5,
                'filename': 'check.cpp',
                'path': 'res/check',
                'pack_token': pack_token,
            })
            self.assertEqual(res.text, 'S')
            pack_token = await self._upload_file('tests/static_file/special_score/res/check/build', admin_session)
            res = admin_session.post('http://localhost:5501/manage/pro/filemanager', data={
                'reqtype': 'addsinglefile',
                'pro_id': 5,
                'filename': 'build',
                'path': 'res/check',
                'pack_token': pack_token,
            })
            self.assertEqual(res.text, 'S')

            def callback():
                chal_id = self.submit_problem(5, 'print(32.27)', 'python3', admin_session)
                self.assertEqual(chal_id, 13)

                chal_id = self.submit_problem(5, 'print(132.27)', 'python3', admin_session)
                self.assertEqual(chal_id, 14)

            await self.wait_for_judge_finish(callback)
            chal_states = self.get_chal_state(13, admin_session)
            self.assertEqual([ChalConst.STATE_PC], chal_states)
            html = self.get_html('http://localhost:5501/chal/13', admin_session)
            states_table = html.select('tr.states')
            self.assertEqual(states_table[0].select_one('td.score').text, '32.27')

            chal_states = self.get_chal_state(14, admin_session)
            self.assertEqual([ChalConst.STATE_AC], chal_states)
            html = self.get_html('http://localhost:5501/chal/14', admin_session)
            states_table = html.select('tr.states')
            self.assertEqual(states_table[0].select_one('td.score').text, '132.27')

            html = self.get_html('http://localhost:5501/chal', admin_session)
            trs = html.select('table#challist > tbody > tr')[1:]
            self.assertEqual(trs[0].select_one('td#score').text, '132.27')
            self.assertEqual(trs[1].select_one('td#score').text, '32.27')
            self.assertEqual(trs[0].select_one('td#state').attrs['class'][0], f'state-{ChalConst.STATE_AC}')
            self.assertEqual(trs[1].select_one('td#state').attrs['class'][0], f'state-{ChalConst.STATE_PC}')

            # TODO: board, contest scoreboard, contest proset rate-precision
