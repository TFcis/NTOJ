import os
import json
import msgpack
import math
import datetime
import tornado.process
import tornado.concurrent
import tornado.web
import tornado.gen
import time
import random
import re
from collections import OrderedDict

from req import RequestHandler
from req import reqenv
from user import UserService
from user import UserConst
from chal import ChalService
from pack import PackService

class ProConst:
    NAME_MIN = 1
    NAME_MAX = 64
    CODE_MAX = 16384
    STATUS_ONLINE = 0
    STATUS_HIDDEN = 1
    STATUS_OFFLINE = 2

class ProService:
    NAME_MIN = 1
    NAME_MAX = 64
    CODE_MAX = 16384
    STATUS_ONLINE = 0
    STATUS_HIDDEN = 1
    STATUS_OFFLINE = 2

    PACKTYPE_FULL = 1
    PACKTYPE_CONTHTML = 2
    PACKTYPE_CONTPDF = 3

    def __init__(self,db,rs):
        self.db = db
        self.rs = rs

        ProService.inst = self

    def get_pclass_list(self,pro_clas):
        clas = self.rs.get(str(pro_clas)+'_pro_list')
        if clas == None:
            return ('Eexist',None)
        return (None,msgpack.unpackb(clas,encoding = 'utf-8'))
    def get_class_list(self):
        clas_list = self.rs.get('pro_class_list')
        if clas_list == None:
            self.rs.set('pro_class_list',msgpack.packb([]))
            return []
        return msgpack.unpackb(clas_list,encoding = 'utf-8')
    def add_pclass(self,pclas_name,p_list):
        clas_list = self.get_class_list()
        if str(pclas_name) in clas_list:
            return 'Eexist'
        clas_list.append(pclas_name)
        self.rs.set('pro_class_list',msgpack.packb(clas_list))
        self.rs.set(str(pclas_name)+'_pro_list',msgpack.packb(p_list))
        return None
    def remove_pclass(self,pclas_name):
        clas_list = self.get_class_list()
        if str(pclas_name) not in clas_list:
            return 'Eexist'
        clas_list.remove(pclas_name)
        self.rs.set('pro_class_list',msgpack.packb(clas_list))
        self.rs.delete(str(pclas_name)+'_pro_list')
        return None
    def edit_pclass(self,pclas_name,p_list):
        clas_list = self.get_class_list()
        if str(pclas_name) not in clas_list:
            return 'Exist'
        self.rs.set(str(pclas_name)+'_pro_list',msgpack.packb(p_list))
        return None
    def get_pro(self,pro_id,acct = None,special = None):
        max_status = self._get_acct_limit(acct,special)

        cur = yield self.db.cursor()
        yield cur.execute(('SELECT "name","status","class","expire","tags" '
            'FROM "problem" WHERE "pro_id" = %s AND "status" <= %s;'),
            (pro_id,max_status))

        if cur.rowcount != 1:
            return ('Enoext',None)

        name,status,clas,expire,tags = cur.fetchone()
        clas = clas[0]
        if expire == datetime.datetime.max:
            expire = None

        yield cur.execute(('SELECT "test_idx","compile_type","score_type",'
            '"check_type","timelimit","memlimit","weight","metadata" '
            'FROM "test_config" WHERE "pro_id" = %s ORDER BY "test_idx" ASC;'),
            (pro_id,))

        testm_conf = OrderedDict()
        for (test_idx,comp_type,score_type,check_type,timelimit,memlimit,weight,
                metadata) in cur:
            testm_conf[test_idx] = {
                'comp_type':comp_type,
                'score_type':score_type,
                'check_type':check_type,
                'timelimit':timelimit,
                'memlimit':memlimit,
                'weight':weight,
                'metadata':json.loads(metadata,'utf-8')
            }

        return (None,{
            'pro_id':pro_id,
            'name':name,
            'status':status,
            'expire':expire,
            'class':clas,
            'testm_conf':testm_conf,
            'tags':tags,
        })

    def list_pro(self,acct = None,state = False,clas = None):
        def _mp_encoder(obj):
            if isinstance(obj,datetime.datetime):
                return obj.astimezone(datetime.timezone.utc).timestamp()

            return obj

        if acct == None:
            max_status = ProService.STATUS_ONLINE

        else:
            max_status = self._get_acct_limit(acct)

        if clas == None:
            clas = [1,2]

        else:
            clas = [clas]

        cur = yield self.db.cursor()

        statemap = {}
        if state == True:
            yield cur.execute(('SELECT "problem"."pro_id",'
                'MIN("challenge_state"."state") AS "state" '
                'FROM "challenge" '
                'INNER JOIN "challenge_state" '
                'ON "challenge"."chal_id" = "challenge_state"."chal_id" '
                'AND "challenge"."acct_id" = %s '
                'INNER JOIN "problem" '
                'ON "challenge"."pro_id" = "problem"."pro_id" '
                'WHERE "problem"."status" <= %s AND "problem"."class" && %s '
                'GROUP BY "problem"."pro_id" '
                'ORDER BY "pro_id" ASC;'),
                (acct['acct_id'],max_status,clas))

            for pro_id,state in cur:
                statemap[pro_id] = state

        field = '%d|%s'%(max_status,str(clas))
        prolist = self.rs.hget('prolist',field)
        if prolist != None:
            prolist = msgpack.unpackb(prolist,encoding = 'utf-8')
            for pro in prolist:
                expire = pro['expire']
                if expire != None:
                    expire = datetime.datetime.fromtimestamp(expire)
                    expire = expire.replace(tzinfo = datetime.timezone(
                        datetime.timedelta(hours = 8)))

                pro['expire'] = expire

        else:
            yield cur.execute(('select '
                '"problem"."pro_id",'
                '"problem"."name",'
                '"problem"."status",'
                '"problem"."expire",'
                '"problem"."class",'
                '"problem"."tags",'
                'sum("test_valid_rate"."rate") as "rate" '
                'from "problem" '
                'inner join "test_valid_rate" '
                'on "test_valid_rate"."pro_id" = "problem"."pro_id" '
                'where "problem"."status" <= %s and "problem"."class" && %s '
                'group by "problem"."pro_id" '
                'order by "pro_id" asc;'),
                (max_status,clas))

            prolist = list()
            for pro_id,name,status,expire,clas,tags,rate in cur:
                if expire == datetime.datetime.max:
                    expire = None

                prolist.append({
                    'pro_id':pro_id,
                    'name':name,
                    'status':status,
                    'expire':expire,
                    'class':clas[0],
                    'tags':tags,
                    'rate':rate,
                })

            self.rs.hset('prolist',field,msgpack.packb(prolist,
                default = _mp_encoder))

        now = datetime.datetime.utcnow()
        now = now.replace(tzinfo = datetime.timezone.utc)

        for pro in prolist:
            pro_id = pro['pro_id']
            if pro_id in statemap:
                pro['state'] = statemap[pro_id]

            else:
                pro['state'] = None

            if pro['expire'] == None:
                pro['outdate'] = False

            else:
                delta = (pro['expire'] - now).total_seconds()
                if delta < 0:
                    pro['outdate'] = True

                else:
                    pro['outdate'] = False

        return (None,prolist)

    def add_pro(self,name,status,clas,expire,pack_token):
        if len(name) < ProService.NAME_MIN:
            return ('Enamemin',None)
        if len(name) > ProService.NAME_MAX:
            return ('Enamemax',None)
        if (status < ProService.STATUS_ONLINE or
                status > ProService.STATUS_OFFLINE):
            return ('Eparam',None)
        if clas not in [1,2]:
            return ('Eparam',None)

        if expire == None:
            expire = datetime.datetime(2099,12,31,0,0,0,0,
                    tzinfo = datetime.timezone.utc)

        cur = yield self.db.cursor()
        yield cur.execute(('INSERT INTO "problem" '
            '("name","status","class","expire") '
            'VALUES (%s,%s,%s,%s) RETURNING "pro_id";'),
            (name,status,[clas],expire))

        if cur.rowcount != 1:
            return ('Eunk',None)

        pro_id = cur.fetchone()[0]

        err,ret = yield from self._unpack_pro(pro_id,ProService.PACKTYPE_FULL,pack_token)
        if err:
            return (err,None)

        yield cur.execute('REFRESH MATERIALIZED VIEW test_valid_rate;')
        self.rs.delete('prolist')
        self.rs.delete('rate@kernel_True')
        self.rs.delete('rate@kernel_False')

        return (None,pro_id)

    def update_pro(self,pro_id,name,status,clas,expire,
            pack_type,pack_token = None, tags=''):
        if len(name) < ProService.NAME_MIN:
            return ('Enamemin',None)
        if len(name) > ProService.NAME_MAX:
            return ('Enamemax',None)
        if (status < ProService.STATUS_ONLINE or
                status > ProService.STATUS_OFFLINE):
            return ('Eparam',None)
        if clas not in [1,2]:
            return ('Eparam',None)
        if not re.match(r'^[a-zA-Z0-9-_, ]+$', tags):
            return ('Etags',None)

        if expire == None:
            expire = datetime.datetime(2099,12,31,0,0,0,0,
                    tzinfo = datetime.timezone.utc)
        cur = yield self.db.cursor()
        yield cur.execute(('UPDATE "problem" '
            'SET "name" = %s,"status" = %s,"class" = %s,"expire" = %s,"tags" = %s '
            'WHERE "pro_id" = %s;'),
            (name,status,[clas],expire,tags,pro_id))

        if cur.rowcount != 1:
            return ('Enoext',None)

        if pack_token != None:
            err,ret = yield from self._unpack_pro(pro_id,pack_type,pack_token)
            if err:
                return (err,None)

            yield cur.execute('REFRESH MATERIALIZED VIEW test_valid_rate;')

        self.rs.delete('prolist')
        self.rs.delete('rate@kernel_True')
        self.rs.delete('rate@kernel_False')

        return (None,None)

    def _get_acct_limit(self,acct,special = None):
        if special == True:
            return ProService.STATUS_OFFLINE
        if acct['acct_type'] == UserService.ACCTTYPE_KERNEL:
            return ProService.STATUS_OFFLINE

        else:
            return ProService.STATUS_ONLINE

    def _unpack_pro(self,pro_id,pack_type,pack_token):
        def _clean_cont(prefix):
            try:
                os.remove(prefix + 'cont.html')

            except OSError:
                pass

            try:
                os.remove(prefix + 'cont.pdf')

            except OSError:
                pass

        if (pack_type != ProService.PACKTYPE_FULL and
                pack_type != ProService.PACKTYPE_CONTHTML and
                pack_type != ProService.PACKTYPE_CONTPDF):
            return ('Eparam',None)

        if pack_type == ProService.PACKTYPE_CONTHTML:
            prefix = 'problem/%d/http/'%pro_id
            _clean_cont(prefix)
            ret = PackService.inst.direct_copy(pack_token,prefix + 'cont.html')

        elif pack_type == ProService.PACKTYPE_CONTPDF:
            prefix = 'problem/%d/http/'%pro_id
            _clean_cont(prefix)
            ret = PackService.inst.direct_copy(pack_token,prefix + 'cont.pdf')

        elif pack_type == ProService.PACKTYPE_FULL:
            err,ret = yield from PackService.inst.unpack(
                    pack_token,'problem/%d'%pro_id,True)
            if err:
                return (err,None)

            try:
                os.chmod('problem/%d'%pro_id,0o755)
                os.symlink(os.path.abspath('problem/%d/http'%pro_id),
                        '/srv/oj/http/problem/%d'%pro_id)

            except FileExistsError:
                pass

            try:
                conf_f = open('problem/%d/conf.json'%pro_id)
                conf = json.load(conf_f)
                conf_f.close()

            except Exception:
                return ('Econf',None)

            comp_type = conf['compile']
            score_type = conf['score']
            check_type = conf['check']
            timelimit = conf['timelimit']
            memlimit = conf['memlimit'] * 1024

            cur = yield self.db.cursor()
            yield cur.execute('DELETE FROM "test_config" WHERE "pro_id" = %s;',
                    (pro_id,))

            for test_idx,test_conf in enumerate(conf['test']):
                metadata = {
                    'data':test_conf['data']
                }
                yield cur.execute(('insert into "test_config" '
                    '("pro_id","test_idx",'
                    '"compile_type","score_type","check_type",'
                    '"timelimit","memlimit","weight","metadata") '
                    'values (%s,%s,%s,%s,%s,%s,%s,%s,%s);'),
                    (pro_id,test_idx,comp_type,score_type,check_type,
                        timelimit,memlimit,test_conf['weight'],
                        json.dumps(metadata)))

        return (None,None)

