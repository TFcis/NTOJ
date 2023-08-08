import datetime

from msgpack import packb, unpackb


class InformService:
    def __init__(self, db, rs) -> None:
        self.db = db
        self.rs = rs
        InformService.inst = self

    async def set_inform(self, text):
        inform_list = unpackb((await self.rs.get('inform')))
        inform_list.append({'text': str(text), 'time': str(datetime.datetime.now())[:-7], 'color': 'white'})
        inform_list.sort(key=lambda row: row['time'], reverse=True)
        await self.rs.set('inform', packb(inform_list))
        await self.rs.publish('informsub', 1)
        return

    async def edit_inform(self, index, text, color):
        inform_list = unpackb((await self.rs.get('inform')))
        inform_list[int(index)] = {'text': str(text), 'time': str(datetime.datetime.now())[:-7], 'color': color}
        inform_list.sort(key=lambda row: row['time'], reverse=True)
        await self.rs.set('inform', packb(inform_list))
        await self.rs.publish('informsub', 1)
        return

    async def del_inform(self, index):
        inform_list = unpackb((await self.rs.get('inform')))
        inform_list.pop(int(index))
        inform_list.sort(key=lambda row: row['time'], reverse=True)
        await self.rs.set('inform', packb(inform_list))
        return
