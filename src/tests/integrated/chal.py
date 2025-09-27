from decimal import Decimal
import json
import shutil

from tornado.websocket import websocket_connect

from services.pro import ProConst, ProService
from services.rate import RateService
from services.user import UserService
from services.chal import ChalSearchingParamBuilder, ChalService, ChalConst, Compiler, MessageType, SubtaskResult, TotalResult
from tests.integrated.util import AsyncTest, AccountContext


class ChalTest(AsyncTest):
    async def main(self):
        with AccountContext('test1@test', 'test') as user_session:
            # check code permission
            res = user_session.post('code', data={
                'chal_id': 1
            })
            self.assertAPIReturnValue(res.text, ('Eacces', 'Permission denied'))

        with AccountContext('admin@test', 'testtest') as admin_session:
            # NOTE: If STATE_ERR(IE), judge request will not send
            shutil.move('code/1/main.py', 'code/1/main.cpp')
            res = admin_session.post('code', data={
                'chal_id': 1
            })
            res = json.loads(res.text)
            self.assertNotEqual(res['status'], 'Eacces')
            self.assertEqual(res['data']['compiler_type'], 'python')
            self.assertEqual(res['data']['code'].strip(), 'ERROR: The code is lost on the server.')

            res = admin_session.post('submit', data={
                'reqtype': 'rechal',
                'chal_id': 1
            })
            self.assertAPIReturnValue(res.text, ('S', 1))
            err, chal = await ChalService.inst.get_chal(1, with_result=True)
            self.assertIsNone(err)
            self.assertEqual(chal.total_result.state, ChalConst.STATE_ERR)
            self.assertEqual([v.state for v in chal.testdata_results.values()], [ChalConst.STATE_ERR] * len(chal.testdata_results))
            self.assertEqual([v.state for v in chal.subtask_results.values()], [ChalConst.STATE_ERR] * len(chal.subtask_results))

            shutil.move('code/1/main.cpp', 'code/1/main.py')

            ws = await websocket_connect('ws://localhost:5501/chalnewstatesub')
            await ws.write_message(str(1))

            def callback():
                res = admin_session.post('submit', data={
                    'reqtype': 'rechal',
                    'chal_id': 1
                })
                self.assertAPIReturnValue(res.text, ('S', 1))

            await self.wait_for_judge_finish(callback)

            # TODO: test chalnewstatesub
            # is_state_received = False
            # while True:
            #     judging = False
            #     msg = await ws.read_message()
            #     if msg is None:
            #         break
            #
            #     chal_states = json.loads(msg)
            #     for state in chal_states:
            #         is_state_received = True
            #         if state['state'] == ChalConst.STATE_JUDGE:
            #             judging = True
            #             break
            #
            #     if not judging:
            #         break
            #
            # self.assertTrue(is_state_received)
            err, chal = await ChalService.inst.get_chal(1, with_result=True)
            self.assertIsNone(err)
            self.assertEqual(chal.total_result.state, ChalConst.STATE_AC)
            self.assertEqual([v.state for v in chal.testdata_results.values()], [ChalConst.STATE_AC] * len(chal.testdata_results))
            self.assertEqual([v.state for v in chal.subtask_results.values()], [ChalConst.STATE_AC] * len(chal.subtask_results))

            res = admin_session.post('chal/1', data={
                'reqtype': 'reject',
                'reason': 'Reject reason'
            })
            self.assertAPIReturnSuccess(res.text)
            err, chal = await ChalService.inst.get_chal(1, with_result=True)
            self.assertIsNone(err)
            self.assertEqual(chal.total_result.state, ChalConst.STATE_REJECTED)
            self.assertEqual([v.state for v in chal.testdata_results.values()], [ChalConst.STATE_REJECTED] * len(chal.testdata_results))
            self.assertEqual([v.state for v in chal.subtask_results.values()], [ChalConst.STATE_REJECTED] * len(chal.subtask_results))
            self.assertEqual(chal.total_result.message, 'Reject reason')

            def callback():
                res = admin_session.post('submit', data={
                    'reqtype': 'rechal',
                    'chal_id': 1
                })
                self.assertAPIReturnValue(res.text, ('S', 1))

            await self.wait_for_judge_finish(callback)

        await ChalService.inst.db.execute('UPDATE problem SET rate_precision = 3 WHERE pro_id=1;')
        err, pro = await ProService.inst.get_pro(1, ProConst.PRO_STATUS_FULL)
        self.assertIsNone(err)
        self.assertEqual(pro.config.rate_precision, 3)
        await ChalService.inst.update_total_result(1,
                                                   TotalResult(ChalConst.STATE_AC, 0, 65536, Decimal("1.110"), "", MessageType.NONE))
        await ChalService.inst.update_subtask_result(1, SubtaskResult(0, ChalConst.STATE_AC, 0, 65536, Decimal("1.110")))
        await ChalService.inst.update_subtask_result(1, SubtaskResult(1, ChalConst.STATE_AC, 0, 65536, Decimal("1.110")))

        err, acct = await UserService.inst.info_acct(1)
        self.assertIsNone(err)
        assert acct

        err, ratemap = await RateService.inst.map_rate_acct(acct)
        self.assertEqual(ratemap[1]['rate'], Decimal('1.110'))
        err, ratemap = await RateService.inst.map_rate()
        self.assertEqual(ratemap[1][1]['rate'], Decimal('1.110'))
        err, acctrate = await RateService.inst.get_acct_rate_and_chal_cnt(acct)
        self.assertEqual(acctrate['rate'], Decimal('2.220'))

        await ChalService.inst.db.execute('UPDATE problem SET rate_precision = 1 WHERE pro_id=1;')
        err, ratemap = await RateService.inst.map_rate_acct(acct)
        self.assertEqual(ratemap[1]['rate'], Decimal('1.1'))
        err, ratemap = await RateService.inst.map_rate()
        self.assertEqual(ratemap[1][1]['rate'], Decimal('1.1'))
        err, acctrate = await RateService.inst.get_acct_rate_and_chal_cnt(acct)
        self.assertEqual(acctrate['rate'], Decimal('2.220'))

        await ChalService.inst.db.execute('UPDATE problem SET rate_precision = 0 WHERE pro_id=1;')
        err, acctrate = await RateService.inst.get_acct_rate_and_chal_cnt(acct)
        self.assertEqual(acctrate['rate'], Decimal('2.220'))
        with AccountContext('admin@test', 'testtest') as admin_session:
            def callback():
                res = admin_session.post('submit', data={
                    'reqtype': 'rechal',
                    'chal_id': 1
                })
                self.assertAPIReturnValue(res.text, ('S', 1))

            await self.wait_for_judge_finish(callback)


