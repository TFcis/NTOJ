from req import Service
from req import reqenv
from req import RequestHandler

import xlwt3 as xlwt

class MoodleService:
    def __init__(self,db,rs):
        self.db = db
        self.rs = rs
        MoodleService.inst = self
    def list_moodle(self):
        cur = yield self.db.cursor()
        yield cur.execute('SELECT '
            '"moodle"."name" '
            'FROM "moodle";'
            )
        moodlelist = []
        for (name,) in cur:
            moodlelist.append(name)
        return moodlelist
    def add_moodle(self,grade,clas,count):
        moodlelist = yield from  self.list_moodle()
        mname = str(grade)+'%02d'%clas
        if mname in moodlelist:
            return 'Eexist'
        acctlist = []
        for i in range(1,count+1):
            acct_name = 's'+str(grade)+str(clas)+'%02d'%i
            acct_pwd = acct_name
            acct_id = yield from Service.Acct.sign_up(acct_name+'@tnfsh',acct_pwd,acct_name)
            acctlist.append(int(acct_id[1]))
        cur = yield self.db.cursor()
        yield cur.execute('INSERT INTO "moodle" '
            '("name","acctlist","prolist") '
            'VALUES (%s,%s,%s) '
            ,(mname,acctlist,[]))
        return None
    def update_moodle(self,mname,macctlist,mprolist):
        acctlist = []
        prolist = []
        macctlist = macctlist.replace(' ','').split(',')
        mprolist = mprolist.replace(' ','').split(',')
        acctlist[:] = [int(x) for x in macctlist]
        prolist[:] = [int(x) for x in mprolist]
        acctlist = list(set(acctlist))
        prolist = list(set(prolist))
        acctlist.sort()
        prolist.sort()
        cur = yield self.db.cursor()
        yield cur.execute('UPDATE "moodle" '
            'SET "acctlist" = %s,'
            'prolist = %s '
            'WHERE "name" = %s;'
            ,(acctlist,prolist,mname))
        return None
    def info_moodle(self,mname):
        cur = yield self.db.cursor()
        yield cur.execute('SELECT '
            '"moodle"."acctlist","moodle"."prolist" '
            'FROM "moodle" '
            'WHERE "moodle"."name" = %s;'
            ,(mname,))
        (acctlist,prolist) = cur.fetchone()
        acctlist[:] = [int(x) for x in acctlist]
        prolist[:] = [int(x) for x in prolist]
        return {'acct':acctlist,'pro':prolist}
    def moodle_pro_map(self,mname,mpro_id,order = False):
        info = yield from self.info_moodle(mname)
        acctlist = info['acct']
        if order:
            qorder = 'ORDER BY "score" DESC, "count" ASC '
        else:
            qorder = ''
        cur = yield self.db.cursor()
        yield cur.execute('SELECT '
            '"challenge"."acct_id",'
            'COUNT("challenge_state") AS "count", '
            'MAX("challenge_state"."ratte") AS "score" '
            'FROM "challenge" '
            'INNER JOIN "challenge_state" '
            'ON "challenge"."chal_id" = "challenge_state"."chal_id" '
            'WHERE ("challenge"."acct_id" && %s) '
            'AND ("challenge"."pro_id" = "challenge_state"."pro_id") '
            'GROUP BY "challenge"."acct_id" '
            '%s ;'
            ,(acctlist,mpro_id,qorder))
        ratemap = {}
        for (acct_id,score,count) in cur:
            ratemap[acct_id] = {'rate':score,'count':count}
        return ratemap
    def moodle_map(self,mname,order = False):
        info = yield from self.info_moodle(mname)
        acctlist = info['acct']
        prolist = info['pro']
        if order:
            qorder = 'ORDER BY score DESC, count ASC '
        else:
            qorder = ''
        #qorder = ''
        cur = yield self.db.cursor()
        yield cur.execute('SELECT '
            '"challenge"."acct_id", '
            '"challenge"."pro_id", '
            'MAX("challenge_state"."rate") AS "score", '
            'COUNT("challenge_state") AS "count" '
            'FROM "challenge" '
            'INNER JOIN "challenge_state" '
            'ON "challenge"."chal_id" = "challenge_state"."chal_id" '
            'WHERE (ARRAY["challenge"."acct_id"] && %s) '
            'AND   (ARRAY["challenge"."pro_id"] && %s) '
            'GROUP BY "challenge"."acct_id","challenge"."pro_id" '
            +qorder+' ;'
            ,(acctlist,prolist))
        ratemap = {}
        for (acct_id,pro_id,score,count) in cur:
            if acct_id not in ratemap:
                ratemap[acct_id] = {}
            ratemap[acct_id][pro_id] = {'rate':score,'count':count}
        return ratemap
    def create_excel(self,mname):
        info = yield from self.info_moodle(mname)
        workbook = xlwt.Workbook()
        sheet = workbook.add_sheet(mname)
        ratemap = yield from self.moodle_map(mname)
        acctlist = info['acct']
        prolist = info['pro']
        acctlist.sort()
        prolist.sort()
        i = 1
        for acct_id in acctlist:
            sheet.write(i,0,str(acct_id))
            j = 1
            for pro_id in prolist:
                if acct_id in ratemap and pro_id in ratemap[acct_id]:
                    rate = ratemap[acct_id][pro_id]
                    sheet.write(i,j,str(rate['rate']))
                j += 1
            i += 1
        i = 1
        for pro_id in prolist:
            sheet.write(0,i,str(pro_id))
            i += 1
        workbook.save('/srv/oj/share/'+mname+'.xls')
        return None
