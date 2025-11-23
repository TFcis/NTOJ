import asyncio
import base64
from msgpack import packb

import config
from handlers.base import RequestHandler, reqenv, require_permission
from services.chal import ChalConst, ChalService
from services.judge import JudgeServerClusterService
from services.log import LogService
from services.pro import ProService, ProConst
from services.user import UserConst

PERMISSION_DENIED_ERROR = ('Eacces', 'Permission denied')
ALLOW_STATUSES = [ProConst.STATUS_ONLINE, ProConst.STATUS_CONTEST, ProConst.STATUS_HIDDEN]


class ManageProListHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
        pageoff = int(self.get_argument('pageoff', default=0))
        err, prolist = await ProService.inst.list_pro(ALLOW_STATUSES)
        pro_total_cnt = len(prolist)
        prolist = prolist[pageoff: pageoff + 40]

        await self.render(
            'manage/pro/pro-list',
            page='pro',
            prolist=prolist,
            pageoff=pageoff,
            pro_total_cnt=pro_total_cnt
        )

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        reqtype = self.get_argument('reqtype')

        if reqtype in ['rechal', 'rechalall']:
            is_all_chal = (reqtype == 'rechalall')

            if is_all_chal:
                pwd = self.get_argument('pwd')
                if config.unlock_pwd != base64.b64encode(packb(pwd)):
                    return self.error(('Eacces', 'Wrong password'))

            pro_id = int(self.get_argument('pro_id'))
            can_submit = JudgeServerClusterService.inst.is_server_online()
            if not can_submit:
                return self.error(('Ejudge', 'No available judge'))

            err, pro = await ProService.inst.get_pro(pro_id, ALLOW_STATUSES)
            if err:
                return self.error(err)

            log_type = "manage.chal.rechalall" if is_all_chal else "manage.chal.rechal"

            async with self.db.acquire() as con:
                sql = "" if is_all_chal else f'AND "total_result"."state" = {ChalConst.STATE_NOTSTARTED}'
                result = await con.fetch(
                    f'''
                        SELECT "challenge"."chal_id", "challenge"."compiler_type" FROM "challenge"
                        INNER JOIN "total_result"
                        ON "challenge"."chal_id" = "total_result"."chal_id"
                        WHERE "pro_id" = $1 {sql};
                    ''',
                    pro_id,
                )

            await LogService.inst.add_log(
                f"{self.acct.name} made a request to rejudge the problem #{pro_id} with {len(result)} chals",
                log_type,
            )

            async def _rechal(rechals):
                _, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
                for chal_id, compiler_type in rechals:
                    _, _ = await ChalService.inst.reset_chal(chal_id)
                    _, _ = await ChalService.inst.emit_chal(
                        chal_id, pro.config, compiler_type,
                        ChalConst.NORMAL_REJUDGE_PRI, pro.problem_type,
                        skip_nonac=False
                    )

            await asyncio.create_task(_rechal(rechals=result))
            self.error(('S', ''))
