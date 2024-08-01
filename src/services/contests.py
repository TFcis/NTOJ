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
    desc: str = ''

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

    def is_member(self, acct: Account = None, acct_id: int = None):
        if acct is not None:
            return acct.acct_id in self.acct_list or acct.acct_id in self.admin_list

        if acct_id is not None:
            return acct_id in self.acct_list or acct_id in self.admin_list

        assert acct is not None and acct_id is not None, 'one of args(acct or acct_id) must not None'

    def is_admin(self, acct: Account = None, acct_id: int = None):
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
                        "name", "desc",
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
                    "name" = $1, "desc" = $2,
                    "contest_mode" = $3, "contest_start" = $4, "contest_end" = $5,
                    "acct_list" = $6, "admin_list" = $7, "pro_list" = $8,
                    "reg_mode" = $9, "reg_end" = $10, "reg_list" = $11,

                    "allow_compilers" = $12,
                    "is_public_scoreboard" = $13,
                    "allow_view_other_page" = $14,
                    "hide_admin" = $15,
                    "submission_cd_time" = $16,
                    "freeze_scoreboard_period" = $17
                    WHERE "contest_id" = $18;
                ''',
                contest.name, contest.desc,
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

    async def get_ioi_style_score_data(self, contest_id: int, acct_id: int, before_time: datetime.datetime):
        async with self.db.acquire() as con:
            res = await con.fetch("""
            WITH ranked_challenges AS (
                SELECT
                    "challenge"."chal_id",
                    "challenge"."pro_id",
                    "challenge"."acct_id",
                    "challenge"."timestamp",
                    "challenge_state"."rate",

                    ROW_NUMBER() OVER (
                        PARTITION BY "challenge"."pro_id"
                        ORDER BY "challenge_state"."rate" DESC, "challenge"."timestamp" ASC
                    ) AS rank,

                    COUNT(*) OVER (
                        PARTITION BY "challenge"."pro_id"
                        ORDER BY "challenge"."timestamp" ASC
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ) AS challenge_count_before_first_max_rate_challenge
                FROM "challenge"
                INNER JOIN "challenge_state"
                ON "challenge"."contest_id" = $1 AND "challenge"."acct_id" = $2 AND "challenge"."timestamp" < $3 AND "challenge"."chal_id" = "challenge_state"."chal_id"
            )
            SELECT
                chal_id,
                pro_id,
                timestamp,
                rate,
                challenge_count_before_first_max_rate_challenge,
                SUM(rate) OVER () AS total_score
            FROM ranked_challenges
            WHERE rank = 1 ORDER BY pro_id;
            """,
                                  contest_id, acct_id, before_time)

        if len(res) == 0:
            return {}, 0

        total_score = 0
        rate = {}
        for chal_id, pro_id, timestamp, score, fail_cnt, total_s in res:
            total_score = total_s
            rate[pro_id] = {
                'chal_id': chal_id,
                'pro_id': pro_id,
                'timestamp': timestamp,
                'score': score,
                'fail_cnt': fail_cnt,
            }

        return rate, total_score
