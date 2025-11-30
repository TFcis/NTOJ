import asyncio
import decimal
import json
from dataclasses import is_dataclass, asdict

from handlers.base import (
    ActionDispatcher,
    RequestHandler,
    WebSocketSubHandler,
    reqenv,
    require_permission,
)
from handlers.contests.base import contest_require_permission
from services.chal import (
    ChalService,
    ChalSearchingParamBuilder,
    ChalConst,
    COMPILER_INFOS,
    MessageType,
)
from services.pro import ProService, ProConst
from services.user import UserService, UserConst
from services.contests import UserStatus
from utils.numeric import parse_str_to_list
from services.log import LogService

chal_dispatcher = ActionDispatcher()


class ChalListHandler(RequestHandler):
    @reqenv
    async def get(self):
        pageoff = int(self.get_argument("pageoff", default=0))
        ppro_id = str(self.get_argument("proid", default=""))
        pacct_id = str(self.get_argument("acctid", default=""))
        state = int(self.get_argument("state", default=0))
        compiler_type = int(self.get_argument("compiler_type", default=-1))

        query_pros = self._parse_problem_filter(ppro_id)
        query_accts = self._parse_account_filter(pacct_id)

        flt_builder = ChalSearchingParamBuilder()
        flt_builder.state(state).compiler(compiler_type)

        isadmin = self._setup_permissions(flt_builder)
        query_accts = self._apply_contest_filters(flt_builder, query_accts, isadmin)

        flt = flt_builder.pro(query_pros).acct(query_accts).build()
        _, chal_cnt = await ChalService.inst.get_chals_count(flt)
        _, challist = await ChalService.inst.list_chal(pageoff, 20, flt)

        for chal in challist:
            chal.compiler_type = COMPILER_INFOS[chal.compiler_type].version_name

        await self.render(
            "challist",
            chal_cnt=chal_cnt,
            challist=challist,
            flt=flt,
            pageoff=pageoff,
            ppro_id=ppro_id,
            pacct_id=pacct_id,
            isadmin=isadmin,
            contest=self.contest,
        )

    def _parse_problem_filter(self, ppro_id: str) -> list[int] | None:
        query_pros = parse_str_to_list(ppro_id)
        return None if len(query_pros) == 0 else query_pros

    def _parse_account_filter(self, pacct_id: str) -> list[int] | None:
        query_accts = parse_str_to_list(pacct_id)
        return None if len(query_accts) == 0 else query_accts

    def _setup_permissions(self, flt_builder: ChalSearchingParamBuilder) -> bool:
        isadmin = self.acct.is_kernel()
        if isadmin:
            flt_builder.pro_statuses(ProConst.PRO_STATUS_KERNEL_USER)
        return isadmin

    def _apply_contest_filters(
        self,
        flt_builder: ChalSearchingParamBuilder,
        query_accts: list[int] | None,
        isadmin: bool,
    ) -> list[int] | None:
        if not self.contest:
            return query_accts

        isadmin = self.contest.is_admin(self.acct)
        flt_builder.contest(self.contest.contest_id)
        flt_builder.pro_statuses(ProConst.PRO_STATUS_CONTEST_USER)

        if isadmin:
            return query_accts

        return self._get_non_admin_contest_accounts(query_accts)

    def _get_non_admin_contest_accounts(
        self, query_accts: list[int] | None
    ) -> list[int]:
        if not self.contest.is_start():
            return []

        if self.contest.is_running():
            return [self.acct.acct_id]

        return self._get_post_contest_accounts(query_accts)

    def _get_post_contest_accounts(self, query_accts: list[int] | None) -> list[int]:
        if not self.contest.is_public_scoreboard:
            return [self.acct.acct_id]

        if query_accts is None:
            approved_accts = [
                acct_id
                for acct_id, v in self.contest.user_list.items()
                if v["status"] == UserStatus.APPROVED
            ]
            return approved_accts if approved_accts else []
        else:
            return [
                acct_id
                for acct_id in query_accts
                if not self.contest.is_admin(acct_id=acct_id)
            ]


