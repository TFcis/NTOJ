import re
import os
import json

import tornado.escape

import config
from services.chal import ChalService, ChalConst, Compiler
from services.pro import ProConst
from tests.integrated.util import AsyncTest, AccountContext


class ManageProFileManagerTest(AsyncTest):
    async def _upload_file(self, filepath, session):
        pack_token = self.get_upload_token(session)
        with open(filepath, 'rb') as file:
            size = os.path.getsize(filepath)
            await self.upload_file(file, size, pack_token)

        return pack_token

    async def main(self):
        with AccountContext("admin@test", "testtest") as admin_session:
            # NOTE: preview
            res = admin_session.post('manage/pro/filemanager?proid=1', data={
                'reqtype': 'preview',
                'pro_id': 1,
                'filename': 'cont.html',
                'path': 'http',
            })
            res = json.loads(res.text)
            with open('tests/static_file/toj3/http/cont.html') as f:
                self.assertEqual(tornado.escape.xhtml_unescape(res['data']),
                                 f.read())

            self.assertTable(
                'manage/pro/filemanager',
                {
                    'reqtype': 'preview',
                    'pro_id': 1,
                    'filename': 'cont.html',
                    'path': 'http'
                },
                [
                    {'pro_id': '100', 'equal_value': ('Enoext', 'Problem not found')}, # problem not found
                    {'filename': '../conf.json', 'equal_value': ('Eacces', 'Access denied: invalid file path')}, # illegal filepath access
                    {'filename': 'cont.html.html', 'equal_value': ('Enoext', 'File not found')}, # file not found
                    {'path': '/etc/', 'filename': 'passwd-', 'equal_value': ('Eparam', 'Invalid basepath')},
                ],
                admin_session
            )

            # NOTE: download
            res = admin_session.get('manage/pro/filemanager?proid=1&download=1&filename=cont.html&path=http')
            self.assertIsNotNone(res.headers.get("content-disposition"))
            self.assertEqual(re.findall(r'filename="?([^";]+)"?', res.headers.get("content-disposition"))[0], "cont.html")
            with open('tests/static_file/toj3/http/cont.html') as f:
                self.assertEqual(res.content.decode('utf-8'), f.read())

            res = admin_session.get('manage/pro/filemanager?proid=1&download=1&filename=test.html&path=http')
            self.assertAPIReturnValue(res.text, ('Enoext', 'File not found'))

            res = admin_session.get('manage/pro/filemanager?proid=1&download=1&filename=passwd&path=/etc')
            self.assertAPIReturnValue(res.text, ('Eparam', 'Invalid basepath'))

            # NOTE: addsinglefile
            pack_token = await self._upload_file('tests/static_file/toj3/3.in', admin_session)
            res = admin_session.post('manage/pro/filemanager?proid=1', data={
                'reqtype': 'addsinglefile',
                'pro_id': 1,
                'filename': 'test',
                'path': 'http',
                'pack_token': pack_token,
            })
            self.assertAPIReturnSuccess(res.text)
            self.assertTrue(os.path.exists('problem/1/http/test'))
            with open('tests/static_file/toj3/3.in') as f1:
                with open('problem/1/http/test') as f2:
                    self.assertEqual(f1.read(), f2.read())

            self.assertTable(
                'manage/pro/filemanager',
                {
                    'reqtype': 'addsinglefile',
                    'pro_id': 1,
                    'filename': 'test',
                    'path': 'http',
                    'pack_token': pack_token,
                },
                [
                    {'pro_id': '100', 'equal_value': ('Enoext', 'Problem not found')}, # problem not found
                    {'filename': '../conf.json', 'equal_value': ('Eacces', 'Access denied: invalid file path')}, # illegal filepath access
                    {'filename': 'test', 'equal_value': ('Eexist', 'File already exists')}, # file already exists
                    {'path': '/etc/', 'filename': 'passwd-', 'equal_value': ('Eparam', 'Invalid basepath')},
                ],
                admin_session
            )

            # NOTE: upload checker problem
            await self.upload_problem('float_checker.tar.xz', 'float checker', ProConst.STATUS_ONLINE, 4, admin_session)
            chal_id = -1
            def callback():
                nonlocal chal_id
                with open('tests/static_file/code/float_checker_wa.cpp') as f:
                    chal_id = self.submit_problem(4, f.read(), Compiler.GPP, admin_session)
                # NOTE: chal_id=12
            await self.wait_for_judge_finish(callback)
            err, chal = await ChalService.inst.get_chal(chal_id, with_result=True)
            self.assertIsNone(err)
            self.assertEqual([v.state for v in chal.subtask_results.values()], [ChalConst.STATE_WA] * len(chal.subtask_results))

            # NOTE: updatesinglefile
            pack_token = await self._upload_file('tests/static_file/float_checker/pass_all_checker.cpp', admin_session)
            res = admin_session.post('manage/pro/filemanager?proid=4', data={
                'reqtype': 'updatesinglefile',
                'pro_id': 4,
                'filename': 'checker.cpp',
                'pack_token': pack_token,
                'path': 'res/checker',
            })
            self.assertAPIReturnSuccess(res.text)
            with open('tests/static_file/float_checker/pass_all_checker.cpp') as f1:
                with open('problem/4/res/checker/checker.cpp') as f2:
                    self.assertEqual(f1.read(), f2.read())
            def callback():
                res = admin_session.post('submit', data={
                    'reqtype': 'rechal',
                    'chal_id': 12
                })
                self.assertAPIReturnValue(res.text, ('S', 12))
            await self.wait_for_judge_finish(callback)
            err, chal = await ChalService.inst.get_chal(chal_id, with_result=True)
            self.assertIsNone(err)
            self.assertEqual([v.state for v in chal.subtask_results.values()], [ChalConst.STATE_AC] * len(chal.subtask_results))

            self.assertTable(
                'manage/pro/filemanager',
                {
                    'reqtype': 'updatesinglefile',
                    'pro_id': 4,
                    'filename': 'checker.cpp',
                    'pack_token': pack_token,
                    'path': 'res/checker',
                },
                [
                    {'pro_id': '100', 'equal_value': ('Enoext', 'Problem not found')}, # problem not found
                    {'filename': '../check.cpp', 'equal_value': ('Eacces', 'Access denied: invalid file path')}, # illegal filepath access
                    {'filename': 'abc.cpp', 'equal_value': ('Enoext', 'File not found')}, # file not found
                    {'path': '/etc/', 'filename': 'group-', 'equal_value': ('Eparam', 'Invalid basepath')},
                ],
                admin_session
            )

            # NOTE: renamesinglefile
            res = admin_session.post('manage/pro/filemanager?proid=4', data={
                'reqtype': 'renamesinglefile',
                'pro_id': 4,
                'old_filename': 'checker.cpp',
                'new_filename': 'checker.cpp.cpp',
                'path': 'res/checker'
            })
            self.assertAPIReturnSuccess(res.text)
            res = admin_session.post('manage/pro/filemanager?proid=2', data={
                'reqtype': 'renamesinglefile',
                'pro_id': 2,
                'old_filename': 'stub.cpp',
                'new_filename': 'stub.cpp.old',
                'path': 'res/grader/cpp'
            })
            self.assertAPIReturnSuccess(res.text)
            self.assertTrue(os.path.exists('problem/2/res/grader/cpp/stub.cpp.old'))
            self.assertTrue(os.path.exists('problem/4/res/checker/checker.cpp.cpp'))

            def callback():
                res = admin_session.post('submit', data={
                    'reqtype': 'rechal',
                    'chal_id': 9
                })
                self.assertAPIReturnValue(res.text, ('S', 9))
            await self.wait_for_judge_finish(callback)

            err, chal = await ChalService.inst.get_chal(9, with_result=True)
            self.assertEqual(chal.total_result.state, ChalConst.STATE_CE)
            self.assertEqual([v.state for v in chal.subtask_results.values()], [ChalConst.STATE_SKIPPED] * len(chal.subtask_results))

            def callback():
                res = admin_session.post('submit', data={
                    'reqtype': 'rechal',
                    'chal_id': 12
                })
                self.assertAPIReturnValue(res.text, ('S', 12))
            await self.wait_for_judge_finish(callback)
            err, chal = await ChalService.inst.get_chal(12, with_result=True)
            self.assertEqual([v.state for v in chal.subtask_results.values()], [ChalConst.STATE_SKIPPED] * len(chal.subtask_results))

            self.assertTable(
                'manage/pro/filemanager',
                {
                    'reqtype': 'renamesinglefile',
                    'pro_id': 4,
                    'old_filename': 'checker.cpp',
                    'new_filename': 'checker.cpp.cpp',
                    'path': 'res/checker'
                },
                [
                    {'pro_id': '100', 'equal_value': ('Enoext', 'Problem not found')}, # problem not found
                    {'old_filename': '../../conf.json', 'new_filename': '../../conf.js', 'equal_value': ('Eacces', 'Access denied: invalid file path')}, # illegal filepath access
                    {'old_filename': 'checker.cpp', 'new_filename': 'checker.cpp.cpp', 'equal_value': ('Enoext', 'Old filename not found')}, # file not found
                    {'old_filename': 'checker.cpp.cpp', 'new_filename': 'checker.cpp.cpp', 'equal_value': ('Eexist', 'New filename already exists')}, # file already exists
                    {'path': '/etc/', 'old_filename': 'hostname', 'new_filename': 'chi', 'equal_value': ('Eparam', 'Invalid basepath')},
                ],
                admin_session
            )

            # NOTE: deletesinglefile
            res = admin_session.post('manage/pro/filemanager?proid=4', data={
                'reqtype': 'deletesinglefile',
                'pro_id': 4,
                'filename': 'checker.cpp.cpp',
                'path': 'res/checker'
            })
            self.assertAPIReturnSuccess(res.text)
            self.assertFalse(os.path.exists('problem/4/res/checker/checker.cpp.cpp'))
            res = admin_session.post('manage/pro/filemanager?proid=2', data={
                'reqtype': 'deletesinglefile',
                'pro_id': 2,
                'filename': 'stub.cpp.old',
                'path': 'res/grader/cpp'
            })
            self.assertAPIReturnSuccess(res.text)
            self.assertFalse(os.path.exists('problem/2/res/grader/cpp/stub.cpp.old'))

            self.assertTable(
                'manage/pro/filemanager',
                {
                    'reqtype': 'deletesinglefile',
                    'pro_id': 4,
                    'filename': 'checker.cpp.cpp',
                    'path': 'res/checker'
                },
                [
                    {'pro_id': '100', 'equal_value': ('Enoext', 'Problem not found')}, # problem not found
                    {'filename': 'checker.cpp', 'equal_value': ('Enoext', 'File not found')}, # file not found, checker.cpp was renamed to checker.cpp.cpp in the previous code
                    {'filename': '../../conf.json', 'equal_value': ('Eacces', 'Access denied: invalid file path')}, # file not found, checker.cpp was renamed to checker.cpp.cpp in the previous code
                    {'path': '/etc/', 'filename': 'hostname', 'equal_value': ('Eparam', 'Invalid basepath')},
                ],
                admin_session
            )

            # TODO: 做一次完整的 manual add problem

            pack_token = await self._upload_file('tests/static_file/toj659/res/grader/cpp/stub.cpp', admin_session)
            res = admin_session.post('manage/pro/filemanager?proid=2', data={
                'reqtype': 'addsinglefile',
                'pro_id': 2,
                'filename': 'stub.cpp',
                'path': 'res/grader/cpp',
                'pack_token': pack_token,
            })
            self.assertAPIReturnSuccess(res.text)

            pack_token = await self._upload_file('tests/static_file/float_checker/res/checker/checker.cpp', admin_session)
            res = admin_session.post('manage/pro/filemanager?proid=4', data={
                'reqtype': 'addsinglefile',
                'pro_id': 4,
                'filename': 'checker.cpp',
                'path': 'res/checker',
                'pack_token': pack_token,
            })
            self.assertAPIReturnSuccess(res.text)

            # test markdown support

            # 1. 準備一個測試用的 markdown 檔案
            md_path = 'tests/static_file/temp_cont.md'
            with open(md_path, 'w') as f:
                f.write('# Hello Markdown\n| A | B |\n|---|---|\n| 1 | 2 |\n*wonderhoi* **[k](wow)** $\\frac{mv^2}{r}$')

            # 2. Add: 上傳 cont.md，檢查是否生成 cont.html
            pack_token = await self._upload_file(md_path, admin_session)
            res = admin_session.post('manage/pro/filemanager?proid=4', data={
                'reqtype': 'addsinglefile',
                'pro_id': 4,
                'filename': 'cont.md',
                'path': 'http',
                'pack_token': pack_token,
            })
            self.assertAPIReturnSuccess(res.text)
            self.assertTrue(os.path.exists('problem/4/http/cont.md'))
            self.assertTrue(os.path.exists('problem/4/http/cont.html'))

            # 3. Delete: 刪除 cont.html，檢查是否自動還原 (因為 cont.md 存在)
            res = admin_session.post('manage/pro/filemanager?proid=4', data={
                'reqtype': 'deletesinglefile',
                'pro_id': 4,
                'filename': 'cont.html',
                'path': 'http',
            })
            self.assertAPIReturnSuccess(res.text)
            self.assertTrue(os.path.exists('problem/4/http/cont.html')) # Should be restored

            # 4. Rename: 將 cont.html 改名，檢查是否自動還原
            res = admin_session.post('manage/pro/filemanager?proid=4', data={
                'reqtype': 'renamesinglefile',
                'pro_id': 4,
                'old_filename': 'cont.html',
                'new_filename': 'cont.html.bak',
                'path': 'http',
            })
            self.assertAPIReturnSuccess(res.text)
            self.assertTrue(os.path.exists('problem/4/http/cont.html')) # Should be restored
            self.assertTrue(os.path.exists('problem/4/http/cont.html.bak'))

            # 5. Update: 更新 cont.md，檢查 cont.html 內容是否變更
            md_update_path = 'tests/static_file/temp_cont_update.md'
            with open(md_update_path, 'w') as f:
                f.write('# Updated Content')

            pack_token = await self._upload_file(md_update_path, admin_session)
            res = admin_session.post('manage/pro/filemanager?proid=4', data={
                'reqtype': 'updatesinglefile',
                'pro_id': 4,
                'filename': 'cont.md',
                'path': 'http',
                'pack_token': pack_token,
            })
            self.assertAPIReturnSuccess(res.text)

            with open('problem/4/http/cont.html') as f:
                content = f.read()
                self.assertIn('Updated Content', content)

            # 6. Rename to cont.md: 將其他檔案改名為 cont.md，檢查是否生成 cont.html
            # 6.1 先把原本的 cont.md 改名為 other.md (cont.html 應該不會被動到)
            admin_session.post('manage/pro/filemanager?proid=4', data={
                'reqtype': 'renamesinglefile',
                'pro_id': 4,
                'old_filename': 'cont.md',
                'new_filename': 'other.md',
                'path': 'http',
            })
            # 6.2 刪除 cont.html (確保乾淨)
            admin_session.post('manage/pro/filemanager?proid=4', data={
                'reqtype': 'deletesinglefile',
                'pro_id': 4,
                'filename': 'cont.html',
                'path': 'http',
            })
            self.assertFalse(os.path.exists('problem/4/http/cont.html'))

            # 6.3 改名 other.md 回 cont.md
            res = admin_session.post('manage/pro/filemanager?proid=4', data={
                'reqtype': 'renamesinglefile',
                'pro_id': 4,
                'old_filename': 'other.md',
                'new_filename': 'cont.md',
                'path': 'http',
            })
            self.assertAPIReturnSuccess(res.text)
            self.assertTrue(os.path.exists('problem/4/http/cont.html')) # Should be generated

            # 清理暫存檔案
            if os.path.exists(md_path): os.remove(md_path)
            if os.path.exists(md_update_path): os.remove(md_update_path)
