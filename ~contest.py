import msgpack
import math
import datetime
import time

from operator import attrgetter
from user import UserConst
from pro import ProConst
from req import RequestHandler
from req import reqenv
from req import Service

class ContestConst:
    STATUS_ONLINE = 0
    STATUS_HIDDEN = 1
    STATUS_OFFLINE = 2

class ContestService:
    def __init__(self,db,rs):
        self.db = db
        self.rs = rs

    def get(self,cont_name):
        if cont_name == 'default':
            data = self.rs.get('contest')
            if data == None:
                return (None,{
                    'class':0,
                    'status':ContestConst.STATUS_OFFLINE,
                    'start':datetime.datetime.now().replace(
                        tzinfo = datetime.timezone(
                        datetime.timedelta(hours = 8))),
                    'end':datetime.datetime.now().replace(
                        tzinfo = datetime.timezone(
                        datetime.timedelta(hours = 8))),
                })

            meta = msgpack.unpackb(data,encoding = 'utf-8')
            start = datetime.datetime.fromtimestamp(meta['start'])
            meta['start'] = start.replace(tzinfo = datetime.timezone(
                datetime.timedelta(hours = 8)))

            end = datetime.datetime.fromtimestamp(meta['end'])
            meta['end'] = end.replace(tzinfo = datetime.timezone(
                datetime.timedelta(hours = 8)))

            return (None,meta)
        else:
            cont_list = msgpack.unpackb(self.rs.get('contest_list',encoding = 'utf-8'))
            if cont_name in cont_list:
                meta = msgpack.unpackb(self.rs.get(cont_name+'_contest'),encoding = 'utf-8')
                start = datetime.datetime.fromtimestamp(meta['start'])
                meta['start'] = start.replace(tzinfo = datetime.timezone(
                    datetime.timedelta(hours = 8)))
                end = datetime.datetime.fromtimestamp(meta['end'])
                meta['end'] = end.replace(tzinfo = datetime.timezone(
                    datetime.timedelta(hours = 8)))
                return meta
            else:
                return ('Eexist',None)

    def set(self,cont_name,clas,status,start,end,pro_list = None,acct_list = None):
        def _mp_encoder(obj):
            if isinstance(obj,datetime.datetime):
                return obj.astimezone(datetime.timezone.utc).timestamp()

            return obj
        if cont_name == 'defualt':
            self.rs.set('contest',msgpack.packb({
                'class':clas,
                'status':status,
                'start':start,
                'end':end
            },default = _mp_encoder))

            self.rs.delete('rate@kernel_True')
            self.rs.delete('rate@kernel_False')

            return (None,None)
        else:
            self.rs.set(cont_name+'_contest',msgpack.unpackb({'status':status,'start':start,'end':end,'pro_list':pro_list,'acct_list':act_list},default = _mp_encoder))
            return (None,None)

    def running(self):
        err,meta = self.get('default')

        if meta['status'] == ContestConst.STATUS_OFFLINE:
            return (None,False)

        now = datetime.datetime.now().replace(
                tzinfo = datetime.timezone(datetime.timedelta(hours = 8)))
        if meta['start'] > now or meta['end'] <= now:
            return (None,False)

        return (None,True)

