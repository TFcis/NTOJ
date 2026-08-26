import asyncio
import copy
import datetime
import json

from tornado.websocket import websocket_connect
from tornado.httpclient import HTTPRequest

from services.contests import (
    ContestService,
    ContestMode,
    ContestTimeMode,
    ProblemScoreType,
    RegMode,
    UserStatus,
)
from services.pro import ProService, ProConst
from services.chal import ChalConst, Compiler
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
            # NOTE: If reg_mode is INVITED, reg_end should be the same as contest_end
            self.assertEqual(contest.reg_end, to_utc(contest_end))
            self.assertEqual(contest.contest_creator, 1)

            # NOTE: Should not let contest_end <= contest_start
            config = copy.deepcopy(default_config)
            config['contest_start'] = self.get_isoformat(contest_end + datetime.timedelta(days=1))
            res = admin_session.post('contests/1/manage/general', data=config)
            self.assertAPIReturnValue(res.text, ('Eparam', 'Contest end time should be later than start time'))

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
            self.assertAPIReturnValue(res.text, ('Eacces', 'Cannot add hidden status problem 1'))

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
                'type': 'admin',
            })
            self.assertAPIReturnValue(res.text, ('Eacces', f'Cannot remove user with status {UserStatus.APPROVED.name} from admin list'))
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

        with AccountContext('contest1@test', 'test') as user_session:
            # NOTE: Should not allow register in INVITED mode
            res = user_session.post('contests/1/reg', data={
                'reqtype': 'reg'
            })
            self.assertAPIReturnValue(res.text, ("Eacces", "Invited mode does not allow register"))
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            self.assertNotIn(4, contest.user_list)

            # NOTE: Should not allow unregister in INVITED mode
            res = user_session.post('contests/1/reg', data={
                'reqtype': 'unreg'
            })
            self.assertAPIReturnValue(res.text, ("Eacces", "Invited mode does not allow unregister"))

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

            # NOTE: Should not register again when already approved
            res = user_session.post('contests/1/reg', data={
                'reqtype': 'reg'
            })
            self.assertAPIReturnValue(res.text, ("Eexist", "Your registration has been approved, you cannot register again"))

            res = user_session.post('contests/1/reg', data={
                'reqtype': 'unreg'
            })
            self.assertAPIReturnSuccess(res.text)

            # NOTE: Should not unregister again when not registered
            res = user_session.post('contests/1/reg', data={
                'reqtype': 'unreg'
            })
            self.assertAPIReturnValue(res.text, ("Enoext", "You have not registered yet"))

            # NOTE: Restore
            res = user_session.post('contests/1/reg', data={
                'reqtype': 'reg'
            })
            self.assertAPIReturnSuccess(res.text)

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

            # NOTE: Should not allow remove account in request status from manage account page
            with AccountContext('admin@test', 'testtest') as admin_session:
                res = admin_session.post('contests/1/manage/acct', data={
                    'reqtype': 'remove',
                    'acct_id': 4,
                    'type': 'normal',
                })
                self.assertAPIReturnValue(res.text, ('Eacces', f'Cannot remove user with status {UserStatus.REQUESTED.name} from normal list'))

            # NOTE: Should not register again when already requested
            res = user_session.post('contests/1/reg', data={
                'reqtype': 'reg'
            })
            self.assertAPIReturnValue(res.text, ("Eacces", "Your registration is in request status, please wait for approval"))

            # NOTE: Should allow cancel register when in request status
            res = user_session.post('contests/1/reg', data={
                'reqtype': 'cancelreq'
            })
            self.assertAPIReturnSuccess(res.text)

            # NOTE: Should not unregister again when not registered or requested
            res = user_session.post('contests/1/reg', data={
                'reqtype': 'unreg'
            })
            self.assertAPIReturnValue(res.text, ("Enoext", "You have not registered yet"))

            # NOTE: Restore
            res = user_session.post('contests/1/reg', data={
                'reqtype': 'reg'
            })
            self.assertAPIReturnSuccess(res.text)

        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.post('contests/1/manage/reg', data={
                'reqtype': 'approve',
                'acct_id': 4,
            })
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            self.assertEqual(contest.user_list[4]['status'], UserStatus.APPROVED)

            # NOTE: Should not allow reject when already approved
            res = admin_session.post('contests/1/manage/reg', data={
                'reqtype': 'reject',
                'acct_id': 4,
            })
            self.assertAPIReturnValue(res.text, ("Enoext", "Account(#4) should be in the request status"))
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

                # NOTE: Should not allow remove account in rejected status from manage account page
                res = admin_session.post('contests/1/manage/acct', data={
                    'reqtype': 'remove',
                    'acct_id': 4,
                    'type': 'normal',
                })
                self.assertAPIReturnValue(res.text, ('Eacces', f'Cannot remove user with status {UserStatus.REJECTED.name} from normal list'))

                # NOTE: Should allow re-approve rejected account
                res = admin_session.post('contests/1/manage/reg', data={
                    'reqtype': 'approve',
                    'acct_id': 4,
                })
                self.assertAPIReturnValue(res.text, ('S', 'Re-approve account(#4) successfully.'))
                err, contest = await ContestService.inst.get_contest(1)
                assert contest
                self.assertIsNone(err)
                self.assertEqual(contest.user_list[4]['status'], UserStatus.APPROVED)

                # NOTE: Restore to rejected
                contest.user_list[4]['status'] = UserStatus.REJECTED
                await ContestService.inst.update_contest(None, contest, userlist_updated=True)
                err, contest = await ContestService.inst.get_contest(1)
                assert contest
                self.assertIsNone(err)
                self.assertEqual(contest.user_list[4]['status'], UserStatus.REJECTED)


            # NOTE: Should not allow request register when already rejected
            res = user_session.post('contests/1/reg', data={
                'reqtype': 'reg'
            })
            self.assertAPIReturnValue(res.text, ("Eacces", "Your registration has been rejected, you cannot register"))

            # NOTE: Should not allow cancel register request when already rejected
            res = user_session.post('contests/1/reg', data={
                'reqtype': 'cancelreq'
            })
            self.assertAPIReturnValue(res.text, ("Eacces", "Your registration is not in request status, you cannot cancel request"))


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

            contest_start = now - datetime.timedelta(days=2)
            config = copy.deepcopy(default_config)
            config['contest_start'] = self.get_isoformat(contest_start)
            config['reg_mode'] = RegMode.FREE_REG
            res = admin_session.post('contests/1/manage/general', data=config)
            self.assertAPIReturnSuccess(res.text)
            err, contest = await ContestService.inst.get_contest(1)
            self.assertIsNone(err)
            self.assertEqual(contest.contest_start, to_utc(contest_start))
            self.assertTrue(contest.is_start())

        with AccountContext('contest1@test', 'test') as user_session:
            res = user_session.get('contests/1/pro/5/cont.pdf')
            self.assertEqual(res.status_code, 200)

            # NOTE: Should not allow unregister when contest has started
            res = user_session.post('contests/1/reg', data={
                'reqtype': 'unreg'
            })
            self.assertAPIReturnValue(res.text, ("Etime", "Contest has started, you cannot unregister now"))

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

        with AccountContext('test1@test', 'test') as user_session:
            res = user_session.post('contests/1/qa', data={
                'reqtype': 'ask',
                'subject': 'subject',
                'content': 'content',
            })
            self.assertAPIReturnValue(res.text, ('Eacces', 'Permission denied'))

        with AccountContext('contest1@test', 'test') as user_session:
            def _message(msg):
                if msg is None:
                    return
                data = json.loads(msg)
                if data.get('type') == 'contestnewquessub':
                    self.assertEqual(int(data['data']), 1)
            ws = await websocket_connect('ws://localhost:5501/be/ws', on_message_callback=_message)
            await ws.write_message(json.dumps({'type': 'register', 'data': 'contestnewquessub'}))
            await ws.write_message(json.dumps({
                'type': 'contestnewquessub_init',
                'data': '1'
            }))

            self.assertTable(
                'contests/1/qa',
                {
                    'reqtype': 'ask',
                    'subject': 'subject',
                    'content': 'content',
                },
                [
                    {'subject': '', 'equal_value': ('Eparam', 'Subject too short')},
                    {'subject': 'subject' * 10000, 'equal_value': ('Eparam', 'Subject too long')},
                    {'content': '', 'equal_value': ('Eparam', 'Content too short')},
                    {'content': 'content' * 10000, 'equal_value': ('Eparam', 'Content too long')},
                ],
                user_session
            )

            res = user_session.post('contests/1/qa', data={
                'reqtype': 'ask',
                'subject': 'subject',
                'content': 'content',
            })
            self.assertAPIReturnSuccess(res.text)

            res = user_session.post('contests/1/qa', data={
                'reqtype': 'ask',
                'subject': 'subject',
                'content': 'content',
            })
            res = json.loads(res.text)
            self.assertEqual(res['status'], 'Einternal')

            ws.close()

        with AccountContext('admin@test', 'testtest') as admin_session:
            _, count = await ContestService.inst.get_need_reply_question_cnt(1)
            self.assertEqual(count, 1)

            _, queslist = await ContestService.inst.get_all_question(contest_id=1, ask_acct_id=4)
            self.assertEqual(len(queslist), 1)
            ques = queslist[0]
            self.assertEqual(ques['ask_subject'], 'subject')
            self.assertEqual(ques['ask_content'], 'content')
            self.assertEqual(ques['ask_acct_id'], 4)
            self.assertEqual(ques['reply_content'], None)
            self.assertEqual(ques['reply_acct_id'], None)
            question_id = ques['question_id']

            def _message(msg):
                if msg is None:
                    return

                data = json.loads(msg)
                if data.get('type') == 'contestnewqasub':
                    j = json.loads(data['data'])
                    self.assertEqual(j['contest_id'], 1)
                    self.assertEqual(j['type'], 'reply')
                    self.assertEqual(j['ask_acct_id'], 4)

            cookie_value = admin_session.cookies.get('id')
            headers = {"Cookie": f"id={cookie_value}"}
            ws = await websocket_connect(HTTPRequest('ws://localhost:5501/be/ws', headers=headers), on_message_callback=_message)
            await ws.write_message(json.dumps({'type': 'register', 'data': 'contestnewqasub'}))
            await ws.write_message(json.dumps({
                'type': 'contestnewqasub_init',
                'data': json.dumps({
                    "contest_id": 1,
                })
            }))

            res = admin_session.post('contests/1/manage/question', data={
                'reqtype': 'reply',
                'content': 'answer',
                'question_id': question_id
            })
            self.assertAPIReturnSuccess(res.text)
            err, ques = await ContestService.inst.get_question(1, question_id)
            self.assertIsNone(err)
            self.assertEqual(ques['reply_content'], 'answer')
            self.assertEqual(ques['reply_acct_id'], 1)

            _, count = await ContestService.inst.get_need_reply_question_cnt(1)
            self.assertEqual(count, 0)

            ws.close()
            res = admin_session.post('contests/1/manage/question', data={
                'reqtype': 'reply',
                'content': '',
                'question_id': question_id
            })
            self.assertAPIReturnValue(res.text, ('Eparam', 'Content too short'))
            res = admin_session.post('contests/1/manage/question', data={
                'reqtype': 'reply',
                'content': 'a' * 5000,
                'question_id': question_id
            })
            self.assertAPIReturnValue(res.text, ('Eparam', 'Content too long'))

        with AccountContext('admin@test', 'testtest') as admin_session:
            def _message(msg):
                if msg is None:
                    return

                data = json.loads(msg)
                if data.get('type') == 'contestnewqasub':
                    j = json.loads(data['data'])
                    self.assertEqual(j['contest_id'], 1)
                    self.assertEqual(j['type'], 'add-announce')

            cookie_value = admin_session.cookies.get('id')
            headers = {"Cookie": f"id={cookie_value}"}
            ws = await websocket_connect(HTTPRequest('ws://localhost:5501/be/ws', headers=headers), on_message_callback=_message)
            await ws.write_message(json.dumps({'type': 'register', 'data': 'contestnewqasub'}))
            await ws.write_message(json.dumps({
                'type': 'contestnewqasub_init',
                'data': json.dumps({
                    "contest_id": 1,
                })
            }))
            res = admin_session.post('contests/1/manage/announce', data={
                'reqtype': 'add-announce',
                'subject': 'subject',
                'content': 'content',
            })
            self.assertAPIReturnSuccess(res.text)
            ws.close()

            _, announces = await ContestService.inst.get_all_announce(1)
            self.assertEqual(len(announces), 1)
            announce = announces[0]
            self.assertEqual(announce['subject'], 'subject')
            self.assertEqual(announce['content'], 'content')
            self.assertEqual(announce['acct_id'], 1)
            err, a = await ContestService.inst.get_announce(1, announce['announce_id'])
            self.assertIsNone(err)
            self.assertEqual(a, announce)

            self.assertTable(
                'contests/1/manage/announce',
                {
                    'reqtype': 'add-announce',
                    'subject': 'subject',
                    'content': 'content',
                },
                [
                    {'subject': '', 'equal_value': ('Eparam', 'Subject too short')},
                    {'subject': 'subject' * 10000, 'equal_value': ('Eparam', 'Subject too long')},
                    {'content': '', 'equal_value': ('Eparam', 'Content too short')},
                    {'content': 'content' * 10000, 'equal_value': ('Eparam', 'Content too long')},
                ],
                admin_session
            )
            self.assertTable(
                'contests/1/manage/announce',
                {
                    'reqtype': 'edit-announce',
                    'announce_id': announce['announce_id'],
                    'subject': 'subject',
                    'content': 'content',
                },
                [
                    {'subject': '', 'equal_value': ('Eparam', 'Subject too short')},
                    {'subject': 'subject' * 10000, 'equal_value': ('Eparam', 'Subject too long')},
                    {'content': '', 'equal_value': ('Eparam', 'Content too short')},
                    {'content': 'content' * 10000, 'equal_value': ('Eparam', 'Content too long')},
                ],
                admin_session
            )

        with AccountContext('admin@test', 'testtest') as admin_session:
            def _message(msg):
                if msg is None:
                    return

                data = json.loads(msg)
                if data.get('type') == 'contestnewqasub':
                    j = json.loads(data['data'])
                    self.assertEqual(j['contest_id'], 1)
                    self.assertEqual(j['type'], 'edit-announce')

            cookie_value = admin_session.cookies.get('id')
            headers = {"Cookie": f"id={cookie_value}"}
            ws = await websocket_connect(HTTPRequest('ws://localhost:5501/be/ws', headers=headers), on_message_callback=_message)
            await ws.write_message(json.dumps({'type': 'register', 'data': 'contestnewqasub'}))
            await ws.write_message(json.dumps({
                'type': 'contestnewqasub_init',
                'data': json.dumps({
                    "contest_id": 1,
                })
            }))
            res = admin_session.post('contests/1/manage/announce', data={
                'reqtype': 'edit-announce',
                'subject': 'subject2',
                'content': 'content2',
                'announce_id': 1,
            })
            self.assertAPIReturnSuccess(res.text)
            ws.close()
            _, announces = await ContestService.inst.get_all_announce(1)
            self.assertEqual(len(announces), 1)
            announce = announces[0]
            self.assertEqual(announce['subject'], 'subject2')
            self.assertEqual(announce['content'], 'content2')
            self.assertEqual(announce['acct_id'], 1)
            err, a = await ContestService.inst.get_announce(1, announce['announce_id'])
            self.assertIsNone(err)
            self.assertEqual(a, announce)

        with AccountContext('admin@test', 'testtest') as admin_session:
            def _message(msg):
                if msg is None:
                    return

                j = json.loads(msg)
                self.assertEqual(j['contest_id'], 1)
                self.assertEqual(j['type'], 'popup-announce')

            cookie_value = admin_session.cookies.get('id')
            headers = {"Cookie": f"id={cookie_value}"}
            ws = await websocket_connect(HTTPRequest('ws://localhost:5501/be/ws', headers=headers), on_message_callback=_message)
            await ws.write_message(json.dumps({'type': 'register', 'data': 'contestnewqasub'}))
            await ws.write_message(json.dumps({
                'type': 'contestnewqasub_init',
                'data': json.dumps({
                    "contest_id": 1,
                })
            }))
            res = admin_session.post('contests/1/manage/announce', data={
                'reqtype': 'popup-announce',
                'announce_id': 1,
            })
            self.assertAPIReturnSuccess(res.text)
            ws.close()

            res = admin_session.get('contests/1/qa')
            self.assertAPIReturnValue(res.text, ('Eacces', 'Permission denied'))

        # NOTE: contest end
        with AccountContext('admin@test', 'testtest') as admin_session:
            contest_start = now - datetime.timedelta(days=2)
            contest_end = now - datetime.timedelta(days=1)
            config = copy.deepcopy(default_config)
            config['contest_start'] = self.get_isoformat(contest_start)
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

