import math
import re

from services.user import UserService, UserConst
from services.rate import RateService
from services.pro import ProService
from services.log import LogService
from utils.req import RequestHandler, reqenv


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

        max_status = await ProService.inst.get_acct_limit(self.acct)
        async with self.db.acquire() as con:
            prolist = await con.fetch(
                '''
                    SELECT "pro_id" FROM "problem"
                    WHERE "status" <= $1
                    ORDER BY "pro_id" ASC;
                ''',
                max_status
            )

        err, ratemap2 = await RateService.inst.map_rate_acct(acct, clas=None)

        prolist2 = []

        for pro in prolist:
            pro_id = pro['pro_id']
            tmp = { 'pro_id': pro_id, 'score': -1 }
            if pro_id in ratemap2:
                tmp['score'] = ratemap2[pro_id]['rate']

            prolist2.append(tmp)

        isadmin = (self.acct['acct_type'] == UserConst.ACCTTYPE_KERNEL)
        rate_data['rate'] = math.floor(rate_data['rate'])

        # force https, add by xiplus, 2018/8/24
        acct['photo'] = re.sub(r'^http://', 'https://', acct['photo'])
        acct['cover'] = re.sub(r'^http://', 'https://', acct['cover'])

        await self.render('acct', acct=acct, rate=rate_data, prolist=prolist2, isadmin=isadmin)

    @reqenv
    async def post(self):
        reqtype = self.get_argument('reqtype')

        if reqtype == 'profile':
            name = self.get_argument('name')
            photo = self.get_argument('photo')
            cover = self.get_argument('cover')

            err, ret = await UserService.inst.update_acct(
                self.acct['acct_id'],
                self.acct['acct_type'],
                self.acct['class'],
                name,
                photo,
                cover
            )
            if err:
                self.error(err)
                return

            self.finish('S')
            return

        elif reqtype == 'reset':
            old = self.get_argument('old')
            pw = self.get_argument('pw')
            acct_id = self.get_argument('acct_id')
            if acct_id != self.acct['acct_id']:
                await LogService.inst.add_log((f"{self.acct['name']} was changing the password of user #{acct_id}."), 'manage.acct.update.pwd')

            err, _ = await UserService.inst.update_pw(
                acct_id, old, pw, (self.acct['acct_type'] == UserConst.ACCTTYPE_KERNEL)
            )
            if err:
                self.error(err)
                return

            self.finish('S')
            return

        self.error('Eunk')
        return

class SignHandler(RequestHandler):
    @reqenv
    async def get(self):
        await self.render('sign')
        return

    @reqenv
    async def post(self):
        reqtype = self.get_argument('reqtype')

        if reqtype == 'signin':
            mail = self.get_argument('mail')
            pw = self.get_argument('pw')

            err, acct_id = await UserService.inst.sign_in(mail, pw)
            if err:
                await LogService.inst.add_log(f'{mail} try to sign in but failed: {err}', 'signin.failure', {
                    'type' : 'signin.failure',
                    'mail' : mail,
                    'err'  : err,
                })
                self.error(err)
                return

            await LogService.inst.add_log(f'#{acct_id} sign in successfully', 'signin.success', {
                'type'    : 'signin.success',
                'acct_id' : acct_id
            })

            self.set_secure_cookie('id', str(acct_id), path='/oj', httponly=True)
            self.finish('S')
            return

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
            return

        elif reqtype == 'signout':
            await LogService.inst.add_log(f"{self.acct['name']}(#{self.acct['acct_id']}) sign out", 'signout', {
                'type' : 'signin.failure',
                'name' : self.acct['name'],
                'acct_id'  : self.acct['acct_id'],
            })

            self.clear_cookie('id', path='/oj')
            self.finish('S')
            return
