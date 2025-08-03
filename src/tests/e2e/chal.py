import json
import shutil

from tornado.websocket import websocket_connect

from services.chal import ChalConst, Compiler, MessageType
from tests.e2e.util import AsyncTest, AccountContext


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
            self.assertEqual(res['data']['code'].strip(), 'EROOR: The code is lost on server.')

            res = admin_session.post('submit', data={
                'reqtype': 'rechal',
                'chal_id': 1
            })
            self.assertAPIReturnValue(res.text, ('S', 1))
            _, subtask_results, _ = self.get_chal_results(chal_id=1, session=admin_session)
            self.assertEqual([v.state for v in subtask_results.values()], [ChalConst.STATE_ERR] * len(subtask_results))
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
            _, subtask_results, _ = self.get_chal_results(chal_id=1, session=admin_session)
            self.assertEqual([v.state for v in subtask_results.values()], [ChalConst.STATE_AC] * len(subtask_results))


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

            _, subtask_results, _ = self.get_chal_results(chal_id=3, session=admin_session)
            self.assertEqual([v.state for v in subtask_results.values()], [ChalConst.STATE_WA] * len(subtask_results))

            total_result, subtask_results, _ = self.get_chal_results(chal_id=4, session=admin_session)
            self.assertEqual(total_result.state, ChalConst.STATE_CE)
            self.assertEqual([v.state for v in subtask_results.values()], [ChalConst.STATE_SKIPPED] * len(subtask_results))
            self.assertEqual(total_result.message_type, MessageType.TEXT)
            self.assertTrue(len(total_result.message) > 0)
            with AccountContext('test1@test', 'test') as user_session:
                total_result, _, _ = self.get_chal_results(chal_id=4, session=user_session)
                self.assertEqual(total_result.message_type, MessageType.NONE)

            _, subtask_results, _ = self.get_chal_results(chal_id=5, session=admin_session)
            self.assertEqual([v.state for v in subtask_results.values()], [ChalConst.STATE_TLE] * len(subtask_results))

            _, subtask_results, _ = self.get_chal_results(chal_id=6, session=admin_session)
            # self.assertEqual([v.state for v in subtask_results.values()], [ChalConst.STATE_MLE] * len(subtask_results))

            _, subtask_results, _ = self.get_chal_results(chal_id=7, session=admin_session)
            self.assertEqual([v.state for v in subtask_results.values()], [ChalConst.STATE_RE] * len(subtask_results))

            _, subtask_results, _ = self.get_chal_results(chal_id=8, session=admin_session)
            self.assertEqual([v.state for v in subtask_results.values()], [ChalConst.STATE_RESIG] * len(subtask_results))

            _, subtask_results, _ = self.get_chal_results(chal_id=9, session=admin_session)
            self.assertEqual([v.state for v in subtask_results.values()], [ChalConst.STATE_AC] * len(subtask_results))

            html = self.get_html('chal', admin_session)
            all_states = []
            all_expected_states = [
                ChalConst.STATE_AC, ChalConst.STATE_RESIG, ChalConst.STATE_RE, ChalConst.STATE_MLE, ChalConst.STATE_TLE,
                ChalConst.STATE_CE, ChalConst.STATE_WA, ChalConst.STATE_AC, ChalConst.STATE_AC
            ]
            # all_expected_states = [
            #     ChalConst.STATE_AC, ChalConst.STATE_RESIG, ChalConst.STATE_RE, ChalConst.STATE_RE, ChalConst.STATE_TLE,
            #     ChalConst.STATE_CE, ChalConst.STATE_WA, ChalConst.STATE_AC, ChalConst.STATE_AC
            # ]
            for tr in html.select('tr'):
                if tr.attrs.get('id') in [None, "chalsub"]:
                    continue

                # NOTE: <td id="state" class="state-1"></td>
                state = int(tr.select_one('td#state').attrs['class'][0].split('-')[1])
                all_states.append(state)

            self.assertEqual(len(all_states), len(all_expected_states))
            self.assertEqual(all_states, all_expected_states)

            html = self.get_html('chal?proid=2', admin_session)
            self.assertEqual(len(html.select('tr')), 2 + 1)

            html = self.get_html('chal?acctid=123', admin_session)
            self.assertEqual(len(html.select('tr')), 2)

            html = self.get_html(f'chal?compiler_type={Compiler.PYTHON3}', admin_session)
            self.assertEqual(len(html.select('tr')), 2 + 4)

            html = self.get_html(f'chal?compiler_type={Compiler.PYTHON3}&state={ChalConst.STATE_AC}',
                                 admin_session)
            self.assertEqual(len(html.select('tr')), 2 + 2)
