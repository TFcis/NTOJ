import asyncio
import json
import tornado.web

from services.user import UserService, UserConst
from services.chal import ChalService, ChalConst
from services.pro import ProService
from utils.req import RequestHandler, reqenv
from utils.req import WebSocketHandler


class ChalListHandler(RequestHandler):
    @reqenv
    async def get(self):
        try:
            off = int(self.get_argument('off'))

        except tornado.web.HTTPError:
            off = 0

        try:
            ppro_id = str(self.get_argument('proid'))
            tmp_pro_id = ppro_id.replace(' ', '').split(',')
            pro_id = []
            for p in tmp_pro_id:
                try:
                    pro_id.append(int(p))
                except ValueError:
                    pass

            if len(pro_id) == 0:
                pro_id = None

        except tornado.web.HTTPError:
            pro_id = None
            ppro_id = ''

        try:
            pacct_id = str(self.get_argument('acctid'))
            tmp_acct_id = pacct_id.replace(' ', '').split(',')
            acct_id = []
            for a in tmp_acct_id:
                acct_id.append(int(a))

        except tornado.web.HTTPError:
            acct_id = None
            pacct_id = ''

        try:
            state = int(self.get_argument('state'))

        except (tornado.web.HTTPError, ValueError):
            state = 0

        flt = {
            'pro_id': pro_id,
            'acct_id': acct_id,
            'state': state
        }

        err, chalstat = await ChalService.inst.get_stat(
            min(self.acct['acct_type'], UserConst.ACCTTYPE_USER), flt)

        err, challist = await ChalService.inst.list_chal(off, 20,
                                                         min(self.acct['acct_type'], UserService.ACCTTYPE_USER), flt)

        isadmin = (self.acct['acct_type'] == UserConst.ACCTTYPE_KERNEL)
        chalids = []
        for chal in challist:
            chalids.append(chal['chal_id'])

        await self.render('challist',
                          chalstat=chalstat,
                          challist=challist,
                          flt=flt,
                          pageoff=off,
                          ppro_id=ppro_id,
                          pacct_id=pacct_id,
                          acct=self.acct,
                          chalids=json.dumps(chalids),
                          isadmin=isadmin)
        return


from redis import asyncio as aioredis


class ChalSubHandler(WebSocketHandler):
    async def open(self):
        self.ars = aioredis.Redis(host='localhost', port=6379, db=1)
        self.p = self.ars.pubsub()
        await self.p.subscribe('challist_sub')

        async def test():
            async for msg in self.p.listen():
                if msg['type'] != 'message':
                    continue

                await self.on_message(str(int(msg['data'])))

        self.task = asyncio.tasks.Task(test())

    async def on_message(self, msg):
        self.write_message(msg)

    def on_close(self) -> None:
        self.task.cancel()

    def check_origin(self, origin):
        # TODO: secure
        return True


class ChalHandler(RequestHandler):
    @reqenv
    async def get(self, chal_id):
        chal_id = int(chal_id)

        err, chal = await ChalService.inst.get_chal(chal_id, self.acct)
        if err:
            self.error(err)
            return

        err, pro = await ProService.inst.get_pro(chal['pro_id'], self.acct)
        if err:
            self.error(err)
            return

        if self.acct['acct_type'] == UserService.ACCTTYPE_KERNEL:
            rechal = True
        else:
            rechal = False

        chal['comp_type'] = ChalConst.COMPILER_NAME[chal['comp_type']]

        await self.render('chal', pro=pro, chal=chal, rechal=rechal)
        return


class ChalStateHandler(WebSocketHandler):
    async def open(self):
        self.chal_id = -1
        self.ars = aioredis.Redis(host='localhost', port=6379, db=1)
        self.p = self.ars.pubsub()
        await self.p.subscribe('chalstatesub')

        async def listen_chalstate():
            async for msg in self.p.listen():
                if msg['type'] != 'message':
                    continue

                if int(msg['data']) == self.chal_id:
                    err, chal_states = await ChalService.inst.get_chal_state(self.chal_id)
                    await self.write_message(json.dumps(chal_states))

        self.task = asyncio.tasks.Task(listen_chalstate())

    async def on_message(self, msg):
        self.chal_id = int(msg)

    def on_close(self) -> None:
        self.task.cancel()

    def check_origin(self, origin):
        # TODO: secure
        return True
