import re
import time
import math
import hashlib

from msgpack import packb, unpackb

from handlers.base import RequestHandler, reqenv, require_permission
from services.log import LogService
from services.pro import ProClassService, ProClassConst
from services.rate import RateService
from services.user import UserConst, UserService
from services.chal import ChalConst
from utils.numeric import parse_str_to_list

PERMISSION_DENIED_ERROR = (('Eacces', 'Permission denied'))

class AcctHandler(RequestHandler):
    @reqenv
    async def get(self, acct_id):
        acct_id = int(acct_id)
        err, acct = await UserService.inst.info_acct(acct_id)
        if err:
            return self.error(err)

        acct.acct_type = UserConst.ACCTTYPE_USER
        err, rate_data = await RateService.inst.get_acct_rate_and_chal_cnt(acct)
        if err:
            return self.error(err)

        async with self.db.acquire() as con:
            prolist = await con.fetch(
                '''
                    SELECT "pro_id" FROM "problem"
                    WHERE "status" <= $1
                    ORDER BY "pro_id" ASC;
                ''',
                UserConst.ACCTTYPE_USER,
            )

        err, ratemap = await RateService.inst.map_rate_acct(acct)
        acct.acct_type = UserConst.ACCTTYPE_KERNEL

        prolist2 = []

        ac_pro_cnt = 0
        for pro in prolist:
            pro_id = pro['pro_id']
            tmp = {'pro_id': pro_id, 'score': -1, 'state': None}
            if pro_id in ratemap:
                tmp['score'] = ratemap[pro_id]['rate']
                tmp['state'] = ratemap[pro_id]['state']
                ac_pro_cnt += ratemap[pro_id]['state'] == ChalConst.STATE_AC

            prolist2.append(tmp)

        def chunk_list(la, size):
            for i in range(0, len(la), size):
                yield la[i: i + size]

        rate_data['rate'] = math.floor(rate_data['rate'])
        rate_data['ac_pro_cnt'] = ac_pro_cnt

        # force https, add by xiplus, 2018/8/24
        acct.photo = re.sub(r'^http://', 'https://', acct.photo)
        acct.cover = re.sub(r'^http://', 'https://', acct.cover)

        await self.render('acct/profile', acct=acct, rate=rate_data, prolist=chunk_list(prolist2, 10))


class AcctConfigHandler(RequestHandler):
    @reqenv
    async def get(self, acct_id=None):
        if acct_id is None:
            return self.error(('Enoext', 'Missing parameter acct_id'))
        acct_id = int(acct_id)
        err, acct = await UserService.inst.info_acct(acct_id)
        if err:
            return self.error(err)

        session_keys = {}
        current_session_key = hashlib.md5(self.get_cookie('id').encode()).hexdigest()
        for session_key, v in (await self.rs.hgetall(f'account_session@{acct_id}')).items():
            session_key = hashlib.md5(session_key).hexdigest()
            session_keys[session_key] = unpackb(v)

        await self.render('acct/acct-config', acct=acct, session_keys=session_keys, current_session_key=current_session_key)

    @reqenv
    @require_permission([UserConst.ACCTTYPE_USER, UserConst.ACCTTYPE_KERNEL])
    async def post(self):
        reqtype = self.get_argument('reqtype')

        if reqtype == 'profile':
            name = self.get_argument('name')
            photo = self.get_argument('photo')
            cover = self.get_argument('cover')
            motto = self.get_argument('motto')
            target_acct_id = self.get_argument('acct_id')

            if target_acct_id != str(self.acct.acct_id):
                return self.error(PERMISSION_DENIED_ERROR)

            self.acct.name = name
            self.acct.photo = photo
            self.acct.cover = cover
            self.acct.motto = motto
            err, _ = await UserService.inst.update_acct(self.acct)
            if err:
                return self.error(err)

            return self.error(('S', ''))

        elif reqtype == 'reset':
            old = self.get_argument('old')
            pw = self.get_argument('pw')
            target_acct_id = int(self.get_argument('acct_id'))

            if not (self.acct.acct_id == target_acct_id or self.acct.is_kernel()):
                return self.error(PERMISSION_DENIED_ERROR)

            err, _ = await UserService.inst.update_pw(target_acct_id, old, pw, self.acct.is_kernel())
            if err:
                return self.error(err)

            if not err and target_acct_id != self.acct.acct_id:
                await LogService.inst.add_log(
                    f"{self.acct.name} was changing the password of user #{target_acct_id}.", 'manage.acct.update.pwd'
                )

            return self.error(('S', ''))

        elif reqtype == 'remote-logout':
            target_acct_id = self.get_argument('acct_id')

            if target_acct_id != str(self.acct.acct_id):
                return self.error(PERMISSION_DENIED_ERROR)

            hashed_session_key = self.get_argument('hashed_session_key')
            found = False
            for session_key in (await self.rs.hgetall(f'account_session@{target_acct_id}')):
                if hashlib.md5(session_key).hexdigest() == hashed_session_key:
                    found = True
                    await self.rs.hdel(f'account_session@{target_acct_id}', session_key)
                    break

            if found:
                return self.error(('S', ''))

            return self.error(('Enoext', 'Session not found'))

        elif reqtype == 'remote-logout-all':
            target_acct_id = self.get_argument('acct_id')

            if target_acct_id != str(self.acct.acct_id):
                return self.error(PERMISSION_DENIED_ERROR)

            await self.rs.delete(f'account_session@{target_acct_id}')
            self.clear_cookie('id')
            return self.error(('S', ''))


        return self.error(('Eunk', 'Unknown error'))