class ProsetHandler(RequestHandler):
    @reqenv
    def get(self):
        try:
            off = int(self.get_argument('off'))
        except tornado.web.HTTPError:
            off = 0
        try:
            clas = int(self.get_argument('class'))
        except tornado.web.HTTPError:
            clas = None
        try:
            pclas_name = str (self.get_argument('pclas_name'))
        except:
            pclas_name = None
        err,prolist = yield from ProService.inst.list_pro(
                self.acct,state = True,clas = clas)
        if pclas_name == None:
            pronum = len(prolist)
            prolist = prolist[off:off + 40]
            self.render('proset',pronum = pronum,prolist = prolist,clas = clas,pclas_name = pclas_name,pclist = ProService.inst.get_class_list(),pageoff = off)
            return
        else:
            err,p_list = ProService.inst.get_pclass_list(pclas_name)
            if err:
                self.finish(err)
                return
            prolist2 = []
            for pro in prolist:
                if pro['pro_id'] in p_list:
                    prolist2.append(pro)
            prolist = prolist2
            pronum = len(prolist)
            prolist = prolist[off:off + 40]
            self.render('proset',pronum = pronum,prolist = prolist,clas = clas, pclas_name = pclas_name,pclist = ProService.inst.get_class_list(),pageoff = off)
            return

        return

    @reqenv
    def post(self):
        pass

