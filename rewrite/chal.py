from multiprocessing import shared_memory
import os
import json
import msgpack
import asyncio

from tornado.gen import coroutine
from tornado.websocket import websocket_connect
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter

import config
from user import UserConst
from req import Service
from log import LogService

from dbg import dbg_print

class ChalConst:
    STATE_AC         = 1
    STATE_WA         = 2
    STATE_RE         = 3
    STATE_TLE        = 4
    STATE_MLE        = 5
    STATE_CE         = 6
    STATE_ERR        = 7
    STATE_JUDGE      = 100
    STATE_NOTSTARTED = 101

    STATE_STR = {
        STATE_AC    : 'AC',
        STATE_WA    : 'WA',
        STATE_RE    : 'RE',
        STATE_TLE   : 'TLE',
        STATE_MLE   : 'MLE',
        STATE_CE    : 'CE',
        STATE_ERR   : 'IE',
        STATE_JUDGE : 'JDG',
    }

class DokiDokiService:
    def __init__(self) -> None:
        self.ws = None
        self.doki = shared_memory.SharedMemory(create=False, name='doki_share_memory')
        DokiDokiService.inst = self

    async def collect_judge(self):
        #INFO: connect fronted to backend
        if self.ws == None:
            try:
                self.doki.buf[0] = False
                self.ws = await websocket_connect(config.PATH_JUDGE)

            except Exception as e:
                dbg_print('chal.py', 53, exception=e)
                self.doki.buf[0] = False
                return

            self.doki.buf[0] = True

        while True:
            try:
                self.ws.ping()
                self.doki.buf[1] = False
            except Exception as e:
                dbg_print('chal.py', 69, exception=e)
                self.doki.buf[0] = False
                dbg_print('chal.py', 72, judge_status=Service.doki.buf[0])
                if self.doki.buf[1] == True:
                    self.ws = await websocket_connect(config.PATH_JUDGE)
                    self.doki.buf[1] = False
                    self.doki.buf[0] = True

            await asyncio.sleep(5)

