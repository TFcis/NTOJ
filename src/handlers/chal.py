import asyncio
import json

import tornado.web

from handlers.base import RequestHandler, WebSocketSubHandler, reqenv
from services.chal import ChalConst, ChalService, ChalSearchingParamBuilder
from services.pro import ProService
from services.user import UserService


class ChalListHandler(RequestHandler):
    @reqenv
    async def get(self):
        try:
            pageoff = int(self.get_argument('pageoff'))

        except tornado.web.HTTPError:
            pageoff = 0

        try:
            ppro_id = str(self.get_argument('proid'))
            tmp_pro_id = ppro_id.replace(' ', '').split(',')
            query_pros = [int(pro_id) for pro_id in tmp_pro_id if pro_id.isnumeric()]
            if len(query_pros) == 0:
                query_pros = None

        except tornado.web.HTTPError:
            query_pros = None
            ppro_id = ''

        try:
            pacct_id = str(self.get_argument('acctid'))
            tmp_acct_id = pacct_id.replace(' ', '').split(',')
            query_accts = [int(acct_id) for acct_id in tmp_acct_id if acct_id.isnumeric()]
            if len(query_accts) == 0:
                query_accts = None

        except tornado.web.HTTPError:
            query_accts = None
            pacct_id = ''

        try:
            state = int(self.get_argument('state'))

        except (tornado.web.HTTPError, ValueError):
            state = 0

        try:
            compiler_type = self.get_argument('compiler_type')
        except tornado.web.HTTPError:
            compiler_type = 'all'

        flt = ChalSearchingParamBuilder().pro(query_pros).acct(query_accts).state(state).compiler(compiler_type).build()

        _, chalstat = await ChalService.inst.get_stat(self.acct, flt)

        _, challist = await ChalService.inst.list_chal(pageoff, 20, self.acct, flt)

        isadmin = self.acct.is_kernel()
        chalids = [chal['chal_id'] for chal in challist]

        await self.render(
            'challist',
            chalstat=chalstat,
            challist=challist,
            flt=flt,
            pageoff=pageoff,
            ppro_id=ppro_id,
            pacct_id=pacct_id,
            acct=self.acct,
            chalids=json.dumps(chalids),
            isadmin=isadmin,
        )


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

        chal['comp_type'] = ChalConst.COMPILER_NAME[chal['comp_type']]

        await self.render('chal', pro=pro, chal=chal, rechal=self.acct.is_kernel())
        return


from redis import asyncio as aioredis


class ChalListNewChalHandler(WebSocketSubHandler):
    async def listen_challistnewchal(self):
        async for msg in self.p.listen():
            if msg['type'] != 'message':
                continue

            await self.on_message(str(int(msg['data'])))

    async def open(self):
        await self.p.subscribe('challist_sub')

        self.task = asyncio.tasks.Task(self.listen_challistnewchal())

    async def on_message(self, msg):
        await self.write_message(msg)


class ChalListNewStateHandler(WebSocketSubHandler):
    async def listen_challiststate(self):
        async for msg in self.p.listen():
            if msg['type'] != 'message':
                continue

            chal_id = int(msg['data'])
            if self.first_chal_id <= chal_id <= self.last_chal_id:
                _, new_state = await ChalService.inst.get_single_chal_state_in_list(chal_id, self.acct)
                await self.write_message(json.dumps(new_state))

    async def open(self):
        self.first_chal_id = -1
        self.last_chal_id = -1
        self.acct = None

        await self.p.subscribe('challiststatesub')

        self.task = asyncio.tasks.Task(self.listen_challiststate())

    async def on_message(self, msg):
        if self.acct is None:
            j = json.loads(msg)

            self.first_chal_id = int(j["first_chal_id"])
            self.last_chal_id = int(j["last_chal_id"])
            err, acct = await UserService.inst.info_acct(acct_id=int(j["acct_id"]))
            if err:
                self.on_close()

            self.acct = acct


class ChalNewStateHandler(WebSocketSubHandler):

    async def listen_chalstate(self):
        async for msg in self.p.listen():
            if msg['type'] != 'message':
                continue

            if int(msg['data']) == self.chal_id:
                _, chal_states = await ChalService.inst.get_chal_state(self.chal_id)
                await self.write_message(json.dumps(chal_states))

    async def open(self):
        self.chal_id = -1
        await self.p.subscribe('chalstatesub')
        self.task = asyncio.tasks.Task(self.listen_chalstate())

    async def on_message(self, msg):
        if self.chal_id == -1 and msg.isdigit():
            self.chal_id = int(msg)
