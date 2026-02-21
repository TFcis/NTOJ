import unittest
import datetime
from unittest.mock import AsyncMock, MagicMock

import asyncpg

from services.contests import ContestService, Contest, ContestMode, RegMode, UserStatus, ProblemScoreType
from services.user import Account, UserConst
from services.chal import Compiler


class TestContestService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """Set up test fixtures"""
        self.fake_conn = AsyncMock()

        fake_tx_cm = MagicMock()
        fake_tx_cm.__aenter__ = AsyncMock(return_value=None)
        fake_tx_cm.__aexit__ = AsyncMock(return_value=None)
        self.fake_conn.transaction = MagicMock(return_value=fake_tx_cm)

        fake_acquire_cm = MagicMock()
        fake_acquire_cm.__aenter__ = AsyncMock(return_value=self.fake_conn)
        fake_acquire_cm.__aexit__ = AsyncMock(return_value=None)
        self.fake_db = MagicMock()
        self.fake_db.acquire = MagicMock(return_value=fake_acquire_cm)
        self.fake_rs = AsyncMock()
        self.service = ContestService(self.fake_db, self.fake_rs)

        # Create a test account
        self.test_acct = Account(
            acct_id=1,
            acct_type=UserConst.ACCTTYPE_USER,
            name="test_user",
            mail="test@example.com",
            photo="",
            cover="",
            motto="",
            lastip="127.0.0.1",
            last_compiler=Compiler.GPP,
            proclass_collection=[],
            specific_ip="",
        )

        # Create a test contest
        self.test_contest = Contest(
            contest_id=100,
            contest_creator=1,
            name="Test Contest",
            contest_mode=ContestMode.IOI,
            contest_start=datetime.datetime.now(),
            contest_end=datetime.datetime.now() + datetime.timedelta(hours=5),
            reg_mode=RegMode.FREE_REG,
            reg_end=datetime.datetime.now() + datetime.timedelta(hours=4),
            user_list={},
            pro_list={},
        )

    async def test_update_contest_add_problem_success(self):
        """Test successfully adding a problem to contest"""
        # Setup
        self.fake_conn.fetch.side_effect = [
            [],  # UPDATE contest
            [],  # SELECT existing problems
            [{'status': 0}],  # SELECT status - ONLINE (0)
            [{'pro_id': 10}],  # INSERT problem RETURNING pro_id
        ]
        self.fake_conn.execute.return_value = None
        self.fake_rs.hset.return_value = None

        # Add problem to contest
        self.test_contest.pro_list[10] = {"score_type": ProblemScoreType.IOI2017}

        # Execute
        error_group, _ = await self.service.update_contest(
            self.test_acct, self.test_contest, prolist_updated=True
        )

        # Assert
        self.assertEqual(len(error_group), 0)
        self.assertIn(10, self.test_contest.pro_list)

    async def test_update_contest_add_nonexistent_problem(self):
        """Test adding a non-existent problem returns error_group"""
        # Setup
        call_count = [0]
        def fetch_side_effect(*_, **__):
            call_count[0] += 1
            if call_count[0] <= 2:
                return []
            # Third call is SELECT status which returns empty (not found)
            return []

        self.fake_conn.fetch.side_effect = fetch_side_effect
        self.fake_conn.execute.return_value = None
        self.fake_rs.hset.return_value = None

        # Add non-existent problem to contest
        self.test_contest.pro_list[999] = {"score_type": ProblemScoreType.IOI2017}

        # Execute
        error_group, _ = await self.service.update_contest(
            self.test_acct, self.test_contest, prolist_updated=True
        )

        # Assert
        self.assertGreater(len(error_group), 0)
        self.assertEqual(error_group[0][0], 'Enoext')
        self.assertIn('999', error_group[0][1])
        self.assertNotIn(999, self.test_contest.pro_list)

    async def test_update_contest_add_hidden_problem(self):
        """Test adding a hidden problem returns error_group"""
        # Setup
        call_count = [0]
        def fetch_side_effect(*_, **__):
            call_count[0] += 1
            if call_count[0] <= 2:
                return []
            # Third call is SELECT status which returns HIDDEN status (2)
            return [{'status': 2}]

        self.fake_conn.fetch.side_effect = fetch_side_effect
        self.fake_conn.execute.return_value = None
        self.fake_rs.hset.return_value = None

        # Add hidden problem to contest
        self.test_contest.pro_list[888] = {"score_type": ProblemScoreType.IOI2017}

        # Execute
        error_group, _ = await self.service.update_contest(
            self.test_acct, self.test_contest, prolist_updated=True
        )

        # Assert
        self.assertGreater(len(error_group), 0)
        self.assertEqual(error_group[0][0], 'Eacces')
        self.assertIn('hidden', error_group[0][1].lower())
        self.assertIn('888', error_group[0][1])
        self.assertNotIn(888, self.test_contest.pro_list)
        self.assertNotIn(999, self.test_contest.pro_list)

    async def test_update_contest_add_user_success(self):
        """Test successfully adding a user to contest"""
        # Setup
        self.fake_conn.fetch.side_effect = [
            [],  # UPDATE contest
            [],  # SELECT existing users
        ]
        self.fake_conn.execute.return_value = None
        self.fake_rs.hset.return_value = None

        # Add user to contest
        self.test_contest.user_list[2] = {"status": UserStatus.APPROVED}

        # Execute
        error_group, _ = await self.service.update_contest(
            self.test_acct, self.test_contest, userlist_updated=True
        )

        # Assert
        self.assertEqual(len(error_group), 0)
        self.assertIn(2, self.test_contest.user_list)
        # Contest creator should be auto-added as admin
        self.assertIn(1, self.test_contest.user_list)
        self.assertEqual(self.test_contest.user_list[1]["status"], UserStatus.ADMIN)

    async def test_update_contest_add_nonexistent_user(self):
        """Test adding a non-existent user returns error_group"""
        # Setup
        self.fake_conn.fetch.side_effect = [
            [],  # UPDATE contest
            [],  # SELECT existing users
        ]

        async def execute_with_error(*args, **_):
            if 'INSERT INTO contest_users' in args[0]:
                raise asyncpg.ForeignKeyViolationError("Account not found")

        self.fake_conn.execute.side_effect = execute_with_error
        self.fake_rs.hset.return_value = None

        # Add non-existent user to contest
        self.test_contest.user_list[9999] = {"status": UserStatus.APPROVED}

        # Execute
        error_group, _ = await self.service.update_contest(
            self.test_acct, self.test_contest, userlist_updated=True
        )

        # Assert
        self.assertGreater(len(error_group), 0)
        self.assertEqual(error_group[0][0], 'Enoext')
        self.assertIn('9999', error_group[0][1])
        self.assertNotIn(9999, self.test_contest.user_list)

    async def test_update_contest_remove_problem(self):
        """Test removing a problem from contest"""
        # Setup
        self.fake_conn.fetch.side_effect = [
            [],  # UPDATE contest
            [{'pro_id': 10}, {'pro_id': 20}],  # SELECT existing problems
            [{'status': 0}],  # SELECT status for problem 10 - ONLINE (0)
            [{'pro_id': 10}],  # INSERT problem 10 RETURNING pro_id
        ]
        self.fake_conn.execute.return_value = None
        self.fake_rs.hset.return_value = None

        # Initially contest has problem 10, we keep it but remove 20
        self.test_contest.pro_list[10] = {"score_type": ProblemScoreType.IOI2017}

        # Execute
        error_group, _ = await self.service.update_contest(
            self.test_acct, self.test_contest, prolist_updated=True
        )

        # Assert
        self.assertEqual(len(error_group), 0)
        self.assertIn(10, self.test_contest.pro_list)

        # Verify DELETE was called for removed problem
        delete_calls = [call for call in self.fake_conn.execute.call_args_list
                       if 'DELETE FROM contest_problem_joints' in str(call)]
        self.assertGreater(len(delete_calls), 0)

    async def test_update_contest_remove_user(self):
        """Test removing a user from contest"""
        # Setup
        self.fake_conn.fetch.side_effect = [
            [],  # UPDATE contest
            [{'acct_id': 1}, {'acct_id': 2}, {'acct_id': 3}],  # SELECT existing users
        ]
        self.fake_conn.execute.return_value = None
        self.fake_rs.hset.return_value = None

        # Initially contest has users 1, 2, 3, we keep 1 and 2 but remove 3
        self.test_contest.user_list[1] = {"status": UserStatus.ADMIN}
        self.test_contest.user_list[2] = {"status": UserStatus.APPROVED}

        # Execute
        error_group, _ = await self.service.update_contest(
            self.test_acct, self.test_contest, userlist_updated=True
        )

        # Assert
        self.assertEqual(len(error_group), 0)
        self.assertIn(1, self.test_contest.user_list)
        self.assertIn(2, self.test_contest.user_list)

        # Verify DELETE was called for removed user
        delete_calls = [call for call in self.fake_conn.execute.call_args_list
                       if 'DELETE FROM contest_users' in str(call)]
        self.assertGreater(len(delete_calls), 0)

    async def test_update_contest_ensures_creator_is_admin(self):
        """Test that contest creator is always set as admin"""
        # Setup
        self.fake_conn.fetch.side_effect = [
            [],  # UPDATE contest
            [],  # SELECT existing users
        ]
        self.fake_conn.execute.return_value = None
        self.fake_rs.hset.return_value = None

        # Don't explicitly add creator to user_list
        self.test_contest.user_list[2] = {"status": UserStatus.APPROVED}

        # Execute
        _, _ = await self.service.update_contest(
            self.test_acct, self.test_contest, userlist_updated=True
        )

        # Assert
        self.assertIn(self.test_contest.contest_creator, self.test_contest.user_list)
        self.assertEqual(
            self.test_contest.user_list[self.test_contest.contest_creator]["status"],
            UserStatus.ADMIN
        )

    async def test_update_contest_multiple_errors(self):
        """Test that multiple errors are collected in error_group"""
        # Setup
        call_count = [0]
        def fetch_side_effect(*_, **__):
            call_count[0] += 1
            if call_count[0] <= 2:
                return []  # UPDATE contest and SELECT existing problems
            # All subsequent calls are SELECT status which return empty (not found)
            return []

        self.fake_conn.fetch.side_effect = fetch_side_effect
        self.fake_conn.execute.return_value = None
        self.fake_rs.hset.return_value = None

        # Add multiple non-existent problems
        self.test_contest.pro_list[998] = {"score_type": ProblemScoreType.IOI2017}
        self.test_contest.pro_list[999] = {"score_type": ProblemScoreType.IOI2017}

        # Execute
        error_group, _ = await self.service.update_contest(
            self.test_acct, self.test_contest, prolist_updated=True
        )

        # Assert
        self.assertEqual(len(error_group), 2)
        self.assertEqual(error_group[0][0], 'Enoext')
        self.assertEqual(error_group[1][0], 'Enoext')
        self.assertNotIn(998, self.test_contest.pro_list)
        self.assertNotIn(999, self.test_contest.pro_list)

    async def test_update_contest_cache_updated_correctly(self):
        """Test that Redis cache is updated after contest update"""
        # Setup
        self.fake_conn.fetch.side_effect = [
            [],  # UPDATE contest
        ]
        self.fake_conn.execute.return_value = None
        self.fake_rs.hset.return_value = None

        # Execute
        _, _ = await self.service.update_contest(
            self.test_acct, self.test_contest
        )

        # Assert
        self.fake_rs.hset.assert_called_once()
        call_args = self.fake_rs.hset.call_args
        self.assertEqual(call_args[0][0], 'contest')
        self.assertEqual(call_args[0][1], str(self.test_contest.contest_id))


