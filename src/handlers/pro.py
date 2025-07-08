from handlers.base import RequestHandler, reqenv, require_permission
from services.chal import ChalConst
from services.judge import JudgeServerClusterService
from services.log import LogService
from services.pro import ProClassService, ProClassConst, ProConst, ProService
from services.rate import RateService
from services.user import UserService, UserConst

PERMISSION_DENIED_ERROR = (('Eacces', 'Permission denied'))

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
        pageoff = int(self.get_argument('pageoff', default=0))
        order = self.get_argument('order', default=None)
        problem_show = self.get_argument('show', default='all')
        show_only_online_pro = self.get_argument('online', default=False)
        order_reverse = self.get_argument('reverse', default=False)
        search_name = self.get_argument('name', default=None)
        search_tags = self.get_argument('tags', default=None)

        flt = {
            'order': order,
            'problem_show': problem_show,
            'online': show_only_online_pro,
            'reverse': order_reverse,
            'name': search_name,
            'tags': search_tags,
        }

        proclass_id = int(self.get_argument('proclass_id', default=0))
        if proclass_id == 0:
            proclass_id = None

        allow_statuses = [ProConst.STATUS_ONLINE]
        if self.acct.is_kernel():
            allow_statuses.append(ProConst.STATUS_HIDDEN)
        err, prolist = await ProService.inst.list_pro(allow_statuses)

        proclass = None
        if proclass_id:
            err, proclass = await ProClassService.inst.get_proclass(proclass_id)
            if err:
                return self.error(err)
            proclass = dict(proclass)

            if proclass['type'] == ProClassConst.OFFICIAL_HIDDEN and not self.acct.is_kernel():
                return self.error(PERMISSION_DENIED_ERROR)
            elif proclass['type'] == ProClassConst.USER_HIDDEN and proclass['acct_id'] != self.acct.acct_id:
                return self.error(PERMISSION_DENIED_ERROR)

            p_list = proclass['list']
            prolist = list(filter(lambda pro: pro['pro_id'] in p_list, prolist))
            if proclass['acct_id']:
                _, creator = await UserService.inst.info_acct(proclass['acct_id'])
                proclass['creator_name'] = creator.name

        if search_name:
            search_name = search_name.lower()
            def _find_name(name: str):
                return name.lower().find(search_name) != -1
            prolist = filter(lambda pro: _find_name(pro['name']), prolist)

        if show_only_online_pro:
            prolist = filter(lambda pro: pro['status'] == ProConst.STATUS_ONLINE, prolist)

        _, acct_states = await RateService.inst.map_rate_acct(self.acct)
        ac_pro_cnt = 0
        def _set_pro_state_and_tags(pro):
            nonlocal ac_pro_cnt
            pro['state'] = acct_states.get(pro['pro_id'], {}).get('state')
            ac_pro_cnt += pro['state'] == ChalConst.STATE_AC

            if (self.acct.is_guest()) or (not self.acct.is_kernel() and pro['state'] != ChalConst.STATE_AC):
                pro['tags'] = ''

            return pro

        prolist = map(lambda pro: _set_pro_state_and_tags(pro), prolist)

        if search_tags:
            search_tags = search_tags.lower()
            def _find_tags(tags: str):
                return tags.lower().find(search_tags) != -1
            prolist = filter(lambda pro: _find_tags(pro['tagss']), prolist)

        if problem_show == "onlyac":
            prolist = filter(lambda pro: pro['state'] == ChalConst.STATE_AC, prolist)

        elif problem_show == "notac":
            prolist = filter(lambda pro: pro['state'] != ChalConst.STATE_AC, prolist)

        prolist = list(prolist)
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
            proclass_type = self.get_argument('proclass_type')
            _, proclass_list = await ProClassService.inst.get_proclass_list()

            _, accts = await UserService.inst.list_acct(UserConst.ACCTTYPE_KERNEL)
            accts = {acct.acct_id: acct.name for acct in accts}

            if proclass_type == 'official':
                if self.acct.is_kernel():
                    proclass_list = list(filter(
                        lambda proclass: proclass['type'] in [ProClassConst.OFFICIAL_PUBLIC, ProClassConst.OFFICIAL_HIDDEN], proclass_list))
                else:
                    proclass_list = list(filter(lambda proclass: proclass['type'] == ProClassConst.OFFICIAL_PUBLIC, proclass_list))

            elif proclass_type == 'shared':
                proclass_list = list(filter(lambda proclass: proclass['type'] == ProClassConst.USER_PUBLIC, proclass_list))

            elif proclass_type == 'collection':
                proclass_list = list(filter(lambda proclass: proclass['proclass_id'] in self.acct.proclass_collection, proclass_list))

            elif proclass_type == 'own':
                proclass_list = list(filter(lambda proclass: proclass['acct_id'] == self.acct.acct_id, proclass_list))

            else:
                self.error(('Eparam', 'Wrong proclass_type'))
                return

            _, acct_states = await RateService.inst.map_rate_acct(self.acct)
            for i in range(len(proclass_list)):
                proclass_list[i] = dict(proclass_list[i])
                proclass = proclass_list[i]
                ac_cnt = 0
                err, p = await ProClassService.inst.get_proclass(proclass['proclass_id'])
                if proclass['acct_id']:
                    proclass['creator_name'] = accts[proclass['acct_id']]

                for pro_id in p['list']:
                    if pro_id in acct_states:
                        ac_cnt += acct_states[pro_id]['state'] == ChalConst.STATE_AC

                proclass['ac_cnt'] = ac_cnt
                proclass['total_cnt'] = len(p['list'])

            self.error(('S', proclass_list))

        elif reqtype == "collect":
            if self.acct.is_guest():
                return self.error(('Eacces', 'Please login'))

            proclass_id = int(self.get_argument('proclass_id'))

            if proclass_id in self.acct.proclass_collection:
                return self.error(('Eexist', 'Problem class is already collected'))

            self.acct.proclass_collection.append(proclass_id)
            self.acct.proclass_collection.sort()
            await UserService.inst.update_acct(self.acct)
            self.error(('S', ''))

        elif reqtype == "decollect":
            if self.acct.is_guest():
                return self.error(('Eacces', 'Please login'))

            proclass_id = int(self.get_argument('proclass_id'))

            if proclass_id not in self.acct.proclass_collection:
                return self.error(('Enoext', 'Problem class is not in your collection'))

            self.acct.proclass_collection.remove(proclass_id)
            self.acct.proclass_collection.sort()
            await UserService.inst.update_acct(self.acct)
            self.error(('S', ''))


