import datetime
import enum
from dataclasses import dataclass, field
import pickle

import asyncpg

from services.user import Account


class RegMode(enum.IntEnum):
    INVITED = 0
    FREE_REG = 1
    REG_APPROVAL = 2


class ContestMode(enum.IntEnum):
    IOI = 0
    ACM = 1


@dataclass(slots=True, kw_only=True)
class Contest:
    contest_id: int
    name: str
    desc_before_contest: str = ''
    desc_during_contest: str = ''
    desc_after_contest: str = ''

    # contest_status: bool
    contest_mode: ContestMode
    contest_start: datetime.datetime
    contest_end: datetime.datetime

    acct_list: list[int] = field(default_factory=list)
    pro_list: list[int] = field(default_factory=list)
    admin_list: list[int]

    reg_mode: RegMode
    reg_end: datetime.datetime
    reg_list: list[int] = field(default_factory=list)

    allow_compilers: list[str] = field(default_factory=list)
    is_public_scoreboard: bool = False
    allow_view_other_page: bool = False  # TODO: finish allow view other page
    hide_admin: bool = True
    submission_cd_time: int = 30
    freeze_scoreboard_period: int = 0

    def is_start(self):
        return datetime.datetime.now().replace(
            tzinfo=datetime.timezone(datetime.timedelta(hours=+8))) >= self.contest_start

    def is_end(self):
        return datetime.datetime.now().replace(
            tzinfo=datetime.timezone(datetime.timedelta(hours=+8))) >= self.contest_end

    def is_running(self):
        return self.contest_start <= datetime.datetime.now().replace(
            tzinfo=datetime.timezone(datetime.timedelta(hours=+8))) < self.contest_end

    def is_member(self, acct: Account | None = None, acct_id: int | None = None):
        if acct is not None:
            return acct.acct_id in self.acct_list or acct.acct_id in self.admin_list

        if acct_id is not None:
            return acct_id in self.acct_list or acct_id in self.admin_list

        assert acct is not None and acct_id is not None, 'one of args(acct or acct_id) must not None'

    def is_admin(self, acct: Account | None = None, acct_id: int | None = None):
        if acct is not None:
            return acct.acct_id in self.admin_list

        if acct_id is not None:
            return acct_id in self.admin_list

        assert acct is not None and acct_id is not None, 'one of args(acct or acct_id) must not None'


