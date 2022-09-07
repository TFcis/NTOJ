import msgpack
import base64
import bcrypt
import psycopg2
from group import GroupConst
import config
from log import LogService

class UserConst:
    MAIL_MAX = 1024
    MAIL_MIN = 1
    PW_MAX = 1024
    PW_MIN = 1
    NAME_MAX = 16
    NAME_MIN = 1

    ACCTTYPE_KERNEL = 0
    ACCTTYPE_USER = 3

    ACCTID_GUEST = 0

class UserService:
    MAIL_MAX = 1024
    MAIL_MIN = 1
    PW_MAX = 1024
    PW_MIN = 1
    NAME_MAX = 32
    NAME_MIN = 1

    ACCTTYPE_KERNEL = 0
    ACCTTYPE_USER = 3

    ACCTID_GUEST = 0

    def __init__(self, db, rs):
        self.db = db
        self.rs = rs
        UserService.inst = self

    def sign_in(self, mail, pw):
        cur = yield self.db.cursor()
        yield cur.execute(('SELECT "acct_id","password" FROM "account" '
            'WHERE "mail" = %s;'),
            (mail, ))

        if cur.rowcount != 1:
            return ('Esign', None)

        acct_id, hpw = cur.fetchone()
        hpw = base64.b64decode(hpw.encode('utf-8'))
        if bcrypt.hashpw(pw.encode('utf-8'), hpw) == hpw:
            return (None, acct_id)

        return ('Esign', None)

    def sign_up(self, mail, pw, name):
        if len(mail) < UserConst.MAIL_MIN:
            return ('Emailmin', None)
        if len(mail) > UserConst.MAIL_MAX:
            return ('Emailmax', None)
        if len(pw) < UserConst.PW_MIN:
            return ('Epwmin', None)
        if len(pw) > UserConst.PW_MAX:
            return ('Epwmax', None)
        if len(name) < UserConst.NAME_MIN:
            return ('Enamemin', None)
        if len(name) > UserConst.NAME_MAX:
            return ('Enamemax', None)

        hpw = bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt(12))

        cur = yield self.db.cursor()

        try:
            yield cur.execute(('INSERT INTO "account" '
                '("mail","password","name","acct_type","class","group") '
                'VALUES (%s,%s,%s,%s,\'{%s}\',%s) RETURNING "acct_id";'),
                (mail,base64.b64encode(hpw).decode('utf-8'), name,
                    UserConst.ACCTTYPE_USER, 1, GroupConst.DEFAULT_GROUP))

        except psycopg2.IntegrityError:
            return ('Eexist', None)

        if cur.rowcount != 1:
            return ('Eunk', None)

        self.rs.delete('acctlist')
        return (None, cur.fetchone()[0])

    def info_sign(self,req):
        acct_id = req.get_secure_cookie('id')
        try:
            ip = req.request.remote_ip

        except Exception as e:
            print(e)
            ip = ''

        if acct_id == None:
            return ('Esign', None, ip)

        acct_id = int(acct_id)

        acct = self.rs.exists('account@%d' % acct_id)
        if acct == None:
            cur = yield self.db.cursor()
            yield cur.execute('SELECT "acct_id","lastip" FROM "account" WHERE "acct_id" = %s;',
                    (acct_id, ))

            if cur.rowcount != 1:
                return ('Esign', None, ip)
            tmpid, lastip = cur.fetchone()
            #print("%s %s"%(lastip,ip))
            if lastip != ip and ip != '':
                yield from LogService.inst.add_log("Update acct {} lastip from {} to {} ".format(acct_id, lastip, ip))
                yield cur.execute('UPDATE "account" SET "lastip" = %s WHERE "acct_id" = %s;', (ip, acct_id))
                self.rs.delete('account@%d' % acct_id)
                self.rs.delete('acctlist')

        else:
            try:
                acct2 = self.rs.get('account@%d' % acct_id)
                acct2 = msgpack.unpackb(acct2, encoding = 'utf-8')
                lastip = ''
                if 'lastip' in acct2:
                    lastip = acct2['lastip']
                if ip != '' and lastip != ip:
                    yield from LogService.inst.add_log("Update acct {} lastip from {} to {} ".format(acct_id, lastip, ip))
                    cur = yield self.db.cursor()
                    yield cur.execute('UPDATE "account" SET "lastip" = %s WHERE "acct_id" = %s;', (ip, acct_id))
                    self.rs.delete('account@%d' % acct_id)
                    self.rs.delete('acctlist')

            except Exception as e:
                print(e)


        return (None, acct_id, ip)

    def info_acct(self, acct_id):
        if acct_id == None:
            return (None, {
                'acct_id'   : 0,
                'acct_type' : UserConst.ACCTTYPE_USER,
                'class'     : 0,
                'name'      : '',
                'photo'     : '',
                'cover'     : '',
                'lastip'    : ''
            })

        acct = self.rs.get('account@%d' % acct_id)
        if acct != None:
            acct = msgpack.unpackb(acct, encoding='utf-8')

        else:
            cur = yield self.db.cursor()
            yield cur.execute(('SELECT "mail","name","acct_type",'
                '"class","photo","cover","lastip" '
                'FROM "account" WHERE "acct_id" = %s;'),
                (acct_id, ))
            if cur.rowcount != 1:
                return ('Enoext', None)

            mail, name, acct_type, clas, photo, cover, lastip = cur.fetchone()
            acct = {
                'acct_id'  : acct_id,
                'acct_type': acct_type,
                'class'    : clas[0],
                'mail'     : mail,
                'name'     : name,
                'photo'    : photo,
                'cover'    : cover,
                'lastip'   : lastip
            }

            self.rs.setnx('account@%d' % acct_id, msgpack.packb(acct))

        return (None, {
            'acct_id'  : acct['acct_id'],
            'acct_type': acct['acct_type'],
            'class'    : acct['class'],
            'name'     : acct['name'],
            'photo'    : acct['photo'],
            'cover'    : acct['cover']
        })

    def update_acct(self, acct_id, acct_type, clas, name, photo, cover):
        if (acct_type not in
                [UserConst.ACCTTYPE_KERNEL, UserConst.ACCTTYPE_USER]):
            return ('Eparam1', None)
        if clas not in [0,1,2]:
            return ('Eparam2', None)
        if len(name) < UserConst.NAME_MIN:
            return ('Enamemin', None)
        if len(name) > UserConst.NAME_MAX:
            return ('Enamemax', None)

        cur = yield self.db.cursor()
        yield cur.execute(('UPDATE "account" '
            'SET "acct_type" = %s,"class" = \'{%s}\',"name" = %s,'
            '"photo" = %s,"cover" = %s '
            'WHERE "acct_id" = %s;'),
            (acct_type, clas, name, photo, cover, acct_id))
        if cur.rowcount != 1:
            return ('Enoext', None)

        yield cur.execute('REFRESH MATERIALIZED VIEW test_valid_rate;')
        self.rs.delete('account@%d' % acct_id)
        self.rs.delete('acctlist')
        self.rs.delete('prolist')
        self.rs.delete('rate@kernel_True')
        self.rs.delete('rate@kernel_False')

        return (None, None)

    def update_pw(self,acct_id,old,pw,isadmin):
        if len(pw) < UserConst.PW_MIN:
            return ('Epwmin', None)
        if len(pw) > UserConst.PW_MAX:
            return ('Epwmax', None)

        cur = yield self.db.cursor()
        yield cur.execute(('SELECT "password" FROM "account" '
            'WHERE "acct_id" = %s;'),
            (acct_id,))
        if cur.rowcount != 1:
            return ('Eacct', None)

        hpw = base64.b64decode(cur.fetchone()[0].encode('utf-8'))
        if (bcrypt.hashpw(old.encode('utf-8'), hpw) != hpw) and isadmin==False:
            return ('Epwold', None)

        hpw = bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt(12))
        yield cur.execute(('UPDATE "account" SET "password" = %s '
            'WHERE "acct_id" = %s;'),
            (base64.b64encode(hpw).decode('utf-8'), acct_id))

        return (None, None)

    def list_acct(self, min_type=UserConst.ACCTTYPE_USER, private=False):
        field = '%d|%d' % (min_type, private)
        acctlist = self.rs.hget('acctlist', field)
        if acctlist != None:
            acctlist = msgpack.unpackb(acctlist, encoding='utf-8')

        else:
            cur = yield self.db.cursor()
            yield cur.execute(('SELECT "acct_id","acct_type",'
                '"name","mail","class","lastip" '
                'FROM "account" WHERE "acct_type" >= %s '
                'ORDER BY "acct_id" ASC;'),
                (min_type,))

            acctlist = []
            for acct_id, acct_type, name, mail, clas, lastip in cur:
                acct = {
                    'acct_id'  : acct_id,
                    'acct_type': acct_type,
                    'name'     : name,
                    'class'    : clas[0],
                    'lastip'   : lastip
                }

                if private == True:
                    acct['mail'] = mail

                acctlist.append(acct)

            self.rs.hset('acctlist', field, msgpack.packb(acctlist))

        return (None, acctlist)
