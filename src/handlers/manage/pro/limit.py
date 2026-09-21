from dataclasses import asdict
import json

from handlers.base import RequestHandler, reqenv, require_permission, ActionDispatcher
from services.pro import ProService, ProConst
from services.prospec.program import ProgramConfig, build_program_limits
from services.user import UserConst

limit_dispatcher = ActionDispatcher()


class ManageProLimitHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
        try:
            pro_id = int(self.get_argument("pro_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem ID"))

        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        await self.render("manage/pro/updatelimit", "Update Problem Limit Config", page="pro", pro=pro)

    @limit_dispatcher.action("updatelimit")
    async def update_limit_action(self):
        try:
            pro_id = int(self.get_argument("pro_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem ID"))

        limits = json.loads(self.get_argument("limits"))

        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)
        assert pro

        spec_config = pro.config.spec_config
        if not isinstance(spec_config, ProgramConfig):
            return self.error(("Enotsupport", "Problem type does not support compiler limits"))
        try:
            new_limits = build_program_limits(limits, spec_config.allow_compilers)
        except ValueError as exc:
            return self.error(("Eparam", str(exc)))

        pro.config.limits = new_limits
        await ProService.inst.update_pro_config(pro_id, pro.problem_type, pro.config)

        await self.add_log(
            f"{self.acct.name} has sent a request to update the problem #{pro_id} limit config",
            "manage.pro.update.limit",
            {
                "limits": {
                    comp: asdict(limit) for comp, limit in pro.config.limits.items()
                }
            },
        )

        return self.error(("S", ""))

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        reqtype = self.get_argument("reqtype")
        return await limit_dispatcher.dispatch(self, reqtype)
