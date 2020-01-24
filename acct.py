import math

from req import RequestHandler
from req import reqenv
from user import UserService
from pro import ProService
from chal import ChalService
from pack import PackService
from req import Service

class AcctHandler(RequestHandler):
    @reqenv
    def get(self,acct_id):
        acct_id = int(acct_id)

        err,acct = yield from UserService.inst.info_acct(acct_id)
        if err:
            self.finish(err)
            return

        cur = yield self.db.cursor()
        yield cur.execute(('SELECT '
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
                '    WHERE "account"."acct_id" = %s '
                '    AND "test"."state" = %s '
                '    AND "account"."class" && "problem"."class" '
                '    GROUP BY "test"."pro_id","test"."test_idx","problem"."expire"'
                ') AS "valid_test" '
                'ON "test_valid_rate"."pro_id" = "valid_test"."pro_id" '
                'AND "test_valid_rate"."test_idx" = "valid_test"."test_idx";'),
                (acct_id,ChalService.STATE_AC))
        if cur.rowcount != 1:
            self.finish('Unknown')
            return

        rate = cur.fetchone()[0]
        if rate == None:
            rate = 0

        extrate = 0
        if acct['class'] == 0:
            cur = yield self.db.cursor()
            yield cur.execute(('SELECT '
                    'SUM("test_valid_rate"."rate") '
                    'AS "rate" FROM "test_valid_rate" '
                    'INNER JOIN ('
                    '    SELECT "test"."pro_id","test"."test_idx" '
                    '    FROM "test" '
                    '    INNER JOIN "problem" '
                    '    ON "test"."pro_id" = "problem"."pro_id" '
                    '    WHERE "test"."acct_id" = %s '
                    '    AND "test"."state" = %s '
                    '    AND %s && "problem"."class" '
                    '    GROUP BY "test"."pro_id","test"."test_idx"'
                    ') AS "valid_test" '
                    'ON "test_valid_rate"."pro_id" = "valid_test"."pro_id" '
                    'AND "test_valid_rate"."test_idx" = "valid_test"."test_idx";'),
                    (acct_id,ChalService.STATE_AC,[2]))
            if cur.rowcount != 1:
                self.finish('Unknown')
                return

            extrate = cur.fetchone()[0]
            if extrate == None:
                extrate = 0

        '''
        yield cur.execute(('SELECT '
            '"pro_rank"."pro_id",'
            '(0.3 * power(0.66,("pro_rank"."rank" - 1))) AS "weight" FROM ('
            '    SELECT '
            '    "challenge"."pro_id","challenge"."acct_id",'
            '    row_number() OVER ('
            '        PARTITION BY "challenge"."pro_id" ORDER BY MIN('
            '        "challenge"."chal_id") ASC) AS "rank" '
            '    FROM "challenge" '
            '    INNER JOIN ('
            '        SELECT "pro_id" FROM "challenge" '
            '        WHERE "challenge"."acct_id" = %s'
            '    ) AS need_id ON "challenge"."pro_id" = "need_id"."pro_id" '
            '    INNER JOIN "challenge_state" '
            '    ON "challenge"."chal_id" = "challenge_state"."chal_id" '
            '    INNER JOIN "problem" ON '
            '    "challenge"."pro_id" = "problem"."pro_id" '
            '    INNER JOIN "account" '
            '    ON "challenge"."acct_id" = "account"."acct_id" '
            '    WHERE "challenge_state"."state" = %s '
            '    AND "problem"."class" && "account"."class" '
            '    GROUP BY "challenge"."pro_id","challenge"."acct_id"'
            ') AS "pro_rank" WHERE "pro_rank"."acct_id" = %s;'),
            (acct['acct_id'],ChalService.STATE_AC,acct['acct_id']))

        weightmap = {}
        for pro_id,weight in cur:
            weightmap[pro_id] = float(weight)

        bonus = 0
        for pro in prolist:
            pro_id = pro['pro_id']
            if pro_id in weightmap:
                bonus += pro['rate'] * weightmap[pro_id]
        '''

        err,prolist = yield from Service.Pro.list_pro(acct = self.acct,clas = None)
        err,ratemap = yield from Service.Rate.map_rate(clas = None)

        prolist2 = []
        acct_id = acct['acct_id']
        for pro in prolist:
            pro_id = pro['pro_id']
            tmp = {'pro_id':pro_id,'score':-1}
            if acct_id in ratemap and pro_id in ratemap[acct_id]:
                rate2 = ratemap[acct_id][pro_id]
                tmp['score'] = rate2['rate']
            prolist2.append(tmp)
        # force https, add by xiplus, 2018.08.24
        acct['photo'] = re.sub(r'^http://', 'https://', acct['photo'])
        acct['cover'] = re.sub(r'^http://', 'https://', acct['cover'])

        self.render('acct',
                acct = acct,
                rate = math.floor(rate),
                extrate = math.floor(extrate),
                prolist = prolist2)

        return

    @reqenv
    def post(self):
        reqtype = self.get_argument('reqtype')
        if reqtype == 'profile':
            name = self.get_argument('name')
            photo = self.get_argument('photo')
            cover = self.get_argument('cover')

            err,ret = yield from UserService.inst.update_acct(
                    self.acct['acct_id'],
                    self.acct['acct_type'],
                    self.acct['class'],
                    name,
                    photo,
                    cover)
            if err:
                self.finish(err)
                return

            self.finish('S')
            return

        elif reqtype == 'reset':
            old = self.get_argument('old')
            pw = self.get_argument('pw')

            err,ret = yield from UserService.inst.update_pw(
                    self.acct['acct_id'],old,pw)
            if err:
                self.finish(err)
                return

            self.finish('S')
            return

        self.finish('Eunk')
        return

class SignHandler(RequestHandler):
    @reqenv
    def get(self):
        self.render('sign')
        return

    @reqenv
    def post(self):
        reqtype = self.get_argument('reqtype')
        if reqtype == 'signin':
            mail = self.get_argument('mail')
            pw = self.get_argument('pw')

            err,sign = yield from UserService.inst.sign_in(mail,pw)
            if err:
                self.finish(err)
                return

            self.set_secure_cookie('sign',sign,
                    path = '/oj',httponly = True)
            self.finish('S')
            return

        elif reqtype == 'signup':
            mail = self.get_argument('mail')
            pw = self.get_argument('pw')
            name = self.get_argument('name')
            err,sign = yield from UserService.inst.sign_up(mail,pw,name)
            if err:
                self.finish(err)
                return

            self.set_secure_cookie('sign',sign,
                    path = '/oj',httponly = True)
            self.finish('S')
            return

        elif reqtype == 'signout':
            self.clear_cookie('sign',path = '/oj')
            self.finish('S')
            return