class MoodleHandler(RequestHandler):
    @reqenv
    def get(self,page):
        cur = yield self.db.cursor()
        if self.acct['acct_type'] == Service.Acct.ACCTTYPE_KERNEL:
            manage = True
        else:
            manage = False
        if page == 'dash':
            self.render('moodle',page = page,manage = manage)
            return
        elif page == 'board':
            try:
                mname = str(self.get_argument('mname'))
            except:
                mname = None
            if manage == True:
                moodlelist = yield from Service.Moodle.list_moodle()
            else:
                moodlelist = None
                yield cur.execute('SELECT '
                    '"moodle"."name" '
                    'FROM "moodle" '
                    'WHERE ARRAY[%s] && "moodle"."acctlist";'
                    ,(self.acct['acct_id'],))
                mname = cur.fetchone()[0]
            acctlist = None
            prolist = None
            ratemap = None
            pro_sc_sub = None
            if mname:
                info = yield from Service.Moodle.info_moodle(mname)
                acct = info['acct']
                acctlist = []
                for a in acct:
                    tacct = yield from Service.Acct.info_acct(a)
                    acctlist.append(tacct[1])
                prolist = info['pro']
                ratemap = yield from Service.Moodle.moodle_map(mname,True)
                sort_key = {}
                pro_sc_sub = {}
                for pro in prolist:
                    pro_sc_sub[pro] = (0,0)
                for acct in acctlist:
                    acct_id = acct['acct_id']
                    acct['rate'] = 0
                    acct['count'] = 0
                    for pro_id in prolist:
                        if acct_id in ratemap and pro_id in ratemap[acct_id]:
                            rate = ratemap[acct_id][pro_id]
                            acct['rate'] += rate['rate']
                            acct['count'] += rate['count']
                            tmp = pro_sc_sub[pro_id]
                            pro_sc_sub[pro_id] = (tmp[0]+rate['rate'],tmp[1]+rate['count'])
                    sort_key[acct_id] = (acct['rate'],-acct['count'])
                acctlist.sort(key = lambda acct:sort_key[acct['acct_id']],reverse = True)
                last_rate = None
                last_count = None
                rank = 0
                for acct in acctlist:
                    if acct['rate'] != last_rate:
                        rank += 1
                        last_rate = acct['rate']
                        last_count = acct['count']
                    elif acct['rate'] == last_rate and acct['count'] != last_count:
                        rank += 1
                        last_count = acct['count']
                    acct['rank'] = rank
            self.render('moodle-board',page = page,manage = manage,mname = mname,moodlelist = moodlelist,
                acctlist = acctlist ,prolist = prolist,ratemap = ratemap,pro_sc_sub = pro_sc_sub)
            return
        elif page == 'manage':
            if not manage:
                self.finish('Eacces')
                return
            try:
                mname = str(self.get_argument('mname'))
            except:
                mname = None
            moodlelist = yield from Service.Moodle.list_moodle()
            if mname and mname not in moodlelist:
                self.finish('Eacces')
                return
            acctlist = None
            prolist = None
            if mname:
                info = yield from Service.Moodle.info_moodle(mname)
                acctlist = info['acct']
                prolist = info['pro']

            self.render('moodle-manage',page = page,manage = manage,moodlelist = moodlelist,mname = mname,acctlist = acctlist,prolist = prolist)
            return
        self.finish('Eunk')
        return
    @reqenv
    def post(self,page):
        if page == 'manage':
            reqtype = str(self.get_argument('reqtype'))
            if reqtype == 'add':
                grade = int(self.get_argument('grade'))
                clas = int(self.get_argument('class'))
                count = int(self.get_argument('count'))
                if grade < 100 or clas <= 0 or count <= 0:
                    self.finish('Eparam')
                    return
                err = yield from Service.Moodle.add_moodle(grade,clas,count)
                if err:
                    self.finish(err)
                    return
                self.finish('S')
            elif reqtype == 'update':
                mname = str(self.get_argument('mname'))
                acctlist = str(self.get_argument('acctlist'))
                prolist = str(self.get_argument('prolist'))
                err = yield from Service.Moodle.update_moodle(mname,acctlist,prolist)
                if err:
                    self.finish(err)
                    return
                self.finish('S')
                return
            elif reqtype == 'export':
                mname = str(self.get_argument('mname'))
                err = yield from Service.Moodle.create_excel(mname)
                if err:
                    self.finish(err)
                    return
                self.finish('S')
                return
            return
        self.finish('Eunk')
        return
