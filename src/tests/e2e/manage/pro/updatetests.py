import re
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

    def assertTable(self, url: str, default_data: dict, assert_tables: list[dict], session):
        for table in assert_tables:
            equal_value = table.pop("equal_value")

            d = copy.copy(default_data)
            for key, val in table.items():
                d[key] = val

            res = session.post(url, data=d)
            self.assertAPIReturnValue(res.text, equal_value)

    async def main(self):
        with AccountContext("admin@test", "testtest") as admin_session:
            # NOTE: preview
            res = admin_session.post('manage/pro/updatetestdata?proid=1', data={
                'reqtype': 'preview',
                'pro_id': 1,
                'testdata_id': 0,
                'type': 'output',
            })
            self.assertEqual(json.loads(res.text)['data'], open('tests/static_file/toj3/res/testdata/1.out').read())

            self.assertTable(
                'manage/pro/updatetestdata',
                {
                    'reqtype': 'preview',
                    'pro_id': 1,
                    'testdata_id': 0,
                    'type': 'output',
                },
                [
                    {'pro_id': '100', 'equal_value': ('Enoext', 'Problem not found')}, # problem not found
                    {'testdata_id': 1, 'equal_value': ('Efile', 'File too large')}, # file has more than 25 lines or cannot be decoded as UTF-8.
                    {'testdata_id': 100, 'equal_value': ('Enoext', 'Testdata not found')},
                ],
                admin_session
            )

            # NOTE: download file
            res = admin_session.get('manage/pro/updatetestdata?proid=1&download=1&testdata_id=0&type=output')
            self.assertIsNotNone(res.headers.get("content-disposition"))
            self.assertEqual(re.findall(r'filename="?([^";]+)"?', res.headers.get("content-disposition"))[0], "1.out")
            self.assertEqual(res.content.decode('utf-8'), open('tests/static_file/toj3/res/testdata/1.out').read())

            res = admin_session.get('manage/pro/updatetestdata?proid=1&download=1&testdata_id=123&type=output')
            self.assertAPIReturnValue(res.text, ('Enoext', 'Testdata not found'))

            res = admin_session.get('manage/pro/updatetestdata?proid=1&download=1&testdata_id=0&type=what')
            self.assertAPIReturnValue(res.text, ('Eparam', 'Invalid testdata file type'))

            # NOTE: updateweight
            res = admin_session.post('manage/pro/updatetests?proid=1', data={
                'reqtype': 'updateweight',
                'pro_id': 1,
                'weight': 60,
                'group': 0,
            })
            self.assertAPIReturnSuccess(res.text)
            html = self.get_html('pro/1', admin_session)
            scores_table = html.select('table')[1]
            trs = scores_table.select('tbody > tr')
            self.assertEqual(trs[0].select('td')[1].text.strip(), '60')

            html = self.get_html('manage/pro/updatetests?proid=1', admin_session)
            groups = html.select_one('div#tests').select('div.accordion-item')
            self.assertEqual(groups[0].select_one('button.accordion-button').text.strip(), f'Task Group { 0 + 1 } Weight: { 60 }')

            # NOTE: addtaskgroup
            res = admin_session.post('manage/pro/updatetests?proid=1', data={
                'reqtype': 'addtaskgroup',
                'pro_id': 1,
                'weight': 20,
            })
            self.assertAPIReturnSuccess(res.text)
            html = self.get_html('pro/1', admin_session)
            scores_table = html.select('table')[1]
            trs = scores_table.select('tbody > tr')
            self.assertEqual(trs[2].select('td')[1].text.strip(), '20')

            html = self.get_html('manage/pro/updatetests?proid=1', admin_session)
            groups = html.select_one('div#tests').select('div.accordion-item')
            self.assertEqual(groups[2].select_one('button.accordion-button').text.strip(), f'Task Group { 2 + 1 } Weight: { 20 }')

            # NOTE: addsinglefile
            inputfile_token = await self._upload_file('tests/static_file/toj3/3.in', admin_session)
            outputfile_token = await self._upload_file('tests/static_file/toj3/3.out', admin_session)
            res = admin_session.post('manage/pro/updatetestdata?proid=1', data={
                'reqtype': 'addsinglefile',
                'pro_id': 1,
                'filename': '3',
                'input_pack_token': inputfile_token,
                'output_pack_token': outputfile_token,
            })
            self.assertAPIReturnSuccess(res.text)
            self.assertTrue(os.path.exists('problem/1/res/testdata/3.in'))
            self.assertTrue(os.path.exists('problem/1/res/testdata/3.out'))
            self.assertEqual(open('tests/static_file/toj3/3.in').read(), open('problem/1/res/testdata/3.in').read())
            self.assertEqual(open('tests/static_file/toj3/3.out').read(), open('problem/1/res/testdata/3.out').read())
            html = self.get_html('manage/pro/updatetestdata?proid=1', admin_session)
            trs = html.select('tbody > tr')
            self.assertEqual(len(trs), 3)
            self.assertEqual(trs[2].attrs['testdata_id'], '2')
            self.assertEqual(trs[2].select_one('a.input').text.strip(), '3.in')
            self.assertEqual(trs[2].select_one('a.output').text.strip(), '3.out')

            self.assertTable(
                'manage/pro/updatetestdata',
                {
                    'reqtype': 'addsinglefile',
                    'pro_id': 1,
                    'filename': '3',
                    'input_pack_token': inputfile_token,
                    'output_pack_token': outputfile_token,
                },
                [
                    {'pro_id': '100', 'equal_value': ('Enoext', 'Problem not found')}, # problem not found,
                    {'filename': '../etc', 'equal_value': ('Eacces', 'Permission denied')}, # illegal filepath access
                    {'filename': '3', 'equal_value': ('Eexist', 'File already exists')} # file already exists
                ],
                admin_session
            )

            # NOTE: settestdata (add testdata to range)
            res = admin_session.post('manage/pro/updatetests?proid=1', data={
                'reqtype': 'settestdata',
                'pro_id': 1,
                'testdatas': '0-2',
                'group': 2,
            })
            self.assertAPIReturnSuccess(res.text)
            html = self.get_html('manage/pro/updatetests?proid=1', admin_session)
            groups = html.select_one('div#tests').select('div.accordion-item')
            self.assertEqual(groups[2].select_one('#testdatas').attrs['value'].strip(), "0-2")

            def callback():
                res = admin_session.post('submit', data={
                    'reqtype': 'rechal',
                    'chal_id': 1
                })
                self.assertAPIReturnValue(res.text, ('S', 1))
            await self.wait_for_judge_finish(callback)
            chal_states_result = self.get_chal_state(chal_id=1, session=admin_session)
            self.assertEqual(chal_states_result, [ChalConst.STATE_AC] * len(chal_states_result))

            # NOTE: updatesinglefile
            pack_token = await self._upload_file('tests/static_file/toj3/3.out.incorrect', admin_session)
            res = admin_session.post('manage/pro/updatetestdata?proid=1', data={
                'reqtype': 'updatesinglefile',
                'pro_id': 1,
                'testdata_id': 2,
                'type': 'output',
                'pack_token': pack_token,
            })
            self.assertAPIReturnSuccess(res.text)

            self.assertTable(
                'manage/pro/updatetestdata',
                {
                    'reqtype': 'updatesinglefile',
                    'pro_id': 1,
                    'testdata_id': 2,
                    'type': 'output',
                    'pack_token': pack_token,
                },
                [
                    {'pro_id': '100', 'equal_value': ('Enoext', 'Problem not found')}, # problem not found,
                    {'type': '../../', 'equal_value': ('Eparam', 'Invalid testdata file type')}, # type in ['output', 'input']
                    {'testdata_id': 100, 'equal_value': ('Enoext', 'Testdata not found')},
                ],
                admin_session
            )

            def callback():
                res = admin_session.post('submit', data={
                    'reqtype': 'rechal',
                    'chal_id': 1
                })
                self.assertAPIReturnValue(res.text, ('S', 1))
            await self.wait_for_judge_finish(callback)
            chal_states_result = self.get_chal_state(chal_id=1, session=admin_session)
            self.assertEqual(chal_states_result, [ChalConst.STATE_AC, ChalConst.STATE_AC, ChalConst.STATE_WA])

            # NOTE: settestdata (remove testdata from range)
            inputfile_token = await self._upload_file('tests/static_file/toj3/3.in', admin_session)
            outputfile_token = await self._upload_file('tests/static_file/toj3/3.out', admin_session)
            res = admin_session.post('manage/pro/updatetestdata?proid=1', data={
                'reqtype': 'addsinglefile',
                'pro_id': 1,
                'filename': '4',
                'input_pack_token': inputfile_token,
                'output_pack_token': outputfile_token,
            })
            self.assertAPIReturnSuccess(res.text)
            html = self.get_html('manage/pro/updatetestdata?proid=1', admin_session)
            trs = html.select('tbody > tr')
            self.assertEqual(len(trs), 4)

            res = admin_session.post('manage/pro/updatetests?proid=1', data={
                'reqtype': 'settestdata',
                'pro_id': 1,
                'testdatas': '0-1, 3',
                'group': 2,
            })
            self.assertAPIReturnSuccess(res.text)
            html = self.get_html('manage/pro/updatetests?proid=1', admin_session)
            groups = html.select_one('div#tests').select('div.accordion-item')
            self.assertEqual(groups[2].select_one('#testdatas').attrs['value'].strip(), "0-1,3")
            def callback():
                res = admin_session.post('submit', data={
                    'reqtype': 'rechal',
                    'chal_id': 1
                })
                self.assertAPIReturnValue(res.text, ('S', 1))
            await self.wait_for_judge_finish(callback)
            chal_states_result = self.get_chal_state(chal_id=1, session=admin_session)
            self.assertEqual(chal_states_result, [ChalConst.STATE_AC, ChalConst.STATE_AC, ChalConst.STATE_AC])

            # NOTE: deletesinglefile
            res = admin_session.post('manage/pro/updatetestdata?proid=1', data={
                'reqtype': 'deletesinglefile',
                'pro_id': 1,
                'testdata_id': 3,
            })
            self.assertAPIReturnSuccess(res.text)
            self.assertFalse(os.path.exists('problem/1/res/testdata/4.in'))
            self.assertFalse(os.path.exists('problem/1/res/testdata/4.out'))
            html = self.get_html('manage/pro/updatetestdata?proid=1', admin_session)
            trs = html.select('tbody > tr')
            self.assertEqual(len(trs), 3)

            self.assertTable(
                'manage/pro/updatetestdata',
                {
                    'reqtype': 'deletesinglefile',
                    'pro_id': 1,
                    'testdata_id': 3,
                },
                [
                    {'pro_id': '100', 'equal_value': ('Enoext', 'Problem not found')}, # problem not found,
                    {'testdata_id': 100, 'equal_value': ('Enoext', 'Testdata not found')}, # illegal filepath access
                ],
                admin_session
            )

            # NOTE: deletetaskgroup
            res = admin_session.post('manage/pro/updatetests?proid=1', data={
                'reqtype': 'deletetaskgroup',
                'pro_id': 1,
                'group': 2,
            })
            self.assertAPIReturnSuccess(res.text)
            def callback():
                res = admin_session.post('submit', data={
                    'reqtype': 'rechal',
                    'chal_id': 1
                })
                self.assertAPIReturnValue(res.text, ('S', 1))
            await self.wait_for_judge_finish(callback)
            chal_states_result = self.get_chal_state(chal_id=1, session=admin_session)
            self.assertEqual(chal_states_result, [ChalConst.STATE_AC, ChalConst.STATE_AC])
