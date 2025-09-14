import os
import json

from tests.integrated.util import AsyncTest, AccountContext
from services.chal import ChalConst, Compiler
from services.pro import ProConst, CheckerType, SummaryType


class ManageProSpecialScoreTest(AsyncTest):
    async def _upload_file(self, filepath, session):
        pack_token = self.get_upload_token(session)
        with open(filepath, 'rb') as file:
            size = os.path.getsize(filepath)
            await self.upload_file(file, size, pack_token)

        return pack_token

    async def setup_basic_special_score_problem(self, expected_pro_id: int, checker_path: str):
        with AccountContext("admin@test", "testtest") as admin_session:
            res = admin_session.post('manage/pro/add', data={
                'reqtype': 'addpro',
                'name': 'special score test',
                'status': ProConst.STATUS_ONLINE,
                'mode': 'manual',
            })
            self.assertAPIReturnValue(res.text, ('S', expected_pro_id))

            res = admin_session.post('manage/pro/update', data={
                'reqtype': 'updatejudge',
                'pro_id': expected_pro_id,
                "has_grader": "false",
                "checker_type": CheckerType.CMS_TPS_TESTLIB,
                "checker_compiler": Compiler.GPP,
                "checker_compile_args": "",
                "summary_type": SummaryType.GROUPMIN,
                "summary_compiler": "",
                "summary_compile_args": "",
                "userprog_compile_args": "",
                "allow_compilers[]": [Compiler.PYTHON3],
                "rate_precision": 2,
            })
            self.assertAPIReturnSuccess(res.text)

            res = admin_session.post('manage/pro/update', data={
                'reqtype': 'updatelimit',
                'pro_id': expected_pro_id,
                'limits': json.dumps({
                    'default': {
                        'time': 1000,
                        'memory': 65536,
                        'output': 65536,
                    }
                })
            })
            self.assertAPIReturnSuccess(res.text)

            # NOTE: In this case, the testdata is not important, but we need at least one testdata because without any test cases, the judge cannot function.
            inputfile_token = await self._upload_file('tests/static_file/toj3/3.in', admin_session)
            outputfile_token = await self._upload_file('tests/static_file/toj3/3.out', admin_session)
            res = admin_session.post('manage/pro/updatetestdata', data={
                'reqtype': 'addsinglefile',
                'pro_id': expected_pro_id,
                'filename': '1',
                'input_pack_token': inputfile_token,
                'output_pack_token': outputfile_token,
            })
            self.assertAPIReturnSuccess(res.text)

            # NOTE: add checker
            pack_token = await self._upload_file(f'{checker_path}/res/checker/checker.cpp', admin_session)
            res = admin_session.post('manage/pro/filemanager', data={
                'reqtype': 'addsinglefile',
                'pro_id': expected_pro_id,
                'filename': 'checker.cpp',
                'path': 'res/checker',
                'pack_token': pack_token,
            })
            self.assertAPIReturnSuccess(res.text)

    async def cf_style_special_score(self):
        with AccountContext("admin@test", "testtest") as admin_session:
            await self.setup_basic_special_score_problem(5, 'tests/static_file/special_score')

            res = admin_session.post('manage/pro/updatetests', data={
                'reqtype': 'addsubtask',
                'pro_id': 5,
                'rate': 100, # NOTE: rate is not important, because we will be overwritten by the checker
            })
            self.assertAPIReturnSuccess(res.text)

            res = admin_session.post('manage/pro/updatetests?proid=1', data={
                'reqtype': 'settestdata',
                'pro_id': 5,
                'testdatas': '0',
                'subtask': 0,
            })
            self.assertAPIReturnSuccess(res.text)

            def callback():
                chal_id = self.submit_problem(5, 'print(32.27)', Compiler.PYTHON3, admin_session)
                self.assertEqual(chal_id, 13)

                chal_id = self.submit_problem(5, 'print(132.27)', Compiler.PYTHON3, admin_session)
                self.assertEqual(chal_id, 14)

            await self.wait_for_judge_finish(callback)
            return
            _, subtask_results, _ = self.get_chal_results(chal_id=13, session=admin_session)
            self.assertEqual([v.state for v in subtask_results.values()], [ChalConst.STATE_PC] * len(subtask_results))
            html = self.get_html('chal/13', admin_session)
            states_table = html.select('tr.states')
            self.assertEqual(states_table[0].select_one('td.score').text, '32.27')

            _, subtask_results, _ = self.get_chal_results(chal_id=14, session=admin_session)
            self.assertEqual([v.state for v in subtask_results.values()], [ChalConst.STATE_AC] * len(subtask_results))
            html = self.get_html('chal/14', admin_session)
            states_table = html.select('tr.states')
            self.assertEqual(states_table[0].select_one('td.score').text, '132.27')

            html = self.get_html('chal', admin_session)
            trs = html.select('table#challist > tbody > tr')[1:]
            self.assertEqual(trs[0].select_one('td#score').text, '132.27')
            self.assertEqual(trs[1].select_one('td#score').text, '32.27')
            self.assertEqual(trs[0].select_one('td#state').attrs['class'][0], f'state-{ChalConst.STATE_AC}')
            self.assertEqual(trs[1].select_one('td#state').attrs['class'][0], f'state-{ChalConst.STATE_PC}')

            # TODO: board, contest scoreboard, contest proset rate-precision

    async def cms_style_special_score(self):
        with AccountContext("admin@test", "testtest") as admin_session:
            await self.setup_basic_special_score_problem(6, 'tests/static_file/special_score_cms')

            subtask_rates = [50, 25, 25]
            for subtask_id, rate in enumerate(subtask_rates):
                res = admin_session.post('manage/pro/updatetests', data={
                    'reqtype': 'addsubtask',
                    'pro_id': 6,
                    'rate': rate,
                })
                self.assertAPIReturnSuccess(res.text)

                res = admin_session.post('manage/pro/updatetests?proid=1', data={
                    'reqtype': 'settestdata',
                    'pro_id': 6,
                    'testdatas': '0',
                    'subtask': subtask_id,
                })
                self.assertAPIReturnSuccess(res.text)

            def callback():
                chal_id = self.submit_problem(6, 'print(50)', Compiler.PYTHON3, admin_session)
                self.assertEqual(chal_id, 15)

                chal_id = self.submit_problem(6, 'print(105)', Compiler.PYTHON3, admin_session)
                self.assertEqual(chal_id, 16)

            await self.wait_for_judge_finish(callback)
            return
            _, subtask_results, _ = self.get_chal_results(chal_id=15, session=admin_session)
            self.assertEqual([v.state for v in subtask_results.values()], [ChalConst.STATE_PC] * len(subtask_results))
            html = self.get_html('chal/15', admin_session)
            states_table = html.select('tr.states')
            self.assertEqual(states_table[0].select_one('td.score').text, '25.00')
            self.assertEqual(states_table[1].select_one('td.score').text, '12.50')
            self.assertEqual(states_table[2].select_one('td.score').text, '12.50')

            _, subtask_results, _ = self.get_chal_results(chal_id=16, session=admin_session)
            self.assertEqual([v.state for v in subtask_results.values()], [ChalConst.STATE_AC] * len(subtask_results))
            html = self.get_html('chal/16', admin_session)
            states_table = html.select('tr.states')
            self.assertEqual(states_table[0].select_one('td.score').text, '50.00')
            self.assertEqual(states_table[1].select_one('td.score').text, '25.00')
            self.assertEqual(states_table[2].select_one('td.score').text, '25.00')

            html = self.get_html('chal', admin_session)
            trs = html.select('table#challist > tbody > tr')[1:]
            self.assertEqual(trs[0].select_one('td#score').text, '100.00')
            self.assertEqual(trs[1].select_one('td#score').text, '50.00')
            self.assertEqual(trs[0].select_one('td#state').attrs['class'][0], f'state-{ChalConst.STATE_AC}')
            self.assertEqual(trs[1].select_one('td#state').attrs['class'][0], f'state-{ChalConst.STATE_PC}')

            # TODO: board, contest scoreboard, contest proset rate-precision

    async def main(self):
        # TODO:
        await self.cf_style_special_score()
        await self.cms_style_special_score()
