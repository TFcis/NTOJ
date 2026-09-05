import datetime
import enum
from dataclasses import dataclass, field
import pickle

import asyncpg

from services.chal import Compiler, ChalConst
from services.contest_session import ContestSession
from services.user import Account


class RegMode(enum.IntEnum):
    INVITED = 0
    FREE_REG = 1
    REG_APPROVAL = 2


class ContestMode(enum.IntEnum):
    IOI = 0
    ACM = 1 # NOTE: ACM/ICPC

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
        return ContestSession.fixed(self).is_started()

    def is_end(self) -> bool:
        return ContestSession.fixed(self).is_ended()

    def is_running(self) -> bool:
        return ContestSession.fixed(self).is_running()

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

    async def get_contest(self, contest_id: int):
        if (b_contest := await self.rs.hget('contest', str(contest_id))) is not None:
            contest: Contest = pickle.loads(b_contest)

            contest_session = ContestSession.fixed(contest)
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
                contest.contest_start = contest.contest_start
                contest.contest_end = contest.contest_end
                contest.reg_end = contest.reg_end

                result = await con.fetch('SELECT pro_id, score_type, challenge_style FROM contest_problem_joints WHERE contest_id = $1 ORDER BY "order";', contest_id)
                for pro_id, score_type, challenge_style in result:
                    contest.pro_list[pro_id] = {
                        "score_type": ProblemScoreType(int(score_type)),
                        "challenge_style": ChallengeResultStyle(int(challenge_style))
                    }

                result = await con.fetch('SELECT acct_id, status FROM contest_users WHERE contest_id = $1 ORDER BY acct_id', contest_id)
                for acct_id, status in result:
                    contest.user_list[acct_id] = {
                        "status": UserStatus(int(status))
                    }

            if ContestSession.fixed(contest).is_running():
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
                    "is_public_scoreboard": is_public_scoreboard
                } for contest_id, name, contest_mode, contest_start, contest_end, is_public_scoreboard in result
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
                    "reg_mode" = $8, "reg_end" = $9,
                    "allow_compilers" = $10,
                    "is_public_scoreboard" = $11,
                    "allow_view_other_page" = $12,
                    "hide_admin" = $13,
                    "submission_cd_time" = $14,
                    "freeze_scoreboard_period" = $15,
                    "penalty_value" = $16,
                    "enable_system_test" = $17
                    WHERE "contest_id" = $18;
                ''',
                contest.name,
                contest.desc_before_contest,
                contest.desc_during_contest,
                contest.desc_after_contest,

                contest.contest_mode, contest.contest_start, contest.contest_end,
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
        session: ContestSession | None = None,
    ) -> dict:
        """
        Calculate ICPC scores for a problem.

        Score (Spend Time) = (first_ac_timestamp) + fail_cnt * penalty_value (Minute)
        where fail_cnt is the number of submissions before first AC.

        For users without AC: Score = 0, first_ac_timestamp = NULL, chal_id = latest submission chal_id,
                             fail_cnt = total number of valid submissions

        Filters out invalid/non-verdictable states: CE, CLE, ERR, JE, JUDGE, NOTSTARTED, REJECTED
        """
        _, contest = await self.get_contest(contest_id)
        session = session or ContestSession.fixed(contest)

        # States to filter out (invalid/non-verdictable submissions)
        invalid_states = [
            ChalConst.STATE_CE,
            ChalConst.STATE_CLE,
            ChalConst.STATE_ERR,
            ChalConst.STATE_JE,
            ChalConst.STATE_JUDGE,
            ChalConst.STATE_NOTSTARTED,
            ChalConst.STATE_REJECTED
        ]

        res = await self.db.fetch('''
        WITH valid_challenges AS (
            -- Get all challenges that are valid (not in invalid states) and before before_time
            SELECT
                challenge.chal_id,
                acct_id,
                pro_id,
                timestamp,
                state
            FROM challenge
            INNER JOIN total_result
                ON challenge.chal_id = total_result.chal_id
            WHERE contest_id = $1
                AND pro_id = $2
                AND timestamp < $3::timestamptz
                AND state NOT IN (SELECT unnest($4::int[]))
        ),
        acct_challenges AS (
            -- Partition challenges by acct_id and pro_id, ordered by timestamp
            SELECT
                acct_id,
                chal_id,
                pro_id,
                timestamp,
                state,
                ROW_NUMBER() OVER (PARTITION BY acct_id, pro_id ORDER BY timestamp ASC) AS submission_order
            FROM valid_challenges
        ),
        first_ac_challenges AS (
            -- Find first AC for each acct (may be empty if no AC)
            SELECT
                acct_id,
                chal_id,
                pro_id,
                timestamp AS first_ac_timestamp,
                submission_order - 1 AS fail_cnt  -- Number of submissions before first AC
            FROM acct_challenges
            WHERE state = $5  -- Only AC state
                AND submission_order = (
                    -- Get the first AC submission order for this acct
                    SELECT MIN(submission_order)
                    FROM acct_challenges ac2
                    WHERE ac2.acct_id = acct_challenges.acct_id
                        AND ac2.pro_id = acct_challenges.pro_id
                        AND ac2.state = $5
                )
        ),
        acct_submission_counts AS (
            -- Count total valid submissions for each acct (for those without AC)
            SELECT
                acct_id,
                pro_id,
                COUNT(*) AS total_submissions,
                MAX(chal_id) AS latest_chal_id,
                MAX(timestamp) AS latest_timestamp
            FROM acct_challenges
            GROUP BY acct_id, pro_id
        )
        SELECT
            COALESCE(fac.acct_id, ascsub.acct_id) AS acct_id,
            COALESCE(fac.chal_id, ascsub.latest_chal_id) AS chal_id,
            COALESCE(fac.first_ac_timestamp, ascsub.latest_timestamp) AS timestamp,
            COALESCE(fac.fail_cnt, ascsub.total_submissions) AS fail_cnt,
            CASE
                WHEN fac.acct_id IS NOT NULL THEN (EXTRACT(EPOCH FROM (fac.first_ac_timestamp - $6::timestamptz))::integer / 60) + (fac.fail_cnt * $7)::integer
                ELSE 0
            END AS score
        FROM first_ac_challenges fac
        FULL OUTER JOIN acct_submission_counts ascsub
            ON fac.acct_id = ascsub.acct_id AND fac.pro_id = ascsub.pro_id
        ORDER BY acct_id;
        ''', contest_id, pro_id, before_time,
            invalid_states,  # $4: array of invalid states to filter out
            ChalConst.STATE_AC,  # $5: AC state
            session.start_time,  # $6: effective session start time for score calculation
            contest.penalty_value, # $7: penalty value
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

    async def get_ioi2013_scores(self, contest_id: int, pro_id: int, before_time: datetime.datetime) -> dict:
        res = await self.db.fetch(
            f'''
        WITH ranked_challenges AS (
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
            INNER JOIN "contest_users"
                ON "contest_users"."contest_id" = $1 AND "contest_users"."acct_id" = "challenge"."acct_id"
                AND "contest_users"."status" = {UserStatus.APPROVED} OR "contest_users"."status" = {UserStatus.ADMIN}

            INNER JOIN "total_result"
                ON "challenge"."contest_id" = $1 AND "challenge"."pro_id" = $2
                AND "challenge"."timestamp" < $3 AND "challenge"."chal_id" = "total_result"."chal_id"
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
        ''', contest_id, pro_id, before_time
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

    async def get_ioi2017_scores(self, contest_id: int, pro_id: int, before_time: datetime.datetime) -> dict:
        res = await self.db.fetch('''
        WITH contest_challenges AS (
            SELECT chal_id, acct_id, pro_id, timestamp
            FROM challenge
            WHERE contest_id = $1 AND timestamp < $3
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
        ''', contest_id, pro_id, before_time)

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
