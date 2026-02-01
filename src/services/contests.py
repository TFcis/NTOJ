import datetime
import enum
from dataclasses import dataclass, field
import random
import pickle
from ipaddress import IPv4Address, AddressValueError
from decimal import Decimal

import asyncpg
import tornado.log
from msgpack import packb, unpackb

from services.chal import ChalService, Compiler, ChalConst
from services.user import Account, UserService

logger = tornado.log.app_log

class RegMode(enum.IntEnum):
    INVITED = 0
    FREE_REG = 1
    REG_APPROVAL = 2
    PASSWORD = 3


class ContestMode(enum.IntEnum):
    IOI = 0
    ACM = 1
    RANDOM_SET = 2

class ProblemScoreType(enum.IntEnum):
    IOI2013 = 0
    IOI2017 = 1

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
    pro_sets: list[list[int]] = field(default_factory=list)
    ip_pro_list: dict[IPv4Address, list[int]] = field(default_factory=dict)
    start_ip: IPv4Address
    end_ip: IPv4Address

    reg_mode: RegMode
    reg_end: datetime.datetime
    contest_password: str = ''

    allow_compilers: set[Compiler] = field(default_factory=set)
    is_public_scoreboard: bool = False
    allow_view_other_page: bool = False  # TODO: finish allow view other page
    hide_admin: bool = True
    submission_cd_time: int = 30
    freeze_scoreboard_period: int = 0

    def is_start(self) -> bool:
        return datetime.datetime.now(datetime.UTC) >= self.contest_start

    def is_end(self) -> bool:
        return datetime.datetime.now(datetime.UTC) >= self.contest_end

    def is_running(self) -> bool:
        return self.contest_start <= datetime.datetime.now(datetime.UTC) < self.contest_end

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
            return acct.acct_id in self.user_list

        if acct_id is not None:
            return acct_id in self.user_list

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

    def get_randomset_prolist_from_acct_by_ip(self, acct: Account) -> list[int] | None:
        if self.contest_mode != ContestMode.RANDOM_SET:
            return None

        try:
            ip = IPv4Address(acct.lastip)
        except AddressValueError:
            return None

        try:
            return self.ip_pro_list[ip]
        except KeyError:
            logger.warning(f'TODO: Assign problem set for out of range IP not implemented. Contest {self.contest_id} IP range {self.start_ip} - {self.end_ip}, but acct {acct.acct_id} IP is {ip}.')
            return None

    def is_randomset_pro_allocated(self, acct: Account) -> bool:
        if self.contest_mode != ContestMode.RANDOM_SET:
            return False

        if self.is_admin(acct):
            logger.warning(f'Should not call is_randomset_pro_allocated for admin acct {acct.acct_id} in contest {self.contest_id}.')
            return False

        try:
            ip = IPv4Address(acct.lastip)
        except AddressValueError:
            return False

        return ip in self.ip_pro_list

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
                        SELECT "contest_id", "contest_creator",
                        "name",

                        "desc_before_contest",
                        "desc_during_contest",
                        "desc_after_contest",

                        "contest_mode", "contest_start", "contest_end",
                        "reg_mode", "reg_end", "contest_password", "start_ip", "end_ip",

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
                    return ('Enoext', 'Contest not found'), None

                result = result[0]

                contest = Contest(**result)
                contest.reg_mode = RegMode(contest.reg_mode)
                contest.contest_mode = ContestMode(contest.contest_mode)
                contest.contest_start = contest.contest_start
                contest.contest_end = contest.contest_end
                contest.reg_end = contest.reg_end
                contest.start_ip = IPv4Address(result['start_ip'])
                contest.end_ip = IPv4Address(result['end_ip'])

                result = await con.fetch('SELECT "pro_id", "score_type", "order" FROM contest_problem_joints WHERE contest_id = $1 ORDER BY "order";', contest_id)
                for pro_id, score_type, order in result:
                    contest.pro_list[pro_id] = {
                        "score_type": ProblemScoreType(int(score_type)),
                    }

                result = await con.fetch('SELECT acct_id, status FROM contest_users WHERE contest_id = $1 ORDER BY acct_id', contest_id)
                for acct_id, status in result:
                    contest.user_list[acct_id] = {
                        "status": UserStatus(int(status))
                    }

                if contest.contest_mode == ContestMode.RANDOM_SET:
                    result = await con.fetch(
                        '''
                            SELECT ip, contest_ip_joints.pro_id
                            FROM contest_ip_joints INNER JOIN contest_problem_joints
                            ON contest_ip_joints.contest_id = contest_problem_joints.contest_id
                               AND contest_ip_joints.pro_id = contest_problem_joints.pro_id
                            WHERE contest_ip_joints.contest_id = $1 ORDER BY contest_ip_joints.ip, contest_problem_joints."order" ASC;
                        ''',
                        contest_id
                    )
                    for ip_raw, pro_id in result:
                        ip = IPv4Address(ip_raw)
                        if ip not in contest.ip_pro_list:
                            contest.ip_pro_list[ip] = []
                        contest.ip_pro_list[ip].append(pro_id)

                    pro_set_count = await con.fetchval('''
                        SELECT COUNT(DISTINCT "order") FROM contest_problem_joints
                        WHERE contest_id = $1;
                    ''', contest_id)
                    for order in range(pro_set_count):
                        result = await con.fetch('''
                            SELECT pro_id FROM contest_problem_joints
                            WHERE contest_id = $1 AND "order" = $2;
                        ''', contest_id, order)
                        pro_set = [pro_id for pro_id, in result]
                        contest.pro_sets.append(pro_set)

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
                    "reg_mode" = $8, "reg_end" = $9, "contest_password" = $10,
                    "allow_compilers" = $11,
                    "is_public_scoreboard" = $12,
                    "allow_view_other_page" = $13,
                    "hide_admin" = $14,
                    "submission_cd_time" = $15,
                    "freeze_scoreboard_period" = $16
                    WHERE "contest_id" = $17;
                ''',
                contest.name,
                contest.desc_before_contest,
                contest.desc_during_contest,
                contest.desc_after_contest,

                contest.contest_mode, contest.contest_start, contest.contest_end,
                contest.reg_mode, contest.reg_end, contest.contest_password,

                contest.allow_compilers,
                contest.is_public_scoreboard,
                contest.allow_view_other_page,
                contest.hide_admin,
                contest.submission_cd_time,
                contest.freeze_scoreboard_period,
                contest.contest_id
            )

            if prolist_updated:
                if contest.contest_mode == ContestMode.RANDOM_SET:
                    return ('Eprolist', 'Cannot update problem list for random set contests here'), None
                order = 0
                failed = []
                for pro_id, v in contest.pro_list.items():
                    try:
                        await con.execute('''
                            INSERT INTO contest_problem_joints ("contest_id", "pro_id", "score_type", "order")
                            VALUES ($1, $2, $3, $4) ON CONFLICT (contest_id, pro_id) DO UPDATE
                            SET score_type = EXCLUDED.score_type, "order" = EXCLUDED."order"
                            WHERE
                                contest_problem_joints.score_type != EXCLUDED.score_type OR
                                contest_problem_joints.order != EXCLUDED.order;
                        ''', contest.contest_id, pro_id, int(v['score_type']), order)
                        order += 1
                    except asyncpg.ForeignKeyViolationError:
                        failed.append(pro_id)
                        continue

                await con.execute('DELETE FROM contest_problem_joints WHERE contest_id = $1 AND "order" >= $2', contest.contest_id, order)
                for failed_pro_id in failed:
                    contest.pro_list.pop(failed_pro_id)

            if userlist_updated:
                failed = []
                for acct_id, v in contest.user_list.items():
                    try:
                        await con.execute('''
                            INSERT INTO contest_users ("contest_id", "acct_id", "status")
                            VALUES ($1, $2, $3) ON CONFLICT (contest_id, acct_id) DO UPDATE
                            SET status = EXCLUDED.status
                            WHERE contest_users.status != EXCLUDED.status;
                        ''', contest.contest_id, acct_id, int(v['status']))
                    except asyncpg.ForeignKeyViolationError:
                        failed.append(acct_id)
                        continue

                for failed_acct_id in failed:
                    contest.user_list.pop(failed_acct_id)

        b_contest = pickle.dumps(contest)
        await self.rs.hset('contest', str(contest.contest_id), b_contest)

        # log

        return None, None

    async def update_ip(self, contest: Contest):
        async with self.db.acquire() as con:
            await con.execute('''
                UPDATE contest
                SET start_ip = $1, end_ip = $2
                WHERE contest_id = $3;
            ''', str(contest.start_ip), str(contest.end_ip), contest.contest_id)

        if contest.contest_mode != ContestMode.RANDOM_SET:
            # Updated, but not random set contest, nothing more to do
            return None, None

        # Clear existting ip
        contest.ip_pro_list.clear()
        async with self.db.acquire() as con:
            await con.execute('DELETE FROM contest_ip_joints WHERE contest_id = $1;', contest.contest_id)

        # Readd IPs
        for ip_int in range(int(contest.start_ip), int(contest.end_ip) + 1):
            ip = IPv4Address(ip_int)
            contest.ip_pro_list[ip] = []
        for pro_set in contest.pro_sets:
            await self.add_random_pro(contest, pro_set)

        await self.rs.hset('contest', str(contest.contest_id), pickle.dumps(contest))

        return None, None

    async def add_pro_set(self, contest: Contest , pro_set: list[tuple[int, ProblemScoreType]]):
        for pro_id, _ in pro_set:
            if pro_id in contest.pro_list:
                return ('Eexist', f'Problem {pro_id} already in contest'), None
            contest.pro_list[pro_id] = {} # Add dummy dict for avoiding repeated problem id

        pro_order = len(contest.pro_sets)
        async with self.db.acquire() as con:
            try:
                # Insert problems into contest_problem_joints
                await con.executemany(
                    '''
                    INSERT INTO contest_problem_joints ("contest_id", "pro_id", "score_type", "order")
                    VALUES ($1, $2, $3, $4)
                    ''',
                    [(contest.contest_id, pro_id, int(score_type), pro_order) for pro_id, score_type in pro_set]
                )
            except asyncpg.ForeignKeyViolationError:
                return ('Enoext', 'One or more problem IDs do not exist'), None

        contest.pro_sets.append([pro_id for pro_id, _ in pro_set])

        for pro_id, score_type in pro_set:
            contest.pro_list[pro_id] = {
                "score_type": score_type,
            }

        await self.add_random_pro(contest, [pro_id for pro_id, _ in pro_set])
        await self.rs.hset('contest', str(contest.contest_id), pickle.dumps(contest))
        return None, None

    async def add_random_pro(self, contest: Contest, pro_set: list[int]):
        '''
            Append a random problem in pro_set to each ip's problem list
        '''
        pro_size = len(pro_set)
        if pro_size == 1:
            for pro_list in contest.ip_pro_list.values():
                pro_list.append(pro_set[0])
        elif pro_size == 2:
            for pro_list in contest.ip_pro_list.values():
                pro_list.append(pro_set[random.randint(0, 1)])
        else:
            idx = 0
            for pro_list in contest.ip_pro_list.values():
                idx = (idx + random.randint(1,pro_size-1)) % pro_size
                pro_list.append(pro_set[idx])

        async with self.db.acquire() as con:
            # Insert por_id into contest_ip_joints
            await con.executemany(
                '''
                INSERT INTO contest_ip_joints ("contest_id", "ip", "pro_id")
                VALUES ($1, $2, $3)
                ''',
                [(contest.contest_id, str(ip), pro_list[-1]) for ip, pro_list in contest.ip_pro_list.items()]
            )

    async def remove_pro_set(self, contest: Contest , pro_set_idx: int):
        for pro_list in contest.ip_pro_list.values():
            pro_list.pop(pro_set_idx)

        remove_pro_ids = contest.pro_sets.pop(pro_set_idx)
        for pro_id in remove_pro_ids:
            contest.pro_list.pop(pro_id)
        await self.rs.hset('contest', str(contest.contest_id), pickle.dumps(contest))

        async with self.db.acquire() as con:
            # Remove problems from contest_problem_joints
            await con.execute(
                '''
                DELETE FROM contest_problem_joints
                WHERE "contest_id" = $1 AND "order" = $2;
                ''',
                contest.contest_id, pro_set_idx
            )
            # Subtract order for problems with order > pro_set_idx
            await con.execute(
                '''
                UPDATE contest_problem_joints
                SET "order" = "order" - 1
                WHERE "contest_id" = $1 AND "order" > $2
                ''',
                contest.contest_id, pro_set_idx
            )
            # Remove pro_id from contest_ip_joints
            await con.executemany(
                '''
                DELETE FROM contest_ip_joints
                WHERE "contest_id" = $1 AND "pro_id" = $2
                ''',
                [(contest.contest_id, pro_id) for pro_id in remove_pro_ids]
            )
        return None, None

    async def reorder_pro_set(self, contest: Contest, new_idxs: list[int]):
        # Reorder pro_sets
        contest.pro_sets = [contest.pro_sets[i] for i in new_idxs]
        # Reorder ip_pro_list
        for ip in contest.ip_pro_list:
            contest.ip_pro_list[ip] = [contest.ip_pro_list[ip][i] for i in new_idxs]

        await self.rs.hset('contest', str(contest.contest_id), pickle.dumps(contest))

        async with self.db.acquire() as con:
            # Update contest_problem_joints
            for order, pro_ids in enumerate(contest.pro_sets):
                if new_idxs[order] == order:
                    continue
                await con.executemany(
                    '''
                    UPDATE contest_problem_joints
                    SET "order" = $3
                    WHERE "contest_id" = $1 AND "pro_id" = $2
                    ''',
                    [(contest.contest_id, pro_id, order) for pro_id in pro_ids]
                )
        return None, None

    def _encoder(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.timestamp()

        elif isinstance(obj, Decimal):
            return str(obj)

        return obj

    async def update_randomset_scoreboard(self, chal_id: int):
        err, chal = await ChalService.inst.get_chal(chal_id)
        if err:
            return
        assert chal

        err, contest = await self.get_contest(chal.contest_id)
        if err:
            return
        assert contest

        if contest.contest_mode != ContestMode.RANDOM_SET:
            return

        if contest.is_admin(acct_id=chal.acct_id):
            return

        err, acct = await UserService.inst.info_acct(chal.acct_id)
        if err:
            return
        assert acct

        prolist = contest.get_prolist_from_acct_by_ip(acct)
        if prolist is None:
            return

        try:
            pro_order = prolist.index(chal.pro_id)
        except ValueError:
            logger.error(f'Contest {contest.contest_id} randomset problem list for acct {acct.acct_id} does not contain problem {chal.pro_id}.')
            return

        err, total_result = await ChalService.inst.get_total_result(chal.chal_id)
        if err:
            return
        assert total_result

        best_record = await self.rs.hget(f'contest_{contest.contest_id}_randomset_scoreboard', f'{acct.acct_id}_{pro_order}')
        fail_count = 1 if total_result.state != ChalConst.STATE_AC else 0
        if best_record is not None:
            best_record = unpackb(best_record)
            fail_count += best_record['fail_count']

        # NOTE: IOI2013
        if best_record is None or total_result.rate > Decimal(best_record['score']):
            best_record = {
                'chal_id': chal.chal_id,
                'timestamp': chal.timestamp,
                'state': total_result.state,
                'score': total_result.rate,
                'fail_count': fail_count,
            }

        await self.rs.hset(f'contest_{contest.contest_id}_randomset_scoreboard', f'{acct.acct_id}_{pro_order}', packb(best_record, default=self._encoder))

    async def get_ioi2013_scores(self, contest_id: int, pro_id: int, before_time: datetime.datetime) -> dict:
        _, contest = await self.get_contest(contest_id)
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
                'fail_count': fail_count
            }
            for acct_id, chal_id, score, timestamp, fail_count in res
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
                'fail_count': fail_count
            }
            for acct_id, chal_id, score, timestamp, fail_count in res
        }

        return scores

