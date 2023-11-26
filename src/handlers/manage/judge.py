import base64
import asyncio

from redis import asyncio as aioredis
from msgpack import packb, unpackb

import config
from handlers.base import RequestHandler, reqenv, require_permission, WebSocketHandler
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
                await LogService.inst.add_log(f"{self.acct.name} tried connected {server_name} but failed.",
                                              'manage.judge.connect.failure')
                self.error(err)
                return

            await LogService.inst.add_log(f"{self.acct.name} had been connected {server_name} succesfully.",
                                          'manage.judge.connect')

            self.finish('S')
            return

        elif reqtype == 'disconnect':
            index = int(self.get_argument('index'))
            pwd = str(self.get_argument('pwd'))

            err, server_inform = await JudgeServerClusterService.inst.get_server_status(index)
            if (server_name := server_inform['name']) == '':
                server_name = f"server-{index}"

            if config.unlock_pwd != base64.b64encode(packb(pwd)):
                await LogService.inst.add_log(f"{self.acct.name} tried to disconnect {server_name} but failed.",
                                              'manage.judge.disconnect.failure')
                self.error('Eacces')
                return

            err = await JudgeServerClusterService.inst.disconnect_server(index)
            await LogService.inst.add_log(f"{self.acct.name} had been disconnected {server_name} succesfully.",
                                          'manage.judge.disconnect')
            if err:
                self.error(err)
                return

            self.finish('S')
            return


class JudgeChalCntSub(WebSocketHandler):
    async def open(self):
        self.ars = aioredis.Redis(host='localhost', port=6379, db=1)
        self.p = self.ars.pubsub()
        await self.p.subscribe('judgechalcnt_sub')

        async def loop():
            async for msg in self.p.listen():
                if msg['type'] != 'message':
                    continue

                await self.on_message(msg['data'].decode('utf-8'))

        self.task = asyncio.tasks.Task(loop())

    async def on_message(self, msg):
        await self.write_message(msg)

    def on_close(self) -> None:
        self.task.cancel()

    def check_origin(self, origin):
        # TODO: secure
        return True
