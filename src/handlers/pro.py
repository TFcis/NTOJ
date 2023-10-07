import math

import tornado.web

from services.chal import ChalConst
from services.judge import JudgeServerClusterService
from services.log import LogService
from services.pro import ProService, ProClassService
from services.rate import RateService
from services.user import UserConst
from handlers.base import RequestHandler, reqenv, require_permission


class ProsetHandler(RequestHandler):
    @reqenv
    async def get(self):
        try:
            off = int(self.get_argument('off'))
        except tornado.web.HTTPError:
            off = 0

        clas = None

        try:
            pubclass_id = int(self.get_argument('pubclass_id'))
        except tornado.web.HTTPError:
            pubclass_id = None

        if pubclass_id is None:
            pass

        err, prolist = await ProService.inst.list_pro(
            self.acct, state=True, clas=clas)

        _, pubclass_list = await ProClassService.inst.get_pubclass_list()

        if pubclass_id is None:
            pronum = len(prolist)
            prolist = prolist[off:off + 40]
            for pro in prolist:
                _, rate = await RateService.inst.get_pro_ac_rate(pro['pro_id'])
                pro['rate_data'] = rate

            await self.render('proset', pronum=pronum, prolist=prolist, clas=clas, pubclass_list=pubclass_list,
                              cur_pubclass=None, pageoff=off)
            return

        else:
            err, pubclass = await ProClassService.inst.get_pubclass(pubclass_id)
            if err:
                self.error(err)
                return

            p_list = pubclass['list']
            prolist2 = []
            for pro in prolist:
                if pro['pro_id'] in p_list:
                    prolist2.append(pro)
            prolist = prolist2
            pronum = len(prolist)
            prolist = prolist[off:off + 40]
            for pro in prolist:
                _, rate = await RateService.inst.get_pro_ac_rate(pro['pro_id'])
                pro['rate_data'] = rate

            await self.render('proset', pronum=pronum, prolist=prolist, clas=clas, pubclass_list=pubclass_list,
                              cur_pubclass=pubclass, pageoff=off)
            return

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

        countmap = {}
        for test_idx, count in result:
            countmap[test_idx] = count

        for test in testl:
            if test['test_idx'] in countmap:
                test['rate'] = math.floor(countmap[test['test_idx']])

        isguest = (self.acct['acct_type'] == UserConst.ACCTTYPE_GUEST)
        isadmin = (self.acct['acct_type'] == UserConst.ACCTTYPE_KERNEL)

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
                    int(self.acct['acct_id']), ChalConst.STATE_AC, int(pro['pro_id']), [1, 2]
                )

            if result['state'] is None or result['state'] != ChalConst.STATE_AC:
                pro['tags'] = ''

        judge_status_list = await JudgeServerClusterService.inst.get_servers_status()
        can_submit = False

        for status in judge_status_list:
            if status['status']:
                can_submit = True
                break

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
                (self.acct['name'] + " updated the tag of problem #" + str(pro_id) + " to: \"" + str(tags) + "\"."),
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