class AcctProClassHandler(RequestHandler):
    @reqenv
    @require_permission([UserConst.ACCTTYPE_USER, UserConst.ACCTTYPE_KERNEL])
    async def get(self, acct_id):
        acct_id = int(acct_id)
        page = self.get_argument('page', default=None)

        if page is None:
            _, proclass_list = await ProClassService.inst.get_proclass_list()
            proclass_list = filter(lambda proclass: proclass['acct_id'] == self.acct.acct_id, proclass_list)
            await self.render('acct/proclass-list', proclass_list=proclass_list)

        elif page == "add":
            await self.render('acct/proclass-add', user=self.acct)

        elif page == "update":
            proclass_id = int(self.get_argument('proclassid'))
            _, proclass = await ProClassService.inst.get_proclass(proclass_id)
            if proclass['acct_id'] != self.acct.acct_id:
                return self.error(PERMISSION_DENIED_ERROR)

            await self.render('acct/proclass-update', proclass_id=proclass_id, proclass=proclass)

    @reqenv
    @require_permission([UserConst.ACCTTYPE_USER, UserConst.ACCTTYPE_KERNEL])
    async def post(self, acct_id):
        reqtype = self.get_argument('reqtype')
        acct_id = int(acct_id)

        if reqtype in ['add', 'update']:
            name = self.get_argument('name').strip()
            desc = self.get_argument('desc').strip()
            proclass_type = int(self.get_argument('type'))
            p_list_str = self.get_argument('list')
            p_list = parse_str_to_list(p_list_str)

            if err := self.len_check(name, ProClassConst.NAME_MIN, ProClassConst.NAME_MAX, 'Name'):
                return self.error(err)

            if err := self.len_check(desc, ProClassConst.DESC_MIN, ProClassConst.DESC_MAX, 'Desc'):
                return self.error(err)

            if proclass_type not in [ProClassConst.USER_PUBLIC, ProClassConst.USER_HIDDEN]:
                return self.error(('Eparam', 'Invalid problem class type'))

            if len(p_list) == 0:
                return self.error(('Eparam', 'Problem list should not be empty'))

            if reqtype == 'add':
                await LogService.inst.add_log(
                    f"{self.acct.name} add proclass name={name}", 'user.proclass.add',
                    {
                        "list": p_list,
                        "desc": desc,
                        "proclass_type": proclass_type,
                    }
                )
                err, proclass_id = await ProClassService.inst.add_proclass(name, p_list, desc, acct_id, proclass_type)
                if err:
                    return self.error(err)

                self.error(('S', proclass_id))

            elif reqtype == "update":
                proclass_id = int(self.get_argument('proclass_id'))

                _, proclass = await ProClassService.inst.get_proclass(proclass_id)
                if proclass['acct_id'] != self.acct.acct_id:
                    await LogService.inst.add_log(
                        f"{self.acct.name} tried to remove proclass name={proclass['name']}, but this proclass is not owned by them", 'user.proclass.update.failed'
                    )
                    return self.error(PERMISSION_DENIED_ERROR)

                await LogService.inst.add_log(
                    f"{self.acct.name} update proclass name={name}", 'user.proclass.update',
                    {
                        "list": p_list,
                        "desc": desc,
                        "proclass_type": proclass_type,
                    }
                )
                if err := await ProClassService.inst.update_proclass(proclass_id, name, p_list, desc, proclass_type):
                    return self.error(err)

                self.error(('S', ''))

        elif reqtype == "remove":
            proclass_id = int(self.get_argument('proclass_id'))
            err, proclass = await ProClassService.inst.get_proclass(proclass_id)

            if err:
                return self.error(err)

            if proclass['acct_id'] != self.acct.acct_id:
                await LogService.inst.add_log(
                    f"{self.acct.name} tried to remove proclass name={proclass['name']}, but this proclass is not owned by them", 'user.proclass.remove.failed'
                )
                return self.error(PERMISSION_DENIED_ERROR)

            await LogService.inst.add_log(
                f"{self.acct.name} remove proclass name={proclass['name']}.", 'user.proclass.remove'
            )
            await ProClassService.inst.remove_proclass(proclass_id)

            self.error(('S', ''))

