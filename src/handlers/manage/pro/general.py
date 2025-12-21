import asyncio
import base64
from msgpack import packb

import config
from handlers.base import ActionDispatcher, RequestHandler, reqenv, require_permission
from services.chal import ChalConst, ChalService
from services.judge import JudgeServerClusterService
from services.log import LogService
from services.pro import ProService, ProConst
from services.user import UserConst

PERMISSION_DENIED_ERROR = ("Eacces", "Permission denied")

general_dispatcher = ActionDispatcher()


class ManageProListHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
        pageoff = int(self.get_argument("pageoff", default=0))
        err, prolist = await ProService.inst.list_pro(ProConst.PRO_STATUS_FULL)
        pro_total_cnt = len(prolist)
        prolist = prolist[pageoff : pageoff + 40]

        await self.render(
            "manage/pro/pro-list",
            page="pro",
            prolist=prolist,
            pageoff=pageoff,
            pro_total_cnt=pro_total_cnt,
        )

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        reqtype = self.get_argument("reqtype")
        return await general_dispatcher.dispatch(self, reqtype)

    @general_dispatcher.action("rechal")
    async def rechal_pro(self):
        pro_id = int(self.get_argument("pro_id"))
        can_submit = JudgeServerClusterService.inst.is_server_online()
        if not can_submit:
            return self.error(("Ejudge", "No available judge"))

        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        async with self.db.acquire() as con:
            result = await con.fetch(
                f"""
                    SELECT "challenge"."chal_id", "challenge"."compiler_type" FROM "challenge"
                    INNER JOIN "total_result"
                    ON "challenge"."chal_id" = "total_result"."chal_id"
                    WHERE "pro_id" = $1 AND "total_result"."state" = {ChalConst.STATE_NOTSTARTED};
                """,
                pro_id,
            )

        await LogService.inst.add_log(
            f"{self.acct.name} made a request to rejudge the problem #{pro_id} with {len(result)} chals",
            "manage.chal.rechal",
        )

        async def _rechal(rechals):
            _, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
            for chal_id, compiler_type in rechals:
                _, _ = await ChalService.inst.reset_chal(chal_id)
                _, _ = await ChalService.inst.emit_chal(
                    chal_id,
                    pro.config,
                    compiler_type,
                    ChalConst.NORMAL_REJUDGE_PRI,
                    pro.problem_type,
                    skip_nonac=False,
                    include_system_test=True,  # Non-contest rejudge includes system-test
                )

        await asyncio.create_task(_rechal(rechals=result))
        self.error(("S", ""))

    @general_dispatcher.action("rechalall")
    async def rechal_all_pro(self):
        pwd = self.get_argument("pwd")
        if config.unlock_pwd != base64.b64encode(packb(pwd)):
            return self.error(("Eacces", "Wrong password"))

        pro_id = int(self.get_argument("pro_id"))
        can_submit = JudgeServerClusterService.inst.is_server_online()
        if not can_submit:
            return self.error(("Ejudge", "No available judge"))

        err, _ = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        async with self.db.acquire() as con:
            result = await con.fetch(
                """
                    SELECT "challenge"."chal_id", "challenge"."compiler_type" FROM "challenge"
                    INNER JOIN "total_result"
                    ON "challenge"."chal_id" = "total_result"."chal_id"
                    WHERE "pro_id" = $1;
                """,
                pro_id,
            )

        await LogService.inst.add_log(
            f"{self.acct.name} made a request to rejudge the problem #{pro_id} with {len(result)} chals",
            "manage.chal.rechalall",
        )

        async def _rechal(rechals):
            _, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
            for chal_id, compiler_type in rechals:
                _, _ = await ChalService.inst.reset_chal(chal_id)
                _, _ = await ChalService.inst.emit_chal(
                    chal_id,
                    pro.config,
                    compiler_type,
                    ChalConst.NORMAL_REJUDGE_PRI,
                    pro.problem_type,
                    skip_nonac=False,
                    include_system_test=True,  # Non-contest rejudge includes system-test
                )

        await asyncio.create_task(_rechal(rechals=result))
        self.error(("S", ""))
