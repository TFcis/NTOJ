import math
import re

import tornado.web

from handlers.base import RequestHandler, reqenv, require_permission
from services.log import LogService
from services.pro import ProService, ProClassService, ProConst
from services.rate import RateService
from services.user import UserConst, UserService
from services.chal import ChalConst
from utils.numeric import parse_list_str


class AcctHandler(RequestHandler):
    @reqenv
    async def get(self, acct_id):
        acct_id = int(acct_id)
        err, acct = await UserService.inst.info_acct(acct_id)
        if err:
            self.error(err)
            return

        err, rate_data = await RateService.inst.get_acct_rate_and_chal_cnt(acct)
        if err:
            self.error(err)
            return

        max_status = ProService.inst.get_acct_limit(self.acct)
        async with self.db.acquire() as con:
            prolist = await con.fetch(
                '''
                    SELECT "pro_id" FROM "problem"
                    WHERE "status" <= $1
                    ORDER BY "pro_id" ASC;
                ''',
                max_status,
            )

        err, ratemap = await RateService.inst.map_rate_acct(acct)

        prolist2 = []

        ac_pro_cnt = 0
        for pro in prolist:
            pro_id = pro['pro_id']
            tmp = {'pro_id': pro_id, 'score': -1}
            if pro_id in ratemap:
                tmp['score'] = ratemap[pro_id]['rate']
                ac_pro_cnt += ratemap[pro_id]['state'] == ChalConst.STATE_AC

            prolist2.append(tmp)

        rate_data['rate'] = math.floor(rate_data['rate'])
        rate_data['ac_pro_cnt'] = ac_pro_cnt

        # force https, add by xiplus, 2018/8/24
        acct.photo = re.sub(r'^http://', 'https://', acct.photo)
        acct.cover = re.sub(r'^http://', 'https://', acct.cover)

        await self.render('acct/profile', acct=acct, rate=rate_data, prolist=prolist2)


class AcctConfigHandler(RequestHandler):
    @reqenv
    async def get(self, acct_id=None):
        if acct_id is None:
            self.error('Enoext')
            return
        acct_id = int(acct_id)
        err, acct = await UserService.inst.info_acct(acct_id)
        if err:
            self.error(err)
            return

        await self.render('acct/acct-config', acct=acct)

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
                self.error('Eacces')
                return

            err, _ = await UserService.inst.update_acct(
                self.acct.acct_id, self.acct.acct_type, name, photo, cover, motto, self.acct.proclass_collection,
            )
            if err:
                self.error(err)
                return

            self.finish('S')
            return

        elif reqtype == 'reset':
            old = self.get_argument('old')
            pw = self.get_argument('pw')
            target_acct_id = int(self.get_argument('acct_id'))

            if not (self.acct.acct_id == target_acct_id or self.acct.is_kernel()):
                self.error('Eacces')
                return

            err, _ = await UserService.inst.update_pw(target_acct_id, old, pw, self.acct.is_kernel())
            if err:
                self.error(err)
                return

            if not err and target_acct_id != self.acct.acct_id:
                await LogService.inst.add_log(
                    f"{self.acct.name} was changing the password of user #{target_acct_id}.", 'manage.acct.update.pwd'
                )

            self.finish('S')
            return

        self.error('Eunk')

class AcctProClassHandler(RequestHandler):
    @reqenv
    async def get(self, acct_id):
        acct_id = int(acct_id)
        try:
            page = self.get_argument('page')
        except tornado.web.HTTPError:
            page = None

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
                self.error('Eacces')
                return

            await self.render('acct/proclass-update', proclass_id=proclass_id, proclass=proclass)

    @reqenv
    async def post(self, acct_id):
        reqtype = self.get_argument('reqtype')
        acct_id = int(acct_id)

        if reqtype == 'add':
            name = self.get_argument('name')
            desc = self.get_argument('desc')
            proclass_type = int(self.get_argument('type'))
            p_list_str = self.get_argument('list')
            p_list = parse_list_str(p_list_str)

            if proclass_type not in [ProClassConst.USER_PUBLIC, ProClassConst.USER_HIDDEN]:
                self.error('Eparam')
                return

            if len(p_list) == 0:
                self.error('E')
                return

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
                self.error(err)
                return

            self.finish(str(proclass_id))

        elif reqtype == "update":
            proclass_id = int(self.get_argument('proclass_id'))
            name = self.get_argument('name')
            desc = self.get_argument('desc')
            proclass_type = int(self.get_argument('type'))
            p_list_str = self.get_argument('list')
            p_list = parse_list_str(p_list_str)

            _, proclass = await ProClassService.inst.get_proclass(proclass_id)

            if proclass['acct_id'] != self.acct.acct_id:
                await LogService.inst.add_log(
                    f"{self.acct.name} tried to remove proclass name={proclass['name']}, but this proclass is not owned by them", 'user.proclass.update.failed'
                )
                self.error('Eacces')
                return

            if proclass_type not in [ProClassConst.USER_PUBLIC, ProClassConst.USER_HIDDEN]:
                self.error('Eparam')
                return

            if len(p_list) == 0:
                self.error('E')
                return

            await LogService.inst.add_log(
                f"{self.acct.name} update proclass name={name}", 'user.proclass.update',
                {
                    "list": p_list,
                    "desc": desc,
                    "proclass_type": proclass_type,
                }
            )
            err = await ProClassService.inst.update_proclass(proclass_id, name, p_list, desc, proclass_type)
            if err:
                self.error(err)
                return

            self.finish('S')

        elif reqtype == "remove":
            proclass_id = int(self.get_argument('proclass_id'))
            err, proclass = await ProClassService.inst.get_proclass(proclass_id)

            if err:
                self.error(err)
                return

            if proclass['acct_id'] != self.acct.acct_id:
                await LogService.inst.add_log(
                    f"{self.acct.name} tried to remove proclass name={proclass['name']}, but this proclass is not owned by them", 'user.proclass.remove.failed'
                )
                self.error('Eacces')
                return

            await LogService.inst.add_log(
                f"{self.acct.name} remove proclass name={proclass['name']}.", 'user.proclass.remove'
            )
            await ProClassService.inst.remove_proclass(proclass_id)

            self.finish('S')

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
                self.error(err)
                return

            await LogService.inst.add_log(
                f'#{acct_id} sign in successfully', 'signin.success', {'type': 'signin.success', 'acct_id': acct_id}
            )

            self.set_secure_cookie('id', str(acct_id), path='/oj', httponly=True)
            self.finish('S')

        elif reqtype == 'signup':
            mail = self.get_argument('mail')
            pw = self.get_argument('pw')
            name = self.get_argument('name')

            err, acct_id = await UserService.inst.sign_up(mail, pw, name)
            if err:
                self.error(err)
                return

            self.set_secure_cookie('id', str(acct_id), path='/oj', httponly=True)
            self.finish('S')

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

            self.clear_cookie('id', path='/oj')
            self.finish('S')