class ProStaticHandler(RequestHandler):
    @reqenv
    def get(self,pro_id,path):
        pro_id = int(pro_id)

        err,pro = yield from ProService.inst.get_pro(pro_id,self.acct)
        if err:
            self.finish(err)
            return

        if pro['status'] == ProService.STATUS_OFFLINE:
            self.finish('Eacces')
            return

        if path[-3:] == 'pdf':
            self.set_header('Pragma','public')
            self.set_header('Expires','0')
            self.set_header('Cache-Control','must-revalidate, post-check=0, pre-check=0')
            self.set_header('Content-Type','application/force-download')
            self.set_header('Content-Type','application/octet-stream')
            self.set_header('Content-Type','application/download')
            self.set_header('Content-Disposition','attachment; filename="pro%s.pdf"'%(pro_id))
            self.set_header('Content-Transfer-Encoding','binary')
        self.set_header('X-Accel-Redirect','/oj/problem/%d/%s'%(pro_id,path))
        return

class ProHandler(RequestHandler):
    @reqenv
    def get(self,pro_id):
        pro_id = int(pro_id)

        err,pro = yield from ProService.inst.get_pro(pro_id,self.acct)
        if err:
            self.finish(err)
            return

        if pro['status'] == ProService.STATUS_OFFLINE:
            self.finish('Eacces')
            return

        testl = list()
        for test_idx,test_conf in pro['testm_conf'].items():
            testl.append({
                'test_idx':test_idx,
                'timelimit':test_conf['timelimit'],
                'memlimit':test_conf['memlimit'],
                'weight':test_conf['weight'],
                'rate':2000
            })

        cur = yield self.db.cursor()

        yield cur.execute(('SELECT "test_idx","rate" FROM "test_valid_rate" '
            'WHERE "pro_id" = %s ORDER BY "test_idx" ASC;'),
            (pro_id,))

        countmap = {}
        for test_idx,count in cur:
            countmap[test_idx] = count

        for test in testl:
            if test['test_idx'] in countmap:
                test['rate'] = math.floor(countmap[test['test_idx']])

        add_tags = (self.acct['acct_type'] == UserService.ACCTTYPE_KERNEL)

        self.render('pro',pro = {
            'pro_id':pro['pro_id'],
            'name':pro['name'],
            'status':pro['status'],
            'tags':pro['tags'],
        },testl = testl, add_tags=add_tags)
        return

