import os
import json

import tornado.escape

import config
from services.chal import ChalConst
from services.pro import ProConst
from tests.e2e.util import AsyncTest, AccountContext

# TODO: check_type, is_makefile


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
            res = admin_session.post('http://localhost:5501/manage/pro/filemanager?proid=1', data={
                'reqtype': 'preview',
                'pro_id': 1,
                'filename': 'cont.html',
                'path': 'http',
            })
            self.assertEqual(tornado.escape.xhtml_unescape(json.loads(res.text)),
                             open('tests/static_file/toj3/http/cont.html').read())

            res = admin_session.post('http://localhost:5501/manage/pro/filemanager?proid=1', data={
                'reqtype': 'preview',
                'pro_id': 1,
                'filename': '../conf.json',
                'path': 'http'
            })
            self.assertEqual(res.text, 'Eacces')

            res = admin_session.post('http://localhost:5501/manage/pro/filemanager?proid=1', data={
                'reqtype': 'preview',
                'pro_id': 1,
                'filename': 'cont.cont.html',
                'path': 'http'
            })
            self.assertEqual(res.text, 'Enoext')

            res = admin_session.post('http://localhost:5501/manage/pro/filemanager?proid=1', data={
                'reqtype': 'preview',
                'pro_id': 1,
                'filename': 'cont.html',
                'path': '/etc'
            })
            self.assertEqual(res.text, 'Eparam')

            # NOTE: addsinglefile
            pack_token = await self._upload_file('tests/static_file/toj3/3.in', admin_session)
            res = admin_session.post('http://localhost:5501/manage/pro/filemanager?proid=1', data={
                'reqtype': 'addsinglefile',
                'pro_id': 1,
                'filename': 'test',
                'path': 'http',
                'pack_token': pack_token,
            })
            self.assertEqual(res.text, 'S')
            self.assertTrue(os.path.exists('problem/1/http/test'))
            self.assertTrue(os.path.exists(f'{config.WEB_PROBLEM_STATIC_FILE_DIRECTORY}/1/test'))
            self.assertEqual(open('tests/static_file/toj3/3.in').read(), open('problem/1/http/test').read())

            res = admin_session.post('http://localhost:5501/manage/pro/filemanager?proid=1', data={
                'reqtype': 'addsinglefile',
                'pro_id': 1,
                'filename': 'test2',
                'path': 'httpx',
                'pack_token': pack_token,
            })
            self.assertEqual(res.text, 'Eparam')
            res = admin_session.post('http://localhost:5501/manage/pro/filemanager?proid=1', data={
                'reqtype': 'addsinglefile',
                'pro_id': 1,
                'filename': '../etc',
                'path': 'http',
                'pack_token': pack_token,
            })
            self.assertEqual(res.text, 'Eacces')
            res = admin_session.post('http://localhost:5501/manage/pro/filemanager?proid=1', data={
                'reqtype': 'addsinglefile',
                'pro_id': 1,
                'filename': 'test',
                'path': 'http',
                'pack_token': pack_token,
            })
            self.assertEqual(res.text, 'Eexist')

            # NOTE: upload checker problem
            await self.upload_problem('float_checker.tar.xz', 'float checker', ProConst.STATUS_ONLINE, 4, admin_session)
            chal_id = -1
            def callback():
                nonlocal chal_id
                chal_id = self.submit_problem(4, open('tests/static_file/code/float_checker_wa.cpp').read(), 'g++', admin_session)
                # NOTE: chal_id=12
            await self.wait_for_judge_finish(callback)
            chal_states_result = self.get_chal_state(chal_id=chal_id, session=admin_session)
            self.assertEqual(chal_states_result, [ChalConst.STATE_WA])

            # NOTE: updatesinglefile
            pack_token = await self._upload_file('tests/static_file/float_checker/pass_all_checker.cpp', admin_session)
            res = admin_session.post('http://localhost:5501/manage/pro/filemanager?proid=4', data={
                'reqtype': 'updatesinglefile',
                'pro_id': 4,
                'filename': 'check.cpp',
                'pack_token': pack_token,
                'path': 'res/check',
            })
            self.assertEqual(res.text, 'S')
            self.assertEqual(open('tests/static_file/float_checker/pass_all_checker.cpp').read(), open('problem/4/res/check/check.cpp').read())
            def callback():
                res = admin_session.post('http://localhost:5501/submit', data={
                    'reqtype': 'rechal',
                    'chal_id': 12
                })
                self.assertEqual(res.text, '12')
            await self.wait_for_judge_finish(callback)
            chal_states_result = self.get_chal_state(chal_id=12, session=admin_session)
            self.assertEqual(chal_states_result, [ChalConst.STATE_AC])
            res = admin_session.post('http://localhost:5501/manage/pro/filemanager?proid=4', data={
                'reqtype': 'updatesinglefile',
                'pro_id': 4,
                'filename': '../check.cpp',
                'pack_token': pack_token,
                'path': 'res/check',
            })
            self.assertEqual(res.text, 'Eacces')
            res = admin_session.post('http://localhost:5501/manage/pro/filemanager?proid=4', data={
                'reqtype': 'updatesinglefile',
                'pro_id': 4,
                'filename': 'abc.cpp',
                'pack_token': pack_token,
                'path': 'res/check',
            })
            self.assertEqual(res.text, 'Enoext')
            res = admin_session.post('http://localhost:5501/manage/pro/filemanager?proid=4', data={
                'reqtype': 'updatesinglefile',
                'pro_id': 4,
                'filename': 'abc.cpp',
                'pack_token': pack_token,
                'path': '/etc/',
            })
            self.assertEqual(res.text, 'Eparam')

            # NOTE: renamesinglefile
            res = admin_session.post('http://localhost:5501/manage/pro/filemanager?proid=4', data={
                'reqtype': 'renamesinglefile',
                'pro_id': 4,
                'old_filename': 'check.cpp',
                'new_filename': 'check.cpp.cpp',
                'path': 'res/check'
            })
            self.assertEqual(res.text, 'S')
            res = admin_session.post('http://localhost:5501/manage/pro/filemanager?proid=2', data={
                'reqtype': 'renamesinglefile',
                'pro_id': 2,
                'old_filename': 'stub.cpp',
                'new_filename': 'stub.cpp.cpp',
                'path': 'res/make'
            })
            self.assertEqual(res.text, 'S')
            self.assertTrue(os.path.exists('problem/2/res/make/stub.cpp.cpp'))
            self.assertTrue(os.path.exists('problem/4/res/check/check.cpp.cpp'))

            def callback():
                res = admin_session.post('http://localhost:5501/submit', data={
                    'reqtype': 'rechal',
                    'chal_id': 9
                })
                self.assertEqual(res.text, '9')
            await self.wait_for_judge_finish(callback)
            chal_states_result = self.get_chal_state(chal_id=9, session=admin_session)
            self.assertEqual(chal_states_result, [ChalConst.STATE_CE])

            def callback():
                res = admin_session.post('http://localhost:5501/submit', data={
                    'reqtype': 'rechal',
                    'chal_id': 12
                })
                self.assertEqual(res.text, '12')
            await self.wait_for_judge_finish(callback)
            chal_states_result = self.get_chal_state(chal_id=12, session=admin_session)
            self.assertEqual(chal_states_result, [ChalConst.STATE_ERR])
            res = admin_session.post('http://localhost:5501/manage/pro/filemanager?proid=4', data={
                'reqtype': 'renamesinglefile',
                'pro_id': 4,
                'old_filename': 'check.cpp',
                'new_filename': 'check.cpp.cpp',
                'path': 'res/check'
            })
            self.assertEqual(res.text, 'Enoext')
            res = admin_session.post('http://localhost:5501/manage/pro/filemanager?proid=4', data={
                'reqtype': 'renamesinglefile',
                'pro_id': 4,
                'old_filename': 'check.cpp.cpp',
                'new_filename': 'check.cpp.cpp',
                'path': 'res/check'
            })
            self.assertEqual(res.text, 'Eexist')
            res = admin_session.post('http://localhost:5501/manage/pro/filemanager?proid=4', data={
                'reqtype': 'renamesinglefile',
                'pro_id': 4,
                'old_filename': 'check.cpp.cpp',
                'new_filename': 'check.cpp.cpp',
                'path': '/etc'
            })
            self.assertEqual(res.text, 'Eparam')
            res = admin_session.post('http://localhost:5501/manage/pro/filemanager?proid=4', data={
                'reqtype': 'renamesinglefile',
                'pro_id': 4,
                'old_filename': '../../conf.json',
                'new_filename': '../../conf.sss',
                'path': 'res/check'
            })
            self.assertEqual(res.text, 'Eacces')

            # NOTE: deletesinglefile
            res = admin_session.post('http://localhost:5501/manage/pro/filemanager?proid=4', data={
                'reqtype': 'deletesinglefile',
                'pro_id': 4,
                'filename': 'check.cpp.cpp',
                'path': 'res/check'
            })
            self.assertEqual(res.text, 'S')
            self.assertFalse(os.path.exists('problem/4/res/check/check.cpp.cpp'))
            res = admin_session.post('http://localhost:5501/manage/pro/filemanager?proid=2', data={
                'reqtype': 'deletesinglefile',
                'pro_id': 2,
                'filename': 'stub.cpp.cpp',
                'path': 'res/make'
            })
            self.assertEqual(res.text, 'S')
            self.assertFalse(os.path.exists('problem/2/res/make/stub.cpp.cpp'))

            res = admin_session.post('http://localhost:5501/manage/pro/filemanager?proid=4', data={
                'reqtype': 'deletesinglefile',
                'pro_id': 4,
                'filename': 'check.cpp',
                'path': 'res/check'
            })
            self.assertEqual(res.text, 'Enoext')
            res = admin_session.post('http://localhost:5501/manage/pro/filemanager?proid=4', data={
                'reqtype': 'deletesinglefile',
                'pro_id': 4,
                'filename': 'hostname',
                'path': '/etc'
            })
            self.assertEqual(res.text, 'Eparam')
            res = admin_session.post('http://localhost:5501/manage/pro/filemanager?proid=4', data={
                'reqtype': 'deletesinglefile',
                'pro_id': 4,
                'filename': '../../conf.json',
                'path': 'res/check'
            })
            self.assertEqual(res.text, 'Eacces')

            # TODO: 檢查 pro_id=1只有http, pro_id=2有http與make，pro_id=4有http與check
            html = self.get_html('http://localhost:5501/manage/pro/filemanager?proid=1', admin_session)
            dirs = html.select_one('div#dirs').select('div.accordion-item')
            self.assertEqual(len(dirs), 1) # http

            html = self.get_html('http://localhost:5501/manage/pro/filemanager?proid=2', admin_session)
            dirs = html.select_one('div#dirs').select('div.accordion-item')
            self.assertEqual(len(dirs), 2) # http, res/make

            html = self.get_html('http://localhost:5501/manage/pro/filemanager?proid=4', admin_session)

            dirs = html.select_one('div#dirs').select('div.accordion-item')
            self.assertEqual(len(dirs), 2) # http, res/check

            # TODO: 做一次完整的 manual add problem

            pack_token = await self._upload_file('tests/static_file/toj659/res/make/stub.cpp', admin_session)
            res = admin_session.post('http://localhost:5501/manage/pro/filemanager?proid=2', data={
                'reqtype': 'addsinglefile',
                'pro_id': 2,
                'filename': 'stub.cpp',
                'path': 'res/make',
                'pack_token': pack_token,
            })
            self.assertEqual(res.text, 'S')

            pack_token = await self._upload_file('tests/static_file/float_checker/res/check/check.cpp', admin_session)
            res = admin_session.post('http://localhost:5501/manage/pro/filemanager?proid=4', data={
                'reqtype': 'addsinglefile',
                'pro_id': 4,
                'filename': 'check.cpp',
                'path': 'res/check',
                'pack_token': pack_token,
            })
            self.assertEqual(res.text, 'S')
