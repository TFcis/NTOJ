from dataclasses import dataclass
import datetime
import os

import config
from services.judge import JudgeServerClusterService
from services.pro import ProService
from services.user import Account


class ChalConst:
    STATE_AC = 1
    STATE_WA = 2
    STATE_RE = 3
    STATE_RESIG = 9
    STATE_TLE = 4
    STATE_MLE = 5
    STATE_CE = 6
    STATE_CLE = 10
    STATE_ERR = 7
    STATE_OLE = 8
    STATE_JUDGE = 100
    STATE_NOTSTARTED = 101

    STATE_STR = {
        STATE_AC: 'AC',
        STATE_WA: 'WA',
        STATE_RE: 'RE',
        STATE_RESIG: 'RE(SIG)',
        STATE_TLE: 'TLE',
        STATE_MLE: 'MLE',
        STATE_CE: 'CE',
        STATE_CLE: 'CLE',
        STATE_OLE: 'OLE',
        STATE_ERR: 'IE',
        STATE_JUDGE: 'JDG',
    }

    STATE_LONG_STR = {
        STATE_AC: 'Accepted',
        STATE_WA: 'Wrong Answer',
        STATE_RE: 'Runtime Error',
        STATE_RESIG: 'Runtime Error (Killed by signal)',
        STATE_TLE: 'Time Limit Exceed',
        STATE_MLE: 'Memory Limit Exceed',
        STATE_OLE: 'Output Limit Exceed',
        STATE_CE: 'Compile Error',
        STATE_CLE: 'Compilation Limit Exceed',
        STATE_ERR: 'Internal Error',
        STATE_JUDGE: 'Challenging',
        STATE_NOTSTARTED: 'Not Started',
    }

    FILE_EXTENSION = {
        'gcc': 'c',
        'clang': 'c',
        'g++': 'cpp',
        'clang++': 'cpp',
        'rustc': 'rs',
        'python3': 'py',
        'java': 'java',
    }

    ALLOW_COMPILERS = FILE_EXTENSION.keys()

    COMPILER_NAME = {
        'gcc': 'GCC 12.2.0 GNU11',
        'g++': 'G++ 12.2.0 GNU++17',
        'clang': 'Clang++ 15.0.6 C11',
        'clang++': 'Clang++ 15.0.6 C++17',
        'rustc': 'Rustc 1.63',
        'python3': 'CPython 3.11.2',
        'java': 'OpenJDK 17.0.8',
    }

    NORMAL_PRI = 0
    CONTEST_PRI = 1
    CONTEST_REJUDGE_PRI = 2
    NORMAL_REJUDGE_PRI = 3


@dataclass
class ChalSearchingParam:
    pro: list[int]
    acct: list[int]
    state: int
    compiler: str
    contest: int

    def get_sql_query_str(self):
        query = ' '
        if self.pro:
            query += 'AND ( "challenge"."pro_id" = 0 '
            for pro_id in self.pro:
                query += f' OR "challenge"."pro_id" = {pro_id} '
            query += ')'

        if self.acct:
            query += 'AND ( "challenge"."acct_id" = 0 '
            for acct_id in self.acct:
                query += f' OR "challenge"."acct_id" = {acct_id} '
            query += ')'

        if self.state != 0:
            if self.state == ChalConst.STATE_NOTSTARTED:
                query += ' AND "challenge_state"."state" IS NULL '
            else:
                query += f' AND "challenge_state"."state" = {self.state} '

        if self.compiler != 'all':
            query += f' AND \"challenge\".\"compiler_type\"=\'{self.compiler}\' '

        if self.contest != 0:
            query += f' AND "challenge"."contest_id"={self.contest} '
        else:
            query += ' AND "challenge"."contest_id"=0 '

        return query


class ChalSearchingParamBuilder:
    def __init__(self):
        self.param = ChalSearchingParam([], [], 0, "all", 0)

    def pro(self, pro: list[int]):
        self.param.pro = pro
        return self

    def acct(self, acct: list[int]):
        self.param.acct = acct
        return self

    def state(self, state: int):
        self.param.state = state
        return self

    def compiler(self, compiler: str):
        self.param.compiler = compiler
        return self

    def contest(self, contest: int):
        self.param.contest = contest
        return self

    def build(self) -> ChalSearchingParam:
        return self.param


