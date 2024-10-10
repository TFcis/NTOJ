import os
import copy
import json

from services.chal import ChalConst
from tests.e2e.util import AsyncTest, AccountContext

class ManageProUpdateTestsTest(AsyncTest):
    async def _upload_file(self, filepath, session):
        pack_token = self.get_upload_token(session)
        with open(filepath, 'rb') as file:
            size = os.path.getsize(filepath)
            await self.upload_file(file, size, pack_token)

        return pack_token

    def assertTable(self, default_data: dict, assert_tables: list[dict], session):
        for table in assert_tables:
            equal_value = table.pop("equal_value")

            d = copy.copy(default_data)
            for key, val in table.items():
                d[key] = val

            res = session.post('http://localhost:5501/manage/pro/updatetests', data=d)
            self.assertEqual(res.text, equal_value)

    async def main(self):
        with AccountContext("admin@test", "testtest") as admin_session:
            # NOTE: preview
            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'preview',
                'pro_id': 1,
                'filename': '1',
                'type': 'out',
            })
            self.assertEqual(json.loads(res.text), open('tests/static_file/toj3/res/testdata/1.out').read())

            self.assertTable(
                {
                    'reqtype': 'preview',
                    'pro_id': 1,
                    'filename': '1',
                    'type': 'out',
                },
                [
                    {'pro_id': '100', 'equal_value': 'Enoext'}, # problem not found
                    {'filename': '2', 'equal_value': 'Efile'}, # file has more than 25 lines or cannot be decoded as UTF-8.
                    {'filename': '../conf.json', 'equal_value': 'Eacces'}, # illegal filepath access
                    {'filename': '5', 'equal_value': 'Enoext'} # file not found
                ],
                admin_session
            )

            # NOTE: updateweight
            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'updateweight',
                'pro_id': 1,
                'weight': 60,
                'group': 0,
            })
            self.assertEqual(res.text, 'S')
            html = self.get_html('http://localhost:5501/pro/1', admin_session)
            scores_table = html.select('table')[1]
            trs = scores_table.select('tbody > tr')
            self.assertEqual(trs[0].select('td')[1].text.strip(), '60')

            html = self.get_html('http://localhost:5501/manage/pro/updatetests?proid=1', admin_session)
            groups = html.select_one('div#tests').select('div.accordion-item')
            self.assertEqual(groups[0].select_one('button.accordion-button').text.strip(), f'Task Group { 0 + 1 } Weight: { 60 }')

            # NOTE: addtaskgroup
            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'addtaskgroup',
                'pro_id': 1,
                'weight': 20,
            })
            self.assertEqual(res.text, 'S')
            html = self.get_html('http://localhost:5501/pro/1', admin_session)
            scores_table = html.select('table')[1]
            trs = scores_table.select('tbody > tr')
            self.assertEqual(trs[2].select('td')[1].text.strip(), '20')

            html = self.get_html('http://localhost:5501/manage/pro/updatetests?proid=1', admin_session)
            groups = html.select_one('div#tests').select('div.accordion-item')
            self.assertEqual(groups[2].select_one('button.accordion-button').text.strip(), f'Task Group { 2 + 1 } Weight: { 20 }')

            # NOTE: addsinglefile
            inputfile_token = await self._upload_file('tests/static_file/toj3/3.in', admin_session)
            outputfile_token = await self._upload_file('tests/static_file/toj3/3.out', admin_session)
            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'addsinglefile',
                'pro_id': 1,
                'filename': '3',
                'input_pack_token': inputfile_token,
                'output_pack_token': outputfile_token,
            })
            self.assertEqual(res.text, 'S')
            self.assertTrue(os.path.exists('problem/1/res/testdata/3.in'))
            self.assertTrue(os.path.exists('problem/1/res/testdata/3.out'))
            self.assertEqual(open('tests/static_file/toj3/3.in').read(), open('problem/1/res/testdata/3.in').read())
            self.assertEqual(open('tests/static_file/toj3/3.out').read(), open('problem/1/res/testdata/3.out').read())

            self.assertTable(
                {
                    'reqtype': 'addsinglefile',
                    'pro_id': 1,
                    'filename': '3',
                    'input_pack_token': inputfile_token,
                    'output_pack_token': outputfile_token,
                },
                [
                    {'pro_id': '100', 'equal_value': 'Enoext'}, # problem not found,
                    {'filename': '../etc', 'equal_value': 'Eacces'}, # illegal filepath access
                    {'filename': '3', 'equal_value': 'Eexist'} # file already exists
                ],
                admin_session
            )

            # NOTE: addsingletestcase
            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'addsingletestcase',
                'pro_id': 1,
                'testcase': '3',
                'group': 2,
            })
            self.assertEqual(res.text, 'S')
            html = self.get_html('http://localhost:5501/manage/pro/updatetests?proid=1', admin_session)
            groups = html.select_one('div#tests').select('div.accordion-item')
            testcase_trs = groups[2].select('tbody > tr')
            self.assertEqual(testcase_trs[0].select('td')[0].text.strip(), '3')
            self.assertEqual(testcase_trs[0].attrs.get('testcase'), '3')

            self.assertTable(
                {
                    'reqtype': 'addsingletestcase',
                    'pro_id': 1,
                    'testcase': '3',
                    'group': 2,
                },
                [
                    {'pro_id': '100', 'equal_value': 'Enoext'}, # problem not found,
                    {'testcase': '300', 'equal_value': 'Enoext'}, # testcase not found
                    {'group': '300', 'equal_value': 'Enoext'}, # group not found
                    {'testcase': '3', 'equal_value': 'Eexist'}, # testcase already exists
                ],
                admin_session
            )

            def callback():
                res = admin_session.post('http://localhost:5501/submit', data={
                    'reqtype': 'rechal',
                    'chal_id': 1
                })
                self.assertEqual(res.text, '1')
            await self.wait_for_judge_finish(callback)
            chal_states_result = self.get_chal_state(chal_id=1, session=admin_session)
            self.assertEqual(chal_states_result, [ChalConst.STATE_AC] * len(chal_states_result))

            # NOTE: renamesinglefile
            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'renamesinglefile',
                'pro_id': 1,
                'old_filename': '3',
                'new_filename': '4',
            })
            self.assertEqual(res.text, 'S')
            self.assertTrue(os.path.exists('problem/1/res/testdata/4.in'))
            self.assertTrue(os.path.exists('problem/1/res/testdata/4.out'))
            self.assertEqual(open('tests/static_file/toj3/3.in').read(), open('problem/1/res/testdata/4.in').read())
            self.assertEqual(open('tests/static_file/toj3/3.out').read(), open('problem/1/res/testdata/4.out').read())
            html = self.get_html('http://localhost:5501/manage/pro/updatetests?proid=1', admin_session)
            groups = html.select_one('div#tests').select('div.accordion-item')
            testcase_trs = groups[2].select('tbody > tr')
            self.assertEqual(testcase_trs[0].select('td')[0].text.strip(), '4')
            self.assertEqual(testcase_trs[0].attrs.get('testcase'), '4')

            self.assertTable(
                {
                    'reqtype': 'renamesinglefile',
                    'pro_id': 1,
                    'old_filename': '3',
                    'new_filename': '4',
                },
                [
                    {'pro_id': '100', 'equal_value': 'Enoext'}, # problem not found,
                    {'old_filename': '../conf.json', 'new_filename': '../tw87.json', 'equal_value': 'Eacces'}, # illegal filepath access
                    {'old_filename': '4', 'new_filename': '4', 'equal_value': 'Eexist'}, # new file already exists
                    {'old_filename': '5', 'equal_value': 'Enoext'}, # old file not found
                ],
                admin_session
            )

            # NOTE: updatesinglefile
            pack_token = await self._upload_file('tests/static_file/toj3/3.out.incorrect', admin_session)
            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'updatesinglefile',
                'pro_id': 1,
                'filename': '4',
                'type': 'output',
                'pack_token': pack_token,
            })
            self.assertEqual(res.text, 'S')

            self.assertTable(
                {
                    'reqtype': 'updatesinglefile',
                    'pro_id': 1,
                    'filename': '4',
                    'type': 'output',
                    'pack_token': pack_token,
                },
                [
                    {'pro_id': '100', 'equal_value': 'Enoext'}, # problem not found,
                    {'type': '../../', 'equal_value': 'Eparam'}, # type in ['output', 'input']
                    {'filename': '../conf.json', 'equal_value': 'Eacces'}, # illegal filepath access
                    {'filename': '5', 'equal_value': 'Enoext'}, # file not found
                ],
                admin_session
            )

            def callback():
                res = admin_session.post('http://localhost:5501/submit', data={
                    'reqtype': 'rechal',
                    'chal_id': 1
                })
                self.assertEqual(res.text, '1')
            await self.wait_for_judge_finish(callback)
            chal_states_result = self.get_chal_state(chal_id=1, session=admin_session)
            self.assertEqual(chal_states_result, [ChalConst.STATE_AC, ChalConst.STATE_AC, ChalConst.STATE_WA])

            # NOTE: deletesingletestcase
            inputfile_token = await self._upload_file('tests/static_file/toj3/3.in', admin_session)
            outputfile_token = await self._upload_file('tests/static_file/toj3/3.out', admin_session)
            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'addsinglefile',
                'pro_id': 1,
                'filename': '3',
                'input_pack_token': inputfile_token,
                'output_pack_token': outputfile_token,
            })
            self.assertEqual(res.text, 'S')
            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'addsingletestcase',
                'pro_id': 1,
                'testcase': '3',
                'group': 2,
            })
            self.assertEqual(res.text, 'S')
            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'deletesingletestcase',
                'pro_id': 1,
                'testcase': '4',
                'group': 2,
            })
            self.assertEqual(res.text, 'S')
            def callback():
                res = admin_session.post('http://localhost:5501/submit', data={
                    'reqtype': 'rechal',
                    'chal_id': 1
                })
                self.assertEqual(res.text, '1')
            await self.wait_for_judge_finish(callback)
            chal_states_result = self.get_chal_state(chal_id=1, session=admin_session)
            self.assertEqual(chal_states_result, [ChalConst.STATE_AC, ChalConst.STATE_AC, ChalConst.STATE_AC])

            # NOTE: deletesinglefile
            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'deletesinglefile',
                'pro_id': 1,
                'filename': '4',
            })
            self.assertEqual(res.text, 'S')
            self.assertFalse(os.path.exists('problem/1/res/testdata/4.in'))
            self.assertFalse(os.path.exists('problem/1/res/testdata/4.out'))

            self.assertTable(
                {
                    'reqtype': 'deletesinglefile',
                    'pro_id': 1,
                    'filename': '4',
                },
                [
                    {'pro_id': '100', 'equal_value': 'Enoext'}, # problem not found,
                    {'filename': '../conf.json', 'equal_value': 'Eacces'}, # illegal filepath access
                    {'filename': '5', 'equal_value': 'Enoext'}, # file not found
                ],
                admin_session
            )

            # NOTE: deletetaskgroup
            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'deletetaskgroup',
                'pro_id': 1,
                'group': 2,
            })
            self.assertEqual(res.text, 'S')
            def callback():
                res = admin_session.post('http://localhost:5501/submit', data={
                    'reqtype': 'rechal',
                    'chal_id': 1
                })
                self.assertEqual(res.text, '1')
            await self.wait_for_judge_finish(callback)
            chal_states_result = self.get_chal_state(chal_id=1, session=admin_session)
            self.assertEqual(chal_states_result, [ChalConst.STATE_AC, ChalConst.STATE_AC])