class SignHandler(RequestHandler):
    @reqenv
    async def get(self):
        await self.render('sign')

    @reqenv
    async def post(self):
        reqtype = self.get_argument('reqtype')

        if reqtype == 'signin':
            mail = self.get_argument('mail')
            pw = self.get_argument('pw')

            err, acct_id = await UserService.inst.sign_in(mail, pw)
            if err:
                await LogService.inst.add_log(
                    f'{mail} try to sign in but failed: {err}',
                    'signin.failure',
                    {
                        'type': 'signin.failure',
                        'mail': mail,
                        'err': err,
                    },
                )
                return self.error(err)

            await LogService.inst.add_log(
                f'#{acct_id} sign in successfully', 'signin.success', {'type': 'signin.success', 'acct_id': acct_id}
            )

            session_key = self.create_signed_value('id', str(acct_id))
            await self.rs.hset(f'account_session@{acct_id}', session_key.decode(), packb({
                "ip": self.request.remote_ip,
                "time": time.time(),
                "user-agent": self.request.headers.get('User-Agent', ''),
            }))
            await self.rs.expire(f'account_session@{acct_id}', 30 * 24 * 60 * 60)
            self.set_cookie('id', session_key, path='/oj', httponly=True, expires_days=30)
            self.error(('S', ''))

        elif reqtype == 'signup':
            mail = self.get_argument('mail')
            pw = self.get_argument('pw')
            name = self.get_argument('name')

            err, acct_id = await UserService.inst.sign_up(mail, pw, name)
            if err:
                return self.error(err)

            session_key = self.create_signed_value('id', str(acct_id))
            await self.rs.hset(f'account_session@{acct_id}', session_key.decode(), packb({
                "ip": self.request.remote_ip,
                "time": time.time(),
                "user-agent": self.request.headers.get('User-Agent', ''),
            }))
            await self.rs.expire(f'account_session@{acct_id}', 30 * 24 * 60 * 60)
            self.set_cookie('id', session_key, path='/oj', httponly=True, expires_days=30)
            self.error(('S', ''))

        elif reqtype == 'signout':
            await LogService.inst.add_log(
                f"{self.acct.name}(#{self.acct.acct_id}) sign out",
                'signout',
                {
                    'type': 'signin.failure',
                    'name': self.acct.name,
                    'acct_id': self.acct.acct_id,
                },
            )

            if (session_key := self.get_cookie('id')) is not None:
                await self.rs.hdel(f'account_session@{self.acct.acct_id}', session_key)
            self.clear_cookie('id', path='/oj')
            self.error(('S', ''))
