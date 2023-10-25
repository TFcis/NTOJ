import json

from services.pro import ProService
from services.rate import RateService
from services.user import UserService
from handlers.base import RequestHandler, reqenv


class ApiHandler(RequestHandler):
    @reqenv
    async def get(self):
        pass

    @reqenv
    async def post(self):
        reqtype = str(self.get_argument('reqtype'))
        if reqtype == 'AC':
            acct_id = int(self.get_argument('acct_id'))
            err, prolist = await ProService.inst.list_pro(acct=None, clas=1)
            err, ratemap = await RateService.inst.map_rate(clas=1)
            prolist2 = []
            for pro in prolist:
                pro_id = pro['pro_id']
                if acct_id in ratemap and pro_id in ratemap[acct_id]:
                    rate = ratemap[acct_id][pro_id]
                    if rate['rate'] >= 100:
                        prolist2.append(pro_id)
            self.finish(str(json.dumps({'ac': prolist2})))
            return

        elif reqtype == 'NA':
            acct_id = int(self.get_argument('acct_id'))
            err, acct = await UserService.inst.info_acct(acct_id)

            max_status = ProService.inst.get_acct_limit(acct)
            async with self.db.acquire() as con:
                prolist = await con.fetch(
                    '''
                        SELECT "pro_id" FROM "problem"
                        WHERE "status" <= $1
                        ORDER BY "pro_id" ASC;
                    ''',
                    max_status
                )

            err, ratemap = await RateService.inst.map_rate_acct(acct=acct, clas=1)
            prolist2 = []
            for pro in prolist:
                pro_id = pro['pro_id']
                if (rate := ratemap.get(pro_id)) != None:
                    if rate['rate'] < 100:
                        prolist2.append(pro_id)
            self.finish(str(json.dumps({'na': prolist2})))
            return

        elif reqtype == 'INFO':
            acct_id = int(self.get_argument('acct_id'))
            err, acct = await UserService.inst.info_acct(acct_id)
            if err:
                self.finish(err)
                return

            err, rate = await RateService.inst.get_acct_rate_and_chal_cnt(acct)
            rate = rate['rate']

            if rate == None:
                rate = 0
            self.finish(str(json.dumps({'nick': acct.name, 'score': rate})))
            return
