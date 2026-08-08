import base64

from msgpack import packb

import config
from handlers.base import (
    ActionDispatcher,
    RequestHandler,
    UnifiedWebSocketHandler,
    reqenv,
    require_permission,
)
from services.judge import JudgeServerClusterService
from services.log import LogService
from services.user import UserConst


class JudgeCntCallback:
    """Judge server challenge count update callback - simple message forwarding"""

    async def register(self, conn):
        """Registering does not require special handling"""
        pass

    async def message(self, conn, data):
        """Directly forward the message"""
        return data

    async def unregister(self, conn):
        """Unsubscribing does not require special handling"""
        pass


_judge_cnt_callback = JudgeCntCallback()
UnifiedWebSocketHandler.register_channel_callback("judgechalcnt_sub", _judge_cnt_callback)


judge_dispatcher = ActionDispatcher()


class ManageJudgeHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
        judge_status_list = JudgeServerClusterService.inst.get_servers_status()
        await self.render(
            "manage/judge", "Manage Judge", page="judge", judge_status_list=judge_status_list
        )

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        reqtype = self.get_argument("reqtype")
        return await judge_dispatcher.dispatch(self, reqtype)

    @judge_dispatcher.action("connect")
    async def connect_judge(self):
        try:
            index = int(self.get_argument("index"))
        except ValueError:
            return self.error(("Eparam", "Invalid index"))

        err, server_inform = JudgeServerClusterService.inst.get_server_status(index)
        if err:
            return self.error(err)
        if (server_name := server_inform["name"]) == "":
            server_name = f"server-{index}"

        if err := await JudgeServerClusterService.inst.connect_server(index):
            await self.add_log(
                f"{self.acct.name} tried to connect to {server_name} but failed",
                "manage.judge.connect.failure",
            )
            return self.error(err)

        await self.add_log(
            f"{self.acct.name} connected to {server_name} successfully",
            "manage.judge.connect",
        )

        self.error(("S", ""))

    @judge_dispatcher.action("disconnect")
    async def disconnect_judge(self):
        try:
            index = int(self.get_argument("index"))
        except ValueError:
            return self.error(("Eparam", "Invalid index"))
        pwd = self.get_argument("pwd")

        err, server_inform = JudgeServerClusterService.inst.get_server_status(index)
        if err:
            return self.error(err)
        if (server_name := server_inform["name"]) == "":
            server_name = f"server-{index}"

        if config.unlock_pwd != base64.b64encode(packb(pwd)):
            await self.add_log(
                f"{self.acct.name} tried to disconnect {server_name} but failed",
                "manage.judge.disconnect.failure",
            )
            return self.error(("Eacces", "Wrong password"))

        if err := await JudgeServerClusterService.inst.disconnect_server(index):
            return self.error(err)
        await self.add_log(
            f"{self.acct.name} disconnected {server_name} successfully",
            "manage.judge.disconnect",
        )

        self.error(("S", ""))
