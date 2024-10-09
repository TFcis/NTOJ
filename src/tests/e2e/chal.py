import json
import shutil

from tornado.websocket import websocket_connect

from services.chal import ChalConst
from tests.e2e.util import AsyncTest, AccountContext


class ChalTest(AsyncTest):
    async def main(self):
        with AccountContext('test1@test', 'test') as user_session:
            # check code permission
            res = user_session.post('http://localhost:5501/code', data={
                'chal_id': 1
            })
            self.assertEqual(res.text, 'Eacces')

        with AccountContext('admin@test', 'testtest') as admin_session:
            # NOTE: If STATE_ERR(IE), judge request will not send
            shutil.move('code/1/main.py', 'code/1/main.cpp')
            res = admin_session.post('http://localhost:5501/code', data={
                'chal_id': 1
            })
            self.assertNotEqual(res.text, 'Eacces')
            res = json.loads(res.text)
            self.assertEqual(res['comp_type'], 'python')
            self.assertEqual(res['code'].strip(), 'EROOR: The code is lost on server.')

            res = admin_session.post('http://localhost:5501/submit', data={
                'reqtype': 'rechal',
                'chal_id': 1
            })
            self.assertEqual(res.text, '1')
            chal_states_result = self.get_chal_state(chal_id=1, session=admin_session)
            self.assertEqual(chal_states_result, [ChalConst.STATE_ERR] * len(chal_states_result))
            shutil.move('code/1/main.cpp', 'code/1/main.py')

            ws = await websocket_connect('ws://localhost:5501/chalnewstatesub')
            await ws.write_message(str(1))

            def callback():
                res = admin_session.post('http://localhost:5501/submit', data={
                    'reqtype': 'rechal',
                    'chal_id': 1
                })
                self.assertEqual(res.text, '1')

            await self.wait_for_judge_finish(callback)

            is_state_received = False
            while True:
                judging = False
                msg = await ws.read_message()
                if msg is None:
                    break

                chal_states = json.loads(msg)
                for state in chal_states:
                    is_state_received = True
                    if state['state'] == ChalConst.STATE_JUDGE:
                        judging = True
                        break

                if not judging:
                    break

            self.assertTrue(is_state_received)
            chal_states_result = self.get_chal_state(chal_id=1, session=admin_session)
            self.assertEqual(chal_states_result, [ChalConst.STATE_AC] * len(chal_states_result))


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
                'first_chal_id': 1,
                'last_chal_id': 2,
                'acct_id': 1,
            }))

            # websocket
            def callback():
                chal_id = self.submit_problem(1, open('tests/static_file/code/toj3.ac.py').read(),
                                              'python3', admin_session)
                self.assertEqual(chal_id, 2)

            await self.wait_for_judge_finish(callback)
            ws2.close()

        with AccountContext('admin@test', 'testtest') as admin_session:
            def callback():
                self.submit_problem(1, open('tests/static_file/code/toj3.wa.py').read(), 'python3',
                                    admin_session)  # chal_id: 3

                self.submit_problem(1, open('tests/static_file/code/ce.cpp').read(), 'g++',
                                    admin_session)  # chal_id: 4

                self.submit_problem(1, open('tests/static_file/code/tle.cpp').read(), 'g++',
                                    admin_session)  # chal_id: 5

                self.submit_problem(1, open('tests/static_file/code/mle.py').read(), 'python3',
                                    admin_session)  # chal_id: 6

                self.submit_problem(1, open('tests/static_file/code/re.cpp').read(), 'g++',
                                    admin_session)  # chal_id: 7

                self.submit_problem(1, open('tests/static_file/code/resig.cpp').read(), 'g++',
                                    admin_session)  # chal_id: 8

                self.submit_problem(2, open('tests/static_file/code/toj659.ac.cpp').read(), 'g++',
                                    admin_session)  # chal_id: 9

            await self.wait_for_judge_finish(callback)

            chal_states_result = self.get_chal_state(chal_id=3, session=admin_session)
            self.assertEqual(chal_states_result, [ChalConst.STATE_WA] * len(chal_states_result))

            chal_states_result = self.get_chal_state(chal_id=4, session=admin_session)
            self.assertEqual(chal_states_result, [ChalConst.STATE_CE] * len(chal_states_result))

            chal_states_result = self.get_chal_state(chal_id=5, session=admin_session)
            self.assertEqual(chal_states_result, [ChalConst.STATE_TLE] * len(chal_states_result))

            chal_states_result = self.get_chal_state(chal_id=6, session=admin_session)
            self.assertEqual(chal_states_result, [ChalConst.STATE_MLE] * len(chal_states_result))

            chal_states_result = self.get_chal_state(chal_id=7, session=admin_session)
            self.assertEqual(chal_states_result, [ChalConst.STATE_RE] * len(chal_states_result))

            chal_states_result = self.get_chal_state(chal_id=8, session=admin_session)
            self.assertEqual(chal_states_result, [ChalConst.STATE_RESIG] * len(chal_states_result))

            chal_states_result = self.get_chal_state(chal_id=9, session=admin_session)
            self.assertEqual(chal_states_result, [ChalConst.STATE_AC] * len(chal_states_result))

            html = self.get_html('http://localhost:5501/chal', admin_session)

            all_states = []
            all_expected_states = [
                ChalConst.STATE_AC, ChalConst.STATE_RESIG, ChalConst.STATE_RE, ChalConst.STATE_MLE, ChalConst.STATE_TLE,
                ChalConst.STATE_CE, ChalConst.STATE_WA, ChalConst.STATE_AC, ChalConst.STATE_AC
            ]
            for tr in html.select('tr'):
                if tr.attrs.get('id') in [None, "chalsub"]:
                    continue

                # NOTE: <td id="state" class="state-1"></td>
                state = int(tr.select_one('td#state').attrs['class'][0].split('-')[1])
                all_states.append(state)

            self.assertEqual(len(all_states), len(all_expected_states))
            self.assertEqual(all_states, all_expected_states)

            html = self.get_html('http://localhost:5501/chal?proid=2', admin_session)
            self.assertEqual(len(html.select('tr')), 2 + 1)

            html = self.get_html('http://localhost:5501/chal?acctid=123', admin_session)
            self.assertEqual(len(html.select('tr')), 2)

            html = self.get_html('http://localhost:5501/chal?compiler_type=python3', admin_session)
            self.assertEqual(len(html.select('tr')), 2 + 4)

            html = self.get_html(f'http://localhost:5501/chal?compiler_type=python3&state={ChalConst.STATE_AC}',
                                 admin_session)
            self.assertEqual(len(html.select('tr')), 2 + 2)
