import os
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

            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'preview',
                'pro_id': 1,
                'filename': '2',
                'type': 'out',
            })
            self.assertEqual(res.text, 'Efile')

            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'preview',
                'pro_id': 1,
                'filename': '../conf.json',
                'type': 'out',
            })
            self.assertEqual(res.text, 'Eacces')

            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'preview',
                'pro_id': 1,
                'filename': '5',
                'type': 'out',
            })
            self.assertEqual(res.text, 'Enoext')

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
            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'addsinglefile',
                'pro_id': 1,
                'filename': '../etc',
                'input_pack_token': inputfile_token,
                'output_pack_token': outputfile_token,
            })
            self.assertEqual(res.text, 'Eacces')
            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'addsinglefile',
                'pro_id': 1,
                'filename': '3',
                'input_pack_token': inputfile_token,
                'output_pack_token': outputfile_token,
            })
            self.assertEqual(res.text, 'Eexist')

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
            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'addsingletestcase',
                'pro_id': 1,
                'testcase': '300',
                'group': 2,
            })
            self.assertEqual(res.text, 'Enoext')
            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'addsingletestcase',
                'pro_id': 1,
                'testcase': '3',
                'group': 300,
            })
            self.assertEqual(res.text, 'Enoext')
            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'addsingletestcase',
                'pro_id': 1,
                'testcase': '3',
                'group': 2,
            })
            self.assertEqual(res.text, 'Eexist')
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

            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'renamesinglefile',
                'pro_id': 1,
                'old_filename': '4',
                'new_filename': '4',
            })
            self.assertEqual(res.text, 'Eexist')

            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'renamesinglefile',
                'pro_id': 1,
                'old_filename': '5',
                'new_filename': '4',
            })
            self.assertEqual(res.text, 'Enoext')

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

            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'updatesinglefile',
                'pro_id': 1,
                'filename': '4',
                'type': '../../',
                'pack_token': pack_token,
            })
            self.assertEqual(res.text, 'Eparam')

            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'updatesinglefile',
                'pro_id': 1,
                'filename': '../conf.json',
                'type': 'output',
                'pack_token': pack_token,
            })
            self.assertEqual(res.text, 'Eacces')

            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'updatesinglefile',
                'pro_id': 1,
                'filename': '5',
                'type': 'output',
                'pack_token': pack_token,
            })
            self.assertEqual(res.text, 'Enoext')
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
            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'deletesinglefile',
                'pro_id': 1,
                'filename': '5',
            })
            self.assertEqual(res.text, 'Enoext')
            res = admin_session.post('http://localhost:5501/manage/pro/updatetests?proid=1', data={
                'reqtype': 'deletesinglefile',
                'pro_id': 1,
                'filename': '../conf.json',
            })
            self.assertEqual(res.text, 'Eacces')

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
