import datetime
from msgpack import packb, unpackb

from req import WebSocketHandler

class InformService:
    def __init__(self, db, rs) -> None:
        self.db = db
        self.rs = rs
        InformService.inst = self

    async def set_inform(self, text):
        inform_list = unpackb(self.rs.get('inform'))
        inform_list.append({ 'text': str(text), 'time': str(datetime.datetime.now())[:-7]})
        await self.rs.set('inform', packb(inform_list))
        await self.rs.publish('informsub', 1)
        return

    async def edit_inform(self, index, text):
        inform_list = unpackb((await self.rs.get('inform')))
        inform_list[int(index)] = {'text': str(text), 'time': str(datetime.datetime.now())[:-7]}
        await self.rs.set('inform', packb(inform_list))
        return

    async def del_inform(self, index):
        inform_list = unpackb((await self.rs.get('inform')))
        inform_list.pop(int(index))
        await self.rs.set('inform', packb(inform_list))
        return

import redis

class InformSub(WebSocketHandler):
    def open(self):
        self.ars = redis.Redis(db=1)
        self.p = self.ars.pubsub()
        self.p.subscribe('informsub')

    def on_message(self, msg):
        for ms in self.p.listen():
            if ms['type'] == 'message':
                self.write_message(str(int(ms['data'])))

    def on_close(self) -> None:
        self.p.close()

    def check_origin(self, origin: str) -> bool:
        return True
