import math

import tornado.web

from services.chal import ChalConst
from services.judge import JudgeServerClusterService
from services.log import LogService
from services.pro import ProConst, ProService, ProClassService
from services.rate import RateService
from services.user import UserConst
from handlers.base import RequestHandler, reqenv, require_permission


def user_ac_cmp(pro):
    user_ac_chal_cnt = pro['rate_data']['user_ac_chal_cnt']
    user_all_chal_cnt = pro['rate_data']['user_all_chal_cnt']

    if user_ac_chal_cnt and user_all_chal_cnt:
        return user_ac_chal_cnt / user_all_chal_cnt

    else:
        return -1


def chal_ac_cmp(pro):
    ac_chal_cnt = pro['rate_data']['ac_chal_cnt']
    all_chal_cnt = pro['rate_data']['all_chal_cnt']

    if ac_chal_cnt and all_chal_cnt:
        return ac_chal_cnt / all_chal_cnt

    else:
        return -1


class ProsetHandler(RequestHandler):
    @reqenv
    async def get(self):
        try:
            off = int(self.get_argument('off'))
        except tornado.web.HTTPError:
            off = 0

        try:
            order = self.get_argument('order')
        except tornado.web.HTTPError:
            order = None

        try:
            problem_show = self.get_argument('show')
        except tornado.web.HTTPError:
            problem_show = 'all'

        try:
            show_only_online_pro = self.get_argument('online')
        except tornado.web.HTTPError:
            show_only_online_pro = False

        try:
            order_reverse = self.get_argument('reverse')
        except tornado.web.HTTPError:
            order_reverse = False

        flt = {
            'order': order,
            'problem_show': problem_show,
            'online': show_only_online_pro,
            'reverse': order_reverse,
        }

        clas = None

        try:
            pubclass_id = int(self.get_argument('pubclass_id'))
        except tornado.web.HTTPError:
            pubclass_id = None

        err, prolist = await ProService.inst.list_pro(
            self.acct, state=True, clas=clas)

        _, pubclass_list = await ProClassService.inst.get_pubclass_list()

        pubclass = None
        if pubclass_id is not None:
            err, pubclass = await ProClassService.inst.get_pubclass(pubclass_id)
            if err:
                self.error(err)
                return

            p_list = pubclass['list']
            prolist = list(filter(lambda pro: pro['pro_id'] in p_list, prolist))

        if show_only_online_pro:
            prolist = list(filter(lambda pro: pro['status'] == ProConst.STATUS_ONLINE, prolist))

        if problem_show == "onlyac":
            prolist = list(filter(lambda pro: pro['state'] == ChalConst.STATE_AC, prolist))

        elif problem_show == "notac":
            prolist = list(filter(lambda pro: pro['state'] != ChalConst.STATE_AC, prolist))

        for pro in prolist:
            _, rate = await RateService.inst.get_pro_ac_rate(pro['pro_id'])
            pro['rate_data'] = rate

        if order == "chal":
            prolist.sort(key=chal_ac_cmp)

        elif order == "user":
            prolist.sort(key=user_ac_cmp)

        elif order == "chalcnt":
            prolist.sort(key=lambda pro: pro['rate_data']['all_chal_cnt'])

        elif order == "chalaccnt":
            prolist.sort(key=lambda pro: pro['rate_data']['ac_chal_cnt'])

        elif order == "usercnt":
            prolist.sort(key=lambda pro: pro['rate_data']['user_all_chal_cnt'])

        elif order == "useraccnt":
            prolist.sort(key=lambda pro: pro['rate_data']['user_ac_chal_cnt'])

        if order_reverse:
            prolist.reverse()

        pronum = len(prolist)
        prolist = prolist[off: off + 40]

        await self.render('proset', pronum=pronum, prolist=prolist, clas=clas, pubclass_list=pubclass_list,
                          cur_pubclass=pubclass, pageoff=off, flt=flt, isadmin=self.acct.is_kernel())

    @reqenv
    async def post(self):
        pass


