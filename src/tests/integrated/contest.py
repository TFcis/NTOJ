import copy
import datetime
import json

from tornado.websocket import websocket_connect

from services.contests import ContestService, ContestMode, RegMode, UserStatus
from services.pro import ProService, ProConst
from services.chal import Compiler
from .util import AsyncTest, AccountContext

def to_utc(d: datetime.datetime) -> datetime.datetime:
    return d.replace(tzinfo=datetime.UTC)

class ContestTest(AsyncTest):
    async def main(self):
        # TODO: add special score test
        self.signup('contest1', 'contest1@test', 'test')  # acct_id = 4
        self.signup('contest2', 'contest2@test', 'test')
        self.signup('contest3', 'contest3@test', 'test')
        self.signup('contest4', 'contest4@test', 'test')
        self.signup('contest5', 'contest5@test', 'test')
        self.signup('contest6', 'contest6@test', 'test')  # acct_id = 9
        with AccountContext('admin@test', 'testtest') as admin_session:
            # upload more problem
            for pro_id in range(5, 11 + 1):
                await self.upload_problem('toj674.tar.xz', f'Move {pro_id - 6}', ProConst.STATUS_CONTEST, expected_pro_id=pro_id, session=admin_session)

            res = admin_session.post('contests/manage/add', data={
                'reqtype': 'add',
                'name': ''
            })
            self.assertAPIReturnValue(res.text, ('Eparam', 'Name too short'))

            res = admin_session.post('contests/manage/add', data={
                'reqtype': 'add',
                'name': 'name' * 1000
            })
            self.assertAPIReturnValue(res.text, ('Eparam', 'Name too long'))

            res = admin_session.post('contests/manage/add', data={
                'reqtype': 'add',
                'name': 'contest 1'
            })
            self.assertEqual(json.loads(res.text)['data'], 1)
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            self.assertEqual(contest.name, 'contest 1')

            # update general
            now = datetime.datetime.now()
            contest_start = now + datetime.timedelta(days=1)
            contest_end = now + datetime.timedelta(days=4)
            reg_end = now + datetime.timedelta(days=1) - datetime.timedelta(hours=8)
            default_config = {
                'reqtype': 'update',
                'name': 'contest 1',

                'contest_mode': ContestMode.IOI,
                'contest_start': self.get_isoformat(contest_start),
                'contest_end': self.get_isoformat(contest_end),

                'reg_mode': RegMode.INVITED,
                'reg_end': self.get_isoformat(reg_end),

                'allow_compilers[]': [Compiler.GPP, Compiler.CLANGPP],
                'is_public_scoreboard': 'true',
                'allow_view_other_page': 'true',
                'hide_admin': 'true',

                'submission_cd_time': 60,
                'freeze_scoreboard_period': 0
            }
            res = admin_session.post('contests/1/manage/general', data=default_config)
            self.assertAPIReturnSuccess(res.text)

            err, contest = await ContestService.inst.get_contest(1)
            assert contest
            self.assertIsNone(err)
            self.assertEqual(contest.contest_mode, ContestMode.IOI)
            self.assertEqual(contest.reg_mode, RegMode.INVITED)
            self.assertEqual(contest.allow_compilers, {Compiler.GPP, Compiler.CLANGPP})
            self.assertTrue(contest.is_public_scoreboard)
            self.assertTrue(contest.allow_view_other_page)
            self.assertTrue(contest.hide_admin)
            self.assertEqual(contest.submission_cd_time, 60)
            self.assertEqual(contest.freeze_scoreboard_period, 0)
            self.assertEqual(contest.contest_start, to_utc(contest_start))
            self.assertEqual(contest.contest_end, to_utc(contest_end))
            self.assertEqual(contest.reg_end, to_utc(reg_end))

            # test desc
            res = admin_session.post('contests/1/manage/desc', data={
                'reqtype': 'update',
                'desc_type': 'before',
                'desc': 'desc before contest',
            })
            self.assertAPIReturnSuccess(res.text)
            res = admin_session.post('contests/1/manage/desc', data={
                'reqtype': 'update',
                'desc_type': 'during',
                'desc': 'desc during contest',
            })
            self.assertAPIReturnSuccess(res.text)
            res = admin_session.post('contests/1/manage/desc', data={
                'reqtype': 'update',
                'desc_type': 'after',
                'desc': 'desc after contest',
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            self.assertEqual(contest.desc_before_contest, 'desc before contest')
            self.assertEqual(contest.desc_during_contest, 'desc during contest')
            self.assertEqual(contest.desc_after_contest, 'desc after contest')

            _, contest_list = await ContestService.inst.get_contest_list()
            self.assertEqual(len(contest_list), 1)
            self.assertEqual(contest_list[0]['name'], 'contest 1')
            self.assertEqual(contest_list[0]['contest_mode'], ContestMode.IOI)
            self.assertTrue(contest_list[0]['is_public_scoreboard'])

            # add problem
            res = admin_session.post('contests/1/manage/pro', data={
                'reqtype': 'add',
                'pro_id': 5
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            self.assertIn(5, contest.pro_list)

            res = admin_session.post('contests/1/manage/pro', data={
                'reqtype': 'remove',
                'pro_id': 5
            })
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            self.assertNotIn(5, contest.pro_list)

            res = admin_session.post('contests/1/manage/pro', data={
                'reqtype': 'multi_add',
                'pro_id': '5-11'
            })
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            for pro_id in range(5, 11 + 1, 1):
                self.assertIn(pro_id, contest.pro_list)

            res = admin_session.post('contests/1/manage/pro', data={
                'reqtype': 'multi_remove',
                'pro_id': '5-11'
            })
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            self.assertEqual(len(contest.pro_list), 0)

            res = admin_session.post('contests/1/manage/pro', data={
                'reqtype': 'multi_add',
                'pro_id': '5-11'
            })

            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            for pro_id in range(5, 11 + 1, 1):
                self.assertIn(pro_id, contest.pro_list)

            res = admin_session.post('contests/1/manage/pro', data={
                'reqtype': 'multi_add',
                'pro_id': '5-20'
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            for pro_id in range(5, 11 + 1, 1):
                self.assertIn(pro_id, contest.pro_list)

            res = admin_session.post('contests/1/manage/pro', data={
                'reqtype': 'public',
                'pro_id': '5'
            })
            self.assertAPIReturnValue(res.text, ('Etime', 'Contest is not over yet'))
            err, pro = await ProService.inst.get_pro(5, allow_statuses=ProConst.PRO_STATUS_FULL)
            self.assertIsNone(err)
            self.assertEqual(pro.status, ProConst.STATUS_CONTEST)

        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.post('contests/1/manage/acct', data={
                'reqtype': 'add',
                'acct_id': 4,
                'type': 'normal',
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            self.assertEqual(contest.user_list[4]['status'], UserStatus.APPROVED)

        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.post('contests/1/manage/acct', data={
                'reqtype': 'remove',
                'acct_id': 4,
                'type': 'normal',
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            self.assertNotIn(4, contest.user_list)

        with AccountContext('admin@test', 'testtest') as admin_session:
            config = copy.deepcopy(default_config)
            config['reg_mode'] = RegMode.FREE_REG
            res = admin_session.post('contests/1/manage/general', data=config)
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            self.assertEqual(contest.reg_mode, RegMode.FREE_REG)

        with AccountContext('contest1@test', 'test') as user_session:
            res = user_session.post('contests/1/reg', data={
                'reqtype': 'reg'
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            self.assertEqual(contest.user_list[4]['status'], UserStatus.APPROVED)

        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.post('contests/1/manage/acct', data={
                'reqtype': 'remove',
                'acct_id': 4,
                'type': 'normal',
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            self.assertNotIn(4, contest.user_list)

            config = copy.deepcopy(default_config)
            config['reg_mode'] = RegMode.REG_APPROVAL
            res = admin_session.post('contests/1/manage/general', data=config)
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            self.assertEqual(contest.reg_mode, RegMode.REG_APPROVAL)

        with AccountContext('contest1@test', 'test') as user_session:
            res = user_session.post('contests/1/reg', data={
                'reqtype': 'reg'
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            self.assertEqual(contest.user_list[4]['status'], UserStatus.REQUESTED)

        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.post('contests/1/manage/reg', data={
                'reqtype': 'approval',
                'acct_id': 4,
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            self.assertEqual(contest.user_list[4]['status'], UserStatus.APPROVED)

        with AccountContext('contest1@test', 'test') as user_session:
            res = user_session.post('contests/1/reg', data={
                'reqtype': 'unreg'
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            self.assertNotIn(4, contest.user_list)

        with AccountContext('contest1@test', 'test') as user_session:
            res = user_session.post('contests/1/reg', data={
                'reqtype': 'reg'
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            self.assertEqual(contest.user_list[4]['status'], UserStatus.REQUESTED)

        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.post('contests/1/manage/reg', data={
                'reqtype': 'reject',
                'acct_id': 4,
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            self.assertEqual(contest.user_list[4]['status'], UserStatus.REJECTED)

        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.post('contests/1/manage/acct', data={
                'reqtype': 'multi_add',
                'acct_id': '3,4,5,6,7,8,9',
                'type': 'normal',
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            for acct_id in range(3, 9 + 1, 1):
                self.assertIn(acct_id, contest.user_list)

        with AccountContext('admin@test', 'testtest') as admin_session:
            contest_start = now - datetime.timedelta(days=2)
            config = copy.deepcopy(default_config)
            config['contest_start'] = self.get_isoformat(contest_start)
            res = admin_session.post('contests/1/manage/general', data=config)
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            self.assertEqual(contest.contest_start, to_utc(contest_start))
            self.assertTrue(contest.is_start())

        with AccountContext('contest1@test', 'test') as user_session:
            res = user_session.get('contests/1/pro/5/cont.pdf')

            res = user_session.post('contests/1/submit', data={
                'reqtype': 'submit',
                'pro_id': 1,
                'code': 'cc1',
                'compiler_type': Compiler.GPP,
            })
            self.assertAPIReturnValue(res.text, ('Enoext', 'Problem not in contest'))

            res = user_session.post('contests/1/submit', data={
                'reqtype': 'submit',
                'pro_id': 5,
                'code': 'cc2',
                'compiler_type': Compiler.PYTHON3,
            })
            self.assertAPIReturnValue(res.text, ('Ecomp', 'The compiler is not allowed'))

            with open('tests/static_file/code/toj674.ac.cpp') as f:
                res = user_session.post('contests/1/submit', data={
                    'reqtype': 'submit',
                    'pro_id': 5,
                    'code': f.read(),
                    'compiler_type': Compiler.GPP,
                })
                self.assertAPIReturnValue(res.text, ('S', 13))

            ws = await websocket_connect('ws://localhost:5501/be/ws')
            await ws.write_message(json.dumps({'type': 'register', 'data': 'judgechalcnt_sub'}))

            def _message(msg):
                if msg is None:
                    return
                data = json.loads(msg)
                if data.get('type') == 'contestnewchalsub':
                    self.assertEqual(int(data['data']), 1)

            ws2 = await websocket_connect('ws://localhost:5501/be/ws', on_message_callback=_message)
            await ws2.write_message(json.dumps({'type': 'register', 'data': 'contestnewchalsub'}))
            await ws2.write_message(json.dumps({'type': 'contestnewchalsub_init', 'data': '1'}))

            with open('tests/static_file/code/toj674.ac.cpp') as f:
                res = user_session.post('contests/1/submit', data={
                    'reqtype': 'submit',
                    'pro_id': 5,
                    'code': f.read(),
                    'compiler_type': Compiler.GPP,
                })
                self.assertAPIReturnValue(res.text, ('Esame', 'Do not submit same code'))

            res = user_session.post('contests/1/submit', data={
                'reqtype': 'submit',
                'pro_id': 5,
                'code': 'cc3',
                'compiler_type': Compiler.GPP,
            })
            res = json.loads(res.text)
            self.assertEqual(res['status'], 'Einternal')
            while True:
                msg = await ws.read_message()
                if msg is None:
                    break

                data = json.loads(msg)
                if data.get('type') == 'judgechalcnt_sub':
                    judge_data = json.loads(data['data'])
                    if judge_data['chal_cnt'] == 0:
                        ws.close()
                        break

            # TODO: map_rate_acct
            # TODO: get_pro_ac_rate
            # html = self.get_html('contests/1/proset', user_session)
            # self.assertEqual(len(html.select('tr')[1:]), 6)
            # self.assertEqual(html.select('tr')[1:][0].select('td')[3].text.strip(), '100')

            # test scoreboard
            res = user_session.post('contests/1/scoreboard', data={})
            res = json.loads(res.text)
            self.assertNotEqual(res['status'], 'Eacces')
            scoreboard_data = res['data']
            for scores in scoreboard_data:
                if scores['acct_id'] == 4:
                    self.assertEqual(scores['name'], 'contest1')
                    self.assertEqual(scores['total_score'], 100)

                    score = scores['scores']['5']
                    self.assertEqual(score['chal_id'], 13)
                    self.assertEqual(score['score'], 100)
            ws2.close()

        # NOTE: contest end
        with AccountContext('admin@test', 'testtest') as admin_session:
            contest_end = now - datetime.timedelta(days=1)
            config = copy.deepcopy(default_config)
            config['contest_end'] = self.get_isoformat(contest_end)
            res = admin_session.post('contests/1/manage/general', data=config)
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            self.assertEqual(contest.contest_end, to_utc(contest_end))
            self.assertTrue(contest.is_end())

            res = admin_session.post('contests/1/manage/pro', data={
                'reqtype': 'public',
                'pro_id': '5'
            })
            self.assertAPIReturnSuccess(res.text)
            err, pro = await ProService.inst.get_pro(5, allow_statuses=ProConst.PRO_STATUS_FULL)
            self.assertIsNone(err)
            self.assertEqual(pro.status, ProConst.STATUS_ONLINE)
            err, pro = await ProService.inst.get_pro(8, allow_statuses=ProConst.PRO_STATUS_FULL)
            self.assertIsNone(err)
            self.assertEqual(pro.status, ProConst.STATUS_CONTEST)

        with AccountContext('test1@test', 'test') as user_session:
            res = user_session.get('pro/5')
            self.assertNotIn('Eacces', res.text)
            res = user_session.get('pro/8')
            self.assertAPIReturnValue(res.text, ('Eacces', 'Permission denied'))

        # freeze_scoreboard_period: int = 0

        # test scoreboard, challist
        # hide_admin: bool = True
        # test rechal
