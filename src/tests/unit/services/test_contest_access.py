import datetime
import unittest
from unittest.mock import AsyncMock

from services.chal import Compiler
from services.contest_access import ContestAccess, ContestPermission
from services.contest_session import ContestPhase, ContestSession
from services.contests import Contest, ContestMode, ContestService, RegMode, UserStatus
from services.user import Account, UserConst

UTC = datetime.UTC


def make_account(acct_id: int) -> Account:
    return Account(
        acct_id=acct_id,
        acct_type=UserConst.ACCTTYPE_USER,
        name=f"user-{acct_id}",
        mail=f"user-{acct_id}@example.com",
        photo="",
        cover="",
        motto="",
        lastip="127.0.0.1",
        last_compiler=Compiler.GPP,
        proclass_collection=[],
        specific_ip="",
    )


def make_contest(*, public_scoreboard: bool = False) -> Contest:
    start = datetime.datetime(2026, 8, 20, 1, tzinfo=UTC)
    return Contest(
        contest_id=100,
        contest_creator=1,
        name="Test Contest",
        contest_mode=ContestMode.IOI,
        contest_start=start,
        contest_end=start + datetime.timedelta(hours=5),
        reg_mode=RegMode.FREE_REG,
        reg_end=start,
        user_list={
            1: {"status": UserStatus.ADMIN},
            2: {"status": UserStatus.APPROVED},
        },
        pro_list={},
        is_public_scoreboard=public_scoreboard,
    )


class TestContestSession(unittest.TestCase):
    def test_fixed_session_uses_contest_window(self):
        contest = make_contest()
        session = ContestSession.fixed(contest, acct_id=2)

        self.assertEqual(session.contest_id, contest.contest_id)
        self.assertEqual(session.acct_id, 2)
        self.assertEqual(session.start_time, contest.contest_start)
        self.assertEqual(session.end_time, contest.contest_end)
        self.assertEqual(session.duration, datetime.timedelta(hours=5))

    def test_phase_boundaries_match_existing_contest_semantics(self):
        session = ContestSession.fixed(make_contest(), acct_id=2)

        self.assertIs(
            session.phase(session.start_time - datetime.timedelta(microseconds=1)),
            ContestPhase.BEFORE,
        )
        self.assertIs(session.phase(session.start_time), ContestPhase.RUNNING)
        self.assertIs(
            session.phase(session.end_time - datetime.timedelta(microseconds=1)),
            ContestPhase.RUNNING,
        )
        self.assertIs(session.phase(session.end_time), ContestPhase.ENDED)