class ProTagsHandler(RequestHandler):
    @reqenv
    def post(self):
        if self.acct['acct_id'] == UserService.ACCTID_GUEST:
            self.finish('Esign')
            return

        tags = self.get_argument('tags')
        pro_id = int(self.get_argument('pro_id'))
        if tags and self.acct['acct_type'] == UserService.ACCTTYPE_KERNEL:
            err,pro = yield from ProService.inst.get_pro(pro_id,self.acct)
            if err:
                self.finish(err)
                return

            err,ret = yield from ProService.inst.update_pro(
                pro_id,pro['name'],pro['status'],pro['class'],pro['expire'],'',None,tags)
            if err:
                self.finish(err)
                return

        else:
            self.finish('Eaccess')
            return

        self.finish('setting tags done')
        return

class SubmitHandler(RequestHandler):
    @reqenv
    def get(self,pro_id):
        if self.acct['acct_id'] == UserService.ACCTID_GUEST:
            self.finish('login first')
            return

        pro_id = int(pro_id)
        err,pro = yield from ProService.inst.get_pro(pro_id,self.acct)
        if err:
            self.finish(err)
            return

        if pro['status'] == ProService.STATUS_OFFLINE:
            self.finish('Eacces')
            return

        self.render('submit',pro = pro)
        return

    @reqenv
    def post(self):
        if self.acct['acct_id'] == UserService.ACCTID_GUEST:
            self.finish('Esign')
            return

        reqtype = self.get_argument('reqtype')
        if reqtype == 'submit':
            pro_id = int(self.get_argument('pro_id'))
            code = self.get_argument('code')

            if len(code) > ProService.CODE_MAX:
                self.finish('Ecodemax')
                return
            if self.acct['acct_type'] != UserConst.ACCTTYPE_KERNEL:
                last_submit_name = 'last_submit_time_%s'%self.acct['acct_id']
                if self.rs.get(last_submit_name) == None:
                    self.rs.set(last_submit_name,int(time.time()))
                else:
                    last_submit_time = int(str(self.rs.get(last_submit_name))[2:-1])
                    if int(time.time())-last_submit_time < 30:
                        self.finish('Einternal')
                        return
                    else:
                        self.rs.set(last_submit_name,int(time.time()))

            err,pro = yield from ProService.inst.get_pro(pro_id,self.acct)
            if err:
                self.finish(err)
                return

            if pro['status'] == ProService.STATUS_OFFLINE:
                self.finish('Eacces')
                return
            #code = code.replace('bits/stdc++.h','DontUseMe.h')
            err,chal_id = yield from ChalService.inst.add_chal(
                    pro_id,self.acct['acct_id'],code)
            if err:
                self.finish(err)
                return

        elif (reqtype == 'rechal' and
                self.acct['acct_type'] == UserService.ACCTTYPE_KERNEL):

            chal_id = int(self.get_argument('chal_id'))

            err,ret = yield from ChalService.inst.reset_chal(chal_id)
            err,chal = yield from ChalService.inst.get_chal(chal_id,self.acct)

            pro_id = chal['pro_id']
            err,pro = yield from ProService.inst.get_pro(pro_id,self.acct)
            if err:
                self.finish(err)
                return

        else:
            self.finish('Eparam')
            return

        err,ret = yield from ChalService.inst.emit_chal(
                chal_id,
                pro_id,
                pro['testm_conf'],
                '/nfs/code/%d/main.cpp'%chal_id,
                '/judge/problem/%d/res'%pro_id)
        if err:
            self.finish(err)
            return

        if reqtype == 'submit' and pro['status'] == ProService.STATUS_ONLINE:
            self.rs.publish('challist_sub',1)

        self.finish(json.dumps(chal_id))
        return

