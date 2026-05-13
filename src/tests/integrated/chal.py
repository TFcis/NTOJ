import asyncio
from decimal import Decimal
import json
import shutil

from tornado.websocket import websocket_connect
from tornado.httpclient import HTTPRequest

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

            ws = await websocket_connect('ws://localhost:5501/be/ws')
            await ws.write_message(json.dumps({'type': 'register', 'data': 'chalstatesub'}))
            await ws.write_message(json.dumps({'type': 'chalstatesub_init', 'data': '1'}))
            ws.close() # TODO: Missing some test

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

            # Test non-owner receives sanitized messages (no CE/IE or extra messages)
            with AccountContext('test1@test', 'test') as user_session2:
                cookie_value = user_session2.cookies.get('id')
                headers = {"Cookie": f"id={cookie_value}"}

                # Read messages from ws_user and check sanitized content
                def _message(msg):
                    if msg is None:
                        return
                    data = json.loads(msg)
                    if data.get('type') != 'chalstatesub':
                        return
                    payload = json.loads(data['data'])
                    if 'total_result' in payload:
                        tr = payload['total_result']
                        self.assertEqual(tr.get('ce_message', ''), '')
                        self.assertEqual(tr.get('ie_message', ''), '')
                        self.assertEqual(tr.get('message_type'), MessageType.NONE.value)
                        # also check testdata results messages
                        for td in payload.get('testdata_results', {}).values():
                            self.assertEqual(td.get('message', ''), '')
                            self.assertEqual(td.get('message_type'), MessageType.NONE.value)
                        return

                ws_user = await websocket_connect(HTTPRequest('ws://localhost:5501/be/ws', headers=headers), on_message_callback=_message)
                await ws_user.write_message(json.dumps({'type': 'register', 'data': 'chalstatesub'}))
                await ws_user.write_message(json.dumps({'type': 'chalstatesub_init', 'data': '1'}))

                def callback2():
                    res = admin_session.post('submit', data={
                        'reqtype': 'rechal',
                        'chal_id': 1
                    })
                    self.assertAPIReturnValue(res.text, ('S', 1))

                await self.wait_for_judge_finish(callback2)
                ws_user.close()

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
                data = json.loads(msg)
                if data.get('type') == 'challist_sub':
                    self.assertEqual(int(data['data']), 1)

            ws1 = await websocket_connect('ws://localhost:5501/be/ws',
                                    on_message_callback=_message)
            await ws1.write_message(json.dumps({'type': 'register', 'data': 'challist_sub'}))

            def _message2(msg):
                if msg is None:
                    return
                data = json.loads(msg)
                if data.get('type') == 'challiststatesub':
                    msg_data = json.loads(data['data'])
                    self.assertEqual(int(msg_data['chal_id']), 2)

            ws2 = await websocket_connect('ws://localhost:5501/be/ws',
                                          on_message_callback=_message2)
            await ws2.write_message(json.dumps({'type': 'register', 'data': 'challiststatesub'}))
            await ws2.write_message(json.dumps({
                'type': 'challiststatesub_init',
                'data': json.dumps({
                    'chalids': [1, 2],
                    'acct_id': 1,
                })
            }))

            # websocket
            def callback():
                with open('tests/static_file/code/toj3.ac.py') as f:
                    chal_id = self.submit_problem(1, f.read(),
                                                Compiler.PYTHON3, admin_session)
                self.assertEqual(chal_id, 2)

            await self.wait_for_judge_finish(callback)
            ws1.close()
            ws2.close()

        with AccountContext('admin@test', 'testtest') as admin_session:
            def callback():
                path_prefix = 'tests/static_file/code'
                with open(f'{path_prefix}/toj3.wa.py') as f:
                    self.submit_problem(1, f.read(), Compiler.PYTHON3,
                                        admin_session)  # chal_id: 3

                with open(f'{path_prefix}/ce.cpp') as f:
                    self.submit_problem(1, f.read(), Compiler.GPP,
                                        admin_session)  # chal_id: 4

                with open(f'{path_prefix}/tle.cpp') as f:
                    self.submit_problem(1, f.read(), Compiler.GPP,
                                        admin_session)  # chal_id: 5

                with open(f'{path_prefix}/mle.py') as f:
                    self.submit_problem(1, f.read(), Compiler.PYTHON3,
                                        admin_session)  # chal_id: 6

                with open(f'{path_prefix}/re.cpp') as f:
                    self.submit_problem(1, f.read(), Compiler.GPP,
                                        admin_session)  # chal_id: 7

                with open(f'{path_prefix}/resig.cpp') as f:
                    self.submit_problem(1, f.read(), Compiler.GPP,
                                        admin_session)  # chal_id: 8

                with open(f'{path_prefix}/toj659.ac.cpp') as f:
                    self.submit_problem(2, f.read(), Compiler.GPP,
                                        admin_session)  # chal_id: 9

            await self.wait_for_judge_finish(callback)

            all_expected_states = [
                # 1, 2, 3, 4, 5
                ChalConst.STATE_AC, ChalConst.STATE_AC, ChalConst.STATE_WA, ChalConst.STATE_CE, ChalConst.STATE_TLE,
                # 6, 7, 8, 9
                ChalConst.STATE_RE, ChalConst.STATE_RE, ChalConst.STATE_RESIG, ChalConst.STATE_AC
            ]

            for chal_id, state in enumerate(all_expected_states, start=1):
                err, chal = await ChalService.inst.get_chal(chal_id, with_result=True)
                self.assertIsNone(err)
                self.assertEqual(chal.total_result.state, state, msg=f'chal_id: {chal_id}')

            _, chal = await ChalService.inst.get_chal(4, with_result=True)
            self.assertEqual([v.state for v in chal.subtask_results.values()], [ChalConst.STATE_SKIPPED] * len(chal.subtask_results))
            self.assertEqual(chal.total_result.message_type, MessageType.TEXT)
            self.assertTrue(len(chal.total_result.message) > 0)

            # Admin (owner) should receive full CE messages via WS for chal 4
            cookie_value = admin_session.cookies.get('id')
            headers = {"Cookie": f"id={cookie_value}"}
            got_message = False
            # Read messages and assert owner (admin) receives non-empty messages
            def _message2(msg):
                nonlocal got_message
                if msg is None:
                    return
                data = json.loads(msg)
                if data.get('type') != 'chalstatesub':
                    return
                payload = json.loads(data['data'])
                if 'total_result' in payload:
                    tr = payload['total_result']
                    self.assertGreater(len(tr.get('ce_message', '')), 0)
                    self.assertNotEqual(tr.get('message_type'), MessageType.NONE.value)
                    got_message = True
                    return

            ws_admin = await websocket_connect(HTTPRequest('ws://localhost:5501/be/ws', headers=headers), on_message_callback=_message2)
            await ws_admin.write_message(json.dumps({'type': 'register', 'data': 'chalstatesub'}))
            await ws_admin.write_message(json.dumps({'type': 'chalstatesub_init', 'data': '4'}))

            def callback3():
                res = admin_session.post('submit', data={'reqtype': 'rechal', 'chal_id': 4})
                self.assertAPIReturnValue(res.text, ('S', 4))

            await self.wait_for_judge_finish(callback3)
            ws_admin.close()
            await asyncio.sleep(5) # HACK: workaround to ensure message is processed
            self.assertTrue(got_message)

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