class TestContestAccess(unittest.TestCase):
    def test_roles_preserve_member_and_participant_distinction(self):
        contest = make_contest()
        now = contest.contest_start + datetime.timedelta(hours=1)

        admin = ContestAccess.resolve(contest, make_account(1), now)
        participant = ContestAccess.resolve(contest, make_account(2), now)
        outsider = ContestAccess.resolve(contest, make_account(3), now)

        self.assertTrue(admin.has(ContestPermission.ADMIN | ContestPermission.MEMBER))
        self.assertFalse(admin.has(ContestPermission.PARTICIPANT))
        self.assertTrue(
            participant.has(ContestPermission.PARTICIPANT | ContestPermission.MEMBER)
        )
        self.assertFalse(participant.has(ContestPermission.ADMIN))
        self.assertFalse(outsider.has(ContestPermission.MEMBER))

    def test_problem_access_matches_fixed_contest_rules(self):
        contest = make_contest()
        admin = make_account(1)
        participant = make_account(2)
        outsider = make_account(3)

        before = contest.contest_start - datetime.timedelta(seconds=1)
        running = contest.contest_start
        ended = contest.contest_end

        self.assertTrue(
            ContestAccess.resolve(contest, admin, before).has(
                ContestPermission.VIEW_PROBLEM_SET | ContestPermission.VIEW_PROBLEM
            )
        )
        self.assertFalse(
            ContestAccess.resolve(contest, participant, before).has(
                ContestPermission.VIEW_PROBLEM_SET | ContestPermission.VIEW_PROBLEM
            )
        )
        self.assertTrue(
            ContestAccess.resolve(contest, participant, running).has(
                ContestPermission.VIEW_PROBLEM_SET
                | ContestPermission.VIEW_PROBLEM
                | ContestPermission.SUBMIT
            )
        )
        self.assertFalse(
            ContestAccess.resolve(contest, outsider, running).has(
                ContestPermission.VIEW_PROBLEM_SET
            )
        )
        self.assertTrue(
            ContestAccess.resolve(contest, outsider, ended).has(
                ContestPermission.VIEW_PROBLEM_SET
            )
        )
        self.assertFalse(
            ContestAccess.resolve(contest, participant, ended).has(
                ContestPermission.VIEW_PROBLEM
            )
        )

    def test_scoreboard_access_respects_start_visibility_and_membership(self):
        private_contest = make_contest()
        public_contest = make_contest(public_scoreboard=True)
        participant = make_account(2)
        outsider = make_account(3)
        before = private_contest.contest_start - datetime.timedelta(seconds=1)
        running = private_contest.contest_start

        self.assertFalse(
            ContestAccess.resolve(public_contest, outsider, before).has(
                ContestPermission.VIEW_SCOREBOARD
            )
        )
        self.assertTrue(
            ContestAccess.resolve(private_contest, participant, running).has(
                ContestPermission.VIEW_SCOREBOARD
            )
        )
        self.assertFalse(
            ContestAccess.resolve(private_contest, outsider, running).has(
                ContestPermission.VIEW_SCOREBOARD
            )
        )
        self.assertTrue(
            ContestAccess.resolve(public_contest, outsider, running).has(
                ContestPermission.VIEW_SCOREBOARD
            )
        )

    def test_creator_without_membership_keeps_existing_edge_case(self):
        contest = make_contest()
        contest.user_list.pop(contest.contest_creator)
        access = ContestAccess.resolve(contest, make_account(1), contest.contest_start)

        self.assertTrue(access.is_admin)
        self.assertFalse(access.is_member)
        self.assertFalse(access.has(ContestPermission.SUBMIT))
        self.assertFalse(access.has(ContestPermission.VIEW_SCOREBOARD))

    def test_challenge_visibility_preserves_phase_and_hide_admin_rules(self):
        contest = make_contest(public_scoreboard=True)
        participant = make_account(2)
        other_participant_id = 4
        contest.user_list[other_participant_id] = {"status": UserStatus.APPROVED}

        before = contest.contest_start - datetime.timedelta(seconds=1)
        running = contest.contest_start
        ended = contest.contest_end

        before_access = ContestAccess.resolve(contest, participant, before)
        self.assertTrue(before_access.can_view_challenge(other_participant_id))
        self.assertFalse(before_access.can_view_challenge(contest.contest_creator))

        running_access = ContestAccess.resolve(contest, participant, running)
        self.assertTrue(running_access.can_view_challenge(other_participant_id))
        self.assertFalse(running_access.can_view_challenge(contest.contest_creator))
        contest.hide_admin = False
        running_access = ContestAccess.resolve(contest, participant, running)
        self.assertFalse(running_access.can_view_challenge(other_participant_id))
        self.assertTrue(running_access.can_view_challenge(participant.acct_id))

        ended_access = ContestAccess.resolve(contest, participant, ended)
        self.assertTrue(ended_access.can_view_challenge(other_participant_id))
        contest.is_public_scoreboard = False
        ended_access = ContestAccess.resolve(contest, participant, ended)
        self.assertFalse(ended_access.can_view_challenge(other_participant_id))
        self.assertTrue(ended_access.can_view_challenge(participant.acct_id))

    def test_challenge_list_visibility_matches_existing_filters(self):
        contest = make_contest(public_scoreboard=True)
        contest.user_list[4] = {"status": UserStatus.APPROVED}
        participant = make_account(2)

        before = ContestAccess.resolve(
            contest,
            participant,
            contest.contest_start - datetime.timedelta(seconds=1),
        )
        running = ContestAccess.resolve(contest, participant, contest.contest_start)
        ended = ContestAccess.resolve(contest, participant, contest.contest_end)

        self.assertEqual(before.visible_challenge_accounts(None), [])
        self.assertEqual(
            running.visible_challenge_accounts(None), [participant.acct_id]
        )
        self.assertEqual(ended.visible_challenge_accounts(None), [2, 4])
        self.assertEqual(ended.visible_challenge_accounts([1, 2, 4]), [2, 4])


class TestContestScoreSession(unittest.IsolatedAsyncioTestCase):
    async def test_icpc_score_uses_effective_session_start(self):
        contest = make_contest()
        db = AsyncMock()
        db.fetch.return_value = []
        service = ContestService(db, AsyncMock())
        service.get_contest = AsyncMock(return_value=(None, contest))
        session = ContestSession(
            contest_id=contest.contest_id,
            acct_id=2,
            start_time=contest.contest_start + datetime.timedelta(minutes=30),
            end_time=contest.contest_end,
        )

        await service.get_icpc_scores(
            contest.contest_id,
            10,
            session.end_time,
            session,
        )

        self.assertEqual(db.fetch.await_args.args[6], session.start_time)


if __name__ == "__main__":
    unittest.main()
