import copy
import datetime
import json
import re

from tornado.websocket import websocket_connect

from services.contests import ContestMode, RegMode
from services.pro import ProConst
from .util import AsyncTest, AccountContext


class ContestTest(AsyncTest):
    async def main(self):
        # TODO: update chal_id counter
        # TOOD: add special score test
        self.signup('contest1', 'contest1@test', 'test')  # acct_id = 4
        self.signup('contest2', 'contest2@test', 'test')
        self.signup('contest3', 'contest3@test', 'test')
        self.signup('contest4', 'contest4@test', 'test')
        self.signup('contest5', 'contest5@test', 'test')
        self.signup('contest6', 'contest6@test', 'test')  # acct_id = 9
        with AccountContext('admin@test', 'testtest') as admin_session:
            # upload more problem
            await self.upload_problem('toj674.tar.xz', 'Move 1', ProConst.STATUS_CONTEST, expected_pro_id=6, session=admin_session)
            await self.upload_problem('toj674.tar.xz', 'Move 2', ProConst.STATUS_CONTEST, expected_pro_id=7, session=admin_session)
            await self.upload_problem('toj674.tar.xz', 'Move 3', ProConst.STATUS_CONTEST, expected_pro_id=8, session=admin_session)
            await self.upload_problem('toj674.tar.xz', 'Move 4', ProConst.STATUS_CONTEST, expected_pro_id=9, session=admin_session)
            await self.upload_problem('toj674.tar.xz', 'Move 5', ProConst.STATUS_CONTEST, expected_pro_id=10, session=admin_session)
            await self.upload_problem('toj674.tar.xz', 'Move 6', ProConst.STATUS_CONTEST, expected_pro_id=11, session=admin_session)

            res = admin_session.post('http://localhost:5501/contests/manage/add', data={
                'reqtype': 'add',
                'name': 'contest 1'
            })
            self.assertEqual(json.loads(res.text), 1)

            # update general
            now = datetime.datetime.now()
            contest_start = now + datetime.timedelta(days=1)
            contest_end = now + datetime.timedelta(days=2)
            reg_end = now + datetime.timedelta(days=1) - datetime.timedelta(hours=8)
            default_config = {
                'reqtype': 'update',
                'name': 'contest 1',

                'contest_mode': ContestMode.IOI.value,
                'contest_start': self.get_isoformat(contest_start),
                'contest_end': self.get_isoformat(contest_end),

                'reg_mode': RegMode.INVITED.value,
                'reg_end': self.get_isoformat(reg_end),

                'allow_compilers[]': ['g++', 'clang++'],
                'is_public_scoreboard': 'true',
                'allow_view_other_page': 'true',
                'hide_admin': 'true',

                'submission_cd_time': 60,
                'freeze_scoreboard_period': 0
            }
            res = admin_session.post('http://localhost:5501/contests/1/manage/general', data=default_config)
            self.assertEqual(res.text, 'S')

            # test desc
            res = admin_session.post('http://localhost:5501/contests/1/manage/desc', data={
                'reqtype': 'update',
                'desc_type': 'before',
                'desc': 'desc before contest',
            })
            self.assertEqual(res.text, 'S')
            res = admin_session.post('http://localhost:5501/contests/1/manage/desc', data={
                'reqtype': 'update',
                'desc_type': 'during',
                'desc': 'desc during contest',
            })
            self.assertEqual(res.text, 'S')
            res = admin_session.post('http://localhost:5501/contests/1/manage/desc', data={
                'reqtype': 'update',
                'desc_type': 'after',
                'desc': 'desc after contest',
            })
            self.assertEqual(res.text, 'S')

            res = admin_session.get('http://localhost:5501/contests/1/manage/desc')
            self.assertEqual(re.findall(r'let desc_before_contest = `(.*)`', res.text, re.I)[0], 'desc before contest')
            self.assertEqual(re.findall(r'let desc_during_contest = `(.*)`', res.text, re.I)[0], 'desc during contest')
            self.assertEqual(re.findall(r'let desc_after_contest = `(.*)`', res.text, re.I)[0], 'desc after contest')

            res = admin_session.get('http://localhost:5501/contests/1')
            self.assertEqual(re.findall(r'let desc_tex = `(.*)`', res.text, re.I)[0], 'desc before contest')

            html = self.get_html('http://localhost:5501/contests/1/info', admin_session)
            during_section = html.select('.card-body')[0]
            contest_style_section = html.select('.card-body')[1]
            registration_info = html.select('.card-body')[2]
            registration_status = html.select('.card-body')[3]

            self.assertEqual(during_section.select('h5')[0].text, contest_start.strftime('%Y-%m-%d %H:%M:%S'))
            self.assertEqual(during_section.select('h5')[1].text, contest_end.strftime('%Y-%m-%d %H:%M:%S'))
            self.assertEqual(contest_style_section.select('h5')[0].text, 'IOI')
            self.assertEqual(contest_style_section.select('h5')[1].text, 'Scoreboard')
            self.assertEqual(registration_info.select('h5')[0].text, reg_end.strftime('%Y-%m-%d %H:%M:%S'))
            self.assertEqual(registration_info.select('h5')[1].text, 'Invited')
            self.assertEqual(registration_status.select('h5')[0].text, 'Admin, no registration needed')

            html = self.get_html('http://localhost:5501/contests', admin_session)
            self.assertEqual(len(html.select('tr')[1:]), 1)
            contest0 = html.select('tr')[1]
            self.assertEqual(contest0.select_one('th').text, 'contest 1')
            self.assertEqual(contest0.select('td')[0].text, 'Not Yet')
            self.assertEqual(contest0.select('td')[1].text, contest_start.strftime('%Y-%m-%d %H:%M'))
            self.assertEqual(contest0.select('td')[2].text, str(contest_end - contest_start))
            self.assertEqual(contest0.select('td')[3].text, 'IOI')
            self.assertEqual(contest0.select('td')[4].text, 'Yes')

            # add problem
            res = admin_session.post('http://localhost:5501/contests/1/manage/pro', data={
                'reqtype': 'add',
                'pro_id': 6
            })
            self.assertEqual(res.text, 'S')

            html = self.get_html('http://localhost:5501/contests/1/manage/pro', admin_session)
            self.assertEqual(len(html.select('tr')[1:]), 1)

            res = admin_session.post('http://localhost:5501/contests/1/manage/pro', data={
                'reqtype': 'remove',
                'pro_id': 6
            })
            self.assertEqual(res.text, 'S')
            html = self.get_html('http://localhost:5501/contests/1/manage/pro', admin_session)
            self.assertEqual(len(html.select('tr')[1:]), 0)

            res = admin_session.post('http://localhost:5501/contests/1/manage/pro', data={
                'reqtype': 'multi_add',
                'pro_id': '6..12'
            })
            self.assertEqual(res.text, 'S')
            html = self.get_html('http://localhost:5501/contests/1/manage/pro', admin_session)
            self.assertEqual(len(html.select('tr')[1:]), 6)

            res = admin_session.post('http://localhost:5501/contests/1/manage/pro', data={
                'reqtype': 'multi_remove',
                'pro_id': '6..12'
            })
            self.assertEqual(res.text, 'S')
            html = self.get_html('http://localhost:5501/contests/1/manage/pro', admin_session)
            self.assertEqual(len(html.select('tr')[1:]), 0)

            res = admin_session.post('http://localhost:5501/contests/1/manage/pro', data={
                'reqtype': 'multi_add',
                'pro_id': '6..12'
            })
            self.assertEqual(res.text, 'S')
            html = self.get_html('http://localhost:5501/contests/1/manage/pro', admin_session)
            self.assertEqual(len(html.select('tr')[1:]), 6)

            html = self.get_html('http://localhost:5501/contests/1/proset', admin_session)
            self.assertEqual(len(html.select('tr')[1:]), 6)

            # test reg
            # current reg mode is invite
        with AccountContext('contest1@test', 'test') as user_session:
            html = self.get_html('http://localhost:5501/contests/1/reg', user_session)
            self.assertEqual(html.select_one('h2').text, 'contest 1')
            self.assertEqual(html.select('label')[0].text, 'Status: Not Invited')
            self.assertEqual(html.select('label')[1].text, f"Registration End: {reg_end.strftime('%Y-%m-%d %H:%M:%S')}")
            self.assertIsNone(html.select_one('h4'))  # NOTE: registration end
            self.assertIsNone(html.select_one('button'))  # NOTE: registration button

        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.post('http://localhost:5501/contests/1/manage/acct', data={
                'reqtype': 'add',
                'acct_id': 4,
                'type': 'normal',
            })
            self.assertEqual(res.text, 'S')

        with AccountContext('contest1@test', 'test') as user_session:
            html = self.get_html('http://localhost:5501/contests/1/reg', user_session)
            self.assertEqual(html.select('label')[0].text, 'Status: Invited')
            self.assertIsNone(html.select_one('button'))  # NOTE: registration button

            html = self.get_html('http://localhost:5501/contests/1/info', user_session)
            registration_status = html.select('.card-body')[3]
            self.assertEqual(registration_status.select('h5')[0].text, 'Invited')
            # self.assertIsNone(registration_status.select_one('a')) # TODO: Follow Spec

        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.post('http://localhost:5501/contests/1/manage/acct', data={
                'reqtype': 'remove',
                'acct_id': 4,
                'type': 'normal',
            })
            self.assertEqual(res.text, 'S')

        with AccountContext('contest1@test', 'test') as user_session:
            html = self.get_html('http://localhost:5501/contests/1/reg', user_session)
            self.assertEqual(html.select('label')[0].text, 'Status: Not Invited')

        with AccountContext('admin@test', 'testtest') as admin_session:
            config = copy.deepcopy(default_config)
            config['reg_mode'] = RegMode.FREE_REG.value
            res = admin_session.post('http://localhost:5501/contests/1/manage/general', data=config)
            self.assertEqual(res.text, 'S')

        with AccountContext('contest1@test', 'test') as user_session:
            html = self.get_html('http://localhost:5501/contests/1/reg', user_session)
            self.assertEqual(html.select('label')[0].text, 'Status: Not Registered')
            self.assertIsNotNone(html.select_one('button'))  # NOTE: registration button

            html = self.get_html('http://localhost:5501/contests/1/info', user_session)
            registration_status = html.select('.card-body')[3]
            self.assertEqual(registration_status.select('h5')[0].text, 'Not Registered')
            self.assertIsNotNone(registration_status.select_one('a'))

            res = user_session.post('http://localhost:5501/contests/1/reg', data={
                'reqtype': 'reg'
            })
            self.assertEqual(res.text, 'S')

            html = self.get_html('http://localhost:5501/contests/1/reg', user_session)
            self.assertEqual(html.select('label')[0].text, 'Status: Registered')
            self.assertEqual(html.select_one('button').text, 'Unregister')

            html = self.get_html('http://localhost:5501/contests/1/info', user_session)
            registration_status = html.select('.card-body')[3]
            self.assertEqual(registration_status.select('h5')[0].text, 'Registered')
            self.assertIsNotNone(registration_status.select_one('a'))

        with AccountContext('admin@test', 'testtest') as admin_session:
            html = self.get_html('http://localhost:5501/contests/1/manage/acct', admin_session)
            normal_accts = html.select('div#collapseOne > div > table > tbody > tr')
            self.assertEqual(len(normal_accts), 1)
            self.assertEqual(normal_accts[0].select_one('th').text, '4')
            self.assertEqual(normal_accts[0].select('td')[0].text, 'contest1')

            res = admin_session.post('http://localhost:5501/contests/1/manage/acct', data={
                'reqtype': 'remove',
                'acct_id': 4,
                'type': 'normal',
            })
            self.assertEqual(res.text, 'S')

            config = copy.deepcopy(default_config)
            config['reg_mode'] = RegMode.REG_APPROVAL.value
            res = admin_session.post('http://localhost:5501/contests/1/manage/general', data=config)
            self.assertEqual(res.text, 'S')

        with AccountContext('contest1@test', 'test') as user_session:
            html = self.get_html('http://localhost:5501/contests/1/reg', user_session)
            self.assertEqual(html.select('label')[0].text, 'Status: Not Registered')
            self.assertIsNotNone(html.select_one('button'))  # NOTE: registration button

            res = user_session.post('http://localhost:5501/contests/1/reg', data={
                'reqtype': 'reg'
            })
            self.assertEqual(res.text, 'S')

            html = self.get_html('http://localhost:5501/contests/1/reg', user_session)
            self.assertEqual(html.select('label')[0].text, 'Status: Waiting Approval')
            self.assertEqual(html.select_one('button').text, 'Unregister')

            html = self.get_html('http://localhost:5501/contests/1/info', user_session)
            registration_status = html.select('.card-body')[3]
            self.assertEqual(registration_status.select('h5')[0].text, 'Waiting Approval')
            self.assertIsNotNone(registration_status.select_one('a'))

        with AccountContext('admin@test', 'testtest') as admin_session:
            html = self.get_html('http://localhost:5501/contests/1/manage/reg', admin_session)
            trs = html.select('tr')[1:]
            self.assertEqual(len(trs), 1)
            self.assertEqual(trs[0].select_one('th').text, '4')
            self.assertEqual(trs[0].select('td')[0].text, 'contest1')

            res = admin_session.post('http://localhost:5501/contests/1/manage/reg', data={
                'reqtype': 'approval',
                'acct_id': 4,
            })
            self.assertEqual(res.text, 'S')

        with AccountContext('contest1@test', 'test') as user_session:
            html = self.get_html('http://localhost:5501/contests/1/reg', user_session)
            self.assertEqual(html.select('label')[0].text, 'Status: Registered')
            self.assertIsNotNone(html.select_one('button'))  # NOTE: registration button

            html = self.get_html('http://localhost:5501/contests/1/reg', user_session)
            self.assertEqual(html.select('label')[0].text, 'Status: Registered')
            self.assertEqual(html.select_one('button').text, 'Unregister')

            html = self.get_html('http://localhost:5501/contests/1/info', user_session)
            registration_status = html.select('.card-body')[3]
            self.assertEqual(registration_status.select('h5')[0].text, 'Registered')
            self.assertIsNotNone(registration_status.select_one('a'))

            res = user_session.post('http://localhost:5501/contests/1/reg', data={
                'reqtype': 'unreg'
            })
            self.assertEqual(res.text, 'S')

            html = self.get_html('http://localhost:5501/contests/1/info', user_session)
            registration_status = html.select('.card-body')[3]
            self.assertEqual(registration_status.select('h5')[0].text, 'Not Registered')
            self.assertIsNotNone(registration_status.select_one('a'))

        with AccountContext('admin@test', 'testtest') as admin_session:
            html = self.get_html('http://localhost:5501/contests/1/manage/reg', admin_session)
            trs = html.select('tr')[1:]
            self.assertEqual(len(trs), 0)

        with AccountContext('contest1@test', 'test') as user_session:
            res = user_session.post('http://localhost:5501/contests/1/reg', data={
                'reqtype': 'reg'
            })
            self.assertEqual(res.text, 'S')

        with AccountContext('admin@test', 'testtest') as admin_session:
            html = self.get_html('http://localhost:5501/contests/1/manage/reg', admin_session)
            trs = html.select('tr')[1:]
            self.assertEqual(len(trs), 1)

            res = admin_session.post('http://localhost:5501/contests/1/manage/reg', data={
                'reqtype': 'reject',
                'acct_id': 4,
            })
            self.assertEqual(res.text, 'S')

        with AccountContext('contest1@test', 'test') as user_session:
            html = self.get_html('http://localhost:5501/contests/1/info', user_session)
            registration_status = html.select('.card-body')[3]
            self.assertEqual(registration_status.select('h5')[0].text, 'Not Registered')
            self.assertIsNotNone(registration_status.select_one('a'))

            html = self.get_html('http://localhost:5501/contests/1/reg', user_session)
            self.assertEqual(html.select('label')[0].text, 'Status: Not Registered')
            self.assertEqual(html.select_one('button').text, 'Register')

        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.post('http://localhost:5501/contests/1/manage/acct', data={
                'reqtype': 'multi_add',
                'acct_id': '3,4,5,6,7,8,9',
                'type': 'normal',
            })
            self.assertEqual(res.text, 'S')

        with AccountContext('contest1@test', 'test') as user_session:
            html = self.get_html('http://localhost:5501/contests/1/proset', user_session)
            self.assertEqual(len(html.select('tr')[1:]), 0)

            res = user_session.get('http://localhost:5501/contests/1/pro/6')
            self.assertEqual(res.text, 'Eacces')

            res = user_session.get('http://localhost:5501/contests/1/pro/6/cont.pdf')
            self.assertEqual(res.text, 'Eacces')

        with AccountContext('admin@test', 'testtest') as admin_session:
            contest_start = now - datetime.timedelta(days=1)
            config = copy.deepcopy(default_config)
            config['contest_start'] = self.get_isoformat(contest_start)
            res = admin_session.post('http://localhost:5501/contests/1/manage/general', data=config)
            self.assertEqual(res.text, 'S')

        with AccountContext('contest1@test', 'test') as user_session:
            html = self.get_html('http://localhost:5501/contests', user_session)
            contest0 = html.select('tr')[1]
            self.assertEqual(contest0.select('td')[0].text, 'Started')

            res = user_session.get('http://localhost:5501/contests/1')
            self.assertEqual(re.findall(r'let desc_tex = `(.*)`', res.text, re.I)[0], 'desc during contest')

            html = self.get_html('http://localhost:5501/contests/1/proset', user_session)
            self.assertEqual(len(html.select('tr')[1:]), 6)
            self.assertEqual(html.select('tr')[1:][0].select('td')[3].text.strip(), '0')

            html = self.get_html('http://localhost:5501/contests/1/pro/6', user_session)
            side = html.select_one('div#side')
            self.assertEqual(side.select('a')[0].attrs['href'], '/oj/contests/1/submit/6/')
            self.assertEqual(side.select('a')[1].attrs['href'], '/oj/contests/1/chal/?proid=6&acctid=4')
            self.assertEqual(side.select('a')[2].attrs['href'], '/oj/contests/1/chal/?proid=6')

            res = user_session.get('http://localhost:5501/contests/1/pro/6/cont.pdf')
            self.assertIn('X-Accel-Redirect', res.headers)

            html = self.get_html('http://localhost:5501/contests/1/submit/6', user_session)
            self.assertEqual(len(html.select('option')), 2)

            res = user_session.post('http://localhost:5501/contests/1/submit', data={
                'reqtype': 'submit',
                'pro_id': 1,
                'code': 'cc1',
                'comp_type': 'g++',
            })
            self.assertEqual(res.text, 'Enoext')

            res = user_session.post('http://localhost:5501/contests/1/submit', data={
                'reqtype': 'submit',
                'pro_id': 6,
                'code': 'cc2',
                'comp_type': 'python3',
            })
            self.assertEqual(res.text, 'Ecomp')

            res = user_session.post('http://localhost:5501/contests/1/submit', data={
                'reqtype': 'submit',
                'pro_id': 6,
                'code': open('tests/static_file/code/toj674.ac.cpp').read(),
                'comp_type': 'g++',
            })
            self.assertEqual(res.text, '15')

            ws = await websocket_connect('ws://localhost:5501/manage/judgecntws')

            def _message(msg):
                if msg is None:
                    return

                self.assertEqual(int(msg), 1)

            ws2 = await websocket_connect('ws://localhost:5501/contests/1/scoreboardsub', on_message_callback=_message)
            await ws2.write_message('1')

            res = user_session.post('http://localhost:5501/contests/1/submit', data={
                'reqtype': 'submit',
                'pro_id': 6,
                'code': open('tests/static_file/code/toj674.ac.cpp').read(),
                'comp_type': 'g++',
            })
            self.assertEqual(res.text, 'Esame')

            res = user_session.post('http://localhost:5501/contests/1/submit', data={
                'reqtype': 'submit',
                'pro_id': 6,
                'code': 'cc3',
                'comp_type': 'g++',
            })
            self.assertEqual(res.text, 'Einternal60')
            while True:
                msg = await ws.read_message()
                if msg is None:
                    break

                if json.loads(msg)['chal_cnt'] == 0:
                    ws.close()
                    break

            html = self.get_html('http://localhost:5501/contests/1/proset', user_session)
            self.assertEqual(len(html.select('tr')[1:]), 6)
            self.assertEqual(html.select('tr')[1:][0].select('td')[3].text.strip(), '100')

            # test scoreboard
            res = user_session.post('http://localhost:5501/contests/1/scoreboard', data={})
            scoreboard_data = json.loads(res.text)
            for scores in scoreboard_data:
                if scores['acct_id'] == 4:
                    self.assertEqual(scores['name'], 'contest1')
                    self.assertEqual(scores['total_score'], 100)

                    score = scores['scores']['6']
                    self.assertEqual(score['chal_id'], 15)
                    self.assertEqual(score['score'], 100)
            ws2.close()

            # test challist
            html = self.get_html('http://localhost:5501/contests/1/chal', user_session)
            self.assertEqual(len(html.select('tbody > tr')[1:]), 1)
            chal_tr = html.select('tbody > tr')[1:][0]
            self.assertEqual(chal_tr.attrs.get('id'), 'chal15')
            self.assertEqual(chal_tr.select('td > a')[0].attrs.get('href'), '/oj/contests/1/chal/15/')
            self.assertEqual(chal_tr.select('td > a')[1].attrs.get('href'), '/oj/contests/1/pro/6/')
            self.assertEqual(chal_tr.select('td')[3].attrs.get('class')[0], 'state-1')

        # is_public_scoreboard: bool = False
        # freeze_scoreboard_period: int = 0

        # test scoreboard, challist
        # hide_admin: bool = True
        # test rechal