class ProStaticHandler(RequestHandler):
    @reqenv
    async def get(self, pro_id: int, path: str):
        pro_id = int(pro_id)
        allow_statuses = ProConst.PRO_STATUS_NORMAL_USER
        if self.contest:
            if not self.contest.is_pro(pro_id):
                return self.error(('Enoext', 'Problem not in contest'))

            allow_statuses = ProConst.PRO_STATUS_CONTEST_USER
        else:
            if self.acct.is_kernel():
                allow_statuses = ProConst.PRO_STATUS_KERNEL_USER


        err, pro = await ProService.inst.get_pro(pro_id, allow_statuses)
        if err:
            return self.error(err)

        if pro['status'] == ProConst.STATUS_CONTEST:
            if not (self.contest.is_running() or self.contest.is_admin(self.acct)):
                return self.error(PERMISSION_DENIED_ERROR)

        if path.endswith('pdf'):
            self.set_header('Pragma', 'public')
            self.set_header('Expires', '0')
            self.set_header('Cache-Control', 'must-revalidate, post-check=0, pre-check=0')
            self.set_header('Content-Type', 'application/pdf')

            download = self.get_argument('download', default=None)
            if download:
                self.set_header('Content-Disposition', f'attachment; filename="pro{pro_id}.pdf"')
            else:
                self.set_header('Content-Disposition', 'inline')

        self.set_header('X-Accel-Redirect', f'/oj/problem/{pro_id}/{path}')


class ProHandler(RequestHandler):
    @reqenv
    async def get(self, pro_id):
        pro_id = int(pro_id)
        allow_statuses = ProConst.PRO_STATUS_NORMAL_USER

        if self.contest:
            if not self.contest.is_pro(pro_id):
                return self.error(('Enoext', 'Problem not in contest'))

            if not self.contest.is_start() and not self.contest.is_admin(self.acct):
                return self.error(PERMISSION_DENIED_ERROR)

            elif not self.contest.is_running() and not self.contest.is_member(self.acct):
                return self.error(PERMISSION_DENIED_ERROR)

            allow_statuses = ProConst.PRO_STATUS_CONTEST_USER

        else:
            if self.acct.is_kernel():
                allow_statuses = ProConst.PRO_STATUS_KERNEL_USER

        err, pro = await ProService.inst.get_pro(pro_id, allow_statuses)
        if err:
            return self.error(err)

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
        topcoder = None
        if not self.contest:
            err, topcoder = await RateService.inst.get_pro_topcoder(pro_id)
            if err:
                return self.error(err)

        await self.render(
            'pro',
            pro=pro,
            can_submit=can_submit,
            contest=self.contest,
            topcoder=topcoder,
        )


class ProTagsHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        tags = self.get_argument('tags')
        pro_id = int(self.get_argument('pro_id'))

        allow_statuses = ProConst.PRO_STATUS_NORMAL_USER
        if self.contest:
            allow_statuses = ProConst.PRO_STATUS_CONTEST_USER
        else:
            if self.acct.is_kernel():
                allow_statuses = ProConst.PRO_STATUS_KERNEL_USER

        err, pro = await ProService.inst.get_pro(pro_id, allow_statuses)
        if err:
            return self.error(err)

        await LogService.inst.add_log(
            (self.acct.name + " updated the tag of problem #" + str(pro_id) + " to: \"" + str(tags) + "\"."),
            'manage.pro.update.tag',
        )

        err, _ = await ProService.inst.update_pro(
            pro_id, pro['name'], pro['status'], '', None, tags, pro['allow_submit']
        )

        if err:
            return self.error(err)

        self.error(('S', ''))
