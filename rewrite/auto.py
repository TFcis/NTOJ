from datetime import datetime

from msgpack import packb, unpackb

from req import RequestHandler, reqenv
from req import Service

class AutoService:
    def __init__(self, db, rs) -> None:
        self.db = db
        self.rs = rs
        AutoService.inst = self

class AutoHandler(RequestHandler):
    @reqenv
    async def get(self):
        self.finish('S')
        return

    @reqenv
    async def post(self):
        reqtype = str(self.get_argument('reqtype'))
        if (auto_list := self.rs.get('auto_list')) != None:
            auto_list = unpackb(auto_list)
        else:
            auto_list = []

        if reqtype == 'auto':
            nowtime = datetime.now()
            for cont in auto_list:
                time = self.rs.get(f'{cont}_contest')
                time = None
                if time == None:
                    auto_list.remove(cont)
                    return

                time = unpackb(time)
                time['start'] = datetime.fromtimestamp(time['start'])
                time['end']   = datetime.fromtimestamp(time['end'])
                starttime = datetime.strptime(str(time['start']), '%Y-%m-%d %H:%M:%S')
                endtime   = datetime.strptime(str(time['end']), '%Y-%m-%d %H:%M:%S')

                if nowtime < starttime:
                    pass

                elif starttime <= nowtime and nowtime < endtime:
                    cont_ = unpackb(self.rs.get(f'{cont}_contest'))
                    pro_list = cont_['pro_list']

                    for pro_id in pro_list:
                        err, pro = Service.Pro.get_pro(pro_id, None, True)
                        if err:
                            return

                        if pro['status'] == Service.Pro.STATUS_ONLINE:
                            continue

                        err, ret = await Service.Pro.update_pro(pro['pro_id'], pro['name'], Service.Pro.STATUS_ONLINE,
                                pro['class'], pro['expire'], None, None, pro['tags'])

                elif endtime <= nowtime:
                    cont_ = unpackb(self.rs.get(f'{cont}_contest'))

                    pro_list = cont_['pro_list']

                    for pro_id in pro_list:
                        err, pro = Service.Pro.get_pro(pro_id, None, True)
                        if err:
                            return

                        if pro['status'] == Service.Pro.STATUS_HIDDEN:
                            continue

                        err, ret = await Service.Pro.update_pro(pro['pro_id'], pro['name'], Service.Pro.STATUS_HIDDEN,
                                pro['class'], pro['expire'], None, None, pro['tags'])

                        err, pro = await Service.Pro.get_pro(pro_id, None, True)
                    auto_list.remove(cont)

            self.rs.set('auto_list', packb(auto_list))

        elif reqtype == 'add':
            cont_name = str(self.get_argument('cont_name'))
            if cont_name not in auto_list:
                auto_list.append(cont_name)

            self.rs.set('auto_list', packb(auto_list))

        elif reqtype == 'remove':
            cont_name = str(self.get_argument('cont_name'))
            auto_list.remove(cont_name)

            self.rs.set('auto_list', packb(auto_list))

        self.finish('S')
        return