class ChalService:
    STATE_AC         = 1
    STATE_WA         = 2
    STATE_RE         = 3
    STATE_TLE        = 4
    STATE_MLE        = 5
    STATE_CE         = 6
    STATE_ERR        = 7
    STATE_JUDGE      = 100
    STATE_NOTSTARTED = 101

    STATE_STR = {
        STATE_AC         : 'Accepted',
        STATE_WA         : 'Wrong Answer',
        STATE_RE         : 'Runtime Error',
        STATE_TLE        : 'Time Limit Exceed',
        STATE_MLE        : 'Memory Limit Exceed',
        STATE_CE         : 'Compile Error',
        STATE_ERR        : 'Internal Error',
        STATE_JUDGE      : 'Challenging',
        STATE_NOTSTARTED : 'Not Started',
    }

    def __init__(self, db, rs):
        self.db = db
        self.rs = rs
        self.ws = None

        ChalService.inst = self

    async def add_chal(self, pro_id, acct_id, code: str):
        if (await Service.Contest.running())[1] == False:
            return ('Eacces', None)

        result = await self.db.fetch(
            '''
                INSERT INTO "challenge" ("pro_id", "acct_id")
                VALUES ($1, $2) RETURNING "chal_id";
            ''',
            int(pro_id), int(acct_id)
        )
        if result.__len__() != 1:
            return ('Eunk', None)
        result = result[0]


        chal_id = result['chal_id']

        os.mkdir(f'code/{chal_id}')
        code_f = open(f'code/{chal_id}/main.cpp', 'wb')
        code_f.write(code.encode('utf-8'))
        code_f.close()

        return (None, chal_id)

    async def reset_chal(self, chal_id):
        await self.db.execute('DELETE FROM "test" WHERE "chal_id" = $1;', int(chal_id))

        await self.rs.publish('materialized_view_req', (await self.rs.get('materialized_view_counter')))
        await self.rs.delete('rate@kernel_True')
        await self.rs.delete('rate@kernel_False')

        return (None, None)

    async def get_chal(self, chal_id, acct):
        chal_id = int(chal_id)
        result = await self.db.fetch(
            '''
                SELECT "challenge"."pro_id", "challenge"."acct_id",
                "challenge"."timestamp", "account"."name" AS "acct_name"
                FROM "challenge"
                INNER JOIN "account"
                ON "challenge"."acct_id" = "account"."acct_id"
                WHERE "chal_id" = $1;
            ''',
            chal_id
        )
        if result.__len__() != 1:
            return ('Enoext', None)
        result = result[0]

        pro_id, acct_id, timestamp, acct_name = result['pro_id'], result['acct_id'], result['timestamp'], result['acct_name']

        result = await self.db.fetch(
            '''
                SELECT "test_idx", "state", "runtime", "memory"
                FROM "test"
                WHERE "chal_id" = $1 ORDER BY "test_idx" ASC;
            ''',
            chal_id
        )

        testl = []
        for (test_idx, state, runtime, memory) in result:
            testl.append({
                'test_idx' : test_idx,
                'state'    : state,
                'runtime'  : int(runtime),
                'memory'   : int(memory),
            })

        owner = await self.rs.get(f'{pro_id}_owner')
        unlock = [1]
        if (acct['acct_id'] == acct_id or
                (acct['acct_type'] == UserConst.ACCTTYPE_KERNEL and
                    (owner == None or acct['acct_id'] in config.lock_user_list) and (acct['acct_id'] in config.can_see_code_user))):
                # owner is problem uploader. if problem was locked, only problem owner can see submit code about this problem

            if (acct['acct_type'] == UserConst.ACCTTYPE_KERNEL) and (acct['acct_id'] != acct_id):
                await LogService.inst.add_log(f"{acct['name']} view the challenge {chal_id}")

            try:
                with open(f'code/{chal_id}/main.cpp', 'rb') as code_f:
                    code = code_f.read().decode('utf-8')

            except FileNotFoundError:
                code = 'EROOR: The code is lost on server.'

        else:
            code = None

        return (None, {
            'chal_id'   : chal_id,
            'pro_id'    : pro_id,
            'acct_id'   : acct_id,
            'acct_name' : acct_name,
            'timestamp' : timestamp,
            'testl'     : testl,
            'code'      : code
        })

    async def emit_chal(self, chal_id, pro_id, testm_conf, code_path, res_path):
        chal_id = int(chal_id)
        result = await self.db.fetch(
            '''
                SELECT "acct_id", "timestamp" FROM "challenge"
                WHERE "chal_id" = $1;
            ''',
            chal_id
        )
        if result.__len__() != 1:
            return ('Enoext', None)
        result = result[0]

        acct_id, timestamp = result['acct_id'], result['timestamp']

        testl = []
        for test_idx, test_conf in testm_conf.items():
            testl.append({
                'test_idx'  : test_idx,
                'timelimit' : test_conf['timelimit'],
                'memlimit'  : test_conf['memlimit'],
                'metadata'  : test_conf['metadata']
            })

            await self.db.execute(
                '''
                    INSERT INTO "test"
                    ("chal_id", "acct_id", "pro_id", "test_idx", "state", "timestamp")
                    VALUES ($1, $2, $3, $4, $5, $6);
                ''',
                chal_id, int(acct_id), int(pro_id), int(test_idx), ChalService.STATE_JUDGE, timestamp
            )

        await self.rs.publish('materialized_view_req', (await self.rs.get('materialized_view_counter')))
        if self.ws == None:
            self.ws = await websocket_connect(config.PATH_JUDGE)

        try:
            code_f = open(f'code/{chal_id}/main.cpp', 'rb')
            code = code_f.read().decode('utf-8')
            code_f.close()

        except FileNotFoundError:
            for test in testl:
                err, ret = await self.update_test(chal_id, test['test_idx'],
                        ChalService.STATE_ERR, 0, 0, '')
            return (None, None)

        chalmeta = test_conf['chalmeta']
        self.ws.write_message(json.dumps({
            'chal_id'    : chal_id,
            'test'       : testl,
            'code_path'  : code_path,
            'res_path'   : res_path,
            'code'       : code,
            'metadata'   : chalmeta,
            'comp_type'  : test_conf['comp_type'],
            'check_type' : test_conf['check_type'],
        }))

        '''tmp_ws.write_message(json.dumps({
            'chal_id':chal_id,
            'testl':testl,
            'code_path':code_path,
            'res_path':res_path
        }))'''
        return (None, None)

    #TODO: Porformance test
    async def list_chal(self, off, num, min_accttype=UserConst.ACCTTYPE_USER,
            flt = {'pro_id': None, 'acct_id': None, 'state': 0}):

        fltquery = await self._get_fltquery(flt)

        result = await self.db.fetch(
            f'''
                SELECT "challenge"."chal_id", "challenge"."pro_id", "challenge"."acct_id",
                "challenge"."timestamp", "account"."name" AS "acct_name",
                "challenge_state"."state", "challenge_state"."runtime", "challenge_state"."memory"
                FROM "challenge"
                INNER JOIN "account"
                ON "challenge"."acct_id" = "account"."acct_id"
                LEFT JOIN "challenge_state"
                ON "challenge"."chal_id" = "challenge_state"."chal_id"
                WHERE "account"."acct_type" >= {min_accttype}
            ''' + fltquery +
            f'''
                ORDER BY "challenge"."timestamp" DESC OFFSET {off} LIMIT {num};
            '''
        )

        challist = []
        for (chal_id, pro_id, acct_id, timestamp, acct_name,
                state, runtime, memory) in result:
            if state == None:
                state = ChalService.STATE_NOTSTARTED

            if runtime == None:
                runtime = 0
            else:
                runtime = int(runtime)

            if memory == None:
                memory = 0
            else:
                memory = int(memory)

            challist.append({
                'chal_id'   : chal_id,
                'pro_id'    : pro_id,
                'acct_id'   : acct_id,
                'timestamp' : timestamp,
                'acct_name' : acct_name,
                'state'     : state,
                'runtime'   : runtime,
                'memory'    : memory
            })
        return (None, challist)

    async def get_stat(self, min_accttype=UserConst.ACCTTYPE_USER, flt=None):
        fltquery = await self._get_fltquery(flt)

        result = await self.db.fetch(('SELECT COUNT(1) FROM "challenge" '
            'INNER JOIN "account" '
            'ON "challenge"."acct_id" = "account"."acct_id" '
            'LEFT JOIN "challenge_state" '
            'ON "challenge"."chal_id"="challenge_state"."chal_id" '
            f'WHERE "account"."acct_type" >= {min_accttype}' + fltquery + ';'))

        if result.__len__() != 1:
            return ('Eunk', None)

        total_chal = result[0]['count']
        return (None, {
            'total_chal': total_chal
        })

    async def update_test(self, chal_id, test_idx, state, runtime, memory, response):
        result = await self.db.fetch(
            '''
                UPDATE "test"
                SET "state" = $1, "runtime" = $2, "memory" = $3, "response" = $4
                WHERE "chal_id" = $5 AND "test_idx" = $6;
            ''',
            state, runtime, memory, response, int(chal_id), test_idx
        )

        #TODO: redis publish materialized_view_req
        await self.rs.publish('materialized_view_req', (await self.rs.get('materialized_view_counter')))
        await self.rs.delete('prolist')
        await self.rs.delete('rate@kernel_True')
        await self.rs.delete('rate@kernel_False')

        return (None, None)

    async def _get_fltquery(self, flt):
        query = ' '
        if flt['pro_id'] != None:
            query += 'AND ( "challenge"."pro_id" = 0 '
            for pro_id in flt['pro_id']:
                query += f' OR "challenge"."pro_id" = {pro_id} '
            query += ')'

        if flt['acct_id'] != None:
            query += 'AND ( "challenge"."acct_id" = 0 '
            for acct_id in flt['acct_id']:
                query += f' OR "challenge"."acct_id" = {acct_id} '
            query += ')'

        if flt['state'] != 0:
            if flt['state'] == ChalService.STATE_NOTSTARTED:
                query += ' AND "challenge_state"."state" IS NULL '
            else:
                query += (' AND "challenge_state"."state" = ' + str(flt['state']) + ' ')

        return (query)

    async def collect_judge(self):
        #INFO: connect fronted to backend
        dbg_print(__file__, 393, r='r')
        dbg_print(__file__, 395, doki=Service.doki.buf[0])
        # if self.ws == None:
        # if self.doki.buf[0] == False:
        if Service.doki.buf[0] == False:
            try:
                Service.doki.buf[0] = False
                self.ws = await websocket_connect(config.PATH_JUDGE)

            except Exception as e:
                dbg_print('chal.py', 394, exception=e)
                Service.doki.buf[0] = False
                return

            Service.doki.buf[0] = True
            Service.doki.buf[1] = True

        while True:
            ret = await self.ws.read_message()
            if ret == None:
                break

            res = json.loads(ret)
            if res['result'] != None:
                for result in res['result']:
                    err, ret = await self.update_test(
                        res['chal_id'],
                        result['test_idx'],
                        result['state'],
                        result['runtime'],
                        result['peakmem'],
                        ret)

        return

