import datetime
import enum
from dataclasses import dataclass, field
import pickle

import asyncpg

from services.chal import Compiler, ChalConst
from services.contest_session import (
    ContestScoreboardContext,
    ContestSession,
    ContestSessionType,
)
from services.user import Account


class RegMode(enum.IntEnum):
    INVITED = 0
    FREE_REG = 1
    REG_APPROVAL = 2


class ContestMode(enum.IntEnum):
    IOI = 0
    ACM = 1 # NOTE: ACM/ICPC


class ContestTimeMode(enum.IntEnum):
    FIXED = 0
    FLEXIBLE = 1

class ProblemScoreType(enum.IntEnum):
    IOI2013 = 0
    IOI2017 = 1
    ICPC = 2 # NOTE: ContestMode.ACM

class ChallengeResultStyle(enum.IntEnum):
    FULL = 1  # Total + Subtask + Testcase
    STATE_COUNT = 2  # Total + Subtask + Testcase State Count
    SUBTASK_ONLY = 3  # Total + Subtask
    TOTAL_ONLY = 4  # Total Only

class UserStatus(enum.IntEnum):
    REJECTED = 0
    REQUESTED = 1
    APPROVED = 2
    ADMIN = 3

class ContestConst:
    NAME_MIN = 1
    NAME_MAX = 50


_SCORE_ACCOUNT_WINDOWS_CTE = """
account_windows AS (
    SELECT
        cu.acct_id,
        CASE
            WHEN ($8::boolean OR c.contest_time_mode = $5) AND cu.status = $6
                THEN cs.start_time
            ELSE c.contest_start
        END AS start_time,
        CASE
            WHEN ($8::boolean OR c.contest_time_mode = $5) AND cu.status = $6
                THEN cs.end_time
            ELSE c.contest_end
        END AS end_time
    FROM contest_users AS cu
    INNER JOIN contest AS c ON c.contest_id = cu.contest_id
    LEFT JOIN contest_sessions AS cs
      ON cs.contest_id = cu.contest_id
     AND cs.acct_id = cu.acct_id
     AND cs.session_type = $4
    WHERE cu.contest_id = $1
      AND cu.status IN ($6, $7)
      AND (
          (NOT $8::boolean AND c.contest_time_mode != $5)
          OR cu.status = $7
          OR cs.session_id IS NOT NULL
      )
)
"""

@dataclass(slots=True, kw_only=True)
class Contest:
    contest_id: int
    contest_creator: int
    name: str
    desc_before_contest: str = ''
    desc_during_contest: str = ''
    desc_after_contest: str = ''

    # contest_status: bool
    contest_mode: ContestMode
    contest_start: datetime.datetime
    contest_end: datetime.datetime
    contest_time_mode: ContestTimeMode = ContestTimeMode.FIXED
    contest_duration: int = 0

    user_list: dict[int, dict] = field(default_factory=dict)
    pro_list: dict[int, dict] = field(default_factory=dict)

    reg_mode: RegMode
    reg_end: datetime.datetime

    allow_compilers: set[Compiler] = field(default_factory=set)
    is_public_scoreboard: bool = False
    allow_view_other_page: bool = False  # TODO: finish allow view other page
    hide_admin: bool = True
    submission_cd_time: int = 30
    freeze_scoreboard_period: int = 0
    penalty_value: int = 20
    enable_system_test: bool = False  # Enable system test feature (pretest/final test)

    def is_start(self) -> bool:
        return self.configured_session().is_started()

    def is_end(self) -> bool:
        return self.configured_session().is_ended()

    def is_running(self) -> bool:
        return self.configured_session().is_running()

    def configured_session(self) -> ContestSession:
        """Return the global availability window, not an account session."""
        return ContestSession.fixed(self)

    def is_pro(self, pro_id: int) -> bool:
        return pro_id in self.pro_list

    def is_admin(self, acct: Account | None = None, acct_id: int | None = None) -> bool:
        if acct is not None:
            return acct.acct_id == self.contest_creator \
                or (acct.acct_id in self.user_list and self.user_list[acct.acct_id]['status'] == UserStatus.ADMIN)

        if acct_id is not None:
            return acct_id == self.contest_creator \
                    or (acct_id in self.user_list and self.user_list[acct_id]['status'] == UserStatus.ADMIN)

        assert acct is not None and acct_id is not None, 'one of args(acct or acct_id) must not None'

    def is_member(self, acct: Account | None = None, acct_id: int | None = None) -> bool:
        if acct is not None:
            return acct.acct_id in self.user_list and self.user_list[acct.acct_id]['status'] in (UserStatus.APPROVED, UserStatus.ADMIN)

        if acct_id is not None:
            return acct_id in self.user_list and self.user_list[acct_id]['status'] in (UserStatus.APPROVED, UserStatus.ADMIN)

        assert acct is not None and acct_id is not None, 'one of args(acct or acct_id) must not None'

    def member_is_status(self, acct: Account | int, status: UserStatus) -> bool:
        acct_id = None
        if isinstance(acct, Account):
            acct_id = acct.acct_id
            if acct.acct_id not in self.user_list:
                return False

        elif isinstance(acct, int):
            acct_id = acct
            if acct not in self.user_list:
                return False

        return self.user_list[acct_id]['status'] == status

