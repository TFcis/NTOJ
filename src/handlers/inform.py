from redis import asyncio as aioredis
import asyncio

from utils.req import WebSocketHandler
from utils.dbg import dbg_print
class InformSub(WebSocketHandler):
    async def open(self):
        self.ars = aioredis.Redis(host='localhost', port=6379, db=1)
        await self.ars.incr('online_counter', 1)
        await self.ars.sadd('online_counter_set', self.request.remote_ip)
        self.p = self.ars.pubsub()
        await self.p.subscribe('informsub')

        async def test():
            async for msg in self.p.listen():
                if msg['type'] != 'message':
                    continue

                await self.on_message(str(int(msg['data'])))

        self.task = asyncio.tasks.Task(test())

    async def on_message(self, msg):
        self.write_message(msg)

    def on_close(self) -> None:
        dbg_print(__file__, 64, ip=self.request.remote_ip)
        asyncio.create_task(self.ars.decr('online_counter', 1))
        asyncio.create_task(self.ars.srem('online_counter_set', self.request.remote_ip))
        self.task.cancel()

    def check_origin(self, origin):
        # TODO: secure
        return True
