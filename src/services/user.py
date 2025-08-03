import time
import base64
import pickle
from dataclasses import dataclass
from typing import List, Tuple

import asyncpg
import bcrypt
from msgpack import unpackb

from services.log import LogService
from services.chal import Compiler
from utils.dbg import dbg_print


class UserConst:
    MAIL_MAX = 1024
    MAIL_MIN = 1
    PW_MAX = 1024
    PW_MIN = 1
    NAME_MAX = 27  # 3227
    NAME_MIN = 1
    MOTTO_MIN = 0
    MOTTO_MAX = 100

    ACCTTYPE_KERNEL = 0
    ACCTTYPE_USER = 3
    ACCTTYPE_GUEST = 6

    ACCTID_GUEST = 0

@dataclass
class Account:
    acct_id: int
    acct_type: int
    mail: str
    name: str
    photo: str
    cover: str
    motto: str
    lastip: str
    last_compiler: Compiler
    proclass_collection: list[int]

    def is_kernel(self):
        return self.acct_type == UserConst.ACCTTYPE_KERNEL

    def is_guest(self):
        return self.acct_type == UserConst.ACCTTYPE_GUEST


GUEST_ACCOUNT = Account(
    acct_id=0, acct_type=UserConst.ACCTTYPE_GUEST, name='', mail='', photo='', cover='', lastip='', last_compiler=Compiler.GPP, motto='', proclass_collection=[]
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
                mail,
            )
        if len(result) != 1:
            return ('Esign', 'Login failed'), None

        acct_id = result[0]['acct_id']
        hpw = result[0]['password']

        hpw = base64.b64decode(hpw.encode('utf-8'))
        if bcrypt.hashpw(pw.encode('utf-8'), hpw) == hpw:
            return None, acct_id

        return ('Esign', 'Login failed'), None

    async def sign_up(self, mail, pw, name):
        tmp_len = len(mail)
        if tmp_len < UserConst.MAIL_MIN:
            return ('Emailmin', 'Mail too short'), None
        if tmp_len > UserConst.MAIL_MAX:
            return ('Emailmax', 'Mail too long'), None
        tmp_len = len(pw)
        if tmp_len < UserConst.PW_MIN:
            return ('Epwmin', 'Password too short'), None
        if tmp_len > UserConst.PW_MAX:
            return ('Epwmax', 'Password too long'), None
        tmp_len = len(name)
        if tmp_len < UserConst.NAME_MIN:
            return ('Enamemin', 'Username too short'), None
        if tmp_len > UserConst.NAME_MAX:
            return ('Enamemax', 'Username too long'), None
        del tmp_len

        hpw = bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt(12))

        try:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    '''
                        INSERT INTO "account"
                        ("mail", "password", "name", "acct_type")
                        VALUES ($1, $2, $3, $4) RETURNING "acct_id";
                    ''',
                    mail,
                    base64.b64encode(hpw).decode('utf-8'),
                    name,
                    UserConst.ACCTTYPE_USER,
                )

        except (asyncpg.IntegrityConstraintViolationError, asyncpg.UniqueViolationError):
            async with self.db.acquire() as con:
                result = await con.fetch("SELECT last_value FROM account_acct_id_seq;")
                cur_acct_id = int(result[0]['last_value'])
                await con.execute(f"SELECT setval('account_acct_id_seq', {cur_acct_id - 1}, true);")

            return ('Eexist', 'Account already exists'), None

        if len(result) != 1:
            return ('Eexist', 'Account already exists'), None

        await self.rs.delete('acctlist')
        return None, result[0]['acct_id']

    async def info_sign(self, req):
        # TODO: There is no check for the return error value of this function anywhere.
        acct_id = req.get_secure_cookie('id')
        if acct_id is None:
            return 'Esign', None, ''
        acct_id = int(acct_id)

        session_key = req.get_cookie('id')
        session_data = await self.rs.hget(f'account_session@{acct_id}', session_key)
        if session_data is None:
            return 'Esign', None, ''

        session_data = unpackb(session_data)

        if time.time() - session_data['time'] > 30 * 24 * 60 * 60:
            return 'Esign', None, ''

        try:
            ip = req.request.remote_ip

        except Exception:
            ip = ''
        session_data['ip'] = ip


        if (await self.rs.exists(f'account@{acct_id}')) is None:
            async with self.db.acquire() as con:
                result = await con.fetch('SELECT "acct_id","lastip" FROM "account" WHERE "acct_id" = $1;', acct_id)

                if len(result) != 1:
                    return 'Esign', None, ip
                result = result[0]

                if (lastip := result['lastip']) != ip and ip != '':
                    await LogService.inst.add_log(
                        f"Update acct {acct_id} lastip from {lastip} to {ip} ", 'acct.updateip'
                    )
                    await con.execute('UPDATE "account" SET "lastip" = $1 WHERE "acct_id" = $2;', ip, acct_id)
                    await self.rs.delete(f'account@{acct_id}')
                    await self.rs.delete('acctlist')

        else:
            try:
                acct2 = await self.rs.get(f'account@{acct_id}')
                acct2 = pickle.loads(acct2)
                lastip = acct2.lastip

                if lastip != ip and ip != '':
                    await LogService.inst.add_log(
                        f"Update acct {acct_id} lastip from {lastip} to {ip} ", 'acct.updateip'
                    )

                    async with self.db.acquire() as con:
                        await con.execute('UPDATE "account" SET "lastip" = $1 WHERE "acct_id" = $2;', ip, acct_id)

                    await self.rs.delete(f'account@{acct_id}')
                    await self.rs.delete('acctlist')

            except Exception as e:
                dbg_print(__file__, 150, e=e)

        return None, acct_id, ip

    async def info_acct(self, acct_id):
        if acct_id is None:
            return None, GUEST_ACCOUNT

        acct_id = int(acct_id)

        if (acct := (await self.rs.get(f'account@{acct_id}'))) is not None:
            acct = pickle.loads(acct)

        else:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    '''
                        SELECT "name", "acct_type", "mail", "photo", "cover", "lastip", "last_compiler", "motto", "proclass_collection"
                        FROM "account" WHERE "acct_id" = $1;
                    ''',
                    acct_id,
                )
            if len(result) != 1:
                return ('Enoext', 'Account not found'), None

            result = result[0]

            acct = Account(
                acct_id=acct_id,
                acct_type=result['acct_type'],
                mail=result['mail'],
                name=result['name'],
                photo=result['photo'],
                cover=result['cover'],
                motto=result['motto'],
                last_compiler=result['last_compiler'],
                lastip=result['lastip'],
                proclass_collection=result['proclass_collection'],
            )
            b_acct = pickle.dumps(acct)

            await self.rs.setnx(f'account@{acct_id}', b_acct)
            acct.mail = ''

        return None, acct

    async def update_acct(self, acct: Account):
        if acct.acct_type not in [UserConst.ACCTTYPE_KERNEL, UserConst.ACCTTYPE_USER]:
            return ('Eparam', 'Invalid account type'), None
        name_len = len(acct.name)
        if name_len < UserConst.NAME_MIN:
            return ('Enamemin', 'Username too short'), None
        if name_len > UserConst.NAME_MAX:
            return ('Enamemax', 'Username too long'), None
        motto_len = len(acct.motto)
        if motto_len < UserConst.MOTTO_MIN:
            return ('Emottomin', 'Motto too short'), None
        if motto_len > UserConst.MOTTO_MAX:
            return ('Emottomax', 'Motto too long'), None

        if Compiler(acct.last_compiler) not in Compiler:
            return ('Eparam', 'Invalid last compiler option'), None

        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    UPDATE
                        "account"
                    SET
                        "acct_type" = $1, "name" = $2,
                        "photo" = $3, "cover" = $4,
                        "last_compiler" = $5,
                        "motto" = $6, "proclass_collection" = $7
                    WHERE
                        "acct_id" = $8 RETURNING "acct_id";
                ''',
                acct.acct_type,
                acct.name,
                acct.photo,
                acct.cover,
                acct.last_compiler,
                acct.motto,
                acct.proclass_collection,
                acct.acct_id,
            )
            if len(result) != 1:
                return ('Enoext', 'Account not found'), None

        await self.rs.delete(f'account@{acct.acct_id}')
        await self.rs.delete('acctlist')

        return None, None

    async def update_pw(self, acct_id, old, pw, isadmin):
        pw_len = len(pw)
        if pw_len < UserConst.PW_MIN:
            return ('Epwmin', 'Password too short'), None
        if pw_len > UserConst.PW_MAX:
            return ('Epwmax', 'Password too long'), None
        acct_id = int(acct_id)

        async with self.db.acquire() as con:
            result = await con.fetch('SELECT "password" FROM "account" WHERE "acct_id" = $1;', acct_id)
            if len(result) != 1:
                return ('Enoext', 'Account not found'), None
            result = result[0]

            hpw = base64.b64decode(result['password'].encode('utf-8'))
            # NOTE: old != current password
            if (bcrypt.hashpw(old.encode('utf-8'), hpw) != hpw) and not isadmin:
                return ('Epwold', 'New password same as old password'), None

            hpw = bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt(12))
            await con.execute(
                'UPDATE "account" SET "password" = $1 WHERE "acct_id" = $2',
                base64.b64encode(hpw).decode('utf-8'),
                acct_id,
            )

        return None, None

    async def list_acct(
        self, min_type=UserConst.ACCTTYPE_USER, private=False, reload=False
    ) -> Tuple[None, List[Account]]:
        field = f'{min_type}|{int(private)}'
        if (acctlist := (await self.rs.hget('acctlist', field))) is not None and reload is False:
            acctlist = pickle.loads(acctlist)

        else:

            async with self.db.acquire() as con:
                result = await con.fetch(
                    '''
                        SELECT "acct_id", "acct_type", "name", "mail", "lastip"
                        FROM "account" WHERE "acct_type" >= $1
                        ORDER BY "acct_id" ASC;
                    ''',
                    min_type,
                )

            acctlist = []
            for acct_id, acct_type, name, mail, lastip in result:
                acct = Account(
                    acct_id=acct_id,
                    acct_type=acct_type,
                    mail='',
                    name=name,
                    photo='',
                    cover='',
                    motto='',
                    last_compiler='',
                    lastip=lastip,
                    proclass_collection=[],
                )

                if private:
                    acct.mail = mail

                acctlist.append(acct)

            await self.rs.hset('acctlist', field, pickle.dumps(acctlist))

        return None, acctlist

