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
            self.assertEqual(contest.contest_creator, 1)

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

            res = admin_session.post('contests/1/manage/pro' , data={
                'reqtype': 'add_set',
                'pro_id': '5-7'
            })
            self.assertAPIReturnValue(res.text, ('Emod', 'Cannot add problem set to non-random set contests'))
            res = admin_session.post('contests/1/manage/pro' , data={
                'reqtype': 'remove_set',
                'pro_id': '1'
            })
            self.assertAPIReturnValue(res.text, ('Emod', 'Cannot remove problem set from non-random set contests'))
            res = admin_session.post('contests/1/manage/pro' , data={
                'reqtype': 'update_order',
                'pro_id': '1'
            })
            self.assertAPIReturnValue(res.text, ('Emod', 'Cannot update problem order in non-random set contests'))

            # NOTE: Contest problem status
            admin_session.post('manage/pro/update', data={
                'reqtype': 'updategeneral',
                'pro_id': 1,
                'name': 'GCD',
                'status': ProConst.STATUS_HIDDEN,
                'tags': '',
                'allow_submit': 'true',
            })

            res = admin_session.post('contests/1/manage/pro', data={
                'reqtype': 'add',
                'pro_id': 1
            })
            self.assertAPIReturnValue(res.text, ('Eacces', 'Permission denied'))

            res = admin_session.post('contests/1/manage/pro', data={
                'reqtype': 'multi_add',
                'pro_id': '1'
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            self.assertNotIn(1, contest.pro_list)

            admin_session.post('manage/pro/update', data={
                'reqtype': 'updategeneral',
                'pro_id': 1,
                'name': 'GCD',
                'status': ProConst.STATUS_ONLINE,
                'tags': '',
                'allow_submit': 'true',
            })

            res = admin_session.post('contests/1/manage/pro', data={
                'reqtype': 'add',
                'pro_id': 1
            })
            self.assertAPIReturnSuccess(res.text)
            admin_session.post('manage/pro/update', data={
                'reqtype': 'updategeneral',
                'pro_id': 1,
                'name': 'GCD',
                'status': ProConst.STATUS_HIDDEN,
                'tags': '',
                'allow_submit': 'true',
            })
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            self.assertNotIn(1, contest.pro_list)
            admin_session.post('manage/pro/update', data={
                'reqtype': 'updategeneral',
                'pro_id': 1,
                'name': 'GCD',
                'status': ProConst.STATUS_ONLINE,
                'tags': '',
                'allow_submit': 'true',
            })

        with AccountContext('admin@test', 'testtest') as admin_session:
            # NOTE: Should not remove contest_creator or change contest_creator permission
            for list_type in ('admin', 'normal'):
                res = admin_session.post('contests/1/manage/acct', data={
                    'reqtype': 'remove',
                    'acct_id': 1,
                    'type': list_type,
                })
                self.assertAPIReturnValue(res.text, ('Eacces', 'Cannot remove contest creator'))
                err, contest = await ContestService.inst.get_contest(1)
                self.assertIsNone(err)
                assert contest
                self.assertIn(1, contest.user_list)
                self.assertEqual(contest.user_list[1]['status'], UserStatus.ADMIN)

                res = admin_session.post('contests/1/manage/acct', data={
                    'reqtype': 'multi_remove',
                    'acct_id': 1,
                    'type': list_type,
                })
                self.assertAPIReturnSuccess(res.text)
                err, contest = await ContestService.inst.get_contest(1)
                self.assertIsNone(err)
                assert contest
                self.assertIn(1, contest.user_list)
                self.assertEqual(contest.user_list[1]['status'], UserStatus.ADMIN)

                res = admin_session.post('contests/1/manage/acct', data={
                    'reqtype': 'add',
                    'acct_id': 1,
                    'type': list_type,
                })
                self.assertAPIReturnValue(res.text, ("Eexist", "Contest creator already exists"))
                err, contest = await ContestService.inst.get_contest(1)
                self.assertIsNone(err)
                assert contest
                self.assertIn(1, contest.user_list)
                self.assertEqual(contest.user_list[1]['status'], UserStatus.ADMIN)

                res = admin_session.post('contests/1/manage/acct', data={
                    'reqtype': 'multi_add',
                    'acct_id': 1,
                    'type': list_type,
                })
                self.assertAPIReturnSuccess(res.text)
                err, contest = await ContestService.inst.get_contest(1)
                self.assertIsNone(err)
                assert contest
                self.assertIn(1, contest.user_list)
                self.assertEqual(contest.user_list[1]['status'], UserStatus.ADMIN)

            res = admin_session.post('contests/1/manage/acct', data={
                'reqtype': 'add',
                'acct_id': 4,
                'type': 'normal',
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            self.assertEqual(contest.user_list[4]['status'], UserStatus.APPROVED)

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

            # NOTE: Make sure account removed in Cache && DB
            res = admin_session.post('contests/1/manage/acct', data={
                'reqtype': 'remove',
                'acct_id': 4,
                'type': 'normal',
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            self.assertNotIn(4, contest.user_list)
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            self.assertNotIn(4, contest.user_list)

        with AccountContext('test1@test', 'test') as user_session:
            res = user_session.get('pro/5')
            self.assertNotIn('Eacces', res.text)
            res = user_session.get('pro/8')
            self.assertAPIReturnValue(res.text, ('Eacces', 'Permission denied'))

        # freeze_scoreboard_period: int = 0

        # test scoreboard, challist
        # hide_admin: bool = True
        # test rechal

class RandomContestTest(AsyncTest):
    async def main(self):
        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.post('contests/manage/add', data={
                'reqtype': 'add',
                'name': 'random contest 1'
            })
            self.assertEqual(json.loads(res.text)['data'], 2)
            err, contest = await ContestService.inst.get_contest(2)
            self.assertIsNone(err)
            self.assertEqual(contest.name, 'random contest 1')

            # update general
            now = datetime.datetime.now()
            contest_start = now + datetime.timedelta(days=1)
            contest_end = now + datetime.timedelta(days=4)
            reg_end = now + datetime.timedelta(days=1) - datetime.timedelta(hours=8)
            default_config = {
                'reqtype': 'update',
                'name': 'random contest 1',

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
            res = admin_session.post('contests/2/manage/general', data=default_config)
            self.assertAPIReturnSuccess(res.text)

            # add problem
            res = admin_session.post('contests/2/manage/pro', data={
                'reqtype': 'add',
                'pro_id': 5
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(2)
            self.assertIsNone(err)
            self.assertIn(5, contest.pro_list)

            random_set_config = {
                'reqtype': 'update',
                'name': 'random contest 1',

                'contest_mode': ContestMode.RANDOM_SET,
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
            res = admin_session.post('contests/2/manage/general', data=random_set_config)
            self.assertAPIReturnValue(res.text, ('Echmod', 'Cannot change contest mode when problem list is not empty'))

            # Remove problem and try again
            res = admin_session.post('contests/2/manage/pro', data={
                'reqtype': 'remove',
                'pro_id': 5
            })
            res = admin_session.post('contests/2/manage/general', data=random_set_config)
            self.assertAPIReturnSuccess(res.text)

            err, contest = await ContestService.inst.get_contest(2)
            assert contest
            self.assertIsNone(err)
            self.assertEqual(contest.contest_mode, ContestMode.RANDOM_SET)

            _, contest_list = await ContestService.inst.get_contest_list()
            self.assertEqual(len(contest_list), 2)
            self.assertEqual(contest_list[1]['name'], 'random contest 1')
            self.assertEqual(contest_list[1]['contest_mode'], ContestMode.RANDOM_SET)
            self.assertTrue(contest_list[1]['is_public_scoreboard'])

            # Add first problem set
            res = admin_session.post('contests/2/manage/pro', data={
                'reqtype': 'add_set',
                'pro_id': '8,7,9,11'
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(2)
            assert contest
            self.assertIsNone(err)
            self.assertEqual(len(contest.pro_list), 4)
            self.assertEqual(len(contest.pro_sets), 1)
            self.assertEqual(set(contest.pro_sets[0]), {7, 8, 9, 11})
            # No accounts yet, so acct_pro_list should be empty
            self.assertEqual(len(contest.acct_pro_list), 0)

            # NOTE: Should not add hidden problem to contest
            admin_session.post('manage/pro/update', data={
                'reqtype': 'updategeneral',
                'pro_id': 1,
                'name': 'GCD',
                'status': ProConst.STATUS_HIDDEN,
                'tags': '',
                'allow_submit': 'true',
            })

            res = admin_session.post('contests/2/manage/pro', data={
                'reqtype': 'add_set',
                'pro_id': '1,10'
            })
            self.assertAPIReturnValue(res.text, ("Eacces", 'Cannot add hidden problems to contest'))
            err, contest = await ContestService.inst.get_contest(2)
            assert contest
            self.assertIsNone(err)
            self.assertEqual(len(contest.pro_list), 4)
            self.assertEqual(len(contest.pro_sets), 1)

            admin_session.post('manage/pro/update', data={
                'reqtype': 'updategeneral',
                'pro_id': 1,
                'name': 'GCD',
                'status': ProConst.STATUS_ONLINE,
                'tags': '',
                'allow_submit': 'true',
            })

            # Add accounts
            res = admin_session.post('contests/2/manage/acct', data={
                'reqtype': 'multi_add',
                'acct_id': '4,5,6,7,8,9',
                'type': 'normal',
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(2)
            assert contest
            self.assertIsNone(err)
            # Accounts should be added and allocated problems
            self.assertEqual(len(contest.acct_pro_list), 6)
            for acct_id in (4, 5, 6, 7, 8, 9):
                self.assertIn(acct_id, contest.acct_pro_list)
                self.assertEqual(len(contest.acct_pro_list[acct_id]), 1)
                self.assertIn(contest.acct_pro_list[acct_id][0], (7, 8, 9, 11))

            for pro_id in contest.pro_sets[0]:
                res = admin_session.get(f'contests/2/pro/{pro_id}')
                self.assertNotIn('Eacces', res.text)
                res = admin_session.get(url='', full_url=f'http://localhost:5501/contests/2/pro/{pro_id}/cont.pdf')
                self.assertEqual(res.status_code, 200)
                self.assertEqual(res.headers['Content-Type'], 'application/pdf')
                res = admin_session.post('contests/2/submit', data={
                    'reqtype': 'submit',
                    'pro_id': pro_id,
                    'code': 'code',
                    'compiler_type': Compiler.GPP,
                })
                self.assertAPIReturnSuccess(res.text)

            # Test permission after contest starts
            contest_start_now = now - datetime.timedelta(days=1)
            config = copy.deepcopy(random_set_config)
            config['contest_start'] = self.get_isoformat(contest_start_now)
            res = admin_session.post('contests/2/manage/general', data=config)
            self.assertAPIReturnSuccess(res.text)

            for acct_id in (4, 5, 6, 7, 8, 9):
                with AccountContext(f'contest{acct_id - 3}@test', 'test') as user_session:
                    for pro_id in contest.pro_sets[0]:
                        res = user_session.get(f'contests/2/pro/{pro_id}')
                        if pro_id == contest.acct_pro_list[acct_id][0]:
                            self.assertNotIn('Eacces', res.text)
                        else:
                            self.assertAPIReturnValue(res.text, ('Eacces', 'Permission denied'))
                        res = user_session.get(url='', full_url=f'http://localhost:5501/contests/2/pro/{pro_id}/cont.pdf')
                        if pro_id == contest.acct_pro_list[acct_id][0]:
                            self.assertEqual(res.status_code, 200)
                            self.assertEqual(res.headers['Content-Type'], 'application/pdf')
                        else:
                            self.assertEqual(res.status_code, 403)
                            self.assertIn('Permission denied', res.text)
                        res = user_session.post('contests/2/submit', data={
                            'reqtype': 'submit',
                            'pro_id': pro_id,
                            'code': 'code',
                            'compiler_type': Compiler.GPP,
                        })
                        if pro_id == contest.acct_pro_list[acct_id][0]:
                            self.assertNotIn('Eacces', res.text)
                        else:
                            self.assertAPIReturnValue(res.text, ('Eacces', 'Permission denied'))

            # Reset config to test permissions
            res = admin_session.post('contests/2/manage/general', data=random_set_config)
            self.assertAPIReturnSuccess(res.text)

            # Check adjacency constraint: adjacent accounts should have different problems
            acct_ids = sorted(contest.acct_pro_list.keys())
            for i in range(len(acct_ids) - 1):
                self.assertNotEqual(
                    contest.acct_pro_list[acct_ids[i]][0],
                    contest.acct_pro_list[acct_ids[i + 1]][0]
                )

            # Add second problem set
            res = admin_session.post('contests/2/manage/pro', data={
                'reqtype': 'add_set',
                'pro_id': '5,10'
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(2)
            assert contest
            self.assertIsNone(err)
            self.assertEqual(len(contest.pro_list), 6)
            self.assertEqual(len(contest.pro_sets), 2)
            # All accounts should now have 2 problems
            for acct_id in (4, 5, 6, 7, 8, 9):
                self.assertEqual(len(contest.acct_pro_list[acct_id]), 2)
                self.assertIn(contest.acct_pro_list[acct_id][1], (5, 10))

            # Add third problem set
            res = admin_session.post('contests/2/manage/pro', data={
                'reqtype': 'add_set',
                'pro_id': '6'
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(2)
            assert contest
            self.assertIsNone(err)
            self.assertEqual(len(contest.pro_list), 7)
            self.assertEqual(len(contest.pro_sets), 3)
            for acct_id in (4, 5, 6, 7, 8, 9):
                self.assertEqual(len(contest.acct_pro_list[acct_id]), 3)
                self.assertEqual(contest.acct_pro_list[acct_id][2], 6)

            # Test update_order
            res = admin_session.post('contests/2/manage/pro', data={
                'reqtype': 'update_order',
                'pro_id': '1,0,2'
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(2)
            assert contest
            self.assertIsNone(err)
            self.assertEqual(len(contest.pro_sets), 3)
            self.assertEqual(set(contest.pro_sets[0]), {5, 10})
            self.assertEqual(set(contest.pro_sets[1]), {7, 8, 9, 11})
            self.assertEqual(contest.pro_sets[2], [6])
            # Check all accounts still have correct order
            for acct_id in (4, 5, 6, 7, 8, 9):
                self.assertEqual(len(contest.acct_pro_list[acct_id]), 3)
                self.assertIn(contest.acct_pro_list[acct_id][0], (5, 10))
                self.assertIn(contest.acct_pro_list[acct_id][1], (7, 8, 9, 11))
                self.assertEqual(contest.acct_pro_list[acct_id][2], 6)

            # Test remove_set
            res = admin_session.post('contests/2/manage/pro', data={
                'reqtype': 'remove_set',
                'pro_id': '1'
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(2)
            assert contest
            self.assertIsNone(err)
            self.assertEqual(len(contest.pro_sets), 2)
            self.assertEqual(len(contest.pro_list), 3)
            for acct_id in (4, 5, 6, 7, 8, 9):
                self.assertEqual(len(contest.acct_pro_list[acct_id]), 2)
                self.assertIn(contest.acct_pro_list[acct_id][0], [5, 10])
                self.assertEqual(contest.acct_pro_list[acct_id][1], 6)

            # Test add_to_set
            res = admin_session.post('contests/2/manage/pro', data={
                'reqtype': 'add_to_set',
                'pro_set_idx': 0,
                'pro_id': 7
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(2)
            assert contest
            self.assertIsNone(err)
            self.assertIn(7, contest.pro_sets[0])
            self.assertEqual(len(contest.pro_list), 4)

            # Test remove_from_set
            res = admin_session.post('contests/2/manage/pro', data={
                'reqtype': 'remove_from_set',
                'pro_set_idx': 0,
                'pro_id': 7
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(2)
            assert contest
            self.assertIsNone(err)
            self.assertNotIn(7, contest.pro_sets[0])
            self.assertEqual(len(contest.pro_list), 3)

            # Test reallocation - single account, single problem set
            res = admin_session.post('contests/2/manage/acct', data={
                'reqtype': 'reallocate_account_pro_set',
                'acct_id': 4,
                'pro_set_idx': 0
            })
            self.assertAPIReturnSuccess(res.text)

            # Test reallocation - single account, all problem sets
            res = admin_session.post('contests/2/manage/acct', data={
                'reqtype': 'reallocate_account_all_pro_sets',
                'acct_id': 4
            })
            self.assertAPIReturnSuccess(res.text)

            # Test reallocation - all accounts, single problem set
            res = admin_session.post('contests/2/manage/acct', data={
                'reqtype': 'reallocate_all_accounts_pro_set',
                'pro_set_idx': 0
            })
            self.assertAPIReturnSuccess(res.text)

            # Test reallocation - all accounts, all problem sets
            res = admin_session.post('contests/2/manage/acct', data={
                'reqtype': 'reallocate_all_accounts_all_pro_sets'
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(2)
            assert contest
            self.assertIsNone(err)
            # Verify adjacency constraint still holds after reallocation
            acct_ids = sorted(contest.acct_pro_list.keys())
            for i in range(len(acct_ids) - 1):
                self.assertNotEqual(
                    contest.acct_pro_list[acct_ids[i]][0],
                    contest.acct_pro_list[acct_ids[i + 1]][0]
                )

            # Test remove account - CASCADE should remove allocations
            res = admin_session.post('contests/2/manage/acct', data={
                'reqtype': 'remove',
                'acct_id': 4,
                'type': 'normal',
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(2)
            assert contest
            self.assertIsNone(err)
            self.assertNotIn(4, contest.acct_pro_list)
            self.assertEqual(len(contest.acct_pro_list), 5)

        # Test error cases
        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.post('contests/2/manage/pro', data={
                'reqtype': 'add_set',
                'pro_id': '11,6'
            })
            self.assertAPIReturnValue(res.text, ('Eexist', 'Problem 6 already in contest'))

            res = admin_session.post('contests/2/manage/pro', data={
                'reqtype': 'add_set',
                'pro_id': '7,20,8'
            })
            self.assertAPIReturnValue(res.text, ('Enoext', 'One or more problem IDs do not exist'))

            res = admin_session.post('contests/2/manage/pro', data={
                'reqtype': 'add',
                'pro_id': '11'
            })
            self.assertAPIReturnValue(res.text,('Emod', 'Cannot add problems to random set contests'))

            res = admin_session.post('contests/2/manage/pro', data={
                'reqtype': 'multi_add',
                'pro_id': '7-8'
            })
            self.assertAPIReturnValue(res.text,('Emod', 'Cannot add problems to random set contests'))

            invalid_order = ['1,1', '0,2', '2,0', 'a,b', '1', '1,2,3']
            for order in invalid_order:
                res = admin_session.post('contests/2/manage/pro', data={
                    'reqtype': 'update_order',
                    'pro_id': order
                })
                self.assertAPIReturnValue(res.text, ('Eparam', 'Invalid new indexes for problem sets'))

            res = admin_session.post('contests/2/manage/pro', data={
                'reqtype': 'remove_set',
                'pro_id': '5'
            })
            self.assertAPIReturnValue(res.text, ('Eparam', 'Problem set index out of range'))

            res = admin_session.post('contests/2/manage/pro', data={
                'reqtype': 'remove',
                'pro_id': '6'
            })
            self.assertAPIReturnValue(res.text,('Emod', 'Cannot remove problems from random set contests'))

            res = admin_session.post('contests/2/manage/pro', data={
                'reqtype': 'multi_remove',
                'pro_id': '5-6'
            })
            self.assertAPIReturnValue(res.text,('Emod', 'Cannot remove problems from random set contests'))

            # Test remove_from_set - cannot remove last problem
            res = admin_session.post('contests/2/manage/pro', data={
                'reqtype': 'remove_from_set',
                'pro_set_idx': 1,
                'pro_id': 6
            })
            self.assertAPIReturnValue(res.text, ('Eparam', 'Cannot remove the last problem from a problem set'))

            # Test add_to_set - duplicate
            res = admin_session.post('contests/2/manage/pro', data={
                'reqtype': 'add_to_set',
                'pro_set_idx': 0,
                'pro_id': 5
            })
            self.assertAPIReturnValue(res.text, ('Eexist', 'Problem 5 is already in this problem set'))

            # Test update_pro_set after contest starts
            contest_start_now = now - datetime.timedelta(days=1)
            config = copy.deepcopy(default_config)
            config['contest_mode'] = ContestMode.RANDOM_SET
            config['contest_start'] = self.get_isoformat(contest_start_now)
            res = admin_session.post('contests/2/manage/general', data=config)
            self.assertAPIReturnSuccess(res.text)

            err, contest = await ContestService.inst.get_contest(2)
            assert contest
            self.assertIsNone(err)
            self.assertTrue(contest.is_start())

            # After contest starts, can only add, not remove
            res = admin_session.post('contests/2/manage/pro', data={
                'reqtype': 'add_to_set',
                'pro_set_idx': 0,
                'pro_id': 8
            })
            self.assertAPIReturnSuccess(res.text)

            res = admin_session.post('contests/2/manage/pro', data={
                'reqtype': 'remove_from_set',
                'pro_set_idx': 0,
                'pro_id': 8
            })
            self.assertAPIReturnValue(res.text, ('Etime', 'Cannot remove problems from problem set after contest starts'))

        # Test edge cases
        with AccountContext('admin@test', 'testtest') as admin_session:
            # Create another random set contest for edge case testing
            res = admin_session.post('contests/manage/add', data={
                'reqtype': 'add',
                'name': 'random contest edge cases'
            })
            self.assertEqual(json.loads(res.text)['data'], 3)

            edge_config = copy.deepcopy(default_config)
            edge_config['name'] = 'random contest edge cases'
            edge_config['contest_mode'] = ContestMode.RANDOM_SET
            res = admin_session.post('contests/3/manage/general', data=edge_config)
            self.assertAPIReturnSuccess(res.text)

            err, contest = await ContestService.inst.get_contest(3)
            assert contest
            self.assertIsNone(err)
            self.assertEqual(contest.contest_mode, ContestMode.RANDOM_SET)

            # Edge case 1: Only 1 problem in problem set (should work, no adjacency constraint needed)
            res = admin_session.post('contests/3/manage/pro', data={
                'reqtype': 'add_set',
                'pro_id': '5'
            })
            self.assertAPIReturnSuccess(res.text)

            # Add multiple accounts - all should get the same problem
            res = admin_session.post('contests/3/manage/acct', data={
                'reqtype': 'multi_add',
                'acct_id': '4,5,6',
                'type': 'normal',
            })
            self.assertAPIReturnSuccess(res.text)

            err, contest = await ContestService.inst.get_contest(3)
            assert contest
            self.assertIsNone(err)
            # All accounts should have the same problem (only option)
            for acct_id in (4, 5, 6):
                self.assertIn(acct_id, contest.acct_pro_list)
                self.assertEqual(contest.acct_pro_list[acct_id], [5])

            # Edge case 2: Only 1 account
            res = admin_session.post('contests/3/manage/acct', data={
                'reqtype': 'multi_remove',
                'acct_id': '4,5,6',
                'type': 'normal',
            })
            self.assertAPIReturnSuccess(res.text)

            res = admin_session.post('contests/3/manage/acct', data={
                'reqtype': 'add',
                'acct_id': 4,
                'type': 'normal',
            })
            self.assertAPIReturnSuccess(res.text)

            err, contest = await ContestService.inst.get_contest(3)
            assert contest
            self.assertIsNone(err)
            self.assertEqual(len(contest.acct_pro_list), 1)
            self.assertIn(4, contest.acct_pro_list)

            # Edge case 3: More accounts than problems in set (should cycle through problems)
            res = admin_session.post('contests/3/manage/pro', data={
                'reqtype': 'add_set',
                'pro_id': '10,11'  # Only 2 problems
            })
            self.assertAPIReturnSuccess(res.text)

            res = admin_session.post('contests/3/manage/acct', data={
                'reqtype': 'multi_add',
                'acct_id': '5,6,7,8,9',  # 5 more accounts (6 total)
                'type': 'normal',
            })
            self.assertAPIReturnSuccess(res.text)

            err, contest = await ContestService.inst.get_contest(3)
            assert contest
            self.assertIsNone(err)
            self.assertEqual(len(contest.acct_pro_list), 6)
            # All accounts should have 2 problems now
            for acct_id in (4, 5, 6, 7, 8, 9):
                self.assertEqual(len(contest.acct_pro_list[acct_id]), 2)
                self.assertIn(contest.acct_pro_list[acct_id][1], (11, 10))

            # Verify adjacency constraint even with cycling
            acct_ids = sorted(contest.acct_pro_list.keys())
            for i in range(len(acct_ids) - 1):
                self.assertNotEqual(
                    contest.acct_pro_list[acct_ids[i]][1],
                    contest.acct_pro_list[acct_ids[i + 1]][1]
                )

            # Edge case 4: Remove and re-add account (should get new allocation)
            old_problems = contest.acct_pro_list[4].copy()

            res = admin_session.post('contests/3/manage/acct', data={
                'reqtype': 'remove',
                'acct_id': 4,
                'type': 'normal',
            })
            self.assertAPIReturnSuccess(res.text)

            err, contest = await ContestService.inst.get_contest(3)
            assert contest
            self.assertIsNone(err)
            self.assertNotIn(4, contest.acct_pro_list)

            res = admin_session.post('contests/3/manage/acct', data={
                'reqtype': 'add',
                'acct_id': 4,
                'type': 'normal',
            })
            self.assertAPIReturnSuccess(res.text)

            err, contest = await ContestService.inst.get_contest(3)
            assert contest
            self.assertIsNone(err)
            self.assertIn(4, contest.acct_pro_list)
            self.assertEqual(len(contest.acct_pro_list[4]), 2)
            # Problems may be different but should still be valid
            self.assertEqual(contest.acct_pro_list[4][0], 5)  # Only one option
            self.assertIn(contest.acct_pro_list[4][1], (11, 10))

            # Edge case 5: Reallocate multiple times (stress test)
            for _ in range(3):
                res = admin_session.post('contests/3/manage/acct', data={
                    'reqtype': 'reallocate_all_accounts_all_pro_sets'
                })
                self.assertAPIReturnSuccess(res.text)

                err, contest = await ContestService.inst.get_contest(3)
                assert contest
                self.assertIsNone(err)
                # Verify adjacency constraint still holds
                acct_ids = sorted(contest.acct_pro_list.keys())
                for i in range(len(acct_ids) - 1):
                    self.assertNotEqual(
                        contest.acct_pro_list[acct_ids[i]][1],
                        contest.acct_pro_list[acct_ids[i + 1]][1]
                    )

            # Edge case 6: Add admin user (should NOT get problem allocations)
            res = admin_session.post('contests/3/manage/acct', data={
                'reqtype': 'add',
                'acct_id': 3,  # admin account
                'type': 'admin',
            })
            self.assertAPIReturnSuccess(res.text)

            err, contest = await ContestService.inst.get_contest(3)
            assert contest
            self.assertIsNone(err)
            self.assertIn(3, contest.user_list)
            self.assertEqual(contest.user_list[3]['status'], UserStatus.ADMIN)
            # Admin should NOT be in acct_pro_list
            self.assertNotIn(3, contest.acct_pro_list)
            # Other accounts should still have allocations
            self.assertEqual(len(contest.acct_pro_list), 6)

            # Edge case 7: Mixed problem set sizes
            res = admin_session.post('contests/3/manage/pro', data={
                'reqtype': 'add_set',
                'pro_id': '7,8,9'  # 3 problems
            })
            self.assertAPIReturnSuccess(res.text)

            err, contest = await ContestService.inst.get_contest(3)
            assert contest
            self.assertIsNone(err)
            # All accounts should have 3 problems now
            for acct_id in (4, 5, 6, 7, 8, 9):
                self.assertEqual(len(contest.acct_pro_list[acct_id]), 3)
                self.assertIn(contest.acct_pro_list[acct_id][2], (7, 8, 9))

            # Verify adjacency for all problem sets
            acct_ids = sorted(contest.acct_pro_list.keys())
            for pro_set_idx in range(1, 3): # 0 only has 1 problem
                for i in range(len(acct_ids) - 1):
                    self.assertNotEqual(
                        contest.acct_pro_list[acct_ids[i]][pro_set_idx],
                        contest.acct_pro_list[acct_ids[i + 1]][pro_set_idx]
                    )

            # Edge case 8: Update problem set order multiple times
            for perm in (('2', '0', '1'), ('1', '2', '0'), ('0', '1', '2')):
                res = admin_session.post('contests/3/manage/pro', data={
                    'reqtype': 'update_order',
                    'pro_id': ','.join(perm)
                })
                self.assertAPIReturnSuccess(res.text)

                err, contest = await ContestService.inst.get_contest(3)
                assert contest
                self.assertIsNone(err)
                # Verify all accounts still have problems in new order
                for acct_id in (4, 5, 6, 7, 8, 9):
                    self.assertEqual(len(contest.acct_pro_list[acct_id]), 3)

            # Edge case 9: Add accounts incrementally (test that adjacency works with partial lists)
            res = admin_session.post('contests/3/manage/acct', data={
                'reqtype': 'remove',
                'acct_id': 4,
                'type': 'normal',
            })
            self.assertAPIReturnSuccess(res.text)

            # Add account back - should still maintain adjacency with remaining accounts
            res = admin_session.post('contests/3/manage/acct', data={
                'reqtype': 'add',
                'acct_id': 4,
                'type': 'normal',
            })
            self.assertAPIReturnSuccess(res.text)

            err, contest = await ContestService.inst.get_contest(3)
            assert contest
            self.assertIsNone(err)
            # Verify adjacency constraint after re-adding
            acct_ids = sorted(contest.acct_pro_list.keys())
            for pro_set_idx in range(1, 3): # 0 only has 1 problem
                for i in range(len(acct_ids) - 1):
                    self.assertNotEqual(
                        contest.acct_pro_list[acct_ids[i]][pro_set_idx],
                        contest.acct_pro_list[acct_ids[i + 1]][pro_set_idx]
                    )

class ContestRegistrationPasswordModeTest(AsyncTest):
    async def main(self):
        with AccountContext('admin@test', 'testtest') as admin_session:
            now = datetime.datetime.now()
            res = admin_session.post('contests/manage/add', data={
                'reqtype': 'add',
                'name': 'password contest'
            })
            password_contest_id = json.loads(res.text)['data']
            self.assertEqual(password_contest_id, 4)

            # Setup password mode contest
            contest_start = now + datetime.timedelta(days=1)
            contest_end = now + datetime.timedelta(days=2)

            password_config = {
                'reqtype': 'update',
                'name': 'password contest',

                'contest_mode': ContestMode.IOI,
                'contest_start': self.get_isoformat(contest_start),
                'contest_end': self.get_isoformat(contest_end),

                'reg_mode': RegMode.PASSWORD,
                'reg_end': self.get_isoformat(contest_end),  # reg_end should be equal to contest_end
                'contest_password': 'test_password_123',

                'allow_compilers[]': [Compiler.GPP],
                'is_public_scoreboard': 'true',
                'allow_view_other_page': 'false',
                'hide_admin': 'false',

                'submission_cd_time': 30,
                'freeze_scoreboard_period': 0
            }
            res = admin_session.post(f'contests/{password_contest_id}/manage/general', data=password_config)
            self.assertAPIReturnSuccess(res.text)

            # Verify password is saved
            err, contest = await ContestService.inst.get_contest(password_contest_id)
            self.assertIsNone(err)
            assert contest
            self.assertEqual(contest.reg_mode, RegMode.PASSWORD)
            self.assertEqual(contest.contest_password, 'test_password_123')
            self.assertEqual(contest.reg_end, to_utc(contest_end))

        # Test password registration
        with AccountContext('contest1@test', 'test') as user_session:
            # Try to register without password
            res = user_session.post(f'contests/{password_contest_id}/reg', data={
                'reqtype': 'reg',
                'password': '',
            })
            self.assertAPIReturnValue(res.text, ('Eacces', 'Invalid password'))

            # Try with wrong password
            res = user_session.post(f'contests/{password_contest_id}/reg', data={
                'reqtype': 'reg',
                'password': 'wrong_password',
            })
            self.assertAPIReturnValue(res.text, ('Eacces', 'Invalid password'))

            # Register with correct password
            res = user_session.post(f'contests/{password_contest_id}/reg', data={
                'reqtype': 'reg',
                'password': 'test_password_123',
            })
            self.assertAPIReturnSuccess(res.text, 'Register Successfully')

            # Verify user is registered
            err, contest = await ContestService.inst.get_contest(password_contest_id)
            self.assertIsNone(err)
            self.assertEqual(contest.user_list[4]['status'], UserStatus.APPROVED)  # contest1 is acct_id 4

            # Try to unregister - should fail
            res = user_session.post(f'contests/{password_contest_id}/reg', data={
                'reqtype': 'unreg',
            })
            self.assertAPIReturnValue(res.text, ('Eacces', 'Password mode do not allow unregister'))

            # Verify user is still registered
            err, contest = await ContestService.inst.get_contest(password_contest_id)
            self.assertIsNone(err)
            self.assertEqual(contest.user_list[4]['status'], UserStatus.APPROVED)

        # Test another user with PASSWORD mode
        with AccountContext('contest2@test', 'test') as user_session:
            # Register with correct password
            res = user_session.post(f'contests/{password_contest_id}/reg', data={
                'reqtype': 'reg',
                'password': 'test_password_123',
            })
            self.assertAPIReturnSuccess(res.text, 'Register Successfully')

            # Verify this user is also registered
            err, contest = await ContestService.inst.get_contest(password_contest_id)
            self.assertIsNone(err)
            self.assertEqual(contest.user_list[5]['status'], UserStatus.APPROVED)  # contest2 is acct_id 5


class ContestProblemPermissionTest(AsyncTest):
    async def main(self):
        for mail, password in (('test1@test', 'test'), ('contest1@test', 'test')):
            with AccountContext(mail, password) as user_session:
                for pro_id in range(6, 11 + 1): # 5 already public after contest
                    res = user_session.get(f'pro/{pro_id}')
                    self.assertAPIReturnValue(res.text, ('Eacces', 'Permission denied'))
                    res = user_session.get(url='', full_url=f'http://localhost:5501/pro/{pro_id}/cont.pdf')
                    self.assertEqual(res.status_code, 403)
                    self.assertIn('Permission denied', res.text)
                    res = user_session.post('submit', data={
                        'reqtype': 'submit',
                        'pro_id': pro_id,
                        'code': 'code',
                        'compiler_type': Compiler.GPP,
                    })
                    self.assertAPIReturnValue(res.text, ('Eacces', 'Permission denied'))

        with AccountContext('admin@test', 'testtest') as user_session:
            for pro_id in range(6, 11 + 1): # 5 already public after contest
                res = user_session.get(f'pro/{pro_id}')
                self.assertNotIn('Permission denied', res.text)
                res = user_session.get(url='', full_url=f'http://localhost:5501/pro/{pro_id}/cont.pdf')
                self.assertEqual(res.status_code, 200)
                self.assertEqual(res.headers['Content-Type'], 'application/pdf')
                res = user_session.post('submit', data={
                    'reqtype': 'submit',
                    'pro_id': pro_id,
                    'code': 'code',
                    'compiler_type': Compiler.GPP,
                })
                self.assertAPIReturnSuccess(res.text)


