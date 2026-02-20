from dataclasses import asdict
import json

from handlers.base import RequestHandler, reqenv, require_permission, ActionDispatcher
from services.chal import Compiler
from services.log import LogService
from services.pro import ProService, ProConst, Limit
from services.user import UserConst

limit_dispatcher = ActionDispatcher()


class ManageProLimitHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
        try:
            pro_id = int(self.get_argument("proid"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem ID"))

        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        await self.render("manage/pro/updatelimit", page="pro", pro=pro)

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

        # TODO: Support different problem types
        from services.prospec.batch import BatchConfig

        assert isinstance(pro.config.spec_config, BatchConfig)
        ALLOW_COMPILERS = pro.config.spec_config.allow_compilers.copy()
        ALLOW_COMPILERS.add("default")

        new_limits: dict[str, Limit] = {}
        for compiler_type, limit in limits.items():
            if compiler_type != "default":
                try:
                    compiler_type = Compiler(int(compiler_type))
                except ValueError:
                    continue
            if compiler_type not in ALLOW_COMPILERS:
                continue
            new_limits[compiler_type] = Limit(0, 0, 0)
            try:
                new_limits[compiler_type].time = max(int(limit["time"]), 0)
                new_limits[compiler_type].memory = max(int(limit["memory"]), 0)
                new_limits[compiler_type].output = max(int(limit["output"]), 0)
            except (ValueError, KeyError):
                new_limits.pop(compiler_type)
                continue

        if "default" not in new_limits:
            return self.error(("Eparam", "Missing default limit config"))

        pro.config.limits = new_limits
        await ProService.inst.update_pro_config(pro_id, pro.problem_type, pro.config)

        await LogService.inst.add_log(
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