class ChalListHandler(RequestHandler):
    @reqenv
    def get(self):
        try:
            off = int(self.get_argument('off'))

        except tornado.web.HTTPError:
            off = 0
        try:
            ppro_id = str(self.get_argument('proid'))
            tmp_pro_id = ppro_id.replace(' ','').split(',')
            pro_id = list()
            for p in tmp_pro_id:
                pro_id.append(int(p))

        except tornado.web.HTTPError:
            pro_id = None
            ppro_id = ''

        try:
            pacct_id = str(self.get_argument('acctid'))
            tmp_acct_id = pacct_id.replace(' ','').split(',')
            acct_id = list()
            for a in tmp_acct_id:
                acct_id.append(int(a))

        except tornado.web.HTTPError:
            acct_id = None
            pacct_id = ''

        try:
            state = int(self.get_argument('state'))
        except tornado.web.HTTPError:
            state = 0
        flt = {
            'pro_id':pro_id,
            'acct_id':acct_id,
            'state':state
        }

        err,chalstat = yield from ChalService.inst.get_stat(
                min(self.acct['acct_type'],UserService.ACCTTYPE_USER),flt)
        err,challist = yield from ChalService.inst.list_chal(off,20,
                min(self.acct['acct_type'],UserService.ACCTTYPE_USER),flt)
        self.render('challist',
                chalstat = chalstat,
                challist = challist,
                flt = flt,
                pageoff = off,
                ppro_id = ppro_id,
                pacct_id = pacct_id,
                acct = self.acct)
        return

    @reqenv
    def post(self):
        seq = self.get_argument('seq')

import tornadoredis
from req import WebSocketHandler

class ChalSubHandler(WebSocketHandler):
    @tornado.gen.engine
    def open(self):
        self.ars = tornadoredis.Client(selected_db = 1)
        self.ars.connect()

        yield tornado.gen.Task(self.ars.subscribe,'challist_sub')
        self.ars.listen(self.on_message)

    def on_message(self,msg):
        if msg.kind == 'message':
            self.write_message(str(int(msg.body)))

    def on_close(self):
        pass

class ChalHandler(RequestHandler):
    @reqenv
    def get(self,chal_id):
        chal_id = int(chal_id)

        err,chal = yield from ChalService.inst.get_chal(chal_id,self.acct)
        if err:
            self.finish(err)
            return

        err,pro = yield from ProService.inst.get_pro(chal['pro_id'],self.acct)
        if err:
            self.finish(err)
            return

        if self.acct['acct_type'] == UserService.ACCTTYPE_KERNEL:
            rechal = True

        else:
            rechal = False
        self.render('chal',pro = pro,chal = chal,rechal = rechal)
        return

    @reqenv
    def post(self):
        reqtype = self.get_argument('reqtype')
        self.finish('Eunk')
        return
