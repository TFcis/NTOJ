import asyncio
import datetime
import json
import unittest
from unittest.mock import AsyncMock, patch

import config

# test_code installs the service layer's intentionally minimal config stub.
if not hasattr(config, "BASE_URL"):
    config.BASE_URL = "/"

from handlers.contests.scoreboard import ContestScoreboardCallback
from services.chal import Compiler
from services.contest_scoreboard import (
    ContestScoreboardRevealService,
    ContestScoreboardUpdate,
)
from services.contests import (
    Contest,
    ContestMode,
    ContestService,
    ContestTimeMode,
    RegMode,
    UserStatus,
)


UTC = datetime.UTC


def make_flexible_contest(start):
    return Contest(
        contest_id=100,
        contest_creator=1,
        name="Flexible",
        contest_mode=ContestMode.IOI,
        contest_start=start - datetime.timedelta(hours=1),
        contest_end=start + datetime.timedelta(hours=6),
        contest_time_mode=ContestTimeMode.FLEXIBLE,
        contest_duration=3600,
        reg_mode=RegMode.INVITED,
        reg_end=start + datetime.timedelta(hours=6),
        allow_compilers={Compiler.GPP},
        user_list={
            1: {"status": UserStatus.ADMIN},
            2: {
                "status": UserStatus.APPROVED,
                "session_id": 20,
                "session_start": start,
                "session_end": start + datetime.timedelta(hours=1),
            },
        },
    )


class DummyConnection:
    def __init__(self, acct_id=2):
        self.acct_id = acct_id
        self.write_message = AsyncMock()


class TestContestScoreboardRevealService(unittest.IsolatedAsyncioTestCase):
    def test_update_serialization_supports_new_and_legacy_payloads(self):
        update = ContestScoreboardUpdate(
            contest_id=9,
            chal_id=12,
            elapsed=datetime.timedelta(minutes=30),
        )

        self.assertEqual(ContestScoreboardUpdate.loads(update.dumps()), update)
        self.assertEqual(
            ContestScoreboardUpdate.loads("9"),
            ContestScoreboardUpdate(contest_id=9),
        )

    async def test_build_update_uses_owner_official_session(self):
        db = AsyncMock()
        db.fetchval.return_value = datetime.timedelta(minutes=30)
        service = ContestScoreboardRevealService(db)

        update = await service.build_update(9, 12)

        self.assertEqual(update.contest_id, 9)
        self.assertEqual(update.chal_id, 12)
        self.assertEqual(update.elapsed, datetime.timedelta(minutes=30))
        query = db.fetchval.await_args.args[0]
        self.assertIn("contest_sessions", query)
        self.assertIn("challenge.timestamp < contest_sessions.end_time", query)

    async def test_next_elapsed_excludes_pending_and_out_of_window_results(self):
        db = AsyncMock()
        expected = datetime.timedelta(minutes=31)
        db.fetchval.return_value = expected
        service = ContestScoreboardRevealService(db)

        actual = await service.get_next_elapsed(
            9,
            datetime.timedelta(minutes=30),
            datetime.timedelta(hours=1),
        )

        self.assertEqual(actual, expected)
        query = db.fetchval.await_args.args[0]
        self.assertIn("MIN(challenge.timestamp - contest_sessions.start_time)", query)
        self.assertIn("total_result.state NOT IN", query)


class TestContestScoreboardCallback(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.start = datetime.datetime(2026, 8, 21, 0, tzinfo=UTC)
        self.now = self.start
        self.contest = make_flexible_contest(self.start)
        self.reveal_service = AsyncMock()
        self.reveal_service.get_next_elapsed.return_value = None
        self.contest_service = AsyncMock()
        self.contest_service.get_contest.return_value = (None, self.contest)
        self.callback = ContestScoreboardCallback(
            reveal_service_factory=lambda: self.reveal_service,
            now=lambda: self.now,
        )
        self.conn = DummyConnection()
        self.service_patch = patch.object(
            ContestService,
            "inst",
            self.contest_service,
            create=True,
        )
        self.service_patch.start()
        await self.callback.register(self.conn)

    async def asyncTearDown(self):
        await self.callback.unregister(self.conn)
        await asyncio.sleep(0)
        self.service_patch.stop()

    async def init_scoreboard(self):
        await self.callback.handle_custom_message(
            self.conn,
            "contestnewchalsub_init",
            {"contest_id": self.contest.contest_id, "purpose": "scoreboard"},
        )

    async def test_hidden_update_rearms_earlier_and_visible_update_is_immediate(self):
        self.reveal_service.get_next_elapsed.return_value = datetime.timedelta(
            minutes=30
        )
        await self.init_scoreboard()
        state = self.callback.conn_state[self.conn]
        self.assertEqual(state.scheduled_elapsed, datetime.timedelta(minutes=30))

        hidden = ContestScoreboardUpdate(
            contest_id=self.contest.contest_id,
            elapsed=datetime.timedelta(minutes=20),
        )
        self.assertIsNone(await self.callback.message(self.conn, hidden.dumps()))
        self.assertEqual(state.scheduled_elapsed, datetime.timedelta(minutes=20))

        visible = ContestScoreboardUpdate(
            contest_id=self.contest.contest_id,
            elapsed=datetime.timedelta(),
        )
        self.assertEqual(
            await self.callback.message(self.conn, visible.dumps()),
            str(self.contest.contest_id),
        )

    async def test_timer_pushes_refresh_and_schedules_the_next_reveal(self):
        first_elapsed = datetime.timedelta(milliseconds=20)
        self.reveal_service.get_next_elapsed.side_effect = [first_elapsed, None]
        await self.init_scoreboard()

        await asyncio.sleep(0.05)

        self.conn.write_message.assert_awaited_once()
        message = json.loads(self.conn.write_message.await_args.args[0])
        self.assertEqual(message, {
            "type": "contestnewchalsub",
            "data": str(self.contest.contest_id),
        })
        self.assertEqual(self.reveal_service.get_next_elapsed.await_count, 2)

    async def test_pending_participant_receives_no_scoreboard_events(self):
        self.contest.user_list[2].update(
            session_id=None,
            session_start=None,
            session_end=None,
        )
        await self.init_scoreboard()

        update = ContestScoreboardUpdate(
            contest_id=self.contest.contest_id,
            elapsed=datetime.timedelta(),
        )
        self.assertIsNone(await self.callback.message(self.conn, update.dumps()))
        self.assertFalse(self.callback.conn_state[self.conn].forward_updates)

    async def test_admin_and_challenge_list_keep_immediate_updates(self):
        admin_conn = DummyConnection(acct_id=1)
        await self.callback.register(admin_conn)
        await self.callback.handle_custom_message(
            admin_conn,
            "contestnewchalsub_init",
            {"contest_id": self.contest.contest_id, "purpose": "scoreboard"},
        )
        update = ContestScoreboardUpdate(
            contest_id=self.contest.contest_id,
            elapsed=datetime.timedelta(minutes=30),
        )
        self.assertEqual(
            await self.callback.message(admin_conn, update.dumps()),
            str(self.contest.contest_id),
        )

        list_conn = DummyConnection()
        await self.callback.register(list_conn)
        await self.callback.handle_custom_message(
            list_conn,
            "contestnewchalsub_init",
            str(self.contest.contest_id),
        )
        self.assertEqual(
            await self.callback.message(list_conn, update.dumps()),
            str(self.contest.contest_id),
        )
        await self.callback.unregister(admin_conn)
        await self.callback.unregister(list_conn)
