import os
import json
import msgpack
import tornado.web
import psycopg2
from req import Service
from req import RequestHandler
from req import reqenv
from user import UserConst
from user import UserService

class TotalRankService:
    def __init__(self, db, rs):
        self.db = db
        self.rs = rs
        RankService.inst = self

class TotalRankHandler(RequestHandler):
    @reqenv
    def get(self, pro_id):
        pro_id = int(pro_id)
        cur = yield self.db.cursor()
        yield cur.execute(('SELECT '
            '"challenge"."chal_id",'
            '"challenge"."acct_id",'
            '"challenge"."timestamp",'
            '"account"."name" AS "acct_name",'
            '"challenge_state"."runtime",'
            '"challenge_state"."memory" '
            'FROM "challenge" '
            'INNER JOIN "account" '
            'ON "challenge"."acct_id"="account"."acct_id" '
            'LEFT JOIN "challenge_state" '
            'ON "challenge"."chal_id"="challenge_state"."chal_id" '
            'WHERE "account"."acct_type">=%s AND "challenge"."pro_id"=%s '
            'AND "challenge_state"."state"=1 '
            'ORDER BY "challenge_state"."runtime" ASC,"challenge_state"."memory" ASC,'
            '"challenge"."timestamp" ASC,"account"."acct_id" ASC;'),
            (self.acct['acct_type'], pro_id, ))
        chal_list = list()
        for chal_id, acct_id, timestamp, acct_name, runtime, memory in cur:
            runtime = int(runtime)
            memory = int(memory)
            chal_list.append({
                'chal_id'   : chal_id,
                'acct_id'   : acct_id,
                'acct_name' : acct_name,
                'runtime'   : runtime,
                'memory'    : memory,
                'timestamp' : timestamp,
            })
        self.render('rank', pro_id=pro_id, chal_list=chal_list)
        return

    @reqenv
    def post(self):
        return
