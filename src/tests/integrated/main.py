import os
import json
import shutil

import requests
import tornado

from services.chal import ChalConst, ChalSearchingParamBuilder, ChalService, Compiler
from services.pro import ProConst, ProService
from services.user import UserService, UserConst
from services.judge import JudgeServerClusterService
from services.rate import RateService
from .util import AccountContext, AsyncTest
from .manage.acct import ManageAcctTest
from .manage.pro.filemanager import ManageProFileManagerTest
from .manage.pro.update import ManageProUpdateTest
from .manage.pro.updatetests import ManageProUpdateTestsTest
from .manage.pro.specialscore import ManageProSpecialScoreTest
from .manage.pack import ManagePackTest
from .pro import ProTest
from .acct import SignTest, AcctPageTest
from .board import BoardTest
from .bulletin import BulletinTest
from .chal import ChalTest, ChalListTest
from .contest import ContestTest
from .proclass import ProClassTest
from .proset import ProsetTest
from .ques import QuesTest
from .rank import ProRankTest, UserRankTest
from .submit import SubmitTest


class IntegratedTest(AsyncTest):
    async def init(self):
        self.session = requests.Session()
        _, acct_id = await UserService.inst.sign_up('admin@test', 'testtest', 'admin')
        _, acct = await UserService.inst.info_acct(acct_id)
        acct.acct_type = UserConst.ACCTTYPE_KERNEL
        await UserService.inst.update_acct(acct)

        try:
            shutil.move('problem', 'problem-tmp')
            shutil.move('code', 'code-tmp')
        except:
            pass
        os.mkdir('problem')
        os.mkdir('code')

    def cleanup(self):
        shutil.rmtree('problem')
        shutil.rmtree('code')
        try:
            shutil.move('problem-tmp', 'problem')
            shutil.move('code-tmp', 'code')
        except:
            pass
    def login(self, mail: str, pw: str):
        res = self.session.post('sign', data={
            'reqtype': 'signin',
            'mail': mail,
            'pw': pw,
        })
        for cookie in self.session.cookies:
            cookie.path = '/'

        self.assertAPIReturnSuccess(res.text)
        self.assertIn('id', self.session.cookies.get_dict())

    def logout(self):
        res = self.session.post('sign', data={
            'reqtype': 'signout',
        })
        self.assertAPIReturnSuccess(res.text)
        self.assertNotIn('id', self.session.cookies.get_dict())

    async def test_main(self):
        try:
            await self.init()

            with AccountContext('admin@test', 'testtest') as admin_session:
                # private=True will provide email
                err, acctlist = await UserService.inst.list_acct(UserConst.ACCTTYPE_KERNEL, private=True)
                self.assertIsNone(err)
                self.assertEqual(len(acctlist), 1)
                self.assertEqual(acctlist[0].mail, 'admin@test')
                self.assertEqual(acctlist[0].acct_type, UserConst.ACCTTYPE_KERNEL)
                self.assertTrue(JudgeServerClusterService.inst.is_server_online(), 'Integrated test need judge connected')

                await self.upload_problem('toj3.tar.xz', 'GCD', ProConst.STATUS_ONLINE, expected_pro_id=1, session=admin_session)

                err, pro = await ProService.inst.get_pro(1, ProConst.PRO_STATUS_NORMAL_USER)
                self.assertIsNone(err)
                assert pro
                self.assertTrue(pro.allow_submit)
                self.assertEqual(pro.name, 'GCD')
                self.assertEqual(pro.status, ProConst.STATUS_ONLINE)
                self.assertEqual(pro.tags, '')

                err, prolist = await ProService.inst.list_pro(ProConst.PRO_STATUS_NORMAL_USER)
                self.assertIsNone(err)
                self.assertEqual(len(prolist), 1)
                self.assertEqual(prolist[0].pro_id, 1)
                self.assertEqual(prolist[0].name, 'GCD')
                self.assertEqual(prolist[0].status, ProConst.STATUS_ONLINE)
                self.assertEqual(prolist[0].tags, '')
                self.assertTrue(prolist[0].allow_submit)

                err, rate = await RateService.inst.get_pro_ac_rate(pro.pro_id)
                self.assertIsNone(err)
                self.assertEqual(rate, {
                    'all_chal_cnt': 0,
                    'ac_chal_cnt': 0,
                    'user_all_chal_cnt': 0,
                    'user_ac_chal_cnt': 0,
                })

                err, topcoder = await RateService.inst.get_pro_topcoder(1)
                self.assertIsNone(err)
                self.assertIsNone(topcoder)

                err, acct = await UserService.inst.info_acct(1)
                self.assertIsNone(err)
                assert acct
                err, ratemap = await RateService.inst.map_rate_acct(acct)
                self.assertIsNone(err)
                self.assertEqual(len(ratemap), 0)
                err, ratemap = await RateService.inst.map_rate()
                self.assertIsNone(err)
                self.assertEqual(len(ratemap), 0)

                def callback():
                    chal_id = self.submit_problem(1, open('tests/static_file/code/toj3.ac.py').read(),
                                                  Compiler.PYTHON3, admin_session)
                    self.assertEqual(chal_id, 1)

                await self.wait_for_judge_finish(callback)

                err, chal = await ChalService.inst.get_chal(1, with_result=True)
                self.assertIsNone(err)
                assert chal
                self.assertEqual(chal.pro_id, 1)
                self.assertEqual(chal.acct_id, 1)
                self.assertEqual(chal.acct_name, 'admin')
                self.assertEqual(chal.contest_id, 0)
                self.assertEqual(chal.compiler_type, Compiler.PYTHON3)
                self.assertEqual(chal.total_result.state, ChalConst.STATE_AC)
                self.assertEqual([v.state for v in chal.testdata_results.values()], [ChalConst.STATE_AC] * len(chal.testdata_results))
                self.assertEqual([v.state for v in chal.subtask_results.values()], [ChalConst.STATE_AC] * len(chal.subtask_results))

                res = admin_session.post('code', {
                    'chal_id': 1
                })
                res = json.loads(res.text)
                self.assertNotEqual(res['status'], 'Eacces')
                self.assertEqual(res['data']['compiler_type'], 'python')
                self.assertEqual(res['data']['code'].strip(),
                                 tornado.escape.xhtml_escape(open('tests/static_file/code/toj3.ac.py').read().strip()))

                # view challist
                flt = ChalSearchingParamBuilder().build()
                err, challist = await ChalService.inst.list_chal(0, 20, flt)
                self.assertIsNone(err)
                self.assertEqual(len(challist), 1)
                self.assertEqual(challist[0].chal_id, 1)
                self.assertEqual(challist[0].pro_id, 1)
                self.assertEqual(challist[0].acct_id, 1)
                self.assertEqual(challist[0].contest_id, 0)
                self.assertEqual(challist[0].acct_name, 'admin')
                self.assertEqual(challist[0].total_result.state, ChalConst.STATE_AC)

                err, rate = await RateService.inst.get_pro_ac_rate(pro.pro_id)
                self.assertIsNone(err)
                self.assertEqual(rate, {
                    'all_chal_cnt': 1,
                    'ac_chal_cnt': 1,
                    'user_all_chal_cnt': 1,
                    'user_ac_chal_cnt': 1,
                })

                err, topcoder = await RateService.inst.get_pro_topcoder(1)
                self.assertIsNone(err)
                self.assertEqual(topcoder, {'acct_id': 1, 'name': 'admin', 'motto': ''})

                err, ratemap = await RateService.inst.map_rate_acct(acct)
                self.assertEqual(len(ratemap), 1)
                self.assertEqual(ratemap[1]['count'], 1)
                self.assertEqual(ratemap[1]['state'], ChalConst.STATE_AC)
                err, ratemap = await RateService.inst.map_rate()
                self.assertIsNone(err)
                self.assertEqual(ratemap[1][1]['count'], 1)
                self.assertEqual(ratemap[1][1]['state'], 1)

                # upload more problem
                await self.upload_problem('toj659.tar.xz', '猜數字', ProConst.STATUS_ONLINE, expected_pro_id=2,
                                          session=admin_session)
                await self.upload_problem('toj674.tar.xz', 'Move', ProConst.STATUS_ONLINE, expected_pro_id=3,
                                          session=admin_session)

            # signup
            self.signup('test1', 'test1@test', 'test')
            err, acctlist = await UserService.inst.list_acct(UserConst.ACCTTYPE_KERNEL, private=True)
            self.assertIsNone(err)
            self.assertEqual(len(acctlist), 2)
            self.assertEqual(acctlist[1].mail, 'test1@test')
            self.assertEqual(acctlist[1].acct_type, UserConst.ACCTTYPE_USER)

            s = [
                ChalTest().main,
                ChalListTest().main,
                SubmitTest().main,
                ProTest().main,
                BoardTest().main,
                ProClassTest().main,
                QuesTest().main,
                BulletinTest().main,
                SignTest().main,
                AcctPageTest().main,
                ManageAcctTest().main,
                ManageProUpdateTest().main,
                ManageProUpdateTestsTest().main,
                ManageProFileManagerTest().main,
                ManagePackTest().main,
                ContestTest().main
            ]
            for f in s:
                r = await f()
                if r is None:
                    continue

            # NOTE: all upload file should be cleaned
            self.assertEqual(os.listdir('tmp'), ['.gitkeep'])

        finally:
            self.cleanup()
