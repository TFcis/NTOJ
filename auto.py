import os
import json
import msgpack
import tornado.web
import tornado.gen
import tornadoredis
import datetime
from req import Service
from req import RequestHandler
from req import reqenv
from user import UserConst
from user import UserService
class AutoService:
    def __init__(self,db,rs):
        self.db = db
        self.rs = rs
        AutoService.inst = self
class AutoHandler(RequestHandler):

    @reqenv
    def get(self):
        self.finish('S')
        return
    @reqenv
    def post(self):
        reqtype = str(self.get_argument('reqtype'))
        auto_list = msgpack.unpackb(self.rs.get('auto_list'),encoding = 'utf-8')
        if reqtype == 'auto':
            nowtime = datetime.datetime.now()
            for contn in auto_list:
                time = self.rs.get(contn+'_contest')
                if time == None:
                    auto_list.remove(contn)
                    continue
                time = msgpack.unpackb(time,encoding = 'utf-8')
                time['start']=datetime.datetime.fromtimestamp(time['start'])
                time['end']=datetime.datetime.fromtimestamp(time['end'])
                starttime = datetime.datetime.strptime(str(time['start']),
                    '%Y-%m-%d %H:%M:%S')
                endtime = datetime.datetime.strptime(str(time['end']),
                    '%Y-%m-%d %H:%M:%S')
                if nowtime < starttime:
                    pass
                elif starttime <= nowtime and nowtime < endtime:
                    cont = msgpack.unpackb(self.rs.get(contn+'_contest'),encoding = 'utf-8')
                    pro_list = cont['pro_list']
                    for pro_id in pro_list:
                        err,pro = yield from Service.Pro.get_pro(pro_id,None,True)
                        if err:
                            return
                        if pro['status'] == Service.Pro.STATUS_ONLINE:
                            continue
                        err, ret = yield from Service.Pro.update_pro(pro['pro_id'], pro['name'], Service.Pro.STATUS_ONLINE, pro['class'], pro['expire'], None, None, pro['tags'])
                elif endtime <= nowtime:

                    cont = msgpack.unpackb(self.rs.get(contn+'_contest'),encoding = 'utf-8')
                    pro_list = cont['pro_list']
                    for pro_id in pro_list:
                        err,pro = yield from Service.Pro.get_pro(pro_id,None,True)
                        if err:
                            return
                        if pro['status'] == Service.Pro.STATUS_HIDDEN:
                            continue
                        err, ret = yield from Service.Pro.update_pro(pro['pro_id'], pro['name'], Service.Pro.STATUS_HIDDEN, pro['class'], pro['expire'], None, None, pro['tags'])
                        err,pro = yield from Service.Pro.get_pro(pro_id,None,True)
                    auto_list.remove(contn)
            self.rs.set('auto_list',msgpack.packb(auto_list))
        elif reqtype == 'add':
            cont_name = str(self.get_argument('cont_name'))
            if cont_name not in auto_list:
                auto_list.append(cont_name)
            self.rs.set('auto_list',msgpack.packb(auto_list))
        elif reqtype == 'remove':
            cont_name = str(self.argument('cont_name'))
            auto_list.remove(cont_name)
            self.rs.set('auto_list',msgpack.packb(auto_list))
        self.finish('S')
        return
