import datetime

from utils.req import RequestHandler, reqenv

class RankService:
    def __init__(self, db, rs) -> None:
        self.db = db
        self.rs = rs
        RankService.inst = self

class RankHandler(RequestHandler):
    @reqenv
    async def get(self, pro_id):
        tz = datetime.timezone(datetime.timedelta(hours=+8))
        pro_id = int(pro_id)

        async with self.db.acquire() as con:
            result = await con.fetch('SELECT *'
                'FROM ('
                'SELECT DISTINCT ON ("challenge"."acct_id")'
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
                'WHERE "account"."acct_type">= $1 AND "challenge"."pro_id"= $2 '
                'AND "challenge_state"."state"=1 '
                'ORDER BY "challenge"."acct_id" ASC, '
                '"challenge_state"."runtime" ASC, "challenge_state"."memory" ASC,'
                '"challenge"."timestamp" ASC, "challenge"."acct_id" ASC'
                ') temp '
                'ORDER BY "runtime" ASC, "memory" ASC,'
                '"timestamp" ASC, "acct_id" ASC;',
                self.acct['acct_type'], pro_id)

        chal_list = []
        for (chal_id, acct_id, timestamp, acct_name, runtime, memory) in result:
            chal_list.append({
                'chal_id'   : chal_id,
                'acct_id'   : acct_id,
                'acct_name' : acct_name,
                'runtime'   : int(runtime),
                'memory'    : int(memory),
                'timestamp' : timestamp.astimezone(tz).isoformat(timespec="seconds"),
            })

        await self.render('rank', pro_id=pro_id, chal_list=chal_list)
        return

    @reqenv
    async def post(self):
        return