class BoardHandler(RequestHandler):
    @reqenv
    def get(self):
        try:
            cont_name = str(self.get_argument('cont'))
        except tornado.web.HTTPError:
            cont_name = 'default'
        print(cont_name)
        err,meta = Service.Contest.get(cont_name)
        if err:
            self.error(err)
            return
        delta = meta['end']-datetime.datetime.now().replace(tzinfo = datetime.timezone(datetime.timedelta(hours = 8)))
        deltasecond = delta.days*24*60*60+delta.seconds
        

        if deltasecond < 3600 and self.acct['acct_type'] != UserConst.ACCTTYPE_KERNEL:
            self.render('pboard')
            return

        if meta['status'] == ContestConst.STATUS_OFFLINE:
            self.error('Eacces')
            return

        if (meta['status'] == ContestConst.STATUS_HIDDEN and
                self.acct['acct_type'] != UserConst.ACCTTYPE_KERNEL):
            self.error('Eacces')
            return
        
        if cont_name == 'default':
            clas = meta['class']

            err,prolist = yield from Service.Pro.list_pro(acct = self.acct,
                clas = clas)
            err,acctlist = yield from Service.Rate.list_rate(acct = self.acct,
                clas = clas)
            err,ratemap = yield from Service.Rate.map_rate(clas = clas
)
            def turn(acct):
                acct_id=acct['acct_id']
                count=0
                for pro in prolist:
                    pro_id=pro['pro_id']
                    if acct_id in ratemap and pro_id in ratemap[acct_id]:
                        rate=ratemap[acct_id][pro_id]
                        count=count-rate['count']
                return (acct['rate'],count)

            submit_count={None:None}
            for acct in acctlist:
                acct_id = acct['acct_id']
                submit_count.update({acct_id:turn(acct)})
            acctlist.sort(key = lambda acct:submit_count[acct['acct_id']], reverse = True)

            acct_submit={None:None}
            for acct in acctlist:
                acct_id = acct['acct_id']
                acct_submit.update({acct_id:0})

            pro_sc_sub={None:None}
            for pro in prolist:
                pro_id = pro['pro_id']
                sc_add = 0
                sub_add = 0
                for acct in acctlist:
                    acct_id = acct['acct_id']
                    if acct_id in ratemap and pro_id in ratemap[acct_id]:
                        rate = ratemap[acct_id][pro_id]
                        sub_add += rate['count']
                        sc_add += rate['rate']
                        acct_submit[acct_id] += rate['count']
                pro_sc_sub.update({pro_id:(sc_add,sub_add)})

            rank = 0
            last_rate = None
            last_submit = None
            for acct in acctlist:
                submit = submit_count[acct['acct_id']][1]
                if acct['rate'] != last_rate:
                    rank += 1
                    last_rate = acct['rate']
                    last_submit = submit
                elif submit != last_submit and last_rate != 0:
                    rank +=1
                    last_submit = submit
                acct['rank'] = rank

            self.render('board',
                    prolist = prolist,
                    acctlist = acctlist,
                    ratemap = ratemap,
                    pro_sc_sub = pro_sc_sub,
                    acct_submit = acct_submit,
                    end = str(meta['end']).split('+')[0].replace('-','/'))
        else:
            err,prolist = yield from Service.Pro.list_pro(acct = self.acct)
            err,acctlist = yield from Service.Rate.list_rate(acct = self.acct)
            err,ratemap = yield from Service.Rate.map_rate()
            prolist2 = []
            for pro in prolist:
                if pro['pro_id'] in meta['pro_list']:
                    prolist2.append(pro)
            acctlist2 = []
            submit_count = {}
            for acct in acctlist:
                if acct['acct_id'] in meta['acct_list']:
                    acct['rate'] = 0
                    acct_id = acct['acct_id']
                    count = 0
                    for pro in prolist2:
                        pro_id = pro['pro_id']
                        if acct_id in ratemap and pro_id in ratemap[acct_id]:
                            rate = ratemap[acct_id][pro_id]
                            acct['rate'] += rate['rate']
                            count -= rate['count']
                    acctlist2.append(acct)
                    submit_count.update({acct_id:(acct['rate'],count)})
            acctlist2.sort(key = lambda acct:submit_count[acct['acct_id']],reverse = True)
            
            rank = 0
            last_sc = None
            last_sb = None
            for acct in acctlist2:
                acct_id = acct['acct_id']
                sc = submit_count[acct_id][0]
                sb = submit_count[acct_id][1]
                if sc != last_sc:
                    last_sc = sc
                    last_sb = sb
                    rank += 1
                elif sb != last_sb:
                    last_sb = sb
                    rank += 1
                acct['rank'] = rank
            pro_sc_sub = {}
            for pro in prolist2:
                pro_id = pro['pro_id']
                sc = 0
                sub = 0
                for acct in acctlist2:
                    acct_id = acct['acct_id']
                    if acct_id in ratemap and pro_id in ratemap[acct_id]:
                        rate = ratemap[acct_id][pro_id]
                        sc += rate['rate']
                        sub += rate['count']
                pro_sc_sub.update({pro_id:(sc,sub)})
                self.render('board',
                    prolist = prolist,
                    acctlist = acctlist,
                    ratemap = ratemap,
                    pro_sc_sub = pro_sc_sub,
                    acct_submit = acct_submit,
                    end = str(meta['end']).split('+')[0].replace('-','/'))

        return
