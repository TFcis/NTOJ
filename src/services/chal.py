import datetime
import os

import config
from services.judge import JudgeServerClusterService
from services.log import LogService
from services.user import Account, UserConst
from services.pro import ProService


class ChalConst:
    STATE_AC = 1
    STATE_WA = 2
    STATE_RE = 3
    STATE_TLE = 4
    STATE_MLE = 5
    STATE_CE = 6
    STATE_ERR = 7
    STATE_JUDGE = 100
    STATE_NOTSTARTED = 101

    STATE_STR = {
        STATE_AC: 'AC',
        STATE_WA: 'WA',
        STATE_RE: 'RE',
        STATE_TLE: 'TLE',
        STATE_MLE: 'MLE',
        STATE_CE: 'CE',
        STATE_ERR: 'IE',
        STATE_JUDGE: 'JDG',
    }

    FILE_EXTENSION = {
        'gcc': 'c',
        'g++': 'cpp',
        'clang++': 'cpp',
        'rustc': 'rs',
        'python3': 'py',
    }

    COMPILER_NAME = {
        'gcc': 'GCC 9.4.0 C11',
        'g++': 'G++ 9.4.0 GNU++17',
        'clang++': 'Clang++ 10.0.0 C++17',
        'rustc': 'Rustc 1.65',
        'python3': 'CPython 3.8.10',
    }


