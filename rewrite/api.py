import json

from req import Service, RequestHandler, reqenv

class ApiService:
    def __init__(self, db, rs) -> None:
        self.db = db
        self.rs = rs
        ApiService.inst = self

    def gen_json(self, _list):
        return json.dumps(_list)

class ApiHandler(RequestHandler):
    @reqenv
    async def get(self):
        pass

    @reqenv
    async def post(self):
        reqtype = str(self.get_argument('reqtype'))
        if reqtype == 'AC':
            acct_id = int(self.get_argument('acct_id'))
            err, prolist = await Service.Pro.list_pro(acct=None, clas=1)
            err, ratemap = await Service.Rate.map_rate(clas=1)
            prolist2 = []
            for pro in prolist:
                pro_id = pro['pro_id']
                if acct_id in ratemap and pro_id in ratemap[acct_id]:
                    rate = ratemap[acct_id][pro_id]
                    if rate['rate'] >= 100:
                        prolist2.append(pro_id)
            self.finish(str(Service.Api.gen_json({'ac': prolist2})))
            return

        elif reqtype == 'NA':
            acct_id = int(self.get_argument('acct_id'))
            err, acct = await Service.Acct.info_acct(acct_id)

            max_status = await Service.Pro.get_acct_limit(acct)
            async with self.db.acquire() as con:
                prolist = await con.fetch(
                    '''
                        SELECT "pro_id" FROM "problem"
                        WHERE "status" <= $1
                        ORDER BY "pro_id" ASC;
                    ''',
                    max_status
                )

            err, ratemap = await Service.Rate.map_rate_acct(acct=acct, clas=1)
            prolist2 = []
            for pro in prolist:
                pro_id = pro['pro_id']
                if (rate := ratemap.get(pro_id)) != None:
                    if rate['rate'] < 100:
                        prolist2.append(pro_id)
            self.finish(str(Service.Api.gen_json({'na': prolist2})))
            return

        elif reqtype == 'INFO':
            acct_id = int(self.get_argument('acct_id'))
            err, acct = await Service.Acct.info_acct(acct_id)
            if err:
                self.finish(err)
                return

            err, rate = await Service.Rate.get_acct_rate_and_chal_cnt(acct)
            rate = rate['rate']

            if rate == None:
                rate = 0
            self.finish(str(Service.Api.gen_json({'nick': acct['name'], 'score': rate})))
            return

