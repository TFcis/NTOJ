import msgpack
import os
import json
import datetime
import tornado.web
import config
from log import LogService
from user import UserConst
from req import RequestHandler
from req import reqenv
from req import Service
from group import GroupConst
import msgpack
import base64
class ManageHandler(RequestHandler):
    @reqenv
    def get(self,page = 'dash'):
        if self.acct['acct_type'] != UserConst.ACCTTYPE_KERNEL:
            self.error('Eacces')
            return

        if page == 'dash':
            self.render('manage-dash',page = page)
            return

        elif page == 'pro':
            err,prolist = yield from Service.Pro.list_pro(self.acct)
            lock_list = msgpack.unpackb(self.rs.get('lock_list'),encoding='utf-8')
            self.render('manage-pro',page = page,prolist = prolist,lock_list = lock_list)
            return

        elif page == 'addpro':
            self.render('manage-pro-add',page = page)
            return

        elif page == 'updatepro':
            pro_id = int(self.get_argument('proid'))

            err,pro = yield from Service.Pro.get_pro(pro_id,self.acct)
            if err:
                self.error(err)
                return
            lock = self.rs.get(str(pro['pro_id'])+'_owner')

            testl = list()
            for test_idx, test_conf in pro['testm_conf'].items():
                testl.append({
                    'test_idx': test_idx,
                    'timelimit': test_conf['timelimit'],
                    'memlimit': test_conf['memlimit'],
                    'weight': test_conf['weight'],
                    'rate': 2000
                })

            self.render('manage-pro-update', page=page, pro=pro, lock=lock, testl=testl)
            return

        elif page == 'contest':
            try:
                cont_name = str(self.get_argument('cont'))
                if cont_name != 'Add_cont':
                    err,cont_meta = Service.Contest.get(cont_name)
                    if err:
                        self.finish('Eexist')
                        return
                else:
                    cont_meta = {'start':datetime.datetime.now().replace(tzinfo=datetime.timezone(datetime.timedelta(hours=8))),'end':datetime.datetime.now().replace(tzinfo=datetime.timezone(datetime.timedelta(hours=8)))}

            except tornado.web.HTTPError:
                cont_name = 'Add_cont'
                cont_meta = {'start':datetime.datetime.now().replace(tzinfo=datetime.timezone(datetime.timedelta(hours=8))),'end':datetime.datetime.now().replace(tzinfo=datetime.timezone(datetime.timedelta(hours=8)))}

            self.render('manage-contest',
                    page = page,
                    meta = Service.Contest.get('default')[1],
                    contlist = Service.Contest.get_list(),
                    cont_meta = cont_meta,
                    cont_name = cont_name)
            return

        elif page == 'acct':
            err,acctlist = yield from Service.Acct.list_acct(
                    UserConst.ACCTTYPE_KERNEL,True)

            self.render('manage-acct',page = page,acctlist = acctlist)
            return

        elif page == 'updateacct':
            acct_id = int(self.get_argument('acctid'))

            err,acct = yield from Service.Acct.info_acct(acct_id)
            glist = yield from Service.Group.list_group()
            group = yield from Service.Group.group_of_acct(acct_id)
            self.render('manage-acct-update',page = page,acct = acct,glist = glist,group = group)
            return
        elif page == 'question':
            err,acctlist = yield from Service.Acct.list_acct(UserConst.ACCTTYPE_KERNEL,True)
            asklist = {}
            for acct in acctlist:
                ask = self.rs.get(str(acct['acct_id'])+'_msg_ask')
                if ask == None:
                    asklist.update({acct['acct_id']:False})
                else:
                    asklist.update({acct['acct_id']:msgpack.unpackb(self.rs.get(str(acct['acct_id'])+'_msg_ask'),encoding = 'utf-8')})
            self.render('manage-question',page = page,acctlist = acctlist,asklist = asklist)
            return
        elif page == 'rquestion':
            qacct_id = int(self.get_argument('qacct'))
            err,ques_list = Service.Question.get_queslist(acct = None,acctid = qacct_id)
            self.rs.set(str(qacct_id)+'_msg_ask',msgpack.packb(False))
            self.render('manage-rquestion',page = page,qacct_id = qacct_id,ques_list = ques_list)
            return
        elif page == 'inform':
            inform_list = msgpack.unpackb(self.rs.get('inform'),encoding = 'utf-8')
            self.render('manage-inform',page = page,inform_list = inform_list)
            return
        elif page == 'proclass':
            try:
                pclas_name = str(self.get_argument('pclas_name'))
            except:
                pclas_name = None
            if pclas_name == None:
                self.render('manage-proclass',page = page,pclas_name = pclas_name,clas_list = Service.Pro.get_class_list(),p_list = None)
                return
            else:
                err,p_list = Service.Pro.get_pclass_list(pclas_name)
                if err:
                    self.finish(err)
                    return
                self.render('manage-proclass',page = page,pclas_name = pclas_name,clas_list = Service.Pro.get_class_list(),p_list = p_list)
            return
        elif page == 'group':
            try:
                gname = str(self.get_argument('gname'))
                cur = yield self.db.cursor()
                yield cur.execute('SELECT '
                    '"group"."group_type","group"."group_class" '
                    'FROM "group" '
                    'WHERE "group"."group_name"=%s;'
                    ,(gname,))
                (gtype,gclas) = cur.fetchone()
                gtype = int(gtype)
                gclas = int(gclas)
            except:
                gname = None
                gtype = None
                gclas = None
            glist = yield from Service.Group.list_group()
            if gname != None:
                gacct = yield from Service.Group.list_acct_in_group(gname)
            else:
                gacct = None
            self.render('manage-group',page = page,gname = gname,glist = glist,gacct = gacct,gtype = gtype,gclas = gclas)

            return
    @reqenv
    def post(self,page):
        if self.acct['acct_type'] != UserConst.ACCTTYPE_KERNEL:
            self.finish('Eacces')
            return

        if page == 'pack':
            reqtype = self.get_argument('reqtype')

            if reqtype == 'gettoken':
                err,pack_token = Service.Pack.gen_token()
                self.finish(json.dumps(pack_token))
                return

        elif page == 'pro':
            reqtype = self.get_argument('reqtype')

            if reqtype == 'addpro':
                name = self.get_argument('name')
                status = int(self.get_argument('status'))
                clas = int(self.get_argument('class'))
                expire = None
                pack_token = self.get_argument('pack_token')

                err,pro_id = yield from Service.Pro.add_pro(
                        name,status,clas,expire,pack_token)
                yield from LogService.inst.add_log((self.acct['name']+" had been send a request to add the problem #"+str(pro_id)))
                if err:
                    self.finish(err)
                    return

                self.finish(json.dumps(pro_id))
                return

            elif reqtype == 'updatepro':
                pro_id = int(self.get_argument('pro_id'))
                name = self.get_argument('name')
                status = int(self.get_argument('status'))
                clas = int(self.get_argument('class'))
                expire = None
                pack_type = int(self.get_argument('pack_type'))
                pack_token = self.get_argument('pack_token')
                tags = self.get_argument('tags')

                if pack_token == '':
                    pack_token = None

                err,ret = yield from Service.Pro.update_pro(
                    pro_id, name, status, clas, expire, pack_type, pack_token, tags)
                yield from LogService.inst.add_log((self.acct['name']+" had been send a request to update the problem #"+str(pro_id)))
                if err:
                    self.finish(err)
                    return

                self.finish('S')
                return

            elif reqtype == 'updatelimit':
                pro_id = int(self.get_argument('pro_id'))
                timelimit = int(self.get_argument('timelimit'))
                memlimit = int(self.get_argument('memlimit'))

                err, ret = yield from Service.Pro.update_limit(pro_id, timelimit, memlimit)
                yield from LogService.inst.add_log(('{} had been send a request to update the problem #{}'.format(self.acct['name'], pro_id)))
                if err:
                    self.finish(err)
                    return

                self.finish('S')
                return

            elif reqtype == 'rechal':
                pro_id = int(self.get_argument('pro_id'))

                err,pro = yield from Service.Pro.get_pro(pro_id,self.acct)
                if err:
                    self.finish(err)
                    return
                yield from LogService.inst.add_log((self.acct['name']+" made a request to rejudge the problem #"+str(pro_id)))
                cur = yield self.db.cursor()
                yield cur.execute(('SELECT "chal_id" FROM "challenge" '
                    'WHERE "pro_id" = %s'),
                    (pro_id,))

                for chal_id, in cur:
                    err,ret = yield from Service.Chal.reset_chal(chal_id)
                    err,ret = yield from Service.Chal.emit_chal(
                            chal_id,
                            pro_id,
                            pro['testm_conf'],
                            '/nfs/code/%d/main.cpp'%chal_id,
                            '/nfs/problem/%d/res'%pro_id)

                self.finish('S')
                return
            elif reqtype == 'pro-lock':
                pro_id = self.get_argument('pro_id')
                self.rs.set(str(pro_id)+'_owner',msgpack.packb(1))
                lock_list = msgpack.unpackb(self.rs.get('lock_list'),encoding='utf-8')
                if int(pro_id) not in lock_list:
                    lock_list.append(int(pro_id))
                self.rs.set('lock_list',msgpack.packb(lock_list))
                self.finish('S')
                return
            elif reqtype == 'pro-unlock':
                pro_id = self.get_argument('pro_id')
                pwd = str(self.get_argument('pwd'))
                if config.unlock_pwd != base64.encodestring(msgpack.packb(pwd)):
                    self.finish('Eacces')
                    return
                lock_list = msgpack.unpackb(self.rs.get('lock_list'),encoding='utf-8')
                lock_list.remove(int(pro_id))
                self.rs.set('lock_list',msgpack.packb(lock_list))
                self.rs.delete(str(pro_id)+'_owner')
                self.finish('S')
                return

        elif page == 'contest':
            reqtype = self.get_argument('reqtype')
            if reqtype == 'set':
                cont_name = str(self.get_argument('cont_name'))
                clas = int(self.get_argument('class'))
                status = int(self.get_argument('status'))
                start = self.get_argument('start')
                end = self.get_argument('end')
                yield from LogService.inst.add_log((self.acct['name']+" was setting the contest \""+str(cont_name)+"\"."))
                err,start = self.trantime(start)
                if err:
                    self.finish(err)
                    return

                err,end = self.trantime(end)
                if err:
                    self.finish(err)
                    return
                if cont_name == 'default':
                    yield from Service.Contest.set('default',clas,status,start,end)
                else:
                    pro_list = str(self.get_argument('pro_list'))
                    acct_list = str(self.get_argument('acct_list'))
                    yield from Service.Contest.set(cont_name = cont_name,clas = None,status = status,start = start,end = end,pro_list = pro_list,acct_list = acct_list)
                self.finish('S')
                return
            elif reqtype == 'del':
                cont_name = self.get_argument('cont_name')
                Service.Contest.remove_cont(cont_name)
                self.finish('S')
                yield from LogService.inst.add_log((self.acct['name']+" was removing the contest \""+str(cont_name)+"\"."))
                return
        elif page == 'acct':
            reqtype = self.get_argument('reqtype')

            if reqtype == 'updateacct':
                acct_id = int(self.get_argument('acct_id'))
                acct_type = int(self.get_argument('acct_type'))
                clas = int(self.get_argument('class'))
                group = str(self.get_argument('group'))
                #if group == GroupConst.KERNEL_GROUP:
                #    self.finish('Ekernel')
                #    return
                err,acct = yield from Service.Acct.info_acct(acct_id)
                if err:
                    yield from LogService.inst.add_log(("{}(#{}) had been send a request to update the account #{} but not found".format(self.acct['name'], self.acct['acct_id'], acct_id)))
                    self.finish(err)
                    return

                yield from LogService.inst.add_log(("{}(#{}) had been send a request to update the account {}(#{})".format(self.acct['name'], self.acct['acct_id'], acct['name'], acct_id)))

                err,ret = yield from Service.Acct.update_acct(acct_id,
                        acct_type,clas,acct['name'],acct['photo'],acct['cover'])
                if err:
                    self.finish(err)
                    return
                err = yield from Service.Group.set_acct_group(acct_id,group)
                self.finish('S')
                return
        elif page == 'rquestion':
            reqtype = self.get_argument('reqtype')
            if reqtype == 'rpl':
                yield from LogService.inst.add_log((self.acct['name']+" replyed a question from user #"+str(self.get_argument('qacct_id'))+":\""+str(self.get_argument('rtext'))+"\"."))
                index = self.get_argument('index')
                rtext = self.get_argument('rtext')
                qacct_id = int(self.get_argument('qacct_id'))
                Service.Question.reply(self.acct,qacct_id,index,rtext)
                self.finish('S')
                return
            if reqtype == 'rrpl':
                yield from LogService.inst.add_log((self.acct['name']+" re-replyed a question from user #"+str(self.get_argument('qacct_id'))+":\""+str(self.get_argument('rtext'))+"\"."))
                index = self.get_argument('index')
                rtext = self.get_argument('rtext')
                qacct_id = int(self.get_argument('qacct_id'))
                Service.Question.reply(self.acct,qacct_id,index,rtext)
                self.finish('S')
                return
        elif page == 'inform':
            reqtype = str(self.get_argument('reqtype'))

            if reqtype == 'set':
                text = self.get_argument('text')
                Service.Inform.set_inform(text)
                yield from LogService.inst.add_log((self.acct['name']+" added a line on bulletin: \""+text+"\"."))
                return
            elif reqtype == 'edit':
                index = self.get_argument('index')
                text = self.get_argument('text')
                yield from LogService.inst.add_log((self.acct['name']+" changed a line on bulletin to: \""+text+"\" which it used to be the #"+str(int(index)+1)+"th row."))
                Service.Inform.edit_inform(index,text)
                return
            elif reqtype == 'del':
                index = self.get_argument('index')
                yield from LogService.inst.add_log((self.acct['name']+" removed a line on bulletin which it used to be the #"+str(int(index)+1)+"th row."))
                Service.Inform.del_inform(index)
                return
            return
        elif page == 'proclass':
            reqtype = str(self.get_argument('reqtype'))
            if reqtype == 'add':
                pclas_name = str(self.get_argument('pclas_name'))
                p_list = str(self.get_argument('p_list'))
                p_list = p_list.replace(' ','').split(',')
                p_list2 =[]
                for p in p_list:
                    p_list2.append(int(p))
                p_list = p_list2
                Service.Pro.add_pclass(pclas_name,p_list)
                self.finish('S')
                return
            elif reqtype == 'remove':
                pclas_name = str(self.get_argument('pclas_name'))
                Service.Pro.remove_pclass(pclas_name)
                self.finish('S')
                return
            elif reqtype == 'edit':
                pclas_name = str(self.get_argument('pclas_name'))
                p_list = str(self.get_argument('p_list'))
                p_list = p_list.replace(' ','').split(',')
                p_list2 = []
                for p in p_list:
                    p_list2.append(int(p))
                p_list = p_list2
                Service.Pro.edit_pclass(pclas_name,p_list)
                self.finish('S')
                return
        elif page == 'group':
            reqtype = str(self.get_argument('reqtype'))
            if reqtype == 'edit':
                gname = str(self.get_argument('gname'))
                gtype = int(self.get_argument('gtype'))
                gclas = int(self.get_argument('gclas'))
                if gname == GroupConst.KERNEL_GROUP:
                    self.finish('Ekernel')
                    return
                err = yield from Service.Group.update_group(gname,gtype,gclas)
                if err:
                    self.finish(err)
                    return
                self.finish('S')
                return
            elif reqtype == 'add_group':
                gname = str(self.get_argument('gname'))
                gtype = int(self.get_argument('gtype'))
                gclas = int(self.get_argument('gclas'))
                err = yield from Service.Group.add_group(gname,gtype,gclas)
                self.finish('S')
                return
            elif reqtype == 'del_group':
                gname = str(self.get_argument('gname'))
                if gname in [GroupConst.KERNEL_GROUP,GroupConst.DEFAULT_GROUP]:
                    self.finish('Ekernel')
                    return
                err = yield from Service.Group.del_group(gname)
                self.finish('S')
                return
        self.finish('Eunk')
        return

    def trantime(self,time):
        if time == '':
            time = None

        else:
            try:
                time = datetime.datetime.strptime(time,
                        '%Y-%m-%dT%H:%M:%S.%fZ')
                time = time.replace(tzinfo = datetime.timezone.utc)

            except ValueError:
                return ('Eparam',None)

        return (None,time)
