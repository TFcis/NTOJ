import math
import re

from req import RequestHandler, Service, reqenv
from user import UserService, UserConst
from chal import ChalConst
from log import LogService

from dbg import dbg_print

class AcctHandler(RequestHandler):
    @reqenv
    async def get(self, acct_id):
        err, acct = await UserService.inst.info_acct(acct_id)
        if err:
            self.error(err)
            return
        acct_id = int(acct_id)

        result = await self.db.fetch(('SELECT '
                'SUM("test_valid_rate"."rate" * '
                '    CASE WHEN "valid_test"."timestamp" < "valid_test"."expire" '
                '    THEN 1 ELSE '
                '    (1 - (GREATEST(date_part(\'days\',justify_interval('
                '    age("valid_test"."timestamp","valid_test"."expire") '
                '    + \'1 days\')),-1)) * 0.15) '
                '    END) '
                'AS "rate" FROM "test_valid_rate" '
                'INNER JOIN ('
                '    SELECT "test"."pro_id","test"."test_idx",'
                '    MIN("test"."timestamp") AS "timestamp","problem"."expire" '
                '    FROM "test" '
                '    INNER JOIN "account" '
                '    ON "test"."acct_id" = "account"."acct_id" '
                '    INNER JOIN "problem" '
                '    ON "test"."pro_id" = "problem"."pro_id" '
                '    WHERE "account"."acct_id" = $1 '
                '    AND "test"."state" = $2 '
                '    AND "account"."class" && "problem"."class" '
                '    GROUP BY "test"."pro_id","test"."test_idx","problem"."expire"'
                ') AS "valid_test" '
                'ON "test_valid_rate"."pro_id" = "valid_test"."pro_id" '
                'AND "test_valid_rate"."test_idx" = "valid_test"."test_idx";'),
                acct_id, int(ChalConst.STATE_AC))
        if result.__len__() != 1:
            self.error('Eunk')
            return

        rate = 3227
        prolist2 = []
        rate = result[0]['rate']
        if rate == None:
            rate = 0

        #INFO: Not Currently in use
        # extrate = 3227
        # if acct['class'] == 0:
        #     result = await self.db.fetch(('SELECT '
        #             'SUM("test_valid_rate"."rate") '
        #             'AS "rate" FROM "test_valid_rate" '
        #             'INNER JOIN ('
        #             '    SELECT "test"."pro_id","test"."test_idx" '
        #             '    FROM "test" '
        #             '    INNER JOIN "problem" '
        #             '    ON "test"."pro_id" = "problem"."pro_id" '
        #             '    WHERE "test"."acct_id" = $1 '
        #             '    AND "test"."state" = $2 '
        #             '    AND $3 && "problem"."class" '
        #             '    GROUP BY "test"."pro_id","test"."test_idx"'
        #             ') AS "valid_test" '
        #             'ON "test_valid_rate"."pro_id" = "valid_test"."pro_id" '
        #             'AND "test_valid_rate"."test_idx" = "valid_test"."test_idx";'),
        #             acct_id, int(ChalConst.STATE_AC), [2])
        #     if result.__len__() != 1:
        #         self.error('Eunk')
        #         return
        #
        #     extrate = result[0]['rate']
        #     if extrate == None:
        #         extrate = 0

        err, prolist = await Service.Pro.list_pro(acct=self.acct, clas=None)
        # err, ratemap = await Service.Rate.map_rate(clas=None)
        err, ratemap2 = await Service.Rate.map_rate_acct(acct, clas=None)

        prolist2 = []
        # acct_id = acct['acct_id']
        # dbg_print(__file__, 88, ratemap=ratemap)
        dbg_print(__file__, 89, ratemap2=ratemap2)

        for pro in prolist:
            pro_id = pro['pro_id']
            tmp = { 'pro_id': pro_id, 'score': -1 }
            if pro_id in ratemap2:
                tmp['score'] = ratemap2[pro_id]['rate']

            prolist2.append(tmp)

        isadmin = (self.acct['acct_type'] == UserConst.ACCTTYPE_KERNEL)

        # force https, add by xiplus, 2018/8/24
        acct['photo'] = re.sub(r'^http://', 'https://', acct['photo'])
        acct['cover'] = re.sub(r'^http://', 'https://', acct['cover'])

        await self.render('acct', acct=acct, rate=math.floor(rate), prolist=prolist2, isadmin=isadmin)

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
                await LogService.inst.add_log((f"{self.acct['name']} was changing the password of user #{acct_id}."))

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

            #TODO: Special Record xiplus
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