class ChalService:
    STATE_AC = 1
    STATE_WA = 2
    STATE_RE = 3
    STATE_TLE = 4
    STATE_MLE = 5
    STATE_CE = 6
    STATE_ERR = 7
    STATE_JUDGE = 100
    STATE_NOTSTARTED = 101

    STATE_STR = {
        STATE_AC: 'Accepted',
        STATE_WA: 'Wrong Answer',
        STATE_RE: 'Runtime Error',
        STATE_TLE: 'Time Limit Exceed',
        STATE_MLE: 'Memory Limit Exceed',
        STATE_CE: 'Compile Error',
        STATE_ERR: 'Internal Error',
        STATE_JUDGE: 'Challenging',
        STATE_NOTSTARTED: 'Not Started',
    }

    def __init__(self, db, rs):
        self.db = db
        self.rs = rs

        ChalService.inst = self

    async def add_chal(self, pro_id, acct_id, comp_type, code):
        pro_id = int(pro_id)
        acct_id = int(acct_id)

        # TODO: Refactor ContestService

        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    INSERT INTO "challenge" ("pro_id", "acct_id", "compiler_type")
                    VALUES ($1, $2, $3) RETURNING "chal_id";
                ''',
                pro_id, acct_id, comp_type
            )
        if result.__len__() != 1:
            return 'Eunk', None
        result = result[0]

        chal_id = result['chal_id']

        file_ext = ChalConst.FILE_EXTENSION[comp_type]

        os.mkdir(f'code/{chal_id}')
        code_f = open(f'code/{chal_id}/main.{file_ext}', 'wb')
        code_f.write(code.encode('utf-8'))
        code_f.close()

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
                chal_id
            )

        tests = []
        for (test_idx, state, runtime, memory, response) in result:
            tests.append({
                'test_idx': test_idx,
                'state': state,
                'runtime': int(runtime),
                'memory': int(memory),
                'response': response,
            })

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
                chal_id
            )
        if result.__len__() != 1:
            return 'Enoext', None
        result = result[0]

        pro_id, acct_id, timestamp, comp_type, acct_name = result['pro_id'], result['acct_id'], result['timestamp'], result['compiler_type'], result['acct_name']
        response = ""

        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    SELECT "test_idx", "state", "runtime", "memory", "response"
                    FROM "test"
                    WHERE "chal_id" = $1 ORDER BY "test_idx" ASC;
                ''',
                chal_id
            )

        testl = []
        for (test_idx, state, runtime, memory, response) in result:
            response = response
            testl.append({
                'test_idx': test_idx,
                'state': state,
                'runtime': int(runtime),
                'memory': int(memory),
            })

        owner = await self.rs.get(f'{pro_id}_owner')
        unlock = [1]

        if acct.acct_id == acct_id:
            can_see_code = True

        elif acct.is_kernel() and (owner is None or acct.acct_id in config.lock_user_list) and acct.acct_id in config.can_see_code_user:
            # INFO: owner is problem uploader. if problem was locked, only problem owner can see submit code about this problem
            await LogService.inst.add_log(f"{acct.name} view the challenge {chal_id}", 'manage.chal.view')
            can_see_code = True

        else:
            can_see_code = False

        tz = datetime.timezone(datetime.timedelta(hours=+8))

        return (None, {
            'chal_id': chal_id,
            'pro_id': pro_id,
            'acct_id': acct_id,
            'acct_name': acct_name,
            'timestamp': timestamp.astimezone(tz),
            'testl': testl,
            'code': can_see_code,
            'response': response,
            'comp_type': comp_type,
        })

    async def emit_chal(self, chal_id, pro_id, testm_conf, comp_type, code_path, res_path):
        chal_id = int(chal_id)
        pro_id = int(pro_id)

        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    SELECT "acct_id", "timestamp" FROM "challenge"
                    WHERE "chal_id" = $1;
                ''',
                chal_id
            )
        if result.__len__() != 1:
            return 'Enoext', None
        result = result[0]

        # NOTE Recalculate problem rate
        await self.rs.hdel('pro_rate', str(pro_id))

        acct_id, timestamp = int(result['acct_id']), result['timestamp']

        async with self.db.acquire() as con:
            testl = []
            for test_idx, test_conf in testm_conf.items():
                testl.append({
                    'test_idx': test_idx,
                    'timelimit': test_conf['timelimit'],
                    'memlimit': test_conf['memlimit'],
                    'metadata': test_conf['metadata']
                })

                await con.execute(
                    '''
                        INSERT INTO "test"
                        ("chal_id", "acct_id", "pro_id", "test_idx", "state", "timestamp")
                        VALUES ($1, $2, $3, $4, $5, $6);
                    ''',
                    chal_id, acct_id, pro_id, int(test_idx), ChalService.STATE_JUDGE, timestamp
                )

        await self.rs.publish('materialized_view_req', (await self.rs.get('materialized_view_counter')))

        file_ext = ChalConst.FILE_EXTENSION[comp_type]

        try:
            code_f = open(f"code/{chal_id}/main.{file_ext}", 'rb')
            code_f.close()

        except FileNotFoundError:
            for test in testl:
                _, ret = await self.update_test(
                    chal_id,
                    test['test_idx'],
                    ChalService.STATE_ERR,
                    0,
                    0,
                    ''
                )
            return None, None

        chalmeta = test_conf['chalmeta']

        if test_conf['comp_type'] == 'makefile':
            comp_type = 'makefile'

        # await JudgeServerClusterService.inst.new_judge.send_to_compile(chal_id, code_path, file_ext, comp_type)

        """
        create submission
        chal_id, pro_id, code_path, res_path, metadata, comp_type, check_type 
        """
        # await JudgeServerClusterService.inst.send(json.dumps({
        #     'chal_id': chal_id,
        #     'test': testl,
        #     'code_path': code_path,
        #     'res_path': res_path,
        #     'metadata': chalmeta,
        #     'comp_type': comp_type,
        #     'check_type': test_conf['check_type'],
        # }))

        await self.rs.hdel('rate@kernel_True', str(acct_id))
        await self.rs.hdel('rate@kernel_False', str(acct_id))

        return None, None

    # TODO: Porformance test
    async def list_chal(self, off, num, acct: Account,
                        flt=None):

        if flt is None:
            flt = {'pro_id': None, 'acct_id': None, 'state': 0, 'compiler': 'all'}
        fltquery = await self._get_fltquery(flt)

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
                ''' + fltquery +
                f'''
                    ORDER BY "challenge"."timestamp" DESC OFFSET {off} LIMIT {num};
                '''
            )

        challist = []
        for (chal_id, pro_id, acct_id, comp_type, timestamp, acct_name,
             state, runtime, memory) in result:
            if state is None:
                state = ChalService.STATE_NOTSTARTED

            if runtime is None:
                runtime = 0
            else:
                runtime = int(runtime)

            if memory is None:
                memory = 0
            else:
                memory = int(memory)

            tz = datetime.timezone(datetime.timedelta(hours=+8))

            challist.append({
                'chal_id': chal_id,
                'pro_id': pro_id,
                'acct_id': acct_id,
                'comp_type': ChalConst.COMPILER_NAME[comp_type],
                'timestamp': timestamp.astimezone(tz),
                'acct_name': acct_name,
                'state': state,
                'runtime': runtime,
                'memory': memory
            })

        return None, challist

    async def get_stat(self, acct: Account, flt=None):
        fltquery = await self._get_fltquery(flt)
        min_accttype = min(acct.acct_type, UserConst.ACCTTYPE_USER)

        async with self.db.acquire() as con:
            result = await con.fetch(('SELECT COUNT(1) FROM "challenge" '
                                      'INNER JOIN "account" '
                                      'ON "challenge"."acct_id" = "account"."acct_id" '
                                      'LEFT JOIN "challenge_state" '
                                      'ON "challenge"."chal_id"="challenge_state"."chal_id" '
                                      f'WHERE "account"."acct_type" >= {min_accttype}' + fltquery + ';'))

        if result.__len__() != 1:
            return 'Eunk', None

        total_chal = result[0]['count']
        return (None, {
            'total_chal': total_chal
        })

    async def update_test(self, chal_id, test_idx, state, runtime, memory, response):
        chal_id = int(chal_id)
        async with self.db.acquire() as con:
            await con.execute(
                '''
                    UPDATE "test"
                    SET "state" = $1, "runtime" = $2, "memory" = $3, "response" = $4
                    WHERE "chal_id" = $5 AND "test_idx" = $6;
                ''',
                state, runtime, memory, response, chal_id, test_idx
            )

        await self.rs.publish('materialized_view_req', (await self.rs.get('materialized_view_counter')))

        return None, None

    async def _get_fltquery(self, flt):
        query = ' '
        if flt['pro_id'] is not None:
            query += 'AND ( "challenge"."pro_id" = 0 '
            for pro_id in flt['pro_id']:
                query += f' OR "challenge"."pro_id" = {pro_id} '
            query += ')'

        if flt['acct_id'] is not None:
            query += 'AND ( "challenge"."acct_id" = 0 '
            for acct_id in flt['acct_id']:
                query += f' OR "challenge"."acct_id" = {acct_id} '
            query += ')'

        if flt['state'] != 0:
            if flt['state'] == ChalService.STATE_NOTSTARTED:
                query += ' AND "challenge_state"."state" IS NULL '
            else:
                query += (' AND "challenge_state"."state" = ' + str(flt['state']) + ' ')

        if flt['compiler'] != 'all':
            query += f" AND \"challenge\".\"compiler_type\"=\'{flt['compiler']}\' "

        return query
