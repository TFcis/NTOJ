import os
import json
import shutil

import requests
import tornado

from services.chal import ChalConst
from services.pro import ProConst
from services.user import UserService, UserConst
from .util import AccountContext, AsyncTest
from .manage.acct import ManageAcctTest
from .manage.pro.filemanager import ManageProFileManagerTest
from .manage.pro.update import ManageProUpdateTest
from .manage.pro.updatetests import ManageProUpdateTestsTest
from .manage.pack import ManagePackTest
from .pro import ProTest
from .acct import SignTest, AcctPageTest
from .board import BoardTest
from .bulletin import BulletinTest
from .chal import ChalTest, ChalListTest
from .contest import ContestTest
from .proclass import PublicProClassTest
from .proset import ProsetTest
from .ques import QuesTest
from .rank import ProRankTest, UserRankTest
from .submit import SubmitTest


class E2ETest(AsyncTest):
    async def init(self):
        self.session = requests.Session()
        _, acct_id = await UserService.inst.sign_up('admin@test', 'testtest', 'admin')
        await UserService.inst.update_acct(acct_id, UserConst.ACCTTYPE_KERNEL, 'admin', '', '', '')

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
        res = self.session.post('http://localhost:5501/sign', data={
            'reqtype': 'signin',
            'mail': mail,
            'pw': pw,
        })
        for cookie in self.session.cookies:
            cookie.path = '/'

        self.assertEqual(res.text, 'S')
        self.assertIn('id', self.session.cookies.get_dict())

    def logout(self):
        res = self.session.post('http://localhost:5501/sign', data={
            'reqtype': 'signout',
        })
        self.assertEqual(res.text, 'S')
        self.assertNotIn('id', self.session.cookies.get_dict())

    async def test_main(self):
        """

        init test env
        basic function test {
            index
            upload problem
            view problem
            view proset
            submit problem
            view chal
            view challist
            sign
        }

        component test {
            submit restrict
            challist filter, websocket
            chal rechal, websocket
            proset filter
            acct-page
            proclass
            bulletin
            board
            ques
            pro-rank
            user-rank
        }

        manage test {
            acct
            group
            problem
            judge
        }

        contest test {
            basic function test {
            }
        }

        """
        try:
            await self.init()

            with AccountContext('admin@test', 'testtest') as admin_session:
                html = self.get_html('http://localhost:5501/index/', admin_session)
                self.assertIsNotNone(html.select_one('li.manage'))
                self.assertEqual(html.select_one('script#indexjs').attrs.get('acct_id'), '1')

                html = self.get_html('http://localhost:5501/manage/judge', admin_session)
                self.assertEqual(html.select('tr')[1].select('td')[2].text, 'Online', 'Test need judge connected')

                await self.upload_problem('toj3.tar.xz', 'GCD', ProConst.STATUS_ONLINE, expected_pro_id=1, session=admin_session)

                # view proset
                html = self.get_html('http://localhost:5501/proset', admin_session)
                trs = html.select('tr')[1:]
                self.assertEqual(trs[0].select('td')[0].text, '1')  # pro_id
                self.assertEqual(trs[0].select('td')[1].text, 'Todo')  # pro status
                self.assertEqual(trs[0].select('td')[2].text.strip().replace('\n', ''), 'GCD')  # pro name
                self.assertEqual(trs[0].select('td')[3].text.strip().replace('\n', ''),
                                 '0.00%(0/ 0)')  # pro ac ratio (user)
                self.assertEqual(trs[0].select('td')[4].text.strip().replace('\n', ''),
                                 '0.00%(0/0)')  # pro ac ratio (submission)
                self.assertEqual(trs[0].select('td')[5].text, '')  # pro tags

                # view problem
                html = self.get_html('http://localhost:5501/pro/1', admin_session)
                self.assertIsNotNone(html.select_one('h3'))
                self.assertIsNotNone(html.select_one('a.btn.btn-warning'))

                res = admin_session.get('http://localhost:5501/pro/1/cont.html')
                self.assertIn('X-Accel-Redirect', res.headers)

                res = admin_session.get('http://localhost:5501/submit/1')
                self.assertNotEqual(res.text, '<h1 style="color: red;">All Judge Server Offline</h1>')

                # submit problem
                def callback():
                    chal_id = self.submit_problem(1, open('tests/static_file/code/toj3.ac.py').read(),
                                                  'python3', admin_session)

                    self.assertEqual(chal_id, 1)

                # wait for judge finish
                await self.wait_for_judge_finish(callback)

                # view chal
                chal_states_result = self.get_chal_state(chal_id=1, session=admin_session)
                self.assertEqual(chal_states_result, [ChalConst.STATE_AC] * len(chal_states_result))

                # query code
                res = admin_session.post('http://localhost:5501/code', {
                    'chal_id': 1
                })
                self.assertNotEqual(res.text, 'Eacces')
                res = json.loads(res.text)
                self.assertEqual(res['comp_type'], 'python')
                self.assertEqual(res['code'].strip(),
                                 tornado.escape.xhtml_escape(open('tests/static_file/code/toj3.ac.py').read().strip()))

                # view challist
                html = self.get_html('http://localhost:5501/chal', admin_session)

                all_states = []
                all_expected_states = [ChalConst.STATE_AC]
                for tr in html.select('tr'):
                    if tr.attrs.get('id') in [None, "chalsub"]:
                        continue

                    # NOTE: <td id="state" class="state-1"></td>
                    state = int(tr.select_one('td#state').attrs['class'][0].split('-')[1])
                    all_states.append(state)

                self.assertEqual(len(all_states), len(all_expected_states))
                self.assertEqual(all_states, all_expected_states)

                # view proset
                html = self.get_html('http://localhost:5501/proset', admin_session)
                trs = html.select('tr')[1:]
                self.assertEqual(trs[0].select('td')[0].text, '1')  # pro_id
                self.assertEqual(trs[0].select('td')[1].text,
                                 ChalConst.STATE_LONG_STR[ChalConst.STATE_AC])  # pro status
                self.assertEqual(trs[0].select('td')[2].text.strip().replace('\n', ''), 'GCD')  # pro name
                self.assertEqual(trs[0].select('td')[3].text.strip().replace('\n', ''),
                                 '100.00%(1/ 1)')  # pro ac ratio (user)
                self.assertEqual(trs[0].select('td')[4].text.strip().replace('\n', ''),
                                 '100.00%(1/1)')  # pro ac ratio (submission)
                self.assertEqual(trs[0].select('td')[5].text, '')  # pro tags

                # upload more problem
                await self.upload_problem('toj659.tar.xz', '猜數字', ProConst.STATUS_ONLINE, expected_pro_id=2,
                                          session=admin_session)
                await self.upload_problem('toj674.tar.xz', 'Move', ProConst.STATUS_ONLINE, expected_pro_id=3,
                                          session=admin_session)

            # signup
            self.signup('test1', 'test1@test', 'test')

            # login normal
            with AccountContext('test1@test', 'test') as user_session:
                # check index & is_manage
                html = self.get_html('http://localhost:5501/index/', user_session)
                self.assertIsNone(html.select_one('li.manage'))
                self.assertEqual(html.select_one('script#indexjs').attrs.get('acct_id'), '2')

                # check manage permission
                res = user_session.get('http://localhost:5501/manage/dash')
                self.assertEqual(res.text, 'Eacces')

            # pro test, tags
            s = [
                ChalTest().main,
                ChalListTest().main,
                SubmitTest().main,
                ProTest().main,
                ProsetTest().main,
                BoardTest().main,
                PublicProClassTest().main,
                ProRankTest().main,
                UserRankTest().main,
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
