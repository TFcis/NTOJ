import json
import time
import zlib

from handlers.base import RequestHandler, reqenv, require_permission
from handlers.contests.base import contest_require_permission
from services.chal import ChalConst, ChalService
from services.judge import JudgeServerClusterService
from services.pro import ProService
from services.user import UserConst


class SubmitHandler(RequestHandler):
    @reqenv
    @require_permission([UserConst.ACCTTYPE_USER, UserConst.ACCTTYPE_KERNEL])
    @contest_require_permission('all')
    async def get(self, pro_id=None):
        if pro_id is None:
            self.error('Enoext')
            return

        pro_id = int(pro_id)

        allow_compilers = ChalConst.ALLOW_COMPILERS
        if self.contest:
            if not self.contest.is_running() and not self.contest.is_admin(self.acct):
                self.error('Eacces')
                return

            if pro_id not in self.contest.pro_list:
                self.error('Enoext')
                return

            allow_compilers = self.contest.allow_compilers

        can_submit = JudgeServerClusterService.inst.is_server_online()

        if not can_submit:
            self.finish('<h1 style="color: red;">All Judge Server Offline</h1>')
            return

        pro_id = int(pro_id)
        err, pro = await ProService.inst.get_pro(pro_id, self.acct, is_contest=self.contest is not None)
        if err:
            self.error(err)
            return

        if pro['status'] == ProService.STATUS_OFFLINE:
            self.error('Eacces')
            return

        if not pro['allow_submit']:
            self.error('Eacces')
            return

        if pro['testm_conf']['is_makefile']:
            allow_compilers = list(filter(lambda compiler: compiler in ['gcc', 'g++', 'clang', 'clang++'], allow_compilers))

        await self.render('submit', pro=pro,
                          allow_compilers=allow_compilers, contest_id=self.contest.contest_id if self.contest else 0)

    @reqenv
    @require_permission([UserConst.ACCTTYPE_USER, UserConst.ACCTTYPE_KERNEL])
    @contest_require_permission('all')
    async def post(self):
        can_submit = JudgeServerClusterService.inst.is_server_online()

        if not can_submit:
            self.error('Ejudge')
            return

        contest_id = 0
        if self.contest:
            contest_id = self.contest.contest_id

        reqtype = self.get_argument('reqtype')
        if reqtype == 'submit':
            pro_id = int(self.get_argument('pro_id'))
            code = self.get_argument('code')
            comp_type = str(self.get_argument('comp_type'))

            if self.contest:
                pri = ChalConst.CONTEST_PRI
                if not self.contest.is_running() and not self.contest.is_admin(self.acct):
                    self.error('Eacces')
                    return

                if pro_id not in self.contest.pro_list:
                    self.error('Enoext')
                    return
            else:
                pri = ChalConst.NORMAL_PRI

            err = await self.is_allow_submit(code, comp_type, pro_id)
            if err:
                self.error(err)
                return

            err, pro = await ProService.inst.get_pro(pro_id, self.acct, is_contest=self.contest is not None)
            if err:
                self.error(err)
                return

            if pro['status'] == ProService.STATUS_OFFLINE:
                self.error('Eacces')
                return

            elif pro['status'] == ProService.STATUS_CONTEST and not self.contest:
                self.error('Eacces')
                return

            if not pro['allow_submit']:
                self.error('Eacces')
                return

            err, chal_id = await ChalService.inst.add_chal(pro_id, self.acct.acct_id, contest_id, comp_type, code)
            if err:
                self.error(err)
                return

        elif reqtype == 'rechal':
            if ((self.contest is None and self.acct.is_kernel())  # not in contest
                    or (self.contest and self.contest.is_admin(self.acct))):  # in contest
                if self.contest:
                    pri = ChalConst.CONTEST_REJUDGE_PRI
                else:
                    pri = ChalConst.NORMAL_REJUDGE_PRI

                chal_id = int(self.get_argument('chal_id'))

                err, ret = await ChalService.inst.reset_chal(chal_id)
                err, chal = await ChalService.inst.get_chal(chal_id)

                pro_id = chal['pro_id']
                comp_type = chal['comp_type']
                err, pro = await ProService.inst.get_pro(pro_id, self.acct)
                if err:
                    self.finish(err)
                    return

        else:
            self.error('Eparam')
            return

        err, _ = await ChalService.inst.emit_chal(
            chal_id,
            pro_id,
            pro['testm_conf'],
            comp_type,
            pri=pri
        )
        if err:
            self.error(err)
            return

        if reqtype == 'submit' and pro['status'] in [ProService.STATUS_ONLINE, ProService.STATUS_CONTEST]:
            await self.rs.publish('challist_sub', 1)

        self.finish(json.dumps(chal_id))
        return

    async def is_allow_submit(self, code: str, comp_type: str, pro_id: int):
        # limits variable config
        allow_compilers = ChalConst.ALLOW_COMPILERS
        submit_cd_time = 30
        if self.contest:
            allow_compilers = self.contest.allow_compilers
            submit_cd_time = self.contest.submission_cd_time

        if len(code.strip()) == 0:
            return 'Eempty'

        if len(code) > ProService.CODE_MAX:
            return 'Ecodemax'

        # TODO: if problem is makefile type, we should restrict compiler type
        if comp_type not in allow_compilers:
            return 'Ecomp'

        should_check_submit_cd = (
            self.contest is None and not self.acct.is_kernel()  # not in contest
            or
            self.contest and self.acct.acct_id in self.contest.acct_list  # in contest
        )

        name = ''
        crc32 = ''
        if self.contest:
            name = f'contest_{self.contest.contest_id}_acct_{self.acct.acct_id}_pro_{pro_id}_compiler_{comp_type}'
            crc32 = str(zlib.crc32(code.encode('utf-8')))

            if (await self.rs.sismember(name, crc32)):
                return 'Esame'

        if should_check_submit_cd:
            last_submit_name = f"last_submit_time_{self.acct.acct_id}"
            if (last_submit_time := (await self.rs.get(last_submit_name))) is None:
                if submit_cd_time:
                    await self.rs.set(last_submit_name, int(time.time()), ex=submit_cd_time)  # ex means expire

            else:
                last_submit_time = int(str(last_submit_time)[2:-1])
                if int(time.time()) - last_submit_time < submit_cd_time:
                    return f'Einternal{submit_cd_time}'

                else:
                    await self.rs.set(last_submit_name, int(time.time()))

        if self.contest:
            await self.rs.sadd(name, crc32)
            await self.rs.expire(name, time=(self.contest.contest_end - self.contest.contest_start))

        return None
