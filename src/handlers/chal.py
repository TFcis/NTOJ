import asyncio
import json

import tornado.web

from handlers.base import RequestHandler, WebSocketSubHandler, reqenv
from handlers.contests.base import contest_require_permission
from services.chal import ChalConst, ChalService, ChalSearchingParamBuilder
from services.pro import ProService
from services.user import UserService
from utils.numeric import parse_list_str


class ChalListHandler(RequestHandler):
    @reqenv
    async def get(self):
        try:
            pageoff = int(self.get_argument('pageoff'))

        except tornado.web.HTTPError:
            pageoff = 0

        try:
            ppro_id = str(self.get_argument('proid'))
            query_pros = parse_list_str(ppro_id)
            if len(query_pros) == 0:
                query_pros = None

        except tornado.web.HTTPError:
            query_pros = None
            ppro_id = ''

        try:
            pacct_id = str(self.get_argument('acctid'))
            query_accts = parse_list_str(pacct_id)
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

        contest_id = 0
        if self.contest:
            contest_id = self.contest.contest_id

            if self.contest.hide_admin and not self.contest.is_admin(self.acct):
                if query_accts is None:
                    query_accts = self.contest.acct_list
                else:
                    query_accts = list(filter(lambda acct_id: not self.contest.is_admin(acct_id=acct_id), query_accts))

        flt = ChalSearchingParamBuilder().pro(query_pros).acct(query_accts).state(state).compiler(compiler_type).contest(contest_id).build()

        _, chalstat = await ChalService.inst.get_stat(self.acct, flt)

        _, challist = await ChalService.inst.list_chal(pageoff, 20, self.acct, flt)

        isadmin = self.acct.is_kernel()
        if self.contest:
            isadmin = self.acct.is_kernel() and self.contest.is_admin(self.acct)

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
    @contest_require_permission('all')
    async def get(self, chal_id):
        chal_id = int(chal_id)

        err, chal = await ChalService.inst.get_chal(chal_id)
        if err:
            self.error(err)
            return

        err, pro = await ProService.inst.get_pro(chal['pro_id'], self.acct, is_contest=self.contest is not None)
        if err:
            self.error(err)
            return

        chal['comp_type'] = ChalConst.COMPILER_NAME[chal['comp_type']]

        rechal = self.acct.is_kernel()
        if self.contest:
            rechal = rechal and self.contest.is_admin(self.acct)

        await self.render('chal', pro=pro, chal=chal, rechal=rechal)
        return


class ChalListNewChalHandler(WebSocketSubHandler):
    async def listen_challistnewchal(self):
        async for msg in self.p.listen():
            if msg['type'] != 'message':
                continue

            await self.write_message(str(int(msg['data'])))

    async def open(self):
        await self.p.subscribe('challist_sub')

        self.task = asyncio.tasks.Task(self.listen_challistnewchal())


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
