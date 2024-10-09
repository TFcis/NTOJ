import asyncio

from handlers.base import RequestHandler, WebSocketSubHandler, reqenv
from services.bulletin import BulletinService
from services.judge import JudgeServerClusterService


class BulletinHandler(RequestHandler):
    @reqenv
    async def get(self, bulletin_id=None):
        if bulletin_id is None:
            can_submit = JudgeServerClusterService.inst.is_server_online()
            _, bulletin_list = await BulletinService.inst.list_bulletin()
            bulletin_list.sort(key=lambda b: (b['pinned'], b['timestamp']), reverse=True)

            await self.render('info', bulletin_list=bulletin_list, judge_server_status=can_submit)
            return

        bulletin_id = int(bulletin_id)
        err, bulletin = await BulletinService.inst.get_bulletin(bulletin_id)
        if err:
            self.error(err)
            return

        await self.render('bulletin', bulletin=bulletin)


class BulletinSub(WebSocketSubHandler):
    async def listen_newbulletin(self):
        async for msg in self.p.listen():
            if msg['type'] != 'message':
                continue

            await self.on_message(str(int(msg['data'])))

    async def open(self):
        await self.rs.incr('online_counter', 1)
        await self.rs.sadd('online_counter_set', self.request.remote_ip)
        await self.p.subscribe('bulletinsub')

        self.task = asyncio.tasks.Task(self.listen_newbulletin())

    async def on_message(self, msg):
        await self.write_message(msg)

    def on_close(self) -> None:
        super().on_close()
        asyncio.create_task(self.rs.decr('online_counter', 1))
        asyncio.create_task(self.rs.srem('online_counter_set', self.request.remote_ip))
