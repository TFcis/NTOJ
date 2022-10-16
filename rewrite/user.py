import base64

from msgpack import packb, unpackb
import bcrypt
import asyncpg

import config
from group import GroupConst
from log import LogService

from dbg import dbg_print

class UserConst:
    MAIL_MAX = 1024
    MAIL_MIN = 1
    PW_MAX = 1024
    PW_MIN = 1
    NAME_MAX = 27 #3227
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

    async def sign_in(self, mail, pw):
        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    SELECT "acct_id","password" FROM "account"
                    WHERE "mail" = $1;
                ''',
                mail
            )
        if result.__len__() != 1:
            return ('Esign', None)

        acct_id = result[0]['acct_id']
        hpw = result[0]['password']

        hpw = base64.b64decode(hpw.encode('utf-8'))
        if bcrypt.hashpw(pw.encode('utf-8'), hpw) == hpw:
            return (None, acct_id)

        return ('Esign', None)

    async def sign_up(self, mail, pw, name):
        tmp_len = len(mail)
        if tmp_len < UserConst.MAIL_MIN:
            return ('Emailmin', None)
        if tmp_len > UserConst.MAIL_MAX:
            return ('Emailmax', None)
        tmp_len = len(pw)
        if tmp_len < UserConst.PW_MIN:
            return ('Epwmin', None)
        if tmp_len > UserConst.PW_MAX:
            return ('Epwmax', None)
        tmp_len = len(name)
        if tmp_len < UserConst.NAME_MIN:
            return ('Enamemin', None)
        if tmp_len > UserConst.NAME_MAX:
            return ('Enamemax', None)
        del tmp_len

        hpw = bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt(12))

        try:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    '''
                        INSERT INTO "account"
                        ("mail", "password", "name", "acct_type", "class", "group")
                        VALUES ($1, $2, $3, $4, $5, $6) RETURNING "acct_id";
                    ''',
                    mail, base64.b64encode(hpw).decode('utf-8'), name, UserConst.ACCTTYPE_USER, [1], GroupConst.DEFAULT_GROUP
                )

        except asyncpg.IntegrityConstraintViolationError:
            return ('Eexist', None)

        if result.__len__() != 1:
            return ('Eexist', None)

        await self.rs.delete('acctlist')
        return (None, result[0]['acct_id'])

    async def info_sign(self, req):
        acct_id = req.get_secure_cookie('id')
        try:
            ip = req.request.remote_ip

        except Exception as e:
            ip = ''

        if acct_id == None:
            return ('Esign', None, ip)

        acct_id = int(acct_id)

        if (acct := (await self.rs.exists(f'account@{acct_id}'))) == None:
            async with self.db.acquire() as con:
                result = await con.fetch('SELECT "acct_id","lastip" FROM "account" WHERE "acct_id" = $1;', acct_id)

                if result.__len__() != 1:
                    return ('Esign', None, ip)
                result = result[0]

                if result['lastip'] != ip and ip != '':
                    await LogService.inst.add_log(f"Update acct {acct_id} lastip from {lastip} to {ip} ")
                    await con.execute('UPDATE "account" SET "lastip" = $1 WHERE "acct_id" = $2;', ip, acct_id)
                    await self.rs.delete(f'account@{acct_id}')
                    await self.rs.delete('acctlist')

        else:
            try:
                acct2 = await self.rs.get(f'account@{acct_id}')
                acct2 = unpackb(acct2)
                lastip = ''
                if 'lastip' in acct2:
                    lastip = acct2['lastip']

                if lastip != ip and ip != '':
                    await LogService.inst.add_log(f"Update acct {acct_id} lastip from {lastip} to {ip} ")

                    async with self.db.acquire() as con:
                        await con.execute('UPDATE "account" SET "lastip" = $1 WHERE "acct_id" = $2;', ip, acct_id)

                    await self.rs.delete(f'account@{acct_id}')
                    await self.rs.delete('acctlist')

            except Exception as e:
                print(e)

        return (None, acct_id, ip)

    async def info_acct(self, acct_id):
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
        acct_id = int(acct_id)

        if (acct := (await self.rs.get(f'account@{acct_id}'))) != None:
            acct = unpackb(acct)

        else:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    '''
                        SELECT "name", "acct_type", "mail",
                        "class", "photo", "cover", "lastip"
                        FROM "account" WHERE "acct_id" = $1;
                    ''',
                    acct_id
                )
            if result.__len__() != 1:
                return ('Enoext', None)
            result = result[0]

            acct = {
                'acct_id' : acct_id,
                'acct_type' : result['acct_type'],
                'class': result['class'][0],
                'mail' : result['mail'],
                'name' : result['name'],
                'photo' : result['photo'],
                'cover' : result['cover'],
                'lastip' : result['lastip'],
            }

            await self.rs.setnx(f'account@{acct_id}', packb(acct))
            del acct['mail']

        return (None, acct)

        # return (None, {
        #     'acct_id'   : acct_id,
        #     'acct_type' : acct['acct_type'],
        #     'class'     : acct['class'],
        #     'name'      : acct['name'],
        #     'photo'     : acct['photo'],
        #     'cover'     : acct['cover'],
        #     'lastip'    : acct['lastip'],
        # })

    async def update_acct(self, acct_id, acct_type, clas, name, photo, cover):
        if (acct_type not in [UserConst.ACCTTYPE_KERNEL, UserConst.ACCTTYPE_USER]):
            return ('Eparam1', None)
        if clas not in [0, 1, 2]:
            return ('Eparam2', None)
        name_len = len(name)
        if name_len < UserConst.NAME_MIN:
            return ('Enamemin', None)
        if name_len > UserConst.NAME_MAX:
            return ('Enamemax', None)
        acct_id = int(acct_id)

        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    UPDATE "account"
                    SET "acct_type" = $1, "name" = $2,
                    "photo" = $3, "cover" = $4, "class" = $5 WHERE "acct_id" = $6 RETURNING "acct_id";
                ''',
                acct_type, name, photo, cover, [clas], acct_id
            )
            if result.__len__() != 1:
                return ('Enoext', None)

            await con.execute('REFRESH MATERIALIZED VIEW test_valid_rate;')

        await self.rs.delete(f'account@{acct_id}')
        await self.rs.delete('acctlist')
        await self.rs.delete('prolist')
        await self.rs.delete('rate@kernel_True')
        await self.rs.delete('rate@kernel_False')
        dbg_print(__file__, 241, delete_rate=True)

        return (None, None)

    async def update_pw(self, acct_id, old, pw, isadmin):
        pw_len = len(pw)
        if pw_len < UserConst.PW_MIN:
            return ('Epwmin', None)
        if pw_len > UserConst.PW_MAX:
            return ('Epwmax', None)
        acct_id = int(acct_id)

        async with self.db.acquire() as con:
            result = await con.fetch('SELECT "password" FROM "account" WHERE "acct_id" = $1;', acct_id)
            if result.__len__() != 1:
                return ('Eexist', None)
            result = result[0]

            hpw = base64.b64encode(result['password'].encode('utf-8'))
            if (bcrypt.hashpw(old.encode('utf-8'), hpw) != hpw) and isadmin == False:
                return ('Epwold', None)

            hpw = bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt(12))
            await con.execute('UPDATE "account" SET "password" = $1 WHERE "acct_id" = $2',
                    (base64.b64encode(hpw).decode('utf-8'), acct_id))

        return (None, None)

    async def list_acct(self, min_type=UserConst.ACCTTYPE_USER, private=False, reload=False):
        field = f'{min_type}|{int(private)}'
        if (acctlist := (await self.rs.hget('acctlist', field))) != None and reload == False:
            acctlist = unpackb(acctlist)

        else:

            async with self.db.acquire() as con:
                result = await con.fetch(
                    '''
                        SELECT "acct_id", "acct_type", "class", "name", "mail", "lastip"
                        FROM "account" WHERE "acct_type" >= $1
                        ORDER BY "acct_id" ASC;
                    ''',
                    min_type
                )

            acctlist = []
            for (acct_id, acct_type, clas, name, mail, lastip) in result:
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

            await self.rs.hset('acctlist', field, packb(acctlist))

        return (None, acctlist)
