import json

import tornado.web

from handlers.base import RequestHandler, reqenv, require_permission
from services.chal import ChalConst
from services.judge import JudgeServerClusterService
from services.log import LogService
from services.pro import ProClassService, ProClassConst, ProConst, ProService
from services.rate import RateService
from services.user import UserService, UserConst


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
            pageoff = int(self.get_argument('pageoff'))
        except tornado.web.HTTPError:
            pageoff = 0

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

        try:
            proclass_id = int(self.get_argument('proclass_id'))
        except tornado.web.HTTPError:
            proclass_id = None

        err, prolist = await ProService.inst.list_pro(self.acct)

        proclass = None
        if proclass_id is not None:
            err, proclass = await ProClassService.inst.get_proclass(proclass_id)
            if err:
                self.error(err)
                return
            proclass = dict(proclass)

            if proclass['type'] == ProClassConst.OFFICIAL_HIDDEN and not self.acct.is_kernel():
                self.error('Eacces')
                return
            elif proclass['type'] == ProClassConst.USER_HIDDEN and proclass['acct_id'] != self.acct.acct_id:
                self.error('Eacces')
                return

            p_list = proclass['list']
            prolist = list(filter(lambda pro: pro['pro_id'] in p_list, prolist))
            if proclass['acct_id']:
                _, creator = await UserService.inst.info_acct(proclass['acct_id'])
                proclass['creator_name'] = creator.name

        if show_only_online_pro:
            prolist = list(filter(lambda pro: pro['status'] == ProConst.STATUS_ONLINE, prolist))

        _, acct_states = await RateService.inst.map_rate_acct(self.acct)
        ac_pro_cnt = 0
        def _set_pro_state_and_tags(pro):
            nonlocal ac_pro_cnt
            pro['state'] = acct_states.get(pro['pro_id'], {}).get('state')
            ac_pro_cnt += pro['state'] == ChalConst.STATE_AC

            if (self.acct.is_guest()) or (not self.acct.is_kernel() and pro['state'] != ChalConst.STATE_AC):
                pro['tags'] = ''

            return pro

        prolist = list(map(lambda pro: _set_pro_state_and_tags(pro), prolist))

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

        pro_total_cnt = len(prolist)
        prolist = prolist[pageoff: pageoff + 40]

        await self.render(
            'proset',
            user=self.acct,
            pro_total_cnt=pro_total_cnt,
            ac_pro_cnt=ac_pro_cnt,
            prolist=prolist,
            cur_proclass=proclass,
            pageoff=pageoff,
            flt=flt,
        )

    @reqenv
    async def post(self):
        reqtype = self.get_argument('reqtype')
        if reqtype == "listproclass":
            _, accts = await UserService.inst.list_acct(UserConst.ACCTTYPE_KERNEL)
            accts = {acct.acct_id: acct.name for acct in accts}

            _, proclass_list = await ProClassService.inst.get_proclass_list()
            def _set_creator_name(proclass):
                proclass = dict(proclass)
                if proclass['acct_id']:
                    proclass['creator_name'] = accts[proclass['acct_id']]

                return proclass
            proclass_list = list(map(_set_creator_name, proclass_list))

            proclass_cata = {
                "official": list(filter(lambda proclass: proclass['type'] == ProClassConst.OFFICIAL_PUBLIC, proclass_list)),
                "shared": list(filter(lambda proclass: proclass['type'] == ProClassConst.USER_PUBLIC, proclass_list)),
                "collection": list(filter(lambda proclass: proclass['proclass_id'] in self.acct.proclass_collection, proclass_list)),
                "own": list(filter(lambda proclass: proclass['acct_id'] == self.acct.acct_id, proclass_list)),
            }
            if self.acct.is_kernel():
                proclass_cata['official'].extend(filter(lambda proclass: proclass['type'] == ProClassConst.OFFICIAL_HIDDEN, proclass_list))

            self.finish(json.dumps(proclass_cata))

        elif reqtype == "collect":
            if self.acct.is_guest():
                self.error('Eacces')
                return

            proclass_id = int(self.get_argument('proclass_id'))

            if proclass_id in self.acct.proclass_collection:
                self.error('Eexist')
                return

            self.acct.proclass_collection.append(proclass_id)
            self.acct.proclass_collection.sort()
            await UserService.inst.update_acct(self.acct.acct_id, self.acct.acct_type, self.acct.name,
                                         self.acct.photo, self.acct.cover, self.acct.motto, self.acct.proclass_collection)
            self.finish('S')

        elif reqtype == "decollect":
            if self.acct.is_guest():
                self.error('Eacces')
                return

            proclass_id = int(self.get_argument('proclass_id'))

            if proclass_id not in self.acct.proclass_collection:
                self.error('Enoext')
                return

            self.acct.proclass_collection.remove(proclass_id)
            self.acct.proclass_collection.sort()
            await UserService.inst.update_acct(self.acct.acct_id, self.acct.acct_type, self.acct.name,
                                         self.acct.photo, self.acct.cover, self.acct.motto, self.acct.proclass_collection)
            self.finish('S')