class ContestService:
    def __init__(self, db, rs):
        self.db = db
        self.rs = rs

        ContestService.inst = self

    async def get_contest(self, contest_id: int):
        if (b_contest := await self.rs.hget('contest', str(contest_id))) is not None:
            contest: Contest = pickle.loads(b_contest)

            if contest.is_end():
                await self.rs.hdel('contest', str(contest_id))

        else:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    '''
                        SELECT "contest_id",
                        "name",

                        "desc_before_contest",
                        "desc_during_contest",
                        "desc_after_contest",

                        "contest_mode", "contest_start", "contest_end",
                        "acct_list", "pro_list", "admin_list",
                        "reg_mode", "reg_end", "reg_list",

                        "allow_compilers",
                        "is_public_scoreboard",
                        "allow_view_other_page",
                        "hide_admin",
                        "submission_cd_time",
                        "freeze_scoreboard_period"
                        FROM "contest" WHERE "contest_id" = $1;
                    ''',
                    contest_id
                )

                if len(result) != 1:
                    return 'Enoext', None

                result = result[0]

            contest = Contest(**result)
            contest.reg_mode = RegMode(contest.reg_mode)
            contest.contest_mode = ContestMode(contest.contest_mode)
            contest.contest_start = contest.contest_start.astimezone(datetime.timezone(datetime.timedelta(hours=+8)))
            contest.contest_end = contest.contest_end.astimezone(datetime.timezone(datetime.timedelta(hours=+8)))
            contest.reg_end = contest.reg_end.astimezone(datetime.timezone(datetime.timedelta(hours=+8)))

            if contest.is_running():
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
                    "contest_start": contest_start.astimezone(datetime.timezone(datetime.timedelta(hours=+8))),
                    "contest_end": contest_end.astimezone(datetime.timezone(datetime.timedelta(hours=+8))),
                    "is_public_scoreboard": is_public_scoreboard
                } for contest_id, name, contest_mode, contest_start, contest_end, is_public_scoreboard in result
            ]

        return None, contest_list

    async def add_default_contest(self, acct: Account, contest_name: str):
        try:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    '''
                        INSERT INTO "contest" ("name", "admin_list") VALUES($1, $2) RETURNING "contest_id";
                    ''',
                    contest_name,
                    [acct.acct_id],
                )

        except asyncpg.IntegrityConstraintViolationError:
            return 'Eexist', None

        if len(result) != 1:
            return 'Eexist', None

        contest_id = result[0]['contest_id']

        _, contest = await self.get_contest(contest_id)

        b_contest = pickle.dumps(contest)

        await self.rs.hset('contests', f'{contest_id}', b_contest)

        return None, contest_id

    async def update_contest(self, acct: Account, contest: Contest):
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
                    "acct_list" = $8, "admin_list" = $9, "pro_list" = $10,
                    "reg_mode" = $11, "reg_end" = $12, "reg_list" = $13,

                    "allow_compilers" = $14,
                    "is_public_scoreboard" = $15,
                    "allow_view_other_page" = $16,
                    "hide_admin" = $17,
                    "submission_cd_time" = $18,
                    "freeze_scoreboard_period" = $19
                    WHERE "contest_id" = $20;
                ''',
                contest.name,
                contest.desc_before_contest,
                contest.desc_during_contest,
                contest.desc_after_contest,

                contest.contest_mode, contest.contest_start, contest.contest_end,
                contest.acct_list, contest.admin_list, contest.pro_list,
                contest.reg_mode, contest.reg_end, contest.reg_list,

                contest.allow_compilers,
                contest.is_public_scoreboard,
                contest.allow_view_other_page,
                contest.hide_admin,
                contest.submission_cd_time,
                contest.freeze_scoreboard_period,
                contest.contest_id
            )

        b_contest = pickle.dumps(contest)
        await self.rs.hset('contest', str(contest.contest_id), b_contest)

        # log

        return None, None

    async def get_ioi2013_scores(self, contest_id: int, pro_id: int, before_time: datetime.datetime) -> dict:
        _, contest = await self.get_contest(contest_id)
        user = ','.join(list(map(str, contest.acct_list + contest.admin_list)))
        res = await self.db.fetch(
            f'''
        WITH ranked_challenges AS (
            SELECT
                "challenge"."chal_id",
                "challenge"."pro_id",
                "challenge"."acct_id",
                "challenge"."timestamp",
                "challenge_state"."rate",

                ROW_NUMBER() OVER (
                    PARTITION BY "challenge"."pro_id", "challenge"."acct_id"
                    ORDER BY "challenge_state"."rate" DESC, "challenge"."timestamp" ASC
                ) AS rank,

                COUNT(*) OVER (
                    PARTITION BY "challenge"."pro_id", "challenge"."acct_id"
                    ORDER BY "challenge"."timestamp" ASC
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                ) AS challenge_count_before_first_max_rate_challenge
            FROM "challenge"
            INNER JOIN "challenge_state"
            ON "challenge"."contest_id" = $1 AND "challenge"."acct_id" in ({user}) AND "challenge"."pro_id" = $2
            AND "challenge"."timestamp" < $3 AND "challenge"."chal_id" = "challenge_state"."chal_id"

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
            SELECT chal_id, acct_id, pro_id
            FROM challenge
            WHERE contest_id = $1 AND timestamp < $3
        ),
        problem_tests AS (
            SELECT pro_id, test_idx, weight
            FROM test_config
            WHERE pro_id = $2
        ),
        individual_test_results AS (
            SELECT
                cc.acct_id,
                cc.chal_id,
                pt.pro_id,
                pt.test_idx,
                pt.weight,
                CASE WHEN t.state = 1 THEN pt.weight ELSE 0 END AS rate,
                t.timestamp
            FROM problem_tests pt
            JOIN test t ON pt.pro_id = t.pro_id AND pt.test_idx = t.test_idx
            JOIN contest_challenges cc ON t.chal_id = cc.chal_id
        ),
        ranked_results AS (
            SELECT
                acct_id,
                chal_id,
                pro_id,
                test_idx,
                rate,
                timestamp,
                ROW_NUMBER() OVER (PARTITION BY acct_id, pro_id, test_idx ORDER BY rate DESC, timestamp ASC) AS rank
            FROM individual_test_results
        ),
        best_individual_results AS (
            SELECT
                acct_id,
                chal_id,
                pro_id,
                test_idx,
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
            ar.total_rate AS score,
            ar.best_timestamp,
            cc.challenges_before
        FROM aggregated_results ar
        JOIN challenge_counts cc ON ar.acct_id = cc.acct_id AND ar.pro_id = cc.pro_id
        JOIN account a ON ar.acct_id = a.acct_id
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

