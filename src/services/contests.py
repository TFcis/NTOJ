import datetime
import enum
from dataclasses import dataclass, field
import random
import pickle
from decimal import Decimal
from itertools import groupby

import asyncpg
import tornado.log
from msgpack import packb, unpackb

from services.chal import ChalService, Compiler, ChalConst
from services.user import Account, UserService
from services.pro import ProConst

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
    acct_pro_list: dict[int, list[int]] = field(default_factory=dict)

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

    def get_randomset_prolist(self, acct: Account | int) -> list[int] | None:
        if self.contest_mode != ContestMode.RANDOM_SET:
            return None

        acct_id = acct.acct_id if isinstance(acct, Account) else acct
        return self.acct_pro_list.get(acct_id)

    def is_randomset_pro_allocated(self, acct: Account | int) -> bool:
        if self.contest_mode != ContestMode.RANDOM_SET:
            return False

        acct_id = acct.acct_id if isinstance(acct, Account) else acct

        if self.is_admin(acct_id=acct_id):
            logger.warning(f'Should not call is_randomset_pro_allocated for admin acct {acct_id} in contest {self.contest_id}.')
            return False

        return acct_id in self.acct_pro_list

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
                        "reg_mode", "reg_end", "contest_password",

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
                contest.allow_compilers = set(contest.allow_compilers)

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
                            SELECT acct_id, contest_acct_pro_joints.pro_id
                            FROM contest_acct_pro_joints INNER JOIN contest_problem_joints
                            ON contest_acct_pro_joints.contest_id = contest_problem_joints.contest_id
                               AND contest_acct_pro_joints.pro_id = contest_problem_joints.pro_id
                            WHERE contest_acct_pro_joints.contest_id = $1
                            ORDER BY contest_acct_pro_joints.acct_id, contest_problem_joints."order" ASC;
                        ''',
                        contest_id
                    )
                    for acct_id, pro_id in result:
                        if acct_id not in contest.acct_pro_list:
                            contest.acct_pro_list[acct_id] = []
                        contest.acct_pro_list[acct_id].append(pro_id)

                    result = await con.fetch('''
                        SELECT pro_id, "order" FROM contest_problem_joints
                        WHERE contest_id = $1 ORDER BY "order";
                    ''', contest_id)
                    contest.pro_sets = [
                        [pro_id for pro_id, _ in group]
                        for _, group in groupby(result, key=lambda x: x['order'])
                    ]

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

                    result = await con.fetch('''
                        INSERT INTO contest_problem_joints ("contest_id", "pro_id", "score_type", "order")
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (contest_id, pro_id) DO UPDATE
                        SET score_type = EXCLUDED.score_type, "order" = EXCLUDED."order"
                        WHERE
                            contest_problem_joints.score_type != EXCLUDED.score_type OR
                            contest_problem_joints.order != EXCLUDED.order
                        RETURNING pro_id;
                    ''', contest.contest_id, pro_id, int(v['score_type']), order)

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

    async def add_pro_set(self, contest: Contest , pro_set: list[tuple[int, ProblemScoreType]]):
        for pro_id, _ in pro_set:
            if pro_id in contest.pro_list:
                return ('Eexist', f'Problem {pro_id} already in contest'), None
            contest.pro_list[pro_id] = {} # Add dummy dict for avoiding repeated problem id

        pro_order = len(contest.pro_sets)
        pro_ids = [pro_id for pro_id, _ in pro_set]
        score_types = [int(score_type) for _, score_type in pro_set]
        orders = [pro_order for _ in pro_set]
        async with self.db.acquire() as con:
            tr = con.transaction()
            await tr.start()
            try:
                res = await con.execute(
                    f'''
                    WITH hidden_check AS (
                        SELECT 1
                        FROM problem
                        WHERE pro_id = ANY($2)
                        AND status = {ProConst.STATUS_HIDDEN}
                        LIMIT 1
                    )
                    INSERT INTO contest_problem_joints ("contest_id", "pro_id", "score_type", "order")
                    SELECT
                        $1,
                        v.pro_id,
                        v.score_type,
                        v.order
                    FROM UNNEST($2::int[], $3::int[], $4::int[]) AS v(pro_id, score_type, "order")
                    JOIN problem p ON p.pro_id = v.pro_id
                    WHERE NOT EXISTS (SELECT 1 FROM hidden_check);
                    ''',
                    contest.contest_id,
                    pro_ids,
                    score_types,
                    orders,
                )
                inserted_count = res.split(' ')[2]
                if inserted_count != str(len(pro_set)):
                    tr.rollback()
                    return ('Eparam', 'Cannot add proset due to problem not found or problem is hidden'), None

            except Exception as e:
                logger.error(f'Error adding pro set to contest {contest.contest_id}: {e}')
                tr.rollback()
            else:
                tr.commit()

        contest.pro_sets.append([pro_id for pro_id, _ in pro_set])

        for pro_id, score_type in pro_set:
            contest.pro_list[pro_id] = {
                "score_type": score_type,
            }

        await self.add_random_pro(contest, [pro_id for pro_id, _ in pro_set], pro_order)
        await self.rs.hset('contest', str(contest.contest_id), pickle.dumps(contest))
        return None, None

    async def add_random_pro(self, contest: Contest, pro_set: list[int], pro_set_idx: int):
        """
        Allocate a random problem from pro_set to each contest member.
        Only allocates to accounts that haven't been assigned a problem for this pro_set_idx yet.
        Ensures that adjacent accounts (by acct_id) get different problems.

        Args:
            contest: The contest object
            pro_set: List of problem IDs to randomly choose from
            pro_set_idx: The index of this problem set (used for incremental allocation)
        """
        if contest.contest_mode != ContestMode.RANDOM_SET:
            return

        pro_size = len(pro_set)
        if pro_size == 0:
            return

        acct_ids = [acct_id for acct_id in contest.user_list.keys()
                    if contest.user_list[acct_id]['status'] == UserStatus.APPROVED]

        allocations = []

        for i, acct_id in enumerate(acct_ids):
            if acct_id in contest.acct_pro_list and len(contest.acct_pro_list[acct_id]) > pro_set_idx:
                # Already allocated
                continue

            prev_pro = None
            next_pro = None

            if i > 0:
                prev_acct = acct_ids[i-1]
                if prev_acct in contest.acct_pro_list and len(contest.acct_pro_list[prev_acct]) > pro_set_idx:
                    prev_pro = contest.acct_pro_list[prev_acct][pro_set_idx]

            if i < len(acct_ids) - 1:
                next_acct = acct_ids[i+1]
                if next_acct in contest.acct_pro_list and len(contest.acct_pro_list[next_acct]) > pro_set_idx:
                    next_pro = contest.acct_pro_list[next_acct][pro_set_idx]

            if pro_size == 1:
                chosen = pro_set[0]
            elif pro_size == 2:
                chosen = pro_set[0] if prev_pro != pro_set[0] and next_pro != pro_set[0] else pro_set[1]
            else:
                if not next_pro:
                    if i >= 2:
                        next_acct = acct_ids[i-2]
                        if next_acct in contest.acct_pro_list and len(contest.acct_pro_list[next_acct]) > pro_set_idx:
                            next_pro = contest.acct_pro_list[next_acct][pro_set_idx]

                available = [p for p in pro_set if p not in (prev_pro, next_pro)]
                chosen = random.choice(available)

            if acct_id not in contest.acct_pro_list:
                contest.acct_pro_list[acct_id] = []
            contest.acct_pro_list[acct_id].append(chosen)

            allocations.append((contest.contest_id, acct_id, chosen))

        async with self.db.acquire() as con:
            if allocations:
                await con.executemany(
                    '''
                    INSERT INTO contest_acct_pro_joints ("contest_id", "acct_id", "pro_id")
                    VALUES ($1, $2, $3)
                    ''',
                    allocations
                )

    async def remove_pro_set(self, contest: Contest , pro_set_idx: int):
        # Remove from each account's problem list
        for acct_id in contest.acct_pro_list:
            if len(contest.acct_pro_list[acct_id]) > pro_set_idx:
                contest.acct_pro_list[acct_id].pop(pro_set_idx)

        remove_pro_ids = contest.pro_sets.pop(pro_set_idx)
        for pro_id in remove_pro_ids:
            contest.pro_list.pop(pro_id)
        await self.rs.hset('contest', str(contest.contest_id), pickle.dumps(contest))

        delete_keys = [f'{acct_id}_{pro_set_idx}' for acct_id in contest.acct_pro_list.keys()]
        await self.rs.hdel(f"contest_{contest.contest_id}_randomset_scoreboard", *delete_keys)

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
            # Remove pro_id from contest_acct_pro_joints for this pro_set
            await con.executemany(
                '''
                DELETE FROM contest_acct_pro_joints
                WHERE "contest_id" = $1 AND "pro_id" = $2
                ''',
                [(contest.contest_id, pro_id) for pro_id in remove_pro_ids]
            )
        return None, None

    async def reorder_pro_set(self, contest: Contest, new_idxs: list[int]):
        # Create reverse mapping: old_idx -> new_idx
        old_to_new = {}
        for new_idx, old_idx in enumerate(new_idxs):
            old_to_new[old_idx] = new_idx

        # Reorder pro_sets
        contest.pro_sets = [contest.pro_sets[i] for i in new_idxs]
        # Reorder acct_pro_list
        for acct_id in contest.acct_pro_list:
            contest.acct_pro_list[acct_id] = [contest.acct_pro_list[acct_id][i] for i in new_idxs]

        await self.rs.hset('contest', str(contest.contest_id), pickle.dumps(contest))

        # Update scoreboard keys to follow the new order
        # First, collect all old scoreboard data
        scoreboard_data = {}
        for acct_id in contest.acct_pro_list:
            for old_idx in range(len(new_idxs) + 1):  # Original size could be larger
                old_key = f'{acct_id}_{old_idx}'
                value = await self.rs.hget(f"contest_{contest.contest_id}_randomset_scoreboard", old_key)
                if value is not None:
                    scoreboard_data[old_key] = value

        async with self.rs.pipeline() as pipe:
            # Clear all old keys
            if scoreboard_data:
                await pipe.hdel(f"contest_{contest.contest_id}_randomset_scoreboard", *scoreboard_data.keys())

            # Re-insert with new keys based on mapping
            for old_key, value in scoreboard_data.items():
                # Parse acct_id and old_idx from old_key
                parts = old_key.rsplit('_', 1)
                acct_id = int(parts[0])
                old_idx = int(parts[1])

                if old_idx in old_to_new:
                    new_idx = old_to_new[old_idx]
                    new_key = f'{acct_id}_{new_idx}'
                    await pipe.hset(f"contest_{contest.contest_id}_randomset_scoreboard", new_key, value)
                # If old_idx not in old_to_new, it means this problem set was removed, so don't re-insert
            await pipe.execute()

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

    async def update_pro_set(self, contest: Contest, pro_set_idx: int, new_pro_set: list[tuple[int, ProblemScoreType]]):
        """
        Update a problem set in RandomSet mode.
        Rules:
        1. After contest starts: can only add problems, cannot remove
        2. Before contest starts: if removing problems, must reallocate for all users

        Args:
            contest: The contest object
            pro_set_idx: Index of the problem set to update
            new_pro_set: List of (pro_id, score_type) tuples for the new problem set
        """
        if contest.contest_mode != ContestMode.RANDOM_SET:
            return ('Emod', 'Not a RandomSet contest'), None

        if pro_set_idx < 0 or pro_set_idx >= len(contest.pro_sets):
            return ('Eparam', 'Problem set index out of range'), None

        old_pro_set = contest.pro_sets[pro_set_idx]
        new_pro_ids = [pro_id for pro_id, _ in new_pro_set]

        # Check if problems are being removed
        old_pro_set_set = set(old_pro_set)
        new_pro_set_set = set(new_pro_ids)
        removed_pros = old_pro_set_set - new_pro_set_set

        # Rule 1: After contest starts, cannot remove problems
        if contest.is_start() and removed_pros:
            return ('Etime', 'Cannot remove problems from problem set after contest starts'), None

        for pro_id, _ in new_pro_set:
            if pro_id not in old_pro_set and pro_id in contest.pro_list:
                return ('Eexist', f'Problem {pro_id} is already in another problem set'), None

        async with self.db.acquire() as con:
            try:
                await con.execute(
                    '''
                    DELETE FROM contest_problem_joints
                    WHERE "contest_id" = $1 AND "order" = $2;
                    ''',
                    contest.contest_id, pro_set_idx
                )

                await con.executemany(
                    '''
                    INSERT INTO contest_problem_joints ("contest_id", "pro_id", "score_type", "order")
                    VALUES ($1, $2, $3, $4)
                    ''',
                    [(contest.contest_id, pro_id, int(score_type), pro_set_idx) for pro_id, score_type in new_pro_set]
                )
            except asyncpg.ForeignKeyViolationError:
                return ('Enoext', 'One or more problem IDs do not exist'), None

        for pro_id in removed_pros:
            contest.pro_list.pop(pro_id, None)

        for pro_id, score_type in new_pro_set:
            contest.pro_list[pro_id] = {
                "score_type": score_type,
            }

        contest.pro_sets[pro_set_idx] = new_pro_ids

        # Rule 2: If problems were removed before contest starts, reallocate
        if removed_pros and not contest.is_start():
            async with self.db.acquire() as con:
                await con.execute('''
                    DELETE FROM contest_acct_pro_joints
                    WHERE contest_id = $1 AND pro_id = ANY($2::integer[]);
                ''', contest.contest_id, list(removed_pros))

            for acct_id in contest.acct_pro_list:
                if len(contest.acct_pro_list[acct_id]) > pro_set_idx:
                    contest.acct_pro_list[acct_id].pop(pro_set_idx)

            await self.add_random_pro(contest, new_pro_ids, pro_set_idx)

        await self.rs.hset('contest', str(contest.contest_id), pickle.dumps(contest))

        return None, None

    async def reallocate_randomset_account_pro_set(self, contest: Contest, acct_id: int, pro_set_idx: int):
        """
        Reallocate a specific problem set for a specific account.
        Deletes existing allocation and reassigns a new random problem.
        """
        if contest.contest_mode != ContestMode.RANDOM_SET:
            return ('Einval', 'Not a RandomSet contest'), None

        if pro_set_idx < 0 or pro_set_idx >= len(contest.pro_sets):
            return ('Einval', 'Invalid problem set index'), None

        pro_set = contest.pro_sets[pro_set_idx]

        async with self.db.acquire() as con:
            await con.execute('''
                DELETE FROM contest_acct_pro_joints
                WHERE contest_id = $1 AND acct_id = $2 AND pro_id = ANY($3::integer[]);
            ''', contest.contest_id, acct_id, pro_set)

        if acct_id in contest.acct_pro_list and len(contest.acct_pro_list[acct_id]) > pro_set_idx:
            contest.acct_pro_list[acct_id].pop(pro_set_idx)

        await self.add_random_pro(contest, pro_set, pro_set_idx)
        await self.rs.hset('contest', str(contest.contest_id), pickle.dumps(contest))

        return None, None

    async def reallocate_randomset_all_accounts_pro_set(self, contest: Contest, pro_set_idx: int):
        """
        Reallocate a specific problem set for all accounts.
        """
        if contest.contest_mode != ContestMode.RANDOM_SET:
            return ('Einval', 'Not a RandomSet contest'), None

        if pro_set_idx < 0 or pro_set_idx >= len(contest.pro_sets):
            return ('Einval', 'Invalid problem set index'), None

        pro_set = contest.pro_sets[pro_set_idx]

        async with self.db.acquire() as con:
            await con.execute('''
                DELETE FROM contest_acct_pro_joints
                WHERE contest_id = $1 AND pro_id = ANY($2::integer[]);
            ''', contest.contest_id, pro_set)

        for acct_id in contest.acct_pro_list:
            if len(contest.acct_pro_list[acct_id]) > pro_set_idx:
                contest.acct_pro_list[acct_id].pop(pro_set_idx)

        await self.add_random_pro(contest, pro_set, pro_set_idx)
        await self.rs.hset('contest', str(contest.contest_id), pickle.dumps(contest))

        return None, None

    async def reallocate_randomset_account_all_pro_sets(self, contest: Contest, acct_id: int):
        """
        Reallocate all problem sets for a specific account.
        """
        if contest.contest_mode != ContestMode.RANDOM_SET:
            return ('Einval', 'Not a RandomSet contest'), None

        async with self.db.acquire() as con:
            await con.execute('''
                DELETE FROM contest_acct_pro_joints
                WHERE contest_id = $1 AND acct_id = $2;
            ''', contest.contest_id, acct_id)

        if acct_id in contest.acct_pro_list:
            contest.acct_pro_list[acct_id] = []

        for pro_set_idx, pro_set in enumerate(contest.pro_sets):
            await self.add_random_pro(contest, pro_set, pro_set_idx)

        await self.rs.hset('contest', str(contest.contest_id), pickle.dumps(contest))

        return None, None

    async def reallocate_randomset_all_accounts_all_pro_sets(self, contest: Contest):
        """
        Reallocate all problem sets for all accounts.
        Complete reallocation of the entire RandomSet.
        """
        if contest.contest_mode != ContestMode.RANDOM_SET:
            return ('Einval', 'Not a RandomSet contest'), None

        async with self.db.acquire() as con:
            await con.execute('''
                DELETE FROM contest_acct_pro_joints
                WHERE contest_id = $1;
            ''', contest.contest_id)

        contest.acct_pro_list.clear()

        for pro_set_idx, pro_set in enumerate(contest.pro_sets):
            await self.add_random_pro(contest, pro_set, pro_set_idx)

        await self.rs.hset('contest', str(contest.contest_id), pickle.dumps(contest))

        return None, None

    async def allocate_new_accounts(self, contest: Contest):
        """
        Allocate all problem sets to newly added accounts in RandomSet mode.
        This is called when new users are added to a RandomSet contest.

        Args:
            contest: The contest object
            acct_ids: List of account IDs that need allocation
        """
        if contest.contest_mode != ContestMode.RANDOM_SET:
            return None, None

        for pro_set_idx, pro_set in enumerate(contest.pro_sets):
            await self.add_random_pro(contest, pro_set, pro_set_idx)

        await self.rs.hset('contest', str(contest.contest_id), pickle.dumps(contest))

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

        prolist = contest.get_randomset_prolist(acct)
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