class ContestService:
    def __init__(self, db, rs):
        self.db = db
        self.rs = rs

        ContestService.inst = self

    async def invalidate_scoreboard_cache(
        self, contest_id: int, pro_id: int | None = None
    ) -> None:
        """Invalidate every registered session type's scoreboard namespace."""
        for session_type in ContestSessionType:
            context = ContestScoreboardContext(
                session_type=session_type,
                use_stored_sessions=session_type is not ContestSessionType.OFFICIAL,
            )
            cache_name = context.cache_name(contest_id)
            if pro_id is None:
                await self.rs.delete(cache_name)
            else:
                await self.rs.hdel(cache_name, str(pro_id))

    async def get_contest(self, contest_id: int):
        if (b_contest := await self.rs.hget('contest', str(contest_id))) is not None:
            contest: Contest = pickle.loads(b_contest)

            contest_session = contest.configured_session()
            if contest_session.is_ended():
                await self.rs.hdel('contest', str(contest_id))

        else:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    '''
                        SELECT "contest_id", "contest_creator",
                        "name",

                        "desc_before_contest",
                        "desc_during_contest",
                        "desc_after_contest",

                        "contest_mode", "contest_start", "contest_end",
                        "contest_time_mode", "contest_duration",
                        "reg_mode", "reg_end",

                        "allow_compilers",
                        "is_public_scoreboard",
                        "allow_view_other_page",
                        "hide_admin",
                        "submission_cd_time",
                        "freeze_scoreboard_period",
                        "penalty_value",
                        "enable_system_test"
                        FROM "contest" WHERE "contest_id" = $1;
                    ''',
                    contest_id
                )

                if len(result) != 1:
                    return ('Enoext', 'Contest not found'), None

                result = result[0]

                contest = Contest(**result)
                contest.reg_mode = RegMode(contest.reg_mode)
                contest.contest_mode = ContestMode(contest.contest_mode)
                contest.contest_time_mode = ContestTimeMode(contest.contest_time_mode)
                contest.contest_start = contest.contest_start
                contest.contest_end = contest.contest_end
                contest.reg_end = contest.reg_end

                result = await con.fetch('SELECT pro_id, score_type, challenge_style FROM contest_problem_joints WHERE contest_id = $1 ORDER BY "order";', contest_id)
                for pro_id, score_type, challenge_style in result:
                    contest.pro_list[pro_id] = {
                        "score_type": ProblemScoreType(int(score_type)),
                        "challenge_style": ChallengeResultStyle(int(challenge_style))
                    }

                result = await con.fetch('''
                    SELECT cu.acct_id, cu.status,
                           cs.session_id, cs.start_time, cs.end_time
                    FROM contest_users AS cu
                    LEFT JOIN contest_sessions AS cs
                      ON cs.contest_id = cu.contest_id
                     AND cs.acct_id = cu.acct_id
                     AND cs.session_type = $2
                    WHERE cu.contest_id = $1
                    ORDER BY cu.acct_id
                ''', contest_id, int(ContestSessionType.OFFICIAL))
                for acct_id, status, session_id, session_start, session_end in result:
                    contest.user_list[acct_id] = {
                        "status": UserStatus(int(status)),
                        "session_id": session_id,
                        "session_start": session_start,
                        "session_end": session_end,
                    }

            if contest.configured_session().is_running():
                b_contest = pickle.dumps(contest)
                await self.rs.hset('contest', str(contest_id), b_contest)

        return None, contest

    async def get_contest_list(self):
        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    SELECT
                    "contest_id", "name",
                    "contest_mode", "contest_start", "contest_end",
                    "contest_time_mode", "contest_duration",
                    "is_public_scoreboard"
                    FROM "contest" ORDER BY "contest_id" ASC;
                ''',
            )

            contest_list = [
                {
                    "contest_id": contest_id,
                    "name": name,
                    "contest_mode": contest_mode,
                    "contest_start": contest_start,
                    "contest_end": contest_end,
                    "contest_time_mode": ContestTimeMode(contest_time_mode),
                    "contest_duration": contest_duration,
                    "is_public_scoreboard": is_public_scoreboard
                } for contest_id, name, contest_mode, contest_start, contest_end,
                      contest_time_mode, contest_duration, is_public_scoreboard in result
            ]

        return None, contest_list

    async def add_default_contest(self, acct: Account, contest_name: str):
        try:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    '''
                        INSERT INTO "contest" ("name", "contest_creator") VALUES($1, $2) RETURNING "contest_id";
                    ''',
                    contest_name,
                    acct.acct_id,
                )
                await con.execute('INSERT INTO contest_users ("contest_id", "acct_id", "status") VALUES ($1, $2, $3);',
                                  result[0]['contest_id'], acct.acct_id, UserStatus.ADMIN)

        except asyncpg.IntegrityConstraintViolationError:
            return ('Eexist', 'Contest already exists'), None

        if len(result) != 1:
            return ('Eexist', 'Contest already exists'), None

        contest_id = result[0]['contest_id']

        _, contest = await self.get_contest(contest_id)

        b_contest = pickle.dumps(contest)

        await self.rs.hset('contest', f'{contest_id}', b_contest)

        return None, contest_id

    async def start_official_session(self, contest: Contest, acct: Account):
        """Atomically start a flexible contest session for an approved account."""
        if contest.contest_time_mode is not ContestTimeMode.FLEXIBLE:
            return ("Eparam", "This contest does not use flexible time"), None
        if not contest.member_is_status(acct, UserStatus.APPROVED):
            return ("Eacces", "Only approved contestants can start this contest"), None

        row = await self.db.fetchrow(
            """
            WITH clock AS (
                SELECT CURRENT_TIMESTAMP AS now
            )
            INSERT INTO contest_sessions (
                contest_id, acct_id, session_type, start_time, end_time
            )
            SELECT
                c.contest_id,
                $2,
                $3,
                clock.now,
                LEAST(
                    clock.now + c.contest_duration * INTERVAL '1 second',
                    c.contest_end
                )
            FROM contest AS c
            CROSS JOIN clock
            INNER JOIN contest_users AS cu
                ON cu.contest_id = c.contest_id
               AND cu.acct_id = $2
               AND cu.status = $4
            WHERE c.contest_id = $1
              AND c.contest_time_mode = $5
              AND c.contest_duration > 0
              AND c.contest_start <= clock.now
              AND clock.now < c.contest_end
            ON CONFLICT (contest_id, acct_id, session_type) DO NOTHING
            RETURNING session_id, start_time, end_time
            """,
            contest.contest_id,
            acct.acct_id,
            int(ContestSessionType.OFFICIAL),
            int(UserStatus.APPROVED),
            int(ContestTimeMode.FLEXIBLE),
        )

        if row is None:
            row = await self.db.fetchrow(
                """
                SELECT session_id, start_time, end_time
                FROM contest_sessions
                WHERE contest_id = $1 AND acct_id = $2 AND session_type = $3
                """,
                contest.contest_id,
                acct.acct_id,
                int(ContestSessionType.OFFICIAL),
            )
            if row is None:
                return ("Etime", "Contest cannot be started at this time"), None

        session = ContestSession(
            contest_id=contest.contest_id,
            acct_id=acct.acct_id,
            session_id=row["session_id"],
            session_type=ContestSessionType.OFFICIAL,
            start_time=row["start_time"],
            end_time=row["end_time"],
        )
        await self.rs.hdel("contest", str(contest.contest_id))
        await self.invalidate_scoreboard_cache(contest.contest_id)
        return None, session

    async def update_contest(self, acct: Account, contest: Contest, prolist_updated=False, userlist_updated=False):
        from services.pro import ProConst
        error_group = []

        # update db
        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    UPDATE "contest"
                    SET
                    "name" = $1,
                    "desc_before_contest" = $2,
                    "desc_during_contest" = $3,
                    "desc_after_contest" = $4,
                    "contest_mode" = $5, "contest_start" = $6, "contest_end" = $7,
                    "contest_time_mode" = $8, "contest_duration" = $9,
                    "reg_mode" = $10, "reg_end" = $11,
                    "allow_compilers" = $12,
                    "is_public_scoreboard" = $13,
                    "allow_view_other_page" = $14,
                    "hide_admin" = $15,
                    "submission_cd_time" = $16,
                    "freeze_scoreboard_period" = $17,
                    "penalty_value" = $18,
                    "enable_system_test" = $19
                    WHERE "contest_id" = $20;
                ''',
                contest.name,
                contest.desc_before_contest,
                contest.desc_during_contest,
                contest.desc_after_contest,

                contest.contest_mode, contest.contest_start, contest.contest_end,
                contest.contest_time_mode, contest.contest_duration,
                contest.reg_mode, contest.reg_end,

                contest.allow_compilers,
                contest.is_public_scoreboard,
                contest.allow_view_other_page,
                contest.hide_admin,
                contest.submission_cd_time,
                contest.freeze_scoreboard_period,
                contest.penalty_value,
                contest.enable_system_test,
                contest.contest_id
            )

            if prolist_updated:
                # Get existing problems to track operations
                existing_pros = await con.fetch(
                    'SELECT pro_id FROM contest_problem_joints WHERE contest_id = $1',
                    contest.contest_id
                )
                existing_pro_ids = {row['pro_id'] for row in existing_pros}

                order = 0
                current_pro_ids = set()

                for pro_id, v in list(contest.pro_list.items()):
                    pro_status_result = await con.fetch(
                        'SELECT status FROM problem WHERE pro_id = $1',
                        pro_id
                    )

                    if len(pro_status_result) == 0:
                        error_group.append(('Enoext', f'Problem {pro_id} not found'))
                        contest.pro_list.pop(pro_id)
                        continue

                    pro_status = pro_status_result[0]['status']
                    # STATUS_HIDDEN = 2, cannot be added to contest
                    if pro_status == ProConst.STATUS_HIDDEN:
                        error_group.append(('Eacces', f'Cannot add hidden status problem {pro_id}'))
                        contest.pro_list.pop(pro_id)
                        continue

                    challenge_style = v.get('challenge_style', ChallengeResultStyle.FULL)
                    result = await con.fetch('''
                        INSERT INTO contest_problem_joints ("contest_id", "pro_id", "score_type", "challenge_style", "order")
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (contest_id, pro_id) DO UPDATE
                        SET score_type = EXCLUDED.score_type, challenge_style = EXCLUDED.challenge_style, "order" = EXCLUDED."order"
                        WHERE
                            contest_problem_joints.score_type != EXCLUDED.score_type OR
                            contest_problem_joints.challenge_style != EXCLUDED.challenge_style OR
                            contest_problem_joints.order != EXCLUDED.order
                        RETURNING pro_id;
                    ''', contest.contest_id, pro_id, int(v['score_type']), int(challenge_style), order)

                    current_pro_ids.add(pro_id)
                    order += 1

                removed_pros = existing_pro_ids - current_pro_ids
                if removed_pros:
                    await con.execute(
                        'DELETE FROM contest_problem_joints WHERE contest_id = $1 AND pro_id = ANY($2)',
                        contest.contest_id, list(removed_pros)
                    )

            if userlist_updated:
                # Ensure contest creator is always admin
                contest.user_list[contest.contest_creator] = {
                    "status": UserStatus.ADMIN
                }

                # Get existing users to track operations
                existing_users = await con.fetch(
                    'SELECT acct_id FROM contest_users WHERE contest_id = $1',
                    contest.contest_id
                )
                existing_acct_ids = {row['acct_id'] for row in existing_users}

                current_acct_ids = set()

                for acct_id, v in list(contest.user_list.items()):
                    try:
                        await con.execute('''
                            INSERT INTO contest_users (contest_id, acct_id, status)
                            VALUES ($1, $2, $3)
                            ON CONFLICT (contest_id, acct_id) DO UPDATE
                            SET status = EXCLUDED.status
                            WHERE contest_users.status != EXCLUDED.status;
                        ''', contest.contest_id, acct_id, int(v['status']))

                        current_acct_ids.add(acct_id)
                    except asyncpg.ForeignKeyViolationError:
                        error_group.append(('Enoext', f'Account {acct_id} not found'))
                        contest.user_list.pop(acct_id)
                        continue

                # Remove users that are no longer in the list
                removed_users = existing_acct_ids - current_acct_ids
                if removed_users:
                    await con.execute(
                        'DELETE FROM contest_users WHERE contest_id = $1 AND acct_id = ANY($2)',
                        contest.contest_id, list(removed_users)
                    )

        b_contest = pickle.dumps(contest)
        await self.rs.hset('contest', str(contest.contest_id), b_contest)

        # log

        return error_group, None

    async def add_announce(self, contest_id: int, acct_id: int, subject: str, content: str):
        res = await self.db.fetch('INSERT INTO contest_announcement ("contest_id", "acct_id", "subject", "content", "timestamp") VALUES ($1, $2, $3, $4, NOW()) RETURNING announce_id',
                                  contest_id, acct_id, subject, content)

        if len(res) != 1:
            return ('Eunk', 'Unknown error'), None

        return None, res[0]['announce_id']

    async def edit_announce(self, contest_id: int, announce_id: int, subject: str, content: str):
        await self.db.execute('UPDATE contest_announcement SET subject = $1, content = $2, timestamp = NOW() WHERE contest_id = $3 AND announce_id = $4',
                              subject, content, contest_id, announce_id)

        res = await self.db.fetch('SELECT acct_id FROM contest_users WHERE contest_id = $1 AND status = $2', contest_id, UserStatus.APPROVED)
        for acct_id in res:
            await self.db.execute('UPDATE contest_users SET notification_read_count = GREATEST(notification_read_count - 1, 0) WHERE contest_id = $1 AND acct_id = $2',
                                  contest_id, int(acct_id[0]))

        return None, None

    async def get_all_announce(self, contest_id: int):
        res = await self.db.fetch('SELECT * FROM contest_announcement WHERE contest_id = $1 ORDER BY "timestamp" DESC', contest_id)
        return None, res

    async def get_announce(self, contest_id: int, announce_id: int):
        res = await self.db.fetch('SELECT * FROM contest_announcement WHERE contest_id = $1 AND announce_id = $2',
                                  contest_id, announce_id)
        if len(res) != 1:
            return ('Eunk', 'Unknown error'), None

        return None, res[0]

    async def ask_question(self, contest_id: int, ask_acct_id: int, ask_subject: str, ask_content: str):
        res = await self.db.fetch('INSERT INTO contest_question (contest_id, ask_subject, ask_content, ask_acct_id, ask_timestamp) VALUES ($1, $2, $3, $4, NOW()) RETURNING question_id',
                                  contest_id, ask_subject, ask_content, ask_acct_id)
        if len(res) != 1:
            return ('Eunk', 'Unknown error'), None

        return None, res[0]['question_id']

    async def reply_question(self, contest_id: int, question_id: int, reply_acct_id: int, reply_content: str):
        await self.db.execute('UPDATE contest_question SET reply_content = $1, reply_acct_id = $2, reply_timestamp = NOW() WHERE contest_id = $3 AND question_id = $4;',
                              reply_content, reply_acct_id, contest_id, question_id)

        return None, None

    async def get_question(self, contest_id: int, question_id: int):
        res = await self.db.fetch('SELECT * FROM contest_question WHERE contest_id = $1 AND question_id = $2', contest_id, question_id)
        if len(res) != 1:
            return ('Eunk', 'Unknown error'), None

        return None, res[0]

    async def get_all_question(self, contest_id: int, ask_acct_id: int = 0):
        if ask_acct_id:
            res = await self.db.fetch('SELECT * FROM contest_question WHERE contest_id = $1 AND ask_acct_id = $2', contest_id, ask_acct_id)
        else:
            res = await self.db.fetch('SELECT * FROM contest_question WHERE contest_id = $1', contest_id)

        return None, res

    async def get_need_reply_question_cnt(self, contest_id: int):
        res = await self.db.fetch('SELECT COUNT(*) FROM contest_question WHERE contest_id = $1 AND reply_acct_id IS NULL;', contest_id)
        return None, res[0]['count']

    async def get_unread_notification_cnt(self, contest_id: int, acct_id: int):
        """Get unread notification count for user

        Args:
            contest_id: Contest ID
            acct_id: User ID

        Returns:
            tuple: (err, cnt) Unread notification count
        """
        new_cnt = await self.db.fetch('''
        SELECT
            (SELECT COUNT(*) FROM contest_announcement WHERE contest_id = $1) +
            (SELECT COUNT(*) FROM contest_question WHERE contest_id = $1 AND ask_acct_id = $2 AND reply_acct_id IS NOT NULL)
        AS total_count;
        ''', contest_id, acct_id)
        new_cnt = new_cnt[0]['total_count']

        old_cnt = await self.db.fetch('SELECT notification_read_count FROM contest_users WHERE contest_id = $1 AND acct_id = $2',
                                      contest_id, acct_id)
        old_cnt = old_cnt[0]['notification_read_count']

        return None, max(new_cnt - old_cnt, 0)

    async def mark_notifications_as_read(self, contest_id: int, acct_id: int):
        """Mark notifications as read

        Args:
            contest_id: Contest ID
            acct_id: User ID

        Returns:
            tuple: (err, None)
        """
        await self.db.execute(
            '''
            UPDATE contest_users
            SET notification_read_count = sub.total_count
            FROM (
                SELECT
                    (SELECT COUNT(*) FROM contest_announcement WHERE contest_id = $1) +
                    (SELECT COUNT(*) FROM contest_question WHERE contest_id = $1 AND ask_acct_id = $2 AND reply_acct_id IS NOT NULL)
                    AS total_count
            ) AS sub
            WHERE contest_users.contest_id = $1
            AND contest_users.acct_id = $2;
            ''',
            contest_id, acct_id
        )

        return None, None

    async def get_icpc_scores(
        self,
        contest_id: int,
        pro_id: int,
        before_time: datetime.datetime,
        score_context: ContestScoreboardContext | None = None,
    ) -> dict:
        """
        Calculate ICPC scores for a problem.

        Score (Spend Time) = first AC time + fail count * penalty value (Minute)
        where fail count is the number of challenges before first AC.

        For users without AC: Score = 0, first_ac_timestamp = NULL, chal_id = latest challenge ID,
                             fail_cnt = total number of valid challenges

        Filters out invalid/non-verdictable states: CE, CLE, ERR, JE, JUDGE, NOTSTARTED, REJECTED
        """
        _, contest = await self.get_contest(contest_id)
        score_context = score_context or ContestScoreboardContext.official()

        # States to filter out (invalid/non-verdictable challenges)
        invalid_states = [
            ChalConst.STATE_CE,
            ChalConst.STATE_CLE,
            ChalConst.STATE_ERR,
            ChalConst.STATE_JE,
            ChalConst.STATE_JUDGE,
            ChalConst.STATE_NOTSTARTED,
            ChalConst.STATE_REJECTED
        ]

        res = await self.db.fetch(f'''
        WITH {_SCORE_ACCOUNT_WINDOWS_CTE},
        valid_challenges AS (
            SELECT
                challenge.chal_id,
                challenge.acct_id,
                challenge.pro_id,
                challenge.timestamp,
                total_result.state,
                account_windows.start_time
            FROM challenge
            INNER JOIN account_windows
                ON account_windows.acct_id = challenge.acct_id
            INNER JOIN total_result
                ON challenge.chal_id = total_result.chal_id
            WHERE challenge.contest_id = $1
                AND challenge.pro_id = $2
                AND challenge.timestamp >= account_windows.start_time
                AND challenge.timestamp < LEAST(account_windows.end_time, $3::timestamptz)
                AND (
                    $9::interval IS NULL
                    OR challenge.timestamp <= account_windows.start_time + $9::interval
                )
                AND total_result.state NOT IN (SELECT unnest($10::int[]))
        ),
        acct_challenges AS (
            SELECT
                acct_id,
                chal_id,
                pro_id,
                timestamp,
                state,
                start_time,
                ROW_NUMBER() OVER (PARTITION BY acct_id, pro_id ORDER BY timestamp ASC) AS challenge_order
            FROM valid_challenges
        ),
        first_ac_challenges AS (
            SELECT
                acct_id,
                chal_id,
                pro_id,
                timestamp AS first_ac_timestamp,
                start_time,
                challenge_order - 1 AS fail_cnt
            FROM acct_challenges
            WHERE state = $11
                AND challenge_order = (
                    SELECT MIN(challenge_order)
                    FROM acct_challenges ac2
                    WHERE ac2.acct_id = acct_challenges.acct_id
                        AND ac2.pro_id = acct_challenges.pro_id
                        AND ac2.state = $11
                )
        ),
        acct_challenge_counts AS (
            SELECT
                acct_id,
                pro_id,
                COUNT(*) AS total_challenges,
                MAX(chal_id) AS latest_chal_id,
                MAX(timestamp) AS latest_timestamp,
                MIN(start_time) AS start_time
            FROM acct_challenges
            GROUP BY acct_id, pro_id
        )
        SELECT
            COALESCE(fac.acct_id, acc.acct_id) AS acct_id,
            COALESCE(fac.chal_id, acc.latest_chal_id) AS chal_id,
            COALESCE(fac.first_ac_timestamp, acc.latest_timestamp) AS timestamp,
            COALESCE(fac.fail_cnt, acc.total_challenges) AS fail_cnt,
            CASE
                WHEN fac.acct_id IS NOT NULL THEN
                    (EXTRACT(EPOCH FROM (fac.first_ac_timestamp - fac.start_time))::integer / 60)
                    + (fac.fail_cnt * $12)::integer
                ELSE 0
            END AS score
        FROM first_ac_challenges fac
        FULL OUTER JOIN acct_challenge_counts acc
            ON fac.acct_id = acc.acct_id AND fac.pro_id = acc.pro_id
        ORDER BY acct_id;
        ''', contest_id, pro_id, before_time,
            int(score_context.session_type),
            int(ContestTimeMode.FLEXIBLE),
            int(UserStatus.APPROVED),
            int(UserStatus.ADMIN),
            score_context.use_stored_sessions,
            score_context.visible_elapsed,
            invalid_states,
            ChalConst.STATE_AC,
            contest.penalty_value,
        )

        if len(res) == 0:
            return {}

        scores = {
            acct_id: {
                'acct_id': acct_id,
                'chal_id': chal_id,
                'score': score,
                'timestamp': first_ac_timestamp,
                'fail_cnt': fail_cnt
            }
            for acct_id, chal_id, first_ac_timestamp, fail_cnt, score in res
        }

        return scores

    async def get_ioi2013_scores(
        self,
        contest_id: int,
        pro_id: int,
        before_time: datetime.datetime,
        score_context: ContestScoreboardContext | None = None,
    ) -> dict:
        score_context = score_context or ContestScoreboardContext.official()
        res = await self.db.fetch(
            f'''
        WITH {_SCORE_ACCOUNT_WINDOWS_CTE},
        ranked_challenges AS (
            SELECT
                "challenge"."chal_id",
                "challenge"."pro_id",
                "challenge"."acct_id",
                "challenge"."timestamp",
                ROUND("total_result"."rate", problem.rate_precision) AS rate,

                ROW_NUMBER() OVER (
                    PARTITION BY "challenge"."pro_id", "challenge"."acct_id"
                    ORDER BY "total_result"."rate" DESC, "challenge"."timestamp" ASC
                ) AS rank,

                COUNT(*) OVER (
                    PARTITION BY "challenge"."pro_id", "challenge"."acct_id"
                    ORDER BY "challenge"."timestamp" ASC
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                ) AS challenge_count_before_first_max_rate_challenge
            FROM "challenge"
            INNER JOIN account_windows
                ON account_windows.acct_id = challenge.acct_id
            INNER JOIN "total_result"
                ON "challenge"."contest_id" = $1 AND "challenge"."pro_id" = $2
                AND "challenge"."timestamp" >= account_windows.start_time
                AND "challenge"."timestamp" < LEAST(account_windows.end_time, $3::timestamptz)
                AND (
                    $9::interval IS NULL
                    OR "challenge"."timestamp" <= account_windows.start_time + $9::interval
                )
                AND "challenge"."chal_id" = "total_result"."chal_id"
            INNER JOIN "problem"
            ON "problem"."pro_id" = $2
        )
        SELECT
            acct_id,
            chal_id,
            rate AS score,
            timestamp AS best_timestamp,
            challenge_count_before_first_max_rate_challenge AS challenges_before
        FROM ranked_challenges
        WHERE rank = 1
        ORDER BY acct_id;
        ''', contest_id, pro_id, before_time,
            int(score_context.session_type), int(ContestTimeMode.FLEXIBLE),
            int(UserStatus.APPROVED), int(UserStatus.ADMIN),
            score_context.use_stored_sessions,
            score_context.visible_elapsed,
        )

        if len(res) == 0:
            return {}

        scores = {
            acct_id: {
                'acct_id': acct_id,
                'chal_id': chal_id,
                'score': score,
                'timestamp': timestamp,
                'fail_cnt': fail_cnt
            }
            for acct_id, chal_id, score, timestamp, fail_cnt in res
        }

        return scores

    async def get_ioi2017_scores(
        self,
        contest_id: int,
        pro_id: int,
        before_time: datetime.datetime,
        score_context: ContestScoreboardContext | None = None,
    ) -> dict:
        score_context = score_context or ContestScoreboardContext.official()
        res = await self.db.fetch(f'''
        WITH {_SCORE_ACCOUNT_WINDOWS_CTE},
        contest_challenges AS (
            SELECT challenge.chal_id, challenge.acct_id, challenge.pro_id, challenge.timestamp
            FROM challenge
            INNER JOIN account_windows
                ON account_windows.acct_id = challenge.acct_id
            WHERE challenge.contest_id = $1
              AND challenge.timestamp >= account_windows.start_time
              AND challenge.timestamp < LEAST(account_windows.end_time, $3::timestamptz)
              AND (
                  $9::interval IS NULL
                  OR challenge.timestamp <= account_windows.start_time + $9::interval
              )
        ),
        problem_tests AS (
            SELECT pro_id, subtask_id
            FROM subtask_config
            WHERE pro_id = $2
        ),
        individual_test_results AS (
            SELECT
                cc.acct_id,
                cc.chal_id,
                pt.pro_id,
                pt.subtask_id,
                t.rate,
                cc.timestamp
            FROM problem_tests pt
            JOIN subtask_result t ON pt.pro_id = t.pro_id AND pt.subtask_id = t.subtask_id
            JOIN contest_challenges cc ON t.chal_id = cc.chal_id
        ),
        ranked_results AS (
            SELECT
                acct_id,
                chal_id,
                pro_id,
                subtask_id,
                rate,
                timestamp,
                ROW_NUMBER() OVER (PARTITION BY acct_id, pro_id, subtask_id ORDER BY rate DESC, timestamp ASC) AS rank
            FROM individual_test_results
        ),
        best_individual_results AS (
            SELECT
                acct_id,
                chal_id,
                pro_id,
                subtask_id,
                rate AS best_rate,
                timestamp
            FROM ranked_results
            WHERE rank = 1
        ),
        aggregated_results AS (
            SELECT
                acct_id,
                pro_id,
                SUM(best_rate) AS total_rate,
                MAX(chal_id) AS last_chal_id,
                MAX(timestamp) AS best_timestamp
            FROM best_individual_results
            GROUP BY acct_id, pro_id
        ),
        challenge_counts AS (
            SELECT
                ar.acct_id,
                ar.pro_id,
                COUNT(DISTINCT cc.chal_id) AS challenges_before
            FROM aggregated_results ar
            JOIN contest_challenges cc ON cc.acct_id = ar.acct_id AND cc.pro_id = ar.pro_id
            WHERE cc.chal_id <= ar.last_chal_id
            GROUP BY ar.acct_id, ar.pro_id
        )
        SELECT
            ar.acct_id,
            ar.last_chal_id AS chal_id,
            ROUND(ar.total_rate, problem.rate_precision) AS score,
            ar.best_timestamp,
            cc.challenges_before
        FROM aggregated_results ar
        JOIN challenge_counts cc ON ar.acct_id = cc.acct_id AND ar.pro_id = cc.pro_id
        JOIN account a ON ar.acct_id = a.acct_id
        INNER JOIN problem ON problem.pro_id = $2
        ORDER BY ar.acct_id, ar.pro_id;
        ''', contest_id, pro_id, before_time,
            int(score_context.session_type), int(ContestTimeMode.FLEXIBLE),
            int(UserStatus.APPROVED), int(UserStatus.ADMIN),
            score_context.use_stored_sessions, score_context.visible_elapsed)

        if len(res) == 0:
            return {}

        scores = {
            acct_id: {
                'acct_id': acct_id,
                'chal_id': chal_id,
                'score': score,
                'timestamp': timestamp,
                'fail_cnt': fail_cnt
            }
            for acct_id, chal_id, score, timestamp, fail_cnt in res
        }

        return scores
