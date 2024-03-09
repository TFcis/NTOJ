import asyncio

from redis import asyncio as aioredis

from handlers.base import RequestHandler, WebSocketHandler, reqenv
from services.bulletin import BulletinService
from services.judge import JudgeServerClusterService


class BulletinHandler(RequestHandler):
    @reqenv
    async def get(self, bulletin_id=None):
        if bulletin_id is None:
            can_submit = await JudgeServerClusterService.inst.is_server_online()
            _, bulletin_list = await BulletinService.inst.list_bulletin()
            bulletin_list.sort(key=lambda b: (b['pinned'], b['timestamp']), reverse=True)

            await self.render('info', bulletin_list=bulletin_list, judge_server_status=can_submit)
            return

        bulletin_id = int(bulletin_id)
        _, bulletin = await BulletinService.inst.get_bulletin(bulletin_id)
        await self.render('bulletin', bulletin=bulletin)


class BulletinSub(WebSocketHandler):
    async def open(self):
        self.ars = aioredis.Redis(host='localhost', port=6379, db=1)
        await self.ars.incr('online_counter', 1)
        await self.ars.sadd('online_counter_set', self.request.remote_ip)
        self.p = self.ars.pubsub()
        await self.p.subscribe('bulletinsub')

        async def test():
            async for msg in self.p.listen():
                if msg['type'] != 'message':
                    continue

                await self.on_message(str(int(msg['data'])))

        self.task = asyncio.tasks.Task(test())

    async def on_message(self, msg):
        self.write_message(msg)

    def on_close(self) -> None:
        asyncio.create_task(self.ars.decr('online_counter', 1))
        asyncio.create_task(self.ars.srem('online_counter_set', self.request.remote_ip))
        self.task.cancel()

    def check_origin(self, origin):
        # TODO: secure
        return True