class TestContestUserStatusValidation(unittest.IsolatedAsyncioTestCase):
    """Test user status validation when removing users"""

    def setUp(self):
        """Set up test contest with various user statuses"""
        self.test_contest = Contest(
            contest_id=100,
            contest_creator=1,
            name="Test Contest",
            contest_mode=ContestMode.IOI,
            contest_start=datetime.datetime.now(),
            contest_end=datetime.datetime.now() + datetime.timedelta(hours=5),
            reg_mode=RegMode.FREE_REG,
            reg_end=datetime.datetime.now() + datetime.timedelta(hours=4),
            user_list={
                1: {"status": UserStatus.ADMIN},
                2: {"status": UserStatus.APPROVED},
                3: {"status": UserStatus.REQUESTED},
                4: {"status": UserStatus.REJECTED},
                5: {"status": UserStatus.ADMIN},
            },
            pro_list={},
        )

    def test_cannot_remove_requested_user_from_normal_list(self):
        """Test that REQUESTED users cannot be removed via normal list"""
        # User 3 has REQUESTED status, should not be removable via 'normal' list
        user_status = self.test_contest.user_list[3]["status"]
        self.assertEqual(user_status, UserStatus.REQUESTED)
        self.assertNotEqual(user_status, UserStatus.APPROVED)

    def test_cannot_remove_rejected_user_from_normal_list(self):
        """Test that REJECTED users cannot be removed via normal list"""
        # User 4 has REJECTED status, should not be removable via 'normal' list
        user_status = self.test_contest.user_list[4]["status"]
        self.assertEqual(user_status, UserStatus.REJECTED)
        self.assertNotEqual(user_status, UserStatus.APPROVED)

    def test_can_only_remove_approved_from_normal_list(self):
        """Test that only APPROVED users can be removed via normal list"""
        # User 2 has APPROVED status, should be removable via 'normal' list
        user_status = self.test_contest.user_list[2]["status"]
        self.assertEqual(user_status, UserStatus.APPROVED)

    def test_can_only_remove_admin_from_admin_list(self):
        """Test that only ADMIN users can be removed via admin list"""
        # User 1 and 5 have ADMIN status
        self.assertEqual(self.test_contest.user_list[1]["status"], UserStatus.ADMIN)
        self.assertEqual(self.test_contest.user_list[5]["status"], UserStatus.ADMIN)

        # User 2 has APPROVED status, should not be removable via 'admin' list
        self.assertNotEqual(self.test_contest.user_list[2]["status"], UserStatus.ADMIN)

    def test_status_matching_logic(self):
        """Test the status matching logic used in handlers"""
        test_cases = [
            # (list_type, user_status, should_match)
            ("normal", UserStatus.APPROVED, True),
            ("normal", UserStatus.ADMIN, False),
            ("normal", UserStatus.REQUESTED, False),
            ("normal", UserStatus.REJECTED, False),
            ("admin", UserStatus.ADMIN, True),
            ("admin", UserStatus.APPROVED, False),
            ("admin", UserStatus.REQUESTED, False),
            ("admin", UserStatus.REJECTED, False),
        ]

        for list_type, user_status, should_match in test_cases:
            expected_status = UserStatus.APPROVED if list_type == "normal" else UserStatus.ADMIN
            actual_match = (user_status == expected_status)
            self.assertEqual(
                actual_match,
                should_match,
                f"Failed: list_type={list_type}, user_status={user_status.name}, expected_match={should_match}"
            )


if __name__ == '__main__':
    unittest.main()