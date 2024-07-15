from dataclasses import dataclass
import datetime
import json
import os

import config
from services.judge import JudgeServerClusterService
from services.log import LogService
from services.pro import ProService
from services.user import Account, UserConst


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

    COMPILER_NAME = {
        'gcc': 'GCC 12.2.0 GNU11',
        'g++': 'G++ 12.2.0 GNU++17',
        'clang': 'Clang++ 15.0.6 C11',
        'clang++': 'Clang++ 15.0.6 C++17',
        'rustc': 'Rustc 1.63',
        'python3': 'CPython 3.11.2',
        'java': 'OpenJDK 17.0.8',
    }


@dataclass
class ChalSearchingParam:
    pro: list[int]
    acct: list[int]
    state: int
    compiler: str

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
            query += f" AND \"challenge\".\"compiler_type\"=\'{self.compiler}\' "

        return query


class ChalSearchingParamBuilder:
    def __init__(self):
        self.param = ChalSearchingParam([], [], 0, "all")

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

    def build(self) -> ChalSearchingParam:
        return self.param


class ChalService:
    def __init__(self, db, rs):
        self.db = db
        self.rs = rs

        ChalService.inst = self

    async def add_chal(self, pro_id, acct_id, comp_type, code):
        pro_id = int(pro_id)
        acct_id = int(acct_id)

        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    INSERT INTO "challenge" ("pro_id", "acct_id", "compiler_type")
                    VALUES ($1, $2, $3) RETURNING "chal_id";
                ''',
                pro_id,
                acct_id,
                comp_type,
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

        await self.rs.publish('materialized_view_req', (await self.rs.get('materialized_view_counter')))

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

    async def get_chal(self, chal_id, acct: Account):
        chal_id = int(chal_id)
        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    SELECT "challenge"."pro_id", "challenge"."acct_id",
                    "challenge"."timestamp", "challenge"."compiler_type", "account"."name" AS "acct_name"
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

        pro_id, acct_id, timestamp, comp_type, acct_name = (
            result['pro_id'],
            result['acct_id'],
            result['timestamp'],
            result['compiler_type'],
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

        if acct.acct_id == acct_id:
            can_see_code = True

        elif (
                acct.is_kernel()
                and (owner is None or acct.acct_id in config.lock_user_list)
                and acct.acct_id in config.can_see_code_user
        ):
            # INFO: owner is problem uploader. if problem was locked, only problem owner can see submit code about this problem
            await LogService.inst.add_log(f"{acct.name} view the challenge {chal_id}", 'manage.chal.view')
            can_see_code = True

        else:
            can_see_code = False

        tz = datetime.timezone(datetime.timedelta(hours=+8))

        return (
            None,
            {
                'chal_id': chal_id,
                'pro_id': pro_id,
                'acct_id': acct_id,
                'acct_name': acct_name,
                'timestamp': timestamp.astimezone(tz),
                'testl': testl,
                'code': can_see_code,
                'response': final_response,
                'comp_type': comp_type,
            },
        )

    async def emit_chal(self, chal_id, pro_id, testm_conf, comp_type, code_path, res_path):
        chal_id = int(chal_id)
        pro_id = int(pro_id)

        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    SELECT "acct_id", "timestamp" FROM "challenge"
                    WHERE "chal_id" = $1;
                ''',
                chal_id,
            )
        if len(result) != 1:
            return 'Enoext', None
        result = result[0]

        acct_id, timestamp = int(result['acct_id']), result['timestamp']

        async with self.db.acquire() as con:
            testl = []
            for test_idx, test_conf in testm_conf.items():
                testl.append(
                    {
                        'test_idx': test_idx,
                        'timelimit': test_conf['timelimit'],
                        'memlimit': test_conf['memlimit'],
                        'metadata': test_conf['metadata'],
                    }
                )

                await con.execute(
                    '''
                        INSERT INTO "test"
                        ("chal_id", "acct_id", "pro_id", "test_idx", "state", "timestamp")
                        VALUES ($1, $2, $3, $4, $5, $6);
                    ''',
                    chal_id,
                    acct_id,
                    pro_id,
                    test_idx,
                    ChalConst.STATE_JUDGE,
                    timestamp,
                )

        await self.rs.publish('materialized_view_req', (await self.rs.get('materialized_view_counter')))

        file_ext = ChalConst.FILE_EXTENSION[comp_type]

        try:
            code_f = open(f"code/{chal_id}/main.{file_ext}", 'rb')
            code_f.close()

        except FileNotFoundError:
            for test in testl:
                await self.update_test(chal_id, test['test_idx'], ChalConst.STATE_ERR, 0, 0, '', refresh_db=False)
            await self.rs.publish('materialized_view_req', (await self.rs.get('materialized_view_counter')))
            return None, None

        chalmeta = test_conf['chalmeta']

        if test_conf['comp_type'] == 'makefile':
            comp_type = 'makefile'

        await JudgeServerClusterService.inst.send(
            {
                'pri': 1,
                'chal_id': chal_id,
                'test': testl,
                'code_path': code_path,
                'res_path': res_path,
                'metadata': chalmeta,
                'comp_type': comp_type,
                'check_type': test_conf['check_type'],
            },
            1,
            pro_id,
        )

        await self.rs.hdel('rate@kernel_True', str(acct_id))
        await self.rs.hdel('rate@kernel_False', str(acct_id))

        return None, None

    async def list_chal(self, off, num, acct: Account, flt: ChalSearchingParam):

        fltquery = flt.get_sql_query_str()

        max_status = ProService.inst.get_acct_limit(acct)
        min_accttype = min(acct.acct_type, UserConst.ACCTTYPE_USER)

        async with self.db.acquire() as con:
            result = await con.fetch(
                f'''
                    SELECT "challenge"."chal_id", "challenge"."pro_id", "challenge"."acct_id",
                    "challenge"."compiler_type", "challenge"."timestamp", "account"."name" AS "acct_name",
                    "challenge_state"."state", "challenge_state"."runtime", "challenge_state"."memory"
                    FROM "challenge"
                    INNER JOIN "account"
                    ON "challenge"."acct_id" = "account"."acct_id"
                    INNER JOIN "problem"
                    ON "challenge"."pro_id" = "problem"."pro_id" AND "problem"."status" <= {max_status}
                    LEFT JOIN "challenge_state"
                    ON "challenge"."chal_id" = "challenge_state"."chal_id"
                    WHERE "account"."acct_type" >= {min_accttype}
                '''
                + fltquery
                + f'''
                    ORDER BY "challenge"."timestamp" DESC OFFSET {off} LIMIT {num};
                '''
            )

        challist = []
        for chal_id, pro_id, acct_id, comp_type, timestamp, acct_name, state, runtime, memory in result:
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
        min_accttype = min(acct.acct_type, UserConst.ACCTTYPE_USER)

        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    SELECT "challenge"."chal_id", "challenge_state"."state", "challenge_state"."runtime", "challenge_state"."memory"
                    FROM "challenge"
                    INNER JOIN "account" ON "challenge"."acct_id" = "account"."acct_id"
                    INNER JOIN "problem" ON "challenge"."pro_id" = "problem"."pro_id"
                    INNER JOIN "challenge_state" ON "challenge"."chal_id" = "challenge_state"."chal_id"
                    WHERE "account"."acct_type" >= $1 AND "problem"."status" <= $2 AND "challenge_state"."chal_id" = $3;
                ''',
                min_accttype,
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
        min_accttype = min(acct.acct_type, UserConst.ACCTTYPE_USER)

        async with self.db.acquire() as con:
            result = await con.fetch(
                (
                        'SELECT COUNT(1) FROM "challenge" '
                        'INNER JOIN "account" '
                        'ON "challenge"."acct_id" = "account"."acct_id" '
                        'LEFT JOIN "challenge_state" '
                        'ON "challenge"."chal_id"="challenge_state"."chal_id" '
                        f'WHERE "account"."acct_type" >= {min_accttype}' + fltquery + ';'
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
            await self.rs.publish('materialized_view_req', (await self.rs.get('materialized_view_counter')))

        return None, None
