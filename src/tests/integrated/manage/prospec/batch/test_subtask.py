"""Integration tests for Batch problem subtask and testdata configuration."""
import re
import os
import json

from services.pro import ProService, ProConst, Problem, ProblemConfig
from services.chal import ChalService, ChalConst
from tests.integrated.util import AsyncTest, AccountContext


class BatchSubtaskTest(AsyncTest):
    """Test Batch problem subtask and testdata management."""

    async def _upload_file(self, filepath, session):
        pack_token = self.get_upload_token(session)
        with open(filepath, 'rb') as file:
            size = os.path.getsize(filepath)
            await self.upload_file(file, size, pack_token)

        return pack_token

    async def get_pro(self, pro_id: int) -> Problem:
        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        self.assertIsNone(err)
        assert pro
        assert pro.config
        return pro

    async def get_proconfig(self, pro_id: int) -> ProblemConfig:
            pro = await self.get_pro(pro_id)
            assert pro.config
            return pro.config


    async def main(self):
        with AccountContext("admin@test", "testtest") as admin_session:
            # NOTE: preview
            res = admin_session.post('manage/pro/updatetestdata?proid=1', data={
                'reqtype': 'preview',
                'pro_id': 1,
                'testdata_id': 0,
                'type': 'output',
            })
            with open('tests/static_file/toj3/res/testdata/1.out') as f:
                self.assertEqual(json.loads(res.text)['data'], f.read())

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
            with open('tests/static_file/toj3/res/testdata/1.out') as f:
                self.assertEqual(res.content.decode('utf-8'), f.read())

            res = admin_session.get('manage/pro/updatetestdata?proid=1&download=1&testdata_id=123&type=output')
            self.assertAPIReturnValue(res.text, ('Enoext', 'Testdata not found'))

            res = admin_session.get('manage/pro/updatetestdata?proid=1&download=1&testdata_id=0&type=what')
            self.assertAPIReturnValue(res.text, ('Eparam', 'Invalid testdata file type'))

            # NOTE: updaterate
            res = admin_session.post('manage/pro/updatesubtask?proid=1', data={
                'reqtype': 'updaterate',
                'pro_id': 1,
                'rate': 60,
                'subtask': 0,
            })
            self.assertAPIReturnSuccess(res.text)

            config = await self.get_proconfig(1)
            self.assertEqual(config.subtask_configs[0].rate, 60)

            # NOTE: addsubtask
            res = admin_session.post('manage/pro/updatesubtask?proid=1', data={
                'reqtype': 'addsubtask',
                'pro_id': 1,
                'rate': 20,
            })
            self.assertAPIReturnSuccess(res.text)
            config = await self.get_proconfig(1)
            self.assertEqual(len(config.subtask_configs), 3)
            self.assertEqual(config.subtask_configs[2].rate, 20)

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
            config = await self.get_proconfig(1)
            self.assertEqual(len(config.testdatas), 3)
            self.assertEqual(config.testdatas[2].inputfile, '3.in')
            self.assertEqual(config.testdatas[2].outputfile, '3.out')
            self.assertTrue(os.path.exists(f'problem/1/res/testdata/{config.testdatas[2].inputfile}'))
            self.assertTrue(os.path.exists(f'problem/1/res/testdata/{config.testdatas[2].outputfile}'))
            with open('tests/static_file/toj3/3.in') as f1:
                with open('problem/1/res/testdata/3.in') as f2:
                    self.assertEqual(f1.read(), f2.read())
            with open('tests/static_file/toj3/3.out') as f1:
                with open('problem/1/res/testdata/3.out') as f2:
                    self.assertEqual(f1.read(), f2.read())

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
            res = admin_session.post('manage/pro/updatesubtask?proid=1', data={
                'reqtype': 'settestdata',
                'pro_id': 1,
                'testdatas': '0-2',
                'subtask': 2,
            })
            self.assertAPIReturnSuccess(res.text)
            config = await self.get_proconfig(1)
            self.assertEqual(sorted(t.testdata_id for t in config.subtask_configs[2].testdatas),
                             [0, 1, 2])

            def callback():
                res = admin_session.post('submit', data={
                    'reqtype': 'rechal',
                    'chal_id': 1
                })
                self.assertAPIReturnValue(res.text, ('S', 1))
            await self.wait_for_judge_finish(callback)
            err, chal = await ChalService.inst.get_chal(1, with_result=True)
            self.assertIsNone(err)
            self.assertEqual([v.state for v in chal.subtask_results.values()], [ChalConst.STATE_AC] * len(chal.subtask_results))

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
            with open('tests/static_file/toj3/3.out.incorrect') as f1:
                with open('problem/1/res/testdata/3.out') as f2:
                    self.assertEqual(f1.read(), f2.read())

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
            err, chal = await ChalService.inst.get_chal(1, with_result=True)
            self.assertIsNone(err)
            self.assertEqual([v.state for v in chal.subtask_results.values()], [ChalConst.STATE_AC, ChalConst.STATE_AC, ChalConst.STATE_WA])

            # NOTE: setdepsubtasks
            res = admin_session.post('manage/pro/updatesubtask?proid=1', data={
                'reqtype': 'setdepsubtasks',
                'pro_id': 1,
                'dep_subtasks': '2', # NOTE: user input subtask id start from 1
                'subtask': 2,
            })
            self.assertAPIReturnSuccess(res.text)
            config = await self.get_proconfig(1)
            self.assertIn(1, config.subtask_configs[2].dependency_subtasks)

            res = admin_session.post('manage/pro/updatesubtask?proid=1', data={
                'reqtype': 'setdepsubtasks',
                'pro_id': 1,
                'dep_subtasks': '3', # NOTE: user input subtask id start from 1
                'subtask': 2,
            })
            self.assertAPIReturnValue(res.text, ('Eparam', 'Dependency subtasks have cycle'))
            # TODO: judge test

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
            config = await self.get_proconfig(1)
            self.assertEqual(len(config.testdatas), 4)
            self.assertEqual(config.testdatas[3].inputfile, '4.in')
            self.assertEqual(config.testdatas[3].outputfile, '4.out')

            res = admin_session.post('manage/pro/updatesubtask?proid=1', data={
                'reqtype': 'settestdata',
                'pro_id': 1,
                'testdatas': '0-1, 3',
                'subtask': 2,
            })
            self.assertAPIReturnSuccess(res.text)
            config = await self.get_proconfig(1)
            self.assertEqual(len(config.subtask_configs[2].testdatas), 3)
            self.assertEqual(sorted(t.testdata_id for t in config.subtask_configs[2].testdatas),
                             [0, 1, 3])
            def callback():
                res = admin_session.post('submit', data={
                    'reqtype': 'rechal',
                    'chal_id': 1
                })
                self.assertAPIReturnValue(res.text, ('S', 1))
            await self.wait_for_judge_finish(callback)
            err, chal = await ChalService.inst.get_chal(1, with_result=True)
            self.assertIsNone(err)
            self.assertEqual([v.state for v in chal.subtask_results.values()], [ChalConst.STATE_AC] * len(chal.subtask_results))

            # NOTE: deletesinglefile
            res = admin_session.post('manage/pro/updatetestdata?proid=1', data={
                'reqtype': 'deletesinglefile',
                'pro_id': 1,
                'testdata_id': 3,
            })
            self.assertAPIReturnSuccess(res.text)
            config = await self.get_proconfig(1)
            self.assertEqual(len(config.testdatas), 3)
            self.assertEqual(len(config.subtask_configs[2].testdatas), 2)
            self.assertEqual(sorted(t.testdata_id for t in config.subtask_configs[2].testdatas),
                             [0, 1])
            self.assertFalse(os.path.exists('problem/1/res/testdata/4.in'))
            self.assertFalse(os.path.exists('problem/1/res/testdata/4.out'))

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

            # NOTE: deletesubtask
            res = admin_session.post('manage/pro/updatesubtask?proid=1', data={
                'reqtype': 'deletesubtask',
                'pro_id': 1,
                'subtask': 2,
            })
            self.assertAPIReturnSuccess(res.text)
            config = await self.get_proconfig(1)
            self.assertEqual(len(config.subtask_configs), 2)
            self.assertNotIn(2, config.subtask_configs)

            def callback():
                res = admin_session.post('submit', data={
                    'reqtype': 'rechal',
                    'chal_id': 1
                })
                self.assertAPIReturnValue(res.text, ('S', 1))
            await self.wait_for_judge_finish(callback)
            err, chal = await ChalService.inst.get_chal(1, with_result=True)
            self.assertIsNone(err)
            self.assertEqual([v.state for v in chal.subtask_results.values()], [ChalConst.STATE_AC, ChalConst.STATE_AC])