class ProStaticHandler(RequestHandler):
    @reqenv
    async def get(self, pro_id, path):
        pro_id = int(pro_id)
        if self.contest:
            if pro_id not in self.contest.pro_list:
                self.error('Enoext')
                return

        err, pro = await ProService.inst.get_pro(pro_id, self.acct, is_contest=self.contest is not None)
        if err:
            self.error(err)
            return

        if pro['status'] == ProConst.STATUS_OFFLINE:
            self.error('Eacces')
            return

        elif pro['status'] == ProConst.STATUS_CONTEST:
            if not self.contest:
                self.error('Eacces')
                return

            elif not (self.contest.is_running() or self.contest.is_admin(self.acct)):
                self.error('Eacces')
                return

        if path.endswith('pdf'):
            self.set_header('Pragma', 'public')
            self.set_header('Expires', '0')
            self.set_header('Cache-Control', 'must-revalidate, post-check=0, pre-check=0')
            self.set_header('Content-Type', 'application/pdf')

            try:
                download = self.get_argument('download')
            except tornado.web.HTTPError:
                download = None

            if download:
                self.set_header('Content-Disposition', f'attachment; filename="pro{pro_id}.pdf"')
            else:
                self.set_header('Content-Disposition', 'inline')

        self.set_header('X-Accel-Redirect', f'/oj/problem/{pro_id}/{path}')


class ProHandler(RequestHandler):
    @reqenv
    async def get(self, pro_id):
        pro_id = int(pro_id)

        if self.contest:
            if pro_id not in self.contest.pro_list:
                self.error('Enoext')
                return

            if not self.contest.is_member(self.acct):
                self.error('Eacces')
                return

            if not self.contest.is_running() and not self.contest.is_admin(self.acct):
                self.error('Eacces')
                return

        err, pro = await ProService.inst.get_pro(pro_id, self.acct, is_contest=self.contest is not None)
        if err:
            self.error(err)
            return

        if pro['status'] == ProConst.STATUS_OFFLINE:
            self.error('Eacces')
            return

        elif pro['status'] == ProConst.STATUS_CONTEST and not self.contest:
            self.error('Eacces')
            return

        # NOTE: Guest cannot see tags
        # NOTE: Admin can see tags
        # NOTE: User get ac can see tags

        if self.acct.is_guest() or pro['tags'] is None or pro['tags'] == '':
            pro['tags'] = ''

        elif not self.acct.is_kernel():
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
                        WHERE "problem"."status" <= $2 AND "problem"."pro_id" = $3;
                    ''',
                    self.acct.acct_id,
                    ChalConst.STATE_AC,
                    int(pro['pro_id']),
                )

            if result['state'] is None or result['state'] != ChalConst.STATE_AC:
                pro['tags'] = ''

        can_submit = JudgeServerClusterService.inst.is_server_online()

        await self.render(
            'pro',
            pro=pro,
            can_submit=can_submit,
            contest=self.contest
        )


class ProTagsHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        tags = self.get_argument('tags')
        pro_id = int(self.get_argument('pro_id'))

        err, pro = await ProService.inst.get_pro(pro_id, self.acct)
        if err:
            self.error(err)
            return

        await LogService.inst.add_log(
            (self.acct.name + " updated the tag of problem #" + str(pro_id) + " to: \"" + str(tags) + "\"."),
            'manage.pro.update.tag',
        )

        err, _ = await ProService.inst.update_pro(
            pro_id, pro['name'], pro['status'], '', None, tags, pro['allow_submit']
        )

        if err:
            self.error(err)
            return

        await self.finish('S')
