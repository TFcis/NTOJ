import asyncio
import base64

import config
from msgpack import packb, unpackb

from handlers.base import RequestHandler, WebSocketSubHandler, reqenv, require_permission
from services.judge import JudgeServerClusterService
from services.log import LogService
from services.user import UserConst


class ManageJudgeHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
        judge_status_list = await JudgeServerClusterService.inst.get_servers_status()
        await self.render('manage/judge', page='judge', judge_status_list=judge_status_list)

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        reqtype = self.get_argument('reqtype')

        if reqtype == 'connect':
            index = int(self.get_argument('index'))

            err, server_inform = await JudgeServerClusterService.inst.get_server_status(index)
            if (server_name := server_inform['name']) == '':
                server_name = f"server-{index}"

            err = await JudgeServerClusterService.inst.connect_server(index)
            if err:
                await LogService.inst.add_log(
                    f"{self.acct.name} tried connected {server_name} but failed.", 'manage.judge.connect.failure'
                )
                self.error(err)
                return

            await LogService.inst.add_log(
                f"{self.acct.name} had been connected {server_name} succesfully.", 'manage.judge.connect'
            )

            self.finish('S')

        elif reqtype == 'disconnect':
            index = int(self.get_argument('index'))
            pwd = str(self.get_argument('pwd'))

            err, server_inform = await JudgeServerClusterService.inst.get_server_status(index)
            if (server_name := server_inform['name']) == '':
                server_name = f"server-{index}"

            if config.unlock_pwd != base64.b64encode(packb(pwd)):
                await LogService.inst.add_log(
                    f"{self.acct.name} tried to disconnect {server_name} but failed.", 'manage.judge.disconnect.failure'
                )
                self.error('Eacces')
                return

            err = await JudgeServerClusterService.inst.disconnect_server(index)
            await LogService.inst.add_log(
                f"{self.acct.name} had been disconnected {server_name} succesfully.", 'manage.judge.disconnect'
            )
            if err:
                self.error(err)
                return

            self.finish('S')


class JudgeChalCntSub(WebSocketSubHandler):
    async def listen_newchal(self):
        async for msg in self.p.listen():
            if msg['type'] != 'message':
                continue

            await self.on_message(msg['data'].decode('utf-8'))

    async def open(self):
        await self.p.subscribe('judgechalcnt_sub')

        self.task = asyncio.tasks.Task(self.listen_newchal())

    async def on_message(self, msg):
        await self.write_message(msg)