class ProStaticHandler(RequestHandler):
    @reqenv
    async def get(self, pro_id, path):
        pro_id = int(pro_id)

        err, pro = await ProService.inst.get_pro(pro_id, self.acct)
        if err:
            self.error(err)
            return

        if pro['status'] == ProService.STATUS_OFFLINE:
            self.error('Eacces')
            return

        if path[-3:] == 'pdf':
            self.set_header('Pragma', 'public')
            self.set_header('Expires', '0')
            self.set_header('Cache-Control', 'must-revalidate, post-check=0, pre-check=0')
            self.add_header('Content-Type', 'application/pdf')

            try:
                download = self.get_argument('download')
            except tornado.web.HTTPError:
                download = None

            if download:
                self.set_header('Content-Disposition', f'attachment; filename="pro{pro_id}.pdf"')
            else:
                self.set_header('Content-Disposition', 'inline')

        self.set_header('X-Accel-Redirect', f'/oj/problem/{pro_id}/{path}')
        return


class ProHandler(RequestHandler):
    @reqenv
    async def get(self, pro_id):
        pro_id = int(pro_id)

        err, pro = await ProService.inst.get_pro(pro_id, self.acct)
        if err:
            self.error(err)
            return

        if pro['status'] == ProService.STATUS_OFFLINE:
            self.error('Eacces')
            return

        testl = []
        for test_idx, test_conf in pro['testm_conf'].items():
            testl.append({
                'test_idx': test_idx,
                'timelimit': test_conf['timelimit'],
                'memlimit': test_conf['memlimit'],
                'weight': test_conf['weight'],
                'rate': 2000
            })

        async with self.db.acquire() as con:
            result = await con.fetch(
                '''
                    SELECT "test_idx", "rate" FROM "test_valid_rate"
                    WHERE "pro_id" = $1 ORDER BY "test_idx" ASC;
                ''',
                pro_id
            )

        countmap = {test_idx: count for test_idx, count in result}
        for test in testl:
            if test['test_idx'] in countmap:
                test['rate'] = math.floor(countmap[test['test_idx']])

        isguest = self.acct.is_guest()
        isadmin = self.acct.is_kernel()

        if isadmin:
            pass

        elif isguest or pro['tags'] is None or pro['tags'] == '':
            pro['tags'] = ''

        else:
            async with self.db.acquire() as con:
                result = await con.fetchrow(
                    '''
                        SELECT MIN("challenge_state"."state") AS "state"
                        FROM "challenge"
                        INNER JOIN "challenge_state"
                        ON "challenge"."chal_id" = "challenge_state"."chal_id"
                        AND "challenge"."acct_id" = $1
                        INNER JOIN "problem"
                        ON "challenge"."pro_id" = $3
                        WHERE "problem"."status" <= $2 AND "problem"."pro_id" = $3 AND "problem"."class" && $4;
                    ''',
                    self.acct.acct_id, ChalConst.STATE_AC, int(pro['pro_id']), [1, 2]
                )

            if result['state'] is None or result['state'] != ChalConst.STATE_AC:
                pro['tags'] = ''

        can_submit = await JudgeServerClusterService.inst.is_server_online()

        await self.render('pro', pro={
            'pro_id': pro['pro_id'],
            'name': pro['name'],
            'status': pro['status'],
            'tags': pro['tags'],
        }, testl=testl, isadmin=isadmin, can_submit=can_submit)
        return


class ProTagsHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        tags = self.get_argument('tags')
        pro_id = int(self.get_argument('pro_id'))

        if isinstance(tags, str):
            err, pro = await ProService.inst.get_pro(pro_id, self.acct)
            if err:
                self.error(err)
                return

            await LogService.inst.add_log(
                (self.acct.name + " updated the tag of problem #" + str(pro_id) + " to: \"" + str(tags) + "\"."),
                'manage.pro.update.tag')

            err, ret = await ProService.inst.update_pro(
                pro_id, pro['name'], pro['status'], pro['class'], pro['expire'], '', None, tags)

            if err:
                self.error(err)
                return

        else:
            self.error('Eacces')
            return

        self.finish('setting tags done')
        return