class ChalListTest(AsyncTest):
    async def main(self):
        with AccountContext('admin@test', 'testtest') as admin_session:
            def _message(msg):
                if msg is None:
                    return

                self.assertEqual(int(msg), 1)

            await websocket_connect('ws://localhost:5501/challistnewchalsub',
                                    on_message_callback=_message)

            def _message(msg):
                if msg is None:
                    return

                self.assertEqual(int(json.loads(msg)['chal_id']), 2)

            ws2 = await websocket_connect('ws://localhost:5501/challistnewstatesub',
                                          on_message_callback=_message)

            await ws2.write_message(json.dumps({
                'chalids': [1, 2],
                'acct_id': 1,
            }))

            # websocket
            def callback():
                chal_id = self.submit_problem(1, open('tests/static_file/code/toj3.ac.py').read(),
                                              Compiler.PYTHON3, admin_session)
                self.assertEqual(chal_id, 2)

            await self.wait_for_judge_finish(callback)
            ws2.close()

        with AccountContext('admin@test', 'testtest') as admin_session:
            def callback():
                self.submit_problem(1, open('tests/static_file/code/toj3.wa.py').read(), Compiler.PYTHON3,
                                    admin_session)  # chal_id: 3

                self.submit_problem(1, open('tests/static_file/code/ce.cpp').read(), Compiler.GPP,
                                    admin_session)  # chal_id: 4

                self.submit_problem(1, open('tests/static_file/code/tle.cpp').read(), Compiler.GPP,
                                    admin_session)  # chal_id: 5

                self.submit_problem(1, open('tests/static_file/code/mle.py').read(), Compiler.PYTHON3,
                                    admin_session)  # chal_id: 6

                self.submit_problem(1, open('tests/static_file/code/re.cpp').read(), Compiler.GPP,
                                    admin_session)  # chal_id: 7

                self.submit_problem(1, open('tests/static_file/code/resig.cpp').read(), Compiler.GPP,
                                    admin_session)  # chal_id: 8

                self.submit_problem(2, open('tests/static_file/code/toj659.ac.cpp').read(), Compiler.GPP,
                                    admin_session)  # chal_id: 9

            await self.wait_for_judge_finish(callback)

            all_expected_states = [
                # 1, 2, 3, 4, 5
                ChalConst.STATE_AC, ChalConst.STATE_AC, ChalConst.STATE_WA, ChalConst.STATE_CE, ChalConst.STATE_TLE,
                # 6, 7, 8, 9
                ChalConst.STATE_MLE, ChalConst.STATE_RE, ChalConst.STATE_RESIG, ChalConst.STATE_AC
            ]

            for chal_id, state in enumerate(all_expected_states, start=1):
                err, chal = await ChalService.inst.get_chal(chal_id, with_result=True)
                self.assertIsNone(err)
                self.assertEqual(chal.total_result.state, state, msg=f'chal_id: {chal_id}')

            _, chal = await ChalService.inst.get_chal(4, with_result=True)
            self.assertEqual([v.state for v in chal.subtask_results.values()], [ChalConst.STATE_SKIPPED] * len(chal.subtask_results))
            self.assertEqual(chal.total_result.message_type, MessageType.TEXT)
            self.assertTrue(len(chal.total_result.message) > 0)

            flt = ChalSearchingParamBuilder().build()
            err, challist = await ChalService.inst.list_chal(0, 20, flt)
            self.assertIsNone(err)
            self.assertEqual(len(challist), 9)
            self.assertEqual([v.total_result.state for v in challist], list(reversed(all_expected_states)))
            err, count = await ChalService.inst.get_chals_count(flt)
            self.assertIsNone(err)
            self.assertEqual(count, 9)

            flt = ChalSearchingParamBuilder().pro([2]).build()
            err, challist = await ChalService.inst.list_chal(0, 20, flt)
            self.assertIsNone(err)
            self.assertEqual(len(challist), 1)
            err, count = await ChalService.inst.get_chals_count(flt)
            self.assertIsNone(err)
            self.assertEqual(count, 1)

            flt = ChalSearchingParamBuilder().acct([3227]).build()
            err, challist = await ChalService.inst.list_chal(0, 20, flt)
            self.assertIsNone(err)
            self.assertEqual(len(challist), 0)
            err, count = await ChalService.inst.get_chals_count(flt)
            self.assertIsNone(err)
            self.assertEqual(count, 0)

            flt = ChalSearchingParamBuilder().compiler(Compiler.PYTHON3).build()
            err, challist = await ChalService.inst.list_chal(0, 20, flt)
            self.assertIsNone(err)
            self.assertEqual(len(challist), 4)
            err, count = await ChalService.inst.get_chals_count(flt)
            self.assertIsNone(err)
            self.assertEqual(count, 4)

            flt = ChalSearchingParamBuilder().compiler(Compiler.PYTHON3).state(ChalConst.STATE_AC).build()
            err, challist = await ChalService.inst.list_chal(0, 20, flt)
            self.assertIsNone(err)
            self.assertEqual(len(challist), 2)
            err, count = await ChalService.inst.get_chals_count(flt)
            self.assertIsNone(err)
            self.assertEqual(count, 2)