class ChalHandler(RequestHandler):
    @reqenv
    @contest_require_permission("all")
    async def get(self, chal_id):
        chal_id = int(chal_id)

        err, chal = await ChalService.inst.get_chal(chal_id, with_result=True)
        if err:
            return self.error(err)

        allow_statuses = ProConst.PRO_STATUS_NORMAL_USER
        if chal.contest_id and not self.contest:
            return self.error(("Enoext", "Contest not found"))

        elif self.contest:
            if not self.contest.is_start():
                if self.contest.is_admin(
                    acct_id=chal.acct_id
                ) and not self.contest.is_admin(self.acct):
                    return self.error(("Eacces", "Permission denied"))

            elif self.contest.is_running():
                if (
                    self.contest.hide_admin
                    and self.contest.is_admin(acct_id=chal.acct_id)
                    and not self.contest.is_admin(self.acct)
                ):
                    return self.error(("Eacces", "Permission denied"))

            allow_statuses = ProConst.PRO_STATUS_CONTEST_USER

        elif self.acct.is_kernel():
            allow_statuses = ProConst.PRO_STATUS_KERNEL_USER

        err, pro = await ProService.inst.get_pro(chal.pro_id, allow_statuses)
        if err:
            return self.error(err)

        chal.compiler_type = COMPILER_INFOS[chal.compiler_type].version_name

        rechal = self.acct.is_kernel()
        if self.contest:
            rechal = rechal and self.contest.is_admin(self.acct)

        await self.render("chal", pro=pro, chal=chal, rechal=rechal)
        return

    @reqenv
    @require_permission([UserConst.ACCTTYPE_USER, UserConst.ACCTTYPE_KERNEL])
    @contest_require_permission("admin")
    async def post(self, chal_id):
        chal_id = int(chal_id)
        self.path_args = [chal_id]  # Store for action methods
        reqtype = self.get_argument("reqtype")
        return await chal_dispatcher.dispatch(self, reqtype)

    @chal_dispatcher.action("reject")
    async def reject_challenge(self):
        chal_id = (
            self.path_args[0]
            if hasattr(self, "path_args")
            else int(self.get_argument("chal_id"))
        )
        reason = self.get_argument("reason")
        if err := self.len_check(reason, 0, 1024, "reason"):
            return self.error(err)

        if not self.contest and not self.acct.is_kernel():
            return self.error((("Eacces", "Permission denied")))

        err, chal = await ChalService.inst.get_chal(chal_id, with_result=True)
        if err:
            return self.error(err)

        chal.total_result.reset()
        chal.total_result.message = reason
        chal.total_result.message_type = MessageType.TEXT
        chal.total_result.state = ChalConst.STATE_REJECTED
        await ChalService.inst.update_total_result(chal_id, chal.total_result)

        for r in chal.subtask_results.values():
            r.reset()
            r.state = ChalConst.STATE_REJECTED
            await ChalService.inst.update_subtask_result(chal_id, r)

        for r in chal.testdata_results.values():
            r.reset()
            r.state = ChalConst.STATE_REJECTED
            await ChalService.inst.update_testdata_result(chal_id, r)

        await self.rs.hdel("pro_topcoder", str(chal.pro_id))

        await LogService.inst.add_log(
            f"{self.acct.name}(#{self.acct.acct_id}) reject chal#{chal_id}.",
            "manage.chal.reject",
            {"reason": reason},
        )

        self.error(("S", ""))


class _Encoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return str(o)
        elif is_dataclass(o):
            return asdict(o)
        return super().default(o)


class ChalListNewChalHandler(WebSocketSubHandler):
    async def listen_challistnewchal(self):
        async for msg in self.p.listen():
            if msg["type"] != "message":
                continue

            await self.write_message(str(int(msg["data"])))

    async def open(self):
        await self.p.subscribe("challist_sub")

        self.task = asyncio.tasks.Task(self.listen_challistnewchal())


class ChalListNewStateHandler(WebSocketSubHandler):
    async def listen_challiststate(self):
        async for msg in self.p.listen():
            if msg["type"] != "message":
                continue

            chal_id = int(msg["data"])
            if chal_id in self.chalids:
                _, chal = await ChalService.inst.get_chal(chal_id)
                err, _ = await ProService.inst.get_pro(
                    chal.pro_id, self.allow_pro_statuses
                )
                if err:
                    self.chalids.remove(chal_id)

                _, total_result = await ChalService.inst.get_total_result(chal_id)
                await self.write_message(
                    json.dumps(
                        {"chal_id": chal_id, **asdict(total_result)}, cls=_Encoder
                    )
                )

    async def open(self):
        self.chalids: set[int] = None
        self.allow_pro_statuses = ProConst.STATUS_ONLINE

        await self.p.subscribe("challiststatesub")

        self.task = asyncio.tasks.Task(self.listen_challiststate())

    async def on_message(self, msg):
        # TODO: contest challist
        # TODO: user authentication

        if self.chalids is None:
            j = json.loads(msg)

            self.chalids = set(j["chalids"])

            err, acct = await UserService.inst.info_acct(acct_id=int(j["acct_id"]))
            if not err and acct.is_kernel():
                self.allow_pro_statuses.append(ProConst.STATUS_HIDDEN)


class ChalNewStateHandler(WebSocketSubHandler):
    async def listen_chalstate(self):
        async for msg in self.p.listen():
            if msg["type"] != "message":
                continue

            if json.loads(msg["data"])["chal_id"] == self.chal_id:
                await self.write_message(msg["data"])

    async def open(self):
        self.chal_id = -1
        await self.p.subscribe("chalstatesub")
        self.task = asyncio.tasks.Task(self.listen_chalstate())

    async def on_message(self, msg):
        if self.chal_id == -1 and msg.isdigit():
            self.chal_id = int(msg)