class ContestProblemPermissionTest(AsyncTest):
    async def main(self):
        for mail, password in (('admin@test', 'testtest'), ('test1@test', 'test'), ('contest1@test', 'test')):
            with AccountContext(mail, password) as user_session:
                for pro_id in range(6, 11 + 1): # 5 already public after contest
                    res = user_session.get(f'pro/{pro_id}')
                    print(res.text)
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

class FlexibleContestTimeTest(AsyncTest):
    async def main(self):
        await self._test_configuration_and_start_boundaries()
        await self._test_access_and_session_lifecycle()
        await self._test_ioi_scoreboard_and_cache()
        await self._test_icpc_scoreboard()

    def _config(
        self,
        name,
        contest_start,
        contest_end,
        duration,
        contest_mode=ContestMode.IOI,
    ):
        return {
            'reqtype': 'update',
            'name': name,
            'contest_mode': contest_mode,
            'contest_time_mode': ContestTimeMode.FLEXIBLE,
            'contest_duration': duration,
            'contest_start': self.get_isoformat(contest_start),
            'contest_end': self.get_isoformat(contest_end),
            'reg_mode': RegMode.INVITED,
            'reg_end': self.get_isoformat(contest_end),
            'allow_compilers[]': [Compiler.GPP],
            'is_public_scoreboard': 'true',
            'allow_view_other_page': 'false',
            'hide_admin': 'true',
            'submission_cd_time': 0,
            'freeze_scoreboard_period': 30,
            'penalty_value': 20,
        }

    async def _create_contest(
        self,
        admin_session,
        config,
        acct_ids=(),
        pro_ids=(),
    ):
        res = admin_session.post('contests/manage/add', data={
            'reqtype': 'add',
            'name': config['name'],
        })
        self.assertAPIReturnSuccess(res.text)
        contest_id = json.loads(res.text)['data']

        res = admin_session.post(
            f'contests/{contest_id}/manage/general', data=config
        )
        self.assertAPIReturnSuccess(res.text)
        for acct_id in acct_ids:
            res = admin_session.post(f'contests/{contest_id}/manage/acct', data={
                'reqtype': 'add',
                'acct_id': acct_id,
                'type': 'normal',
            })
            self.assertAPIReturnSuccess(res.text)
        for pro_id in pro_ids:
            res = admin_session.post(f'contests/{contest_id}/manage/pro', data={
                'reqtype': 'add',
                'pro_id': pro_id,
            })
            self.assertAPIReturnSuccess(res.text)
        return contest_id

    async def _set_sessions(self, contest_id, sessions):
        for acct_id, start_time, end_time in sessions:
            await ContestService.inst.db.execute(
                """
                UPDATE contest_sessions
                SET start_time = $3, end_time = $4
                WHERE contest_id = $1 AND acct_id = $2
                """,
                contest_id,
                acct_id,
                start_time,
                end_time,
            )
        await ContestService.inst.rs.hdel('contest', str(contest_id))
        await ContestService.inst.invalidate_scoreboard_cache(contest_id)

    async def _insert_challenge(
        self,
        contest_id,
        pro_id,
        acct_id,
        timestamp,
        state,
        rate=0,
    ):
        row = await ContestService.inst.db.fetchrow(
            """
            INSERT INTO challenge (
                pro_id, acct_id, timestamp, compiler_type, contest_id
            ) VALUES ($1, $2, $3, $4, $5)
            RETURNING chal_id
            """,
            pro_id,
            acct_id,
            timestamp,
            int(Compiler.GPP),
            contest_id,
        )
        chal_id = row['chal_id']
        await ContestService.inst.db.execute(
            """
            INSERT INTO total_result (chal_id, state, time, memory, rate)
            VALUES ($1, $2, 0, 0, $3)
            """,
            chal_id,
            state,
            rate,
        )
        return chal_id

    def _scoreboard(self, session, contest_id, display_time=None):
        data = {}
        if display_time is not None:
            data['display_time'] = display_time.isoformat()
        res = session.post(f'contests/{contest_id}/scoreboard', data=data)
        self.assertAPIReturnSuccess(res.text)
        return {
            row['acct_id']: row
            for row in json.loads(res.text)['data']
        }

    async def _start(self, session, contest_id):
        res = session.post(f'contests/{contest_id}/info', data={
            'reqtype': 'start',
        })
        self.assertAPIReturnSuccess(res.text)

    async def _test_configuration_and_start_boundaries(self):
        now = datetime.datetime.now()
        upcoming_config = self._config(
            'flexible start boundaries',
            now + datetime.timedelta(hours=1),
            now + datetime.timedelta(hours=2),
            1800,
        )

        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.post('contests/manage/add', data={
                'reqtype': 'add',
                'name': upcoming_config['name'],
            })
            self.assertAPIReturnSuccess(res.text)
            contest_id = json.loads(res.text)['data']

            invalid_config = copy.deepcopy(upcoming_config)
            invalid_config['contest_duration'] = 0
            res = admin_session.post(
                f'contests/{contest_id}/manage/general', data=invalid_config
            )
            self.assertAPIReturnValue(
                res.text,
                ('Eparam', 'Contest duration must be a positive integer'),
            )

            invalid_config['contest_duration'] = 'not-an-integer'
            res = admin_session.post(
                f'contests/{contest_id}/manage/general', data=invalid_config
            )
            self.assertAPIReturnValue(
                res.text,
                ('Eparam', 'Contest duration must be a positive integer'),
            )

            res = admin_session.post(
                f'contests/{contest_id}/manage/general', data=upcoming_config
            )
            self.assertAPIReturnSuccess(res.text)
            res = admin_session.post(f'contests/{contest_id}/manage/acct', data={
                'reqtype': 'add',
                'acct_id': 7,
                'type': 'normal',
            })
            self.assertAPIReturnSuccess(res.text)

            fixed_config = copy.deepcopy(upcoming_config)
            fixed_config['contest_time_mode'] = ContestTimeMode.FIXED
            res = admin_session.post(
                f'contests/{contest_id}/manage/general', data=fixed_config
            )
            self.assertAPIReturnSuccess(res.text)
            res = admin_session.post(
                f'contests/{contest_id}/manage/general', data=upcoming_config
            )
            self.assertAPIReturnSuccess(res.text)

            res = admin_session.post(f'contests/{contest_id}/info', data={
                'reqtype': 'start',
            })
            self.assertAPIReturnValue(
                res.text,
                ('Eacces', 'Contest cannot be started at this time'),
            )

        with AccountContext('contest4@test', 'test') as user_session:
            res = user_session.get(f'contests/{contest_id}/info')
            self.assertNotIn('Start Contest', res.text)
            res = user_session.post(f'contests/{contest_id}/info', data={
                'reqtype': 'start',
            })
            self.assertAPIReturnValue(
                res.text,
                ('Eacces', 'Contest cannot be started at this time'),
            )

        with AccountContext('contest5@test', 'test') as outsider_session:
            res = outsider_session.post(f'contests/{contest_id}/info', data={
                'reqtype': 'start',
            })
            self.assertAPIReturnValue(
                res.text,
                ('Eacces', 'Contest cannot be started at this time'),
            )

        ended_config = copy.deepcopy(upcoming_config)
        ended_config['contest_start'] = self.get_isoformat(
            now - datetime.timedelta(hours=2)
        )
        ended_config['contest_end'] = self.get_isoformat(
            now - datetime.timedelta(hours=1)
        )
        ended_config['reg_end'] = ended_config['contest_end']
        with AccountContext('admin@test', 'testtest') as admin_session:
            res = admin_session.post(
                f'contests/{contest_id}/manage/general', data=ended_config
            )
            self.assertAPIReturnSuccess(res.text)

        with AccountContext('contest4@test', 'test') as user_session:
            res = user_session.post(f'contests/{contest_id}/info', data={
                'reqtype': 'start',
            })
            self.assertAPIReturnValue(
                res.text,
                ('Eacces', 'Contest cannot be started at this time'),
            )
            self._scoreboard(user_session, contest_id)

    async def _test_access_and_session_lifecycle(self):
        now = datetime.datetime.now()
        hard_end = now + datetime.timedelta(minutes=5)
        config = self._config(
            'flexible access lifecycle',
            now - datetime.timedelta(minutes=1),
            hard_end,
            3600,
        )

        with AccountContext('admin@test', 'testtest') as admin_session:
            contest_id = await self._create_contest(
                admin_session,
                config,
                acct_ids=(5, 6),
                pro_ids=(8,),
            )

        with AccountContext('contest2@test', 'test') as user_session:
            res = user_session.get(f'contests/{contest_id}/info')
            self.assertIn('Start Contest', res.text)
            for path in (
                f'contests/{contest_id}/proset',
                f'contests/{contest_id}/pro/8',
                f'contests/{contest_id}/submit/8',
            ):
                res = user_session.get(path)
                self.assertAPIReturnValue(res.text, ('Eacces', 'Permission denied'))

            await self._start(user_session, contest_id)

            res = user_session.post(f'contests/{contest_id}/info', data={
                'reqtype': 'start',
            })
            self.assertAPIReturnValue(
                res.text,
                ('Eacces', 'Contest cannot be started at this time'),
            )
            session_count = await ContestService.inst.db.fetchval(
                """
                SELECT COUNT(*) FROM contest_sessions
                WHERE contest_id = $1 AND acct_id = $2
                """,
                contest_id,
                5,
            )
            self.assertEqual(session_count, 1)

            err, contest = await ContestService.inst.get_contest(contest_id)
            self.assertIsNone(err)
            options = contest.user_list[5]
            self.assertIsNotNone(options['session_id'])
            self.assertEqual(options['session_end'], contest.contest_end)
            self.assertEqual(contest.freeze_scoreboard_period, 0)

            for path in (
                f'contests/{contest_id}/proset',
                f'contests/{contest_id}/pro/8',
                f'contests/{contest_id}/submit/8',
            ):
                res = user_session.get(path)
                self.assertNotIn('Eacces', res.text)

            res = user_session.post(f'contests/{contest_id}/scoreboard', data={})
            self.assertAPIReturnSuccess(res.text)

        challenge_id = await self._insert_challenge(
            contest_id,
            8,
            5,
            datetime.datetime.now(datetime.UTC),
            ChalConst.STATE_AC,
            100,
        )
        with AccountContext('contest3@test', 'test') as pending_session:
            for path in (
                f'contests/{contest_id}/proset',
                f'contests/{contest_id}/pro/8',
                f'contests/{contest_id}/submit/8',
                f'contests/{contest_id}/chal/{challenge_id}',
            ):
                res = pending_session.get(path)
                self.assertAPIReturnValue(res.text, ('Eacces', 'Permission denied'))
            res = pending_session.post(
                f'contests/{contest_id}/scoreboard', data={}
            )
            self.assertAPIReturnValue(res.text, ('Eacces', 'Permission denied'))

        with AccountContext('admin@test', 'testtest') as admin_session:
            fixed_config = copy.deepcopy(config)
            fixed_config['contest_time_mode'] = ContestTimeMode.FIXED
            res = admin_session.post(
                f'contests/{contest_id}/manage/general', data=fixed_config
            )
            self.assertAPIReturnValue(
                res.text,
                ('Etime', 'Contest time mode cannot be changed after the contest starts'),
            )

        expired_end = datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=1)
        await self._set_sessions(
            contest_id,
            ((5, expired_end - datetime.timedelta(seconds=1), expired_end),),
        )

        with AccountContext('contest2@test', 'test') as user_session:
            for path in (
                f'contests/{contest_id}/proset',
                f'contests/{contest_id}/pro/8',
                f'contests/{contest_id}/submit/8',
            ):
                res = user_session.get(path)
                self.assertAPIReturnValue(res.text, ('Eacces', 'Permission denied'))

        full_duration_config = self._config(
            'flexible full duration',
            now - datetime.timedelta(minutes=1),
            now + datetime.timedelta(hours=2),
            1800,
        )
        with AccountContext('admin@test', 'testtest') as admin_session:
            full_duration_id = await self._create_contest(
                admin_session,
                full_duration_config,
                acct_ids=(7,),
            )
        with AccountContext('contest4@test', 'test') as user_session:
            await self._start(user_session, full_duration_id)

        row = await ContestService.inst.db.fetchrow(
            """
            SELECT start_time, end_time FROM contest_sessions
            WHERE contest_id = $1 AND acct_id = $2
            """,
            full_duration_id,
            7,
        )
        self.assertEqual((row['end_time'] - row['start_time']).total_seconds(), 1800)

    async def _test_ioi_scoreboard_and_cache(self):
        now = datetime.datetime.now()
        config = self._config(
            'flexible IOI scoreboard',
            now - datetime.timedelta(minutes=1),
            now + datetime.timedelta(hours=2),
            3600,
        )
        with AccountContext('admin@test', 'testtest') as admin_session:
            contest_id = await self._create_contest(
                admin_session,
                config,
                acct_ids=(5, 6, 7, 9),
                pro_ids=(9,),
            )
            res = admin_session.post(f'contests/{contest_id}/manage/pro', data={
                'reqtype': 'update_score_type',
                'pro_id': 9,
                'score_type': ProblemScoreType.IOI2013,
            })
            self.assertAPIReturnSuccess(res.text)

        with AccountContext('contest2@test', 'test') as user_session:
            await self._start(user_session, contest_id)
        with AccountContext('contest3@test', 'test') as user_session:
            await self._start(user_session, contest_id)
        with AccountContext('contest6@test', 'test') as user_session:
            await self._start(user_session, contest_id)

        base = datetime.datetime.now(datetime.UTC)
        acct5_start = base - datetime.timedelta(minutes=30)
        acct6_start = base - datetime.timedelta(minutes=10)
        acct9_start = base - datetime.timedelta(minutes=4, seconds=52)
        session_end = base + datetime.timedelta(minutes=30)
        await self._set_sessions(
            contest_id,
            (
                (5, acct5_start, session_end),
                (6, acct6_start, session_end),
                (9, acct9_start, session_end),
            ),
        )
        await ContestService.inst.db.execute(
            """
            UPDATE contest SET freeze_scoreboard_period = 1
            WHERE contest_id = $1
            """,
            contest_id,
        )
        await ContestService.inst.rs.hdel('contest', str(contest_id))

        await self._insert_challenge(
            contest_id, 9, 5, acct5_start - datetime.timedelta(seconds=1),
            ChalConst.STATE_AC, 99,
        )
        await self._insert_challenge(
            contest_id, 9, 5, acct5_start,
            ChalConst.STATE_PC, 10,
        )
        await self._insert_challenge(
            contest_id, 9, 5, acct5_start + datetime.timedelta(minutes=5),
            ChalConst.STATE_PC, 50,
        )
        await self._insert_challenge(
            contest_id, 9, 5, session_end,
            ChalConst.STATE_AC, 100,
        )
        await self._insert_challenge(
            contest_id, 9, 6, acct6_start - datetime.timedelta(seconds=1),
            ChalConst.STATE_AC, 99,
        )
        await self._insert_challenge(
            contest_id, 9, 6, acct6_start + datetime.timedelta(minutes=2),
            ChalConst.STATE_PC, 70,
        )
        await self._insert_challenge(
            contest_id, 9, 7, base - datetime.timedelta(minutes=5),
            ChalConst.STATE_AC, 100,
        )
        await ContestService.inst.invalidate_scoreboard_cache(contest_id)

        with AccountContext('contest6@test', 'test') as live_session:
            scoreboard_page = live_session.get(f'contests/{contest_id}/scoreboard')
            self.assertIn('flexible-session-time', scoreboard_page.text)
            scores = self._scoreboard(live_session, contest_id)
            self.assertEqual(scores[5]['total_score'], 10)
            self.assertEqual(
                scores[5]['flexible_start'], acct5_start.isoformat()
            )
            self.assertEqual(
                scores[5]['flexible_end'], session_end.isoformat()
            )
            self.assertIsNone(scores[7]['flexible_start'])
            self.assertIsNone(scores[7]['flexible_end'])

            cookie_value = live_session.cookies.get('id')
            ws = await websocket_connect(HTTPRequest(
                'ws://localhost:5501/be/ws',
                headers={"Cookie": f"id={cookie_value}"},
            ))
            await ws.write_message(json.dumps({
                'type': 'register',
                'data': 'contestnewchalsub',
            }))
            await ws.write_message(json.dumps({
                'type': 'contestnewchalsub_init',
                'data': {
                    'contest_id': contest_id,
                    'purpose': 'scoreboard',
                },
            }))

            message = json.loads(await asyncio.wait_for(
                ws.read_message(),
                timeout=15,
            ))
            self.assertEqual(message['type'], 'contestnewchalsub')
            self.assertEqual(int(message['data']), contest_id)
            scores = self._scoreboard(live_session, contest_id)
            self.assertEqual(scores[5]['total_score'], 50)
            ws.close()

        cache_name = f'contest_{contest_id}_scores'
        history_time = acct5_start + datetime.timedelta(minutes=1)
        with AccountContext('contest2@test', 'test') as user_session:
            scores = self._scoreboard(user_session, contest_id, history_time)
            self.assertEqual(scores[5]['total_score'], 10)
            self.assertEqual(scores[5]['scores']['9']['timestamp'], '0:00')
            self.assertEqual(scores[6]['total_score'], 0)
            self.assertEqual(scores[7]['total_score'], 0)
            self.assertIsNone(
                await ContestService.inst.rs.hget(cache_name, '9')
            )

            scores = self._scoreboard(user_session, contest_id)
            self.assertEqual(scores[5]['total_score'], 50)
            self.assertEqual(scores[5]['scores']['9']['timestamp'], '5:00')
            self.assertEqual(scores[6]['total_score'], 70)
            self.assertEqual(scores[6]['scores']['9']['timestamp'], '2:00')
            self.assertEqual(scores[7]['total_score'], 0)
            self.assertIsNone(
                await ContestService.inst.rs.hget(cache_name, '9')
            )

        with AccountContext('contest3@test', 'test') as user_session:
            scores = self._scoreboard(user_session, contest_id, acct6_start)
            self.assertEqual(scores[5]['total_score'], 10)
            self.assertEqual(scores[5]['scores']['9']['timestamp'], '0:00')
            self.assertEqual(scores[6]['total_score'], 0)

            scores = self._scoreboard(
                user_session,
                contest_id,
                acct6_start + datetime.timedelta(minutes=5),
            )
            self.assertEqual(scores[5]['total_score'], 50)
            self.assertEqual(scores[5]['scores']['9']['timestamp'], '5:00')
            self.assertEqual(scores[6]['total_score'], 70)

        with AccountContext('contest4@test', 'test') as pending_session:
            res = pending_session.post(
                f'contests/{contest_id}/scoreboard', data={}
            )
            self.assertAPIReturnValue(res.text, ('Eacces', 'Permission denied'))

        with AccountContext('contest5@test', 'test') as outsider_session:
            res = outsider_session.post(
                f'contests/{contest_id}/scoreboard', data={}
            )
            self.assertAPIReturnValue(res.text, ('Eacces', 'Permission denied'))

        with AccountContext('admin@test', 'testtest') as admin_session:
            scores = self._scoreboard(admin_session, contest_id)
            self.assertEqual(scores[5]['total_score'], 50)
            self.assertEqual(scores[6]['total_score'], 70)
            self.assertIsNotNone(
                await ContestService.inst.rs.hget(cache_name, '9')
            )

            await self._insert_challenge(
                contest_id,
                9,
                5,
                acct5_start + datetime.timedelta(minutes=6),
                ChalConst.STATE_PC,
                80,
            )
            cached_scores = self._scoreboard(admin_session, contest_id)
            self.assertEqual(cached_scores[5]['total_score'], 50)

        with AccountContext('contest2@test', 'test') as user_session:
            uncached_scores = self._scoreboard(user_session, contest_id)
            self.assertEqual(uncached_scores[5]['total_score'], 80)

        await ContestService.inst.invalidate_scoreboard_cache(contest_id)
        with AccountContext('admin@test', 'testtest') as admin_session:
            refreshed_scores = self._scoreboard(admin_session, contest_id)
            self.assertEqual(refreshed_scores[5]['total_score'], 80)
            self.assertEqual(
                refreshed_scores[5]['scores']['9']['timestamp'], '6:00'
            )

        await ContestService.inst.db.execute(
            "UPDATE contest SET contest_end = $2 WHERE contest_id = $1",
            contest_id,
            base,
        )
        await ContestService.inst.rs.hdel('contest', str(contest_id))
        await ContestService.inst.invalidate_scoreboard_cache(contest_id)

        with AccountContext('contest5@test', 'test') as outsider_session:
            scores = self._scoreboard(outsider_session, contest_id)
            self.assertEqual(scores[5]['total_score'], 80)
            self.assertEqual(scores[6]['total_score'], 70)

    async def _test_icpc_scoreboard(self):
        now = datetime.datetime.now()
        config = self._config(
            'flexible ICPC scoreboard',
            now - datetime.timedelta(minutes=1),
            now + datetime.timedelta(hours=2),
            3600,
            contest_mode=ContestMode.ACM,
        )
        with AccountContext('admin@test', 'testtest') as admin_session:
            contest_id = await self._create_contest(
                admin_session,
                config,
                acct_ids=(5, 6),
                pro_ids=(10,),
            )

        with AccountContext('contest2@test', 'test') as user_session:
            await self._start(user_session, contest_id)
        with AccountContext('contest3@test', 'test') as user_session:
            await self._start(user_session, contest_id)

        base = datetime.datetime.now(datetime.UTC)
        acct5_start = base - datetime.timedelta(minutes=30)
        acct6_start = base - datetime.timedelta(minutes=10)
        session_end = base + datetime.timedelta(minutes=30)
        await self._set_sessions(
            contest_id,
            (
                (5, acct5_start, session_end),
                (6, acct6_start, session_end),
            ),
        )

        await self._insert_challenge(
            contest_id, 10, 5, acct5_start - datetime.timedelta(seconds=1),
            ChalConst.STATE_AC,
        )
        await self._insert_challenge(
            contest_id, 10, 5, acct5_start + datetime.timedelta(minutes=1),
            ChalConst.STATE_WA,
        )
        acct5_ac = await self._insert_challenge(
            contest_id, 10, 5, acct5_start + datetime.timedelta(minutes=3),
            ChalConst.STATE_AC,
        )
        await self._insert_challenge(
            contest_id, 10, 5, session_end,
            ChalConst.STATE_AC,
        )
        acct6_ac = await self._insert_challenge(
            contest_id, 10, 6, acct6_start + datetime.timedelta(minutes=2),
            ChalConst.STATE_AC,
        )
        await ContestService.inst.invalidate_scoreboard_cache(contest_id)

        with AccountContext('contest2@test', 'test') as user_session:
            history = self._scoreboard(
                user_session,
                contest_id,
                acct5_start + datetime.timedelta(minutes=2),
            )
            self.assertEqual(history[5]['total_score'], 0)
            self.assertEqual(history[5]['scores']['10']['fail_cnt'], 1)
            self.assertEqual(history[6]['total_score'], 0)

            scores = self._scoreboard(user_session, contest_id)
            self.assertEqual(scores[5]['total_score'], 23)
            self.assertEqual(scores[5]['scores']['10']['chal_id'], acct5_ac)
            self.assertEqual(scores[5]['scores']['10']['timestamp'], '3:00')
            self.assertEqual(scores[5]['scores']['10']['fail_cnt'], 1)
            self.assertEqual(scores[6]['total_score'], 2)
            self.assertEqual(scores[6]['scores']['10']['chal_id'], acct6_ac)
            self.assertEqual(scores[6]['scores']['10']['timestamp'], '2:00')
            self.assertEqual(scores[6]['scores']['10']['fail_cnt'], 0)
