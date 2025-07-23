import asyncio
import decimal
import json

from handlers.base import RequestHandler, WebSocketSubHandler, reqenv
from handlers.contests.base import contest_require_permission
from services.chal import ChalConst, ChalService, ChalSearchingParamBuilder
from services.pro import ProService, ProConst
from services.user import UserService
from services.contests import UserStatus
from utils.numeric import parse_list_str


class ChalListHandler(RequestHandler):
    @reqenv
    async def get(self):
        flt_builder = ChalSearchingParamBuilder()

        pageoff = int(self.get_argument('pageoff', default=0))

        ppro_id = str(self.get_argument('proid', default=''))
        query_pros = parse_list_str(ppro_id)
        if len(query_pros) == 0:
            query_pros = None

        pacct_id = str(self.get_argument('acctid', default=''))
        query_accts = parse_list_str(pacct_id)
        if len(query_accts) == 0:
            query_accts = None

        state = int(self.get_argument('state', default=0))
        flt_builder.state(state)

        compiler_type = self.get_argument('compiler_type', default='all')
        flt_builder.compiler(compiler_type)

        isadmin = self.acct.is_kernel()
        if isadmin:
            flt_builder.pro_statuses(ProConst.PRO_STATUS_KERNEL_USER)

        if self.contest:
            isadmin = self.contest.is_admin(self.acct)
            flt_builder.contest(self.contest.contest_id)
            flt_builder.pro_statuses(ProConst.PRO_STATUS_CONTEST_USER)

            EMPTY = []
            # NOTE: if user is admin, specifying contest_id will list all challenges for that contest; there's no need to specify an account separately.
            if not isadmin:
                if not self.contest.is_start():
                    query_accts = EMPTY
                elif self.contest.is_running():
                    query_accts = [self.acct.acct_id] # NOTE: display self
                else:
                    if self.contest.is_public_scoreboard:
                        if query_accts is None:
                            query_accts = [acct_id for acct_id, v in self.contest.user_list.items() if v['status'] == UserStatus.APPROVED]
                            if not query_accts:
                                query_accts = EMPTY
                        else:
                            query_accts = list(filter(lambda acct_id: not self.contest.is_admin(acct_id=acct_id), query_accts))
                    else:
                        query_accts = [self.acct.acct_id]

        flt = flt_builder.pro(query_pros).acct(query_accts).build()

        _, chalstat = await ChalService.inst.get_chals_count(flt)
        _, challist = await ChalService.inst.list_chal(pageoff, 20, flt)

        await self.render(
            'challist',
            chalstat=chalstat,
            challist=challist,
            flt=flt,
            pageoff=pageoff,
            ppro_id=ppro_id,
            pacct_id=pacct_id,
            isadmin=isadmin,
            contest=self.contest,
        )


class ChalHandler(RequestHandler):
    @reqenv
    @contest_require_permission('all')
    async def get(self, chal_id):
        chal_id = int(chal_id)

        err, chal = await ChalService.inst.get_chal(chal_id, with_test=True)
        if err:
            return self.error(err)

        allow_statuses = ProConst.PRO_STATUS_NORMAL_USER
        if chal['contest_id'] and not self.contest:
            return self.error(('Enoext', 'Contest not found'))

        elif self.contest:
            if not self.contest.is_start():
                if self.contest.is_admin(acct_id=chal['acct_id']) and not self.contest.is_admin(self.acct):
                    return self.error(('Eacces', 'Permission denied'))

            elif self.contest.is_running():
                if self.contest.hide_admin and self.contest.is_admin(acct_id=chal['acct_id']) and not self.contest.is_admin(self.acct):
                    return self.error(('Eacces', 'Permission denied'))

            allow_statuses = ProConst.PRO_STATUS_CONTEST_USER

        elif self.acct.is_kernel():
            allow_statuses = ProConst.PRO_STATUS_KERNEL_USER

        err, pro = await ProService.inst.get_pro(chal['pro_id'], allow_statuses)
        if err:
            return self.error(err)

        chal['comp_type'] = ChalConst.COMPILER_NAME[chal['comp_type']]

        rechal = self.acct.is_kernel()
        if self.contest:
            rechal = rechal and self.contest.is_admin(self.acct)

        final_response = []
        for idx, test in enumerate(chal['testl'], start=1):
            response = test['response']
            final_response.append(f"Task {idx}: {response}")

        await self.render('chal', pro=pro, chal=chal, rechal=rechal, response='\n'.join(final_response))
        return

class _Encoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return str(o)
        return super().default(o)

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
                _, new_state = await ChalService.inst.get_calculated_chal_state(chal_id, self.allow_pro_statuses)
                await self.write_message(json.dumps(new_state, cls=_Encoder))

    async def open(self):
        self.first_chal_id = -1
        self.last_chal_id = -1
        self.allow_pro_statuses = [ProConst.STATUS_ONLINE]

        await self.p.subscribe('challiststatesub')

        self.task = asyncio.tasks.Task(self.listen_challiststate())

    async def on_message(self, msg):
        # TODO: contest challist
        # TODO: user authentication

        if self.first_chal_id == -1:
            j = json.loads(msg)

            self.first_chal_id = int(j["first_chal_id"])
            self.last_chal_id = int(j["last_chal_id"])
            err, acct = await UserService.inst.info_acct(acct_id=int(j["acct_id"]))
            if not err and acct.is_kernel():
                self.allow_pro_statuses.append(ProConst.STATUS_HIDDEN)


class ChalNewStateHandler(WebSocketSubHandler):

    async def listen_chalstate(self):
        async for msg in self.p.listen():
            if msg['type'] != 'message':
                continue

            if int(msg['data']) == self.chal_id:
                _, chal_states = await ChalService.inst.get_chal_state(self.chal_id)
                await self.write_message(json.dumps(chal_states, cls=_Encoder))

    async def open(self):
        self.chal_id = -1
        await self.p.subscribe('chalstatesub')
        self.task = asyncio.tasks.Task(self.listen_chalstate())

    async def on_message(self, msg):
        if self.chal_id == -1 and msg.isdigit():
            self.chal_id = int(msg)