class ChalService:
    def __init__(self, db, rs):
        self.db = db
        self.rs = rs

        ChalService.inst = self

    async def add_chal(self, pro_id: int, acct_id: int, contest_id: int, comp_type: str, code: str):
        pro_id = int(pro_id)
        acct_id = int(acct_id)

        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    INSERT INTO "challenge" ("pro_id", "acct_id", "compiler_type", "contest_id")
                    VALUES ($1, $2, $3, $4) RETURNING "chal_id";
                ''',
                pro_id,
                acct_id,
                comp_type,
                contest_id,
            )
        if len(result) != 1:
            return 'Eunk', None
        result = result[0]

        chal_id = result['chal_id']

        file_ext = ChalConst.FILE_EXTENSION[comp_type]

        os.mkdir(f'code/{chal_id}')
        with open(f"code/{chal_id}/main.{file_ext}", 'wb') as code_f:
            code_f.write(code.encode('utf-8'))

        return None, chal_id

    async def reset_chal(self, chal_id):
        chal_id = int(chal_id)
        async with self.db.acquire() as con:
            await con.execute('DELETE FROM "test" WHERE "chal_id" = $1;', chal_id)

        await self.update_challenge_state(chal_id)
        return None, None

    async def get_chal_state(self, chal_id):
        chal_id = int(chal_id)
        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    SELECT "test_idx", "state", "runtime", "memory", "response"
                    FROM "test"
                    WHERE "chal_id" = $1 ORDER BY "test_idx" ASC;
                ''',
                chal_id,
            )

        tests = []
        for test_idx, state, runtime, memory, response in result:
            tests.append(
                {
                    'test_idx': test_idx,
                    'state': state,
                    'runtime': int(runtime),
                    'memory': int(memory),
                    'response': response,
                }
            )

        return None, tests

    async def get_chal(self, chal_id):
        chal_id = int(chal_id)
        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    SELECT "challenge"."pro_id", "challenge"."acct_id",
                    "challenge"."timestamp", "challenge"."compiler_type", "challenge"."contest_id", "account"."name" AS "acct_name"
                    FROM "challenge"
                    INNER JOIN "account"
                    ON "challenge"."acct_id" = "account"."acct_id"
                    WHERE "chal_id" = $1;
                ''',
                chal_id,
            )
        if len(result) != 1:
            return 'Enoext', None

        result = result[0]

        pro_id, acct_id, timestamp, comp_type, contest_id, acct_name = (
            result['pro_id'],
            result['acct_id'],
            result['timestamp'],
            result['compiler_type'],
            result['contest_id'],
            result['acct_name'],
        )
        final_response = ""

        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    SELECT "test_idx", "state", "runtime", "memory", "response"
                    FROM "test"
                    WHERE "chal_id" = $1 ORDER BY "test_idx" ASC;
                ''',
                chal_id,
            )

        testl = []
        for test_idx, state, runtime, memory, response in result:
            if final_response == "":
                final_response = response

            testl.append(
                {
                    'test_idx': test_idx,
                    'state': state,
                    'runtime': int(runtime),
                    'memory': int(memory),
                }
            )

        owner = await self.rs.get(f'{pro_id}_owner')
        unlock = [1]

        tz = datetime.timezone(datetime.timedelta(hours=+8))

        return (
            None,
            {
                'chal_id': chal_id,
                'pro_id': pro_id,
                'acct_id': acct_id,
                'contest_id': contest_id,
                'acct_name': acct_name,
                'timestamp': timestamp.astimezone(tz),
                'testl': testl,
                'response': final_response,
                'comp_type': comp_type,
            },
        )

    async def emit_chal(self, chal_id, pro_id, testm_conf, comp_type, pri: int):
        from services.pro import ProConst
        chal_id = int(chal_id)
        pro_id = int(pro_id)

        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    SELECT "acct_id", "contest_id", "timestamp" FROM "challenge"
                    WHERE "chal_id" = $1;
                ''',
                chal_id,
            )
        if len(result) != 1:
            return 'Enoext', None
        result = result[0]

        acct_id, contest_id, timestamp = int(result['acct_id']), int(result['contest_id']), result['timestamp']
        limit = testm_conf['limit']

        if comp_type in limit:
            timelimit = limit[comp_type]['timelimit']
            memlimit = limit[comp_type]['memlimit']
        else:
            timelimit = limit['default']['timelimit']
            memlimit = limit['default']['memlimit']

        async with self.db.acquire() as con:
            testl = []
            insert_sql = []
            for test_group_idx, test in testm_conf['test_group'].items():
                testl.append(
                    {
                        'test_idx': test_group_idx,
                        'timelimit': timelimit,
                        'memlimit': memlimit,
                        'metadata': test['metadata'],
                    }
                )
                insert_sql.append(f'({chal_id}, {acct_id}, {pro_id}, {test_group_idx}, {ChalConst.STATE_JUDGE}, \'{timestamp}\')')

            await con.execute(
            f'''
                INSERT INTO "test"
                ("chal_id", "acct_id", "pro_id", "test_idx", "state", "timestamp") VALUES
                {','.join(insert_sql)};
            '''
            )

        await self.update_challenge_state(chal_id)

        file_ext = ChalConst.FILE_EXTENSION[comp_type]

        if not os.path.isfile(f"code/{chal_id}/main.{file_ext}"):
            for test in testl:
                await self.update_test(chal_id, test['test_idx'], ChalConst.STATE_ERR, 0, 0, '', refresh_db=False)
                await self.update_challenge_state(chal_id)
            return None, None

        chalmeta = testm_conf['chalmeta']

        if testm_conf['is_makefile']:
            comp_type = 'makefile'

        await JudgeServerClusterService.inst.send(
            {
                'pri': pri,
                'chal_id': chal_id,
                'test': testl,
                'code_path': f'{chal_id}/main.{file_ext}',
                'res_path': f'{pro_id}/res',
                'metadata': chalmeta,
                'comp_type': comp_type,
                'check_type': ProConst.CHECKER_TYPE[testm_conf['check_type']],
            },
            pro_id,
            contest_id,
        )

        await self.rs.hdel('rate', str(acct_id))

        return None, None

    async def list_chal(self, off, num, acct: Account, flt: ChalSearchingParam):

        fltquery = flt.get_sql_query_str()

        max_status = ProService.inst.get_acct_limit(acct, contest=flt.contest != 0)

        async with self.db.acquire() as con:
            result = await con.fetch(
                f'''
                    SELECT "challenge"."chal_id", "challenge"."pro_id", "challenge"."acct_id", "challenge"."contest_id",
                    "challenge"."compiler_type", "challenge"."timestamp", "account"."name" AS "acct_name",
                    "challenge_state"."state", "challenge_state"."runtime", "challenge_state"."memory"
                    FROM "challenge"
                    INNER JOIN "account"
                    ON "challenge"."acct_id" = "account"."acct_id"
                    INNER JOIN "problem"
                    ON "challenge"."pro_id" = "problem"."pro_id" AND "problem"."status" <= {max_status}
                    LEFT JOIN "challenge_state"
                    ON "challenge"."chal_id" = "challenge_state"."chal_id"
                    WHERE 1=1
                '''
                + fltquery
                + f'''
                    ORDER BY "challenge"."chal_id" DESC OFFSET {off} LIMIT {num};
                '''
            )

        challist = []
        for chal_id, pro_id, acct_id, contest_id, comp_type, timestamp, acct_name, state, runtime, memory in result:
            if state is None:
                state = ChalConst.STATE_NOTSTARTED

            if runtime is None:
                runtime = 0
            else:
                runtime = int(runtime)

            if memory is None:
                memory = 0
            else:
                memory = int(memory)

            tz = datetime.timezone(datetime.timedelta(hours=+8))

            challist.append(
                {
                    'chal_id': chal_id,
                    'pro_id': pro_id,
                    'acct_id': acct_id,
                    'contest_id': contest_id,
                    'comp_type': ChalConst.COMPILER_NAME[comp_type],
                    'timestamp': timestamp.astimezone(tz),
                    'acct_name': acct_name,
                    'state': state,
                    'runtime': runtime,
                    'memory': memory,
                }
            )

        return None, challist

    async def get_single_chal_state_in_list(
            self,
            chal_id: int,
            acct: Account,
    ):
        chal_id = int(chal_id)
        max_status = ProService.inst.get_acct_limit(acct)

        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    SELECT "challenge"."chal_id", "challenge_state"."state", "challenge_state"."runtime", "challenge_state"."memory"
                    FROM "challenge"
                    INNER JOIN "account" ON "challenge"."acct_id" = "account"."acct_id"
                    INNER JOIN "problem" ON "challenge"."pro_id" = "problem"."pro_id"
                    INNER JOIN "challenge_state" ON "challenge"."chal_id" = "challenge_state"."chal_id"
                    WHERE "problem"."status" <= $1 AND "challenge_state"."chal_id" = $2;
                ''',
                max_status,
                chal_id,
            )

        if len(result) != 1:
            return 'Enoext', None
        result = result[0]

        return None, {
            'chal_id': chal_id,
            'state': result['state'],
            'runtime': int(result['runtime']),
            'memory': int(result['memory']),
        }

    async def get_stat(self, acct: Account, flt: ChalSearchingParam):
        fltquery = flt.get_sql_query_str()

        async with self.db.acquire() as con:
            result = await con.fetch(
                (
                        'SELECT COUNT(1) FROM "challenge" '
                        'INNER JOIN "account" '
                        'ON "challenge"."acct_id" = "account"."acct_id" '
                        'LEFT JOIN "challenge_state" '
                        'ON "challenge"."chal_id"="challenge_state"."chal_id" '
                        'WHERE 1=1' + fltquery + ';'
                )
            )

        if len(result) != 1:
            return 'Eunk', None

        total_chal = result[0]['count']
        return None, {'total_chal': total_chal}

    async def update_test(self, chal_id, test_idx, state, runtime, memory, response, refresh_db=True):
        chal_id = int(chal_id)
        async with self.db.acquire() as con:
            await con.execute(
                '''
                    UPDATE "test"
                    SET "state" = $1, "runtime" = $2, "memory" = $3, "response" = $4
                    WHERE "chal_id" = $5 AND "test_idx" = $6;
                ''',
                state,
                runtime,
                memory,
                response,
                chal_id,
                test_idx,
            )

        if refresh_db:
            await self.update_challenge_state(chal_id)

        return None, None

    async def update_challenge_state(self, chal_id: int):
        await self.db.execute(f'SELECT update_challenge_state({chal_id});')
