import os
import json

from tests.integrated.util import AsyncTest, AccountContext
from services.pro import ProService, ProConst, CheckerType, Limit
from services.chal import ChalService, Compiler


class ManageProUpdateTest(AsyncTest):
    async def main(self):
        with AccountContext("admin@test", "testtest") as admin_session:
            res = admin_session.post('manage/pro/update', data={
                'reqtype': 'updategeneral',
                'pro_id': 1,
                'name': 'GCDGCD',
                'tags': 'GCD',
                'status': ProConst.STATUS_HIDDEN,
                'allow_submit': "false",
            })
            self.assertAPIReturnSuccess(res.text)
            err, pro = await ProService.inst.get_pro(1, ProConst.PRO_STATUS_FULL)
            self.assertIsNone(err)
            assert pro
            self.assertEqual(pro.name, 'GCDGCD')
            self.assertEqual(pro.tags, 'GCD')
            self.assertEqual(pro.status, ProConst.STATUS_HIDDEN)
            self.assertFalse(pro.allow_submit)

            admin_session.post('manage/pro/update', data={
                'reqtype': 'updategeneral',
                'pro_id': 1,
                'name': 'GCD',
                'status': ProConst.STATUS_ONLINE,
                'tags': '',
                'allow_submit': 'true',
            })

            res = admin_session.post('manage/pro/update', data={
                'reqtype': 'updatelimit',
                'pro_id': 1,
                'limits': json.dumps({
                })
            })
            self.assertAPIReturnValue(res.text, ('Eparam', 'Missing default limit config'))

            res = admin_session.post('manage/pro/update', data={
                'reqtype': 'updatelimit',
                'pro_id': 1,
                'limits': json.dumps({
                    'default': {
                        'time': 1000,
                        'memory': 65536,
                        'output': 65536,
                    },
                    Compiler.PYTHON3: {
                        'time': 1500,
                        'memory': 65536,
                        'output': 65536,
                    },
                    Compiler.GCC: {},
                    Compiler.GPP: {
                        'timelimit': '',
                        'memlimit': '',
                    }
                })
            })
            self.assertAPIReturnSuccess(res.text)

            err, pro = await ProService.inst.get_pro(1, ProConst.PRO_STATUS_FULL)
            self.assertIsNone(err)
            assert pro
            self.assertEqual(pro.config.limits['default'], Limit(1000, 65536, 65536))
            self.assertEqual(pro.config.limits[str(Compiler.PYTHON3)], Limit(1500, 65536, 65536))

            chal_id = -1
            def callback():
                nonlocal chal_id
                with open('tests/static_file/code/tle.py') as f:
                    chal_id = self.submit_problem(1, f.read(), Compiler.PYTHON3, admin_session)

            await self.wait_for_judge_finish(callback)
            err, chal = await ChalService.inst.get_chal(chal_id, with_result=True)
            for s in chal.subtask_results.values():
                self.assertGreaterEqual(s.time, 1000)
            for t in chal.testdata_results.values():
                self.assertGreaterEqual(t.time, 1000)

            # TODO: we should check limits and file
            pack_token = self.get_upload_token(admin_session)
            file = open('tests/static_file/toj3.tar.xz', 'rb')
            await self.upload_file(file, os.path.getsize('tests/static_file/toj3.tar.xz'), pack_token)
            file.close()

            res = admin_session.post('manage/pro/update', data={
                'reqtype': 'uploadpackage',
                'pro_id': 1,
                'pack_token': pack_token,
            })
            self.assertAPIReturnSuccess(res.text)
