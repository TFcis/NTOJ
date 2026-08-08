from collections import defaultdict

from handlers.base import RequestHandler, reqenv, require_permission, ActionDispatcher
from services.log import LogService
from services.pro import ProService, ProConst, SubtaskConfig
from services.user import UserConst
from utils.numeric import parse_str_to_list

subtask_dispatcher = ActionDispatcher()


class ManageProSubtaskHandler(RequestHandler):
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

        await self.render(
            "manage/pro/updatesubtask", "Update Problem Subtasks Config", page="pro", pro_id=pro_id, config=pro.config
        )

    @subtask_dispatcher.action("updaterate")
    async def update_rate_action(self):
        try:
            pro_id = int(self.get_argument("pro_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem ID"))
        try:
            subtask_id = int(self.get_argument("subtask"))
        except ValueError:
            return self.error(("Eparam", "Invalid subtask ID"))
        try:
            rate = int(self.get_argument("rate"))
        except ValueError:
            return self.error(("Eparam", "Invalid rate"))

        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        subtask_configs = pro.config.subtask_configs
        if subtask_id not in subtask_configs:
            return self.error(("Enoext", "Subtask not found"))

        subtask_configs[subtask_id].rate = rate
        await ProService.inst.update_pro_config(pro_id, pro.problem_type, pro.config)
        await self.add_log(
            f"{self.acct.name} has sent a request to update rate of subtask#{subtask_id} for problem #{pro_id}",
            "manage.pro.update.subtask.updaterate",
            {"rate": rate},
        )
        return self.error(("S", ""))

    @subtask_dispatcher.action("setdepsubtasks")
    async def set_dep_subtasks_action(self):
        try:
            pro_id = int(self.get_argument("pro_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem ID"))
        try:
            subtask_id = int(self.get_argument("subtask"))
        except ValueError:
            return self.error(("Eparam", "Invalid subtask ID"))
        dep_subtasks = set(
            map(lambda x: x - 1, parse_str_to_list(self.get_argument("dep_subtasks")))
        )

        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        subtask_configs = pro.config.subtask_configs
        if subtask_id not in subtask_configs:
            return self.error(("Enoext", "Subtask not found"))

        for dep_subtask_id in dep_subtasks:
            if dep_subtask_id not in subtask_configs:
                return self.error(("Eparam", f"Dependency subtask {dep_subtask_id} not found"))

        subtask_configs[subtask_id].dependency_subtasks = set(dep_subtasks)

        if self.have_cycle(subtask_configs):
            return self.error(("Eparam", "Dependency subtasks have cycle"))

        await ProService.inst.update_pro_config(pro_id, pro.problem_type, pro.config)
        await self.add_log(
            f"{self.acct.name} has sent a request to set dependency subtasks to subtask#{subtask_id} for problem #{pro_id}",
            "manage.pro.update.subtask.setdepsubtasks",
            {"dependency_subtasks": list(dep_subtasks)},
        )
        return self.error(("S", ""))

    @subtask_dispatcher.action("addsubtask")
    async def add_subtask_action(self):
        try:
            pro_id = int(self.get_argument("pro_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem ID"))
        try:
            rate = int(self.get_argument("rate"))
        except ValueError:
            return self.error(("Eparam", "Invalid rate"))

        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        subtask_configs = pro.config.subtask_configs
        subtask_configs[len(subtask_configs)] = SubtaskConfig(
            len(subtask_configs), [], set(), rate
        )

        await ProService.inst.update_pro_config(pro_id, pro.problem_type, pro.config)
        await self.add_log(
            f"{self.acct.name} has sent a request to add a new subtask for problem #{pro_id}",
            "manage.pro.update.subtask.addsubtask",
            {"rate": rate, "subtask_id": len(subtask_configs) - 1},
        )
        return self.error(("S", ""))

    @subtask_dispatcher.action("deletesubtask")
    async def delete_subtask_action(self):
        try:
            pro_id = int(self.get_argument("pro_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem ID"))
        try:
            subtask_id = int(self.get_argument("subtask"))
        except ValueError:
            return self.error(("Eparam", "Invalid subtask ID"))

        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        subtask_configs = pro.config.subtask_configs
        if subtask_id not in subtask_configs:
            return self.error(("Enoext", "Subtask not found"))

        subtask_configs.pop(subtask_id)
        remain_subtasks = list(subtask_configs.values())
        subtask_configs.clear()

        for new_subtask_id, subtask in enumerate(remain_subtasks):
            subtask_configs[new_subtask_id] = subtask

        await ProService.inst.update_pro_config(pro_id, pro.problem_type, pro.config)
        await self.add_log(
            f"{self.acct.name} has sent a request to delete a subtask for problem #{pro_id}",
            "manage.pro.update.subtask.deletesubtask",
        )
        return self.error(("S", ""))

    @subtask_dispatcher.action("settestdata")
    async def set_testdata_action(self):
        try:
            pro_id = int(self.get_argument("pro_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem ID"))
        try:
            subtask_id = int(self.get_argument("subtask"))
        except ValueError:
            return self.error(("Eparam", "Invalid subtask ID"))

        testdatas = list(map(lambda x: x - 1, parse_str_to_list(self.get_argument("testdatas"))))
        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        subtask_configs = pro.config.subtask_configs
        if subtask_id not in subtask_configs:
            return self.error(("Enoext", "Subtask not found"))

        subtask_configs[subtask_id].testdatas.clear()
        for testdata_id in testdatas:
            if testdata_id not in pro.config.testdatas:
                continue
            subtask_configs[subtask_id].testdatas.append(
                pro.config.testdatas[testdata_id]
            )

        await ProService.inst.update_pro_config(pro_id, pro.problem_type, pro.config)
        await self.add_log(
            f"{self.acct.name} has sent a request to set testdatas to subtask#{subtask_id} for problem #{pro_id}",
            "manage.pro.update.subtask.settestdata",
            {
                "testdatas": [
                    testdata.testdata_id
                    for testdata in subtask_configs[subtask_id].testdatas
                ]
            },
        )
        return self.error(("S", ""))

    @subtask_dispatcher.action("updatemetadata")
    async def update_metadata_action(self):
        try:
            pro_id = int(self.get_argument("pro_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem ID"))
        try:
            subtask_id = int(self.get_argument("subtask"))
        except ValueError:
            return self.error(("Eparam", "Invalid testdata ID"))
        tags_str = self.get_argument("tags", default="").strip()

        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        subtask_configs = pro.config.subtask_configs
        if subtask_id not in subtask_configs:
            return self.error(("Enoext", "Subtask not found"))

        # Parse tags from comma-separated string
        tags = [tag.strip() for tag in tags_str.split(",") if tag.strip()]
        subtask_configs[subtask_id].metadata["tags"] = tags

        await ProService.inst.update_pro_config(pro_id, pro.problem_type, pro.config)
        await self.add_log(
            f"{self.acct.name} has sent a request to update metadata tags of subtask#{subtask_id} for problem #{pro_id}",
            "manage.pro.update.subtask.updatemetadata",
            {"tags": tags},
        )
        return self.error(("S", ""))

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        reqtype = self.get_argument("reqtype")
        return await subtask_dispatcher.dispatch(self, reqtype)

    def have_cycle(self, subtask_configs: dict[int, SubtaskConfig]) -> bool:
        vis = defaultdict(int)
        graph = defaultdict(list)

        for u, sconfig in subtask_configs.items():
            for v in sconfig.dependency_subtasks:
                graph[u].append(v)

        def dfs(u) -> bool:
            nonlocal vis
            vis[u] = 1
            for v in graph[u]:
                if vis[v] == 1:
                    return False
                elif vis[v] == 0:
                    if not dfs(v):
                        return False
            vis[u] = 2
            return True

        for u in subtask_configs.keys():
            if vis[u] == 0:
                if not dfs(u):
                    return True

        return False
