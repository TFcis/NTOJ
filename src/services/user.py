import base64
import pickle
from typing import List, Tuple
from dataclasses import dataclass

import asyncpg
import bcrypt

from services.group import GroupConst
from services.log import LogService
from utils.dbg import dbg_print


class UserConst:
    MAIL_MAX = 1024
    MAIL_MIN = 1
    PW_MAX = 1024
    PW_MIN = 1
    NAME_MAX = 27  # 3227
    NAME_MIN = 1

    ACCTTYPE_KERNEL = 0
    ACCTTYPE_USER = 3
    ACCTTYPE_GUEST = 6

    ACCTID_GUEST = 0


@dataclass
class Account:
    acct_id: int
    acct_type: int
    acct_class: int
    mail: str
    name: str
    photo: str
    cover: str
    lastip: str

    def is_kernel(self):
        return self.acct_type == UserConst.ACCTTYPE_KERNEL

    def is_guest(self):
        return self.acct_type == UserConst.ACCTTYPE_GUEST

GUEST_ACCOUNT = Account(
    acct_id=0,
    acct_type=UserConst.ACCTTYPE_GUEST,
    acct_class=0,
    name='',
    mail='',
    photo='',
    cover='',
    lastip=''
)

class UserService:
    MAIL_MAX = 1024
    MAIL_MIN = 1
    PW_MAX = 1024
    PW_MIN = 1
    NAME_MAX = 32
    NAME_MIN = 1

    ACCTTYPE_KERNEL = 0
    ACCTTYPE_USER = 3
    ACCTTYPE_GUEST = 6

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
            return 'Esign', None

        acct_id = result[0]['acct_id']
        hpw = result[0]['password']

        hpw = base64.b64decode(hpw.encode('utf-8'))
        if bcrypt.hashpw(pw.encode('utf-8'), hpw) == hpw:
            return None, acct_id

        return 'Esign', None

    async def sign_up(self, mail, pw, name):
        tmp_len = len(mail)
        if tmp_len < UserConst.MAIL_MIN:
            return 'Emailmin', None
        if tmp_len > UserConst.MAIL_MAX:
            return 'Emailmax', None
        tmp_len = len(pw)
        if tmp_len < UserConst.PW_MIN:
            return 'Epwmin', None
        if tmp_len > UserConst.PW_MAX:
            return 'Epwmax', None
        tmp_len = len(name)
        if tmp_len < UserConst.NAME_MIN:
            return 'Enamemin', None
        if tmp_len > UserConst.NAME_MAX:
            return 'Enamemax', None
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
                    mail, base64.b64encode(hpw).decode('utf-8'), name, UserConst.ACCTTYPE_USER, [1],
                    GroupConst.DEFAULT_GROUP
                )

        except asyncpg.IntegrityConstraintViolationError:
            return 'Eexist', None

        if result.__len__() != 1:
            return 'Eexist', None

        await self.rs.delete('acctlist')
        return None, result[0]['acct_id']

    async def info_sign(self, req):
        acct_id = req.get_secure_cookie('id')
        try:
            ip = req.request.remote_ip

        except Exception:
            ip = ''

        if acct_id is None:
            return 'Esign', None, ip

        acct_id = int(acct_id)

        if (acct := (await self.rs.exists(f'account@{acct_id}'))) is None:
            async with self.db.acquire() as con:
                result = await con.fetch('SELECT "acct_id","lastip" FROM "account" WHERE "acct_id" = $1;', acct_id)

                if result.__len__() != 1:
                    return 'Esign', None, ip
                result = result[0]

                if (lastip := result['lastip']) != ip and ip != '':
                    await LogService.inst.add_log(f"Update acct {acct_id} lastip from {lastip} to {ip} ",
                                                  'acct.updateip')
                    await con.execute('UPDATE "account" SET "lastip" = $1 WHERE "acct_id" = $2;', ip, acct_id)
                    await self.rs.delete(f'account@{acct_id}')
                    await self.rs.delete('acctlist')

        else:
            try:
                acct2 = await self.rs.get(f'account@{acct_id}')
                acct2 = pickle.loads(acct2)
                lastip = acct2.lastip

                if lastip != ip and ip != '':
                    await LogService.inst.add_log(f"Update acct {acct_id} lastip from {lastip} to {ip} ",
                                                  'acct.updateip')

                    async with self.db.acquire() as con:
                        await con.execute('UPDATE "account" SET "lastip" = $1 WHERE "acct_id" = $2;', ip, acct_id)

                    await self.rs.delete(f'account@{acct_id}')
                    await self.rs.delete('acctlist')

            except Exception as e:
                dbg_print(__file__, 150, e=e)

        return None, acct_id, ip

    async def info_acct(self, acct_id) -> Tuple[None, Account]:
        if acct_id is None:
            return None, GUEST_ACCOUNT

        acct_id = int(acct_id)

        if (acct := (await self.rs.get(f'account@{acct_id}'))) is not None:
            acct = pickle.loads(acct)

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
                return 'Enoext', None
            result = result[0]

            acct = Account(
                acct_id=acct_id,
                acct_type=result['acct_type'],
                acct_class=result['class'][0],
                mail=result['mail'],
                name=result['name'],
                photo=result['photo'],
                cover=result['cover'],
                lastip=result['lastip']
            )
            b_acct = pickle.dumps(acct)

            await self.rs.setnx(f'account@{acct_id}', b_acct)
            acct.mail = ''

        return None, acct

    async def update_acct(self, acct_id, acct_type, clas, name, photo, cover):
        if acct_type not in [UserConst.ACCTTYPE_KERNEL, UserConst.ACCTTYPE_USER]:
            return 'Eparam1', None
        if clas not in [0, 1, 2]:
            return 'Eparam2', None
        name_len = len(name)
        if name_len < UserConst.NAME_MIN:
            return 'Enamemin', None
        if name_len > UserConst.NAME_MAX:
            return 'Enamemax', None
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
                return 'Enoext', None

            await con.execute('REFRESH MATERIALIZED VIEW test_valid_rate;')

        await self.rs.delete(f'account@{acct_id}')
        await self.rs.delete('acctlist')

        return None, None

    async def update_pw(self, acct_id, old, pw, isadmin):
        pw_len = len(pw)
        if pw_len < UserConst.PW_MIN:
            return 'Epwmin', None
        if pw_len > UserConst.PW_MAX:
            return 'Epwmax', None
        acct_id = int(acct_id)

        async with self.db.acquire() as con:
            result = await con.fetch('SELECT "password" FROM "account" WHERE "acct_id" = $1;', acct_id)
            if result.__len__() != 1:
                return 'Eexist', None
            result = result[0]

            hpw = base64.b64decode(result['password'].encode('utf-8'))
            if (bcrypt.hashpw(old.encode('utf-8'), hpw) != hpw) and isadmin is False:
                return 'Epwold', None

            hpw = bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt(12))
            await con.execute('UPDATE "account" SET "password" = $1 WHERE "acct_id" = $2',
                              base64.b64encode(hpw).decode('utf-8'), acct_id)

        return None, None

    async def list_acct(self, min_type=UserConst.ACCTTYPE_USER, private=False, reload=False) -> Tuple[None, List[Account]]:
        field = f'{min_type}|{int(private)}'
        if (acctlist := (await self.rs.hget('acctlist', field))) is not None and reload is False:
            acctlist = pickle.loads(acctlist)

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
                acct = Account(
                    acct_id=acct_id,
                    acct_type=acct_type,
                    acct_class=clas[0],
                    mail='',
                    name=name,
                    photo='',
                    cover='',
                    lastip=lastip
                )

                if private:
                    acct.mail = mail

                acctlist.append(acct)

            await self.rs.hset('acctlist', field, pickle.dumps(acctlist))

        return None, acctlist
