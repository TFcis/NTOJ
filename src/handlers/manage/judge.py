import asyncio
import base64

from msgpack import packb

import config
from handlers.base import (
    ActionDispatcher,
    RequestHandler,
    WebSocketSubHandler,
    reqenv,
    require_permission,
)
from services.judge import JudgeServerClusterService
from services.log import LogService
from services.user import UserConst


judge_dispatcher = ActionDispatcher()


class ManageJudgeHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
        judge_status_list = JudgeServerClusterService.inst.get_servers_status()
        await self.render(
            "manage/judge", page="judge", judge_status_list=judge_status_list
        )

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        reqtype = self.get_argument("reqtype")
        return await judge_dispatcher.dispatch(self, reqtype)

    @judge_dispatcher.action("connect")
    async def connect_judge(self):
        index = int(self.get_argument("index"))

        err, server_inform = JudgeServerClusterService.inst.get_server_status(index)
        if (server_name := server_inform["name"]) == "":
            server_name = f"server-{index}"

        if err := await JudgeServerClusterService.inst.connect_server(index):
            await LogService.inst.add_log(
                f"{self.acct.name} tried connected {server_name} but failed.",
                "manage.judge.connect.failure",
            )
            return self.error(err)

        await LogService.inst.add_log(
            f"{self.acct.name} had been connected {server_name} succesfully.",
            "manage.judge.connect",
        )

        self.error(("S", ""))

    @judge_dispatcher.action("disconnect")
    async def disconnect_judge(self):
        index = int(self.get_argument("index"))
        pwd = str(self.get_argument("pwd"))

        err, server_inform = JudgeServerClusterService.inst.get_server_status(index)
        if (server_name := server_inform["name"]) == "":
            server_name = f"server-{index}"

        if config.unlock_pwd != base64.b64encode(packb(pwd)):
            await LogService.inst.add_log(
                f"{self.acct.name} tried to disconnect {server_name} but failed.",
                "manage.judge.disconnect.failure",
            )
            return self.error(("Eacces", "Wrong password"))

        if err := await JudgeServerClusterService.inst.disconnect_server(index):
            return self.error(err)
        await LogService.inst.add_log(
            f"{self.acct.name} had been disconnected {server_name} succesfully.",
            "manage.judge.disconnect",
        )

        self.error(("S", ""))


class JudgeChalCntSub(WebSocketSubHandler):
    async def listen_newchal(self):
        async for msg in self.p.listen():
            if msg["type"] != "message":
                continue

            await self.write_message(msg["data"].decode("utf-8"))

    async def open(self):
        await self.p.subscribe("judgechalcnt_sub")

        self.task = asyncio.tasks.Task(self.listen_newchal())
