import os
import json
import msgpack
import tornado.web
import tornado.gen
import tornadoredis
import datetime
from req import WebSocketHandler
from user import UserConst
from user import UserService

class InformService:
    def __init__(self, db, rs):
        self.db = db
        self.rs = rs
        InformService.inst = self

    def set_inform(self, text):
        inform_list = msgpack.unpackb(self.rs.get('inform'), encoding='utf-8')
        inform_list.append({'text': str(text), 'time': str(datetime.datetime.now())[:-7]})
        self.rs.set('inform', msgpack.packb(inform_list))
        self.rs.publish('informsub', 1)
        return

    def edit_inform(self, index, text):
        inform_list = msgpack.unpackb(self.rs.get('inform'), encoding='utf-8')
        inform_list[int(index)] = {'text': str(text), 'time': str(datetime.datetime.now())[:-7]}
        self.rs.set('inform', msgpack.packb(inform_list))
        return

    def del_inform(self, index):
        inform_list = msgpack.unpackb(self.rs.get('inform'), encoding='utf-8')
        inform_list.pop(int(index))
        self.rs.set('inform', msgpack.packb(inform_list))
        return

class InformSub(WebSocketHandler):
    @tornado.gen.engine
    def open(self):
        self.ars = tornadoredis.Client(selected_db=1)
        self.ars.connect()
        yield tornado.gen.Task(self.ars.subscribe, 'informsub')
        self.ars.listen(self.on_message)

    def on_message(self, msg):
        if msg.kind == 'message':
            self.write_message(str(int(msg.body)))

    def on_close(self):
        self.ars.disconnect()
