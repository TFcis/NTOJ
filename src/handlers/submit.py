import time
import json

from services.user import UserService, UserConst
from services.chal import ChalService, ChalConst
from services.pro import ProService
from services.judge import JudgeServerClusterService
from utils.req import RequestHandler, reqenv

class SubmitHandler(RequestHandler):
    @reqenv
    async def get(self, pro_id):
        if self.acct['acct_id'] == UserService.ACCTID_GUEST:
            self.error('Esign')
            return

        pro_id = int(pro_id)
        err, pro = await ProService.inst.get_pro(pro_id, self.acct)
        if err:
            self.error(err)
            return

        if pro['status'] == ProService.STATUS_OFFLINE:
            self.error('Eacces')
            return

        judge_status_list = await JudgeServerClusterService.inst.get_servers_status()
        can_submit = False

        for status in judge_status_list:
            if status['status']:
                can_submit = True
                break

        if can_submit == False:
            self.finish('<h1 style="color: red;">All Judge Server Offline</h1>')
            return

        await self.render('submit', pro=pro)
        return

    @reqenv
    async def post(self):
        if self.acct['acct_id'] == UserConst.ACCTID_GUEST:
            self.error('Esign')
            return

        judge_status_list = await JudgeServerClusterService.inst.get_servers_status()
        can_submit = False

        for status in judge_status_list:
            if status['status']:
                can_submit = True
                break

        if can_submit == False:
            self.error('Ejudge')
            return

        reqtype = self.get_argument('reqtype')
        if reqtype == 'submit':
            pro_id = int(self.get_argument('pro_id'))
            code = self.get_argument('code')
            comp_type = str(self.get_argument('comp_type'))

            if len(code.strip()) == 0:
                self.error('Eempty')
                return

            if len(code) > ProService.CODE_MAX:
                self.error('Ecodemax')
                return

            if self.acct['acct_type'] != UserConst.ACCTTYPE_KERNEL:
                last_submit_name = f"last_submit_time_{self.acct['acct_id']}"
                if (last_submit_time := (await self.rs.get(last_submit_name))) == None:
                    await self.rs.set(last_submit_name, int(time.time()), ex=600)

                else:
                    last_submit_time = int(str(last_submit_time)[2:-1])
                    if int(time.time()) - last_submit_time < 30:
                        self.error('Einternal')
                        return

                    else:
                        await self.rs.set(last_submit_name, int(time.time()))

            if comp_type not in ['gcc', 'g++', 'clang++', 'python3', 'rustc']:
                self.error('Eparam')
                return

            err, pro = await ProService.inst.get_pro(pro_id, self.acct)
            if err:
                self.error(err)
                return

            if pro['status'] == ProService.STATUS_OFFLINE:
                self.error('Eacces')
                return

            #TODO: code prevent '/dev/random'
            #code = code.replace('bits/stdc++.h','DontUseMe.h')
            err, chal_id = await ChalService.inst.add_chal(
                pro_id, self.acct['acct_id'], comp_type, code)

            if err:
                self.error(err)
                return

        elif (reqtype == 'rechal'
              and self.acct['acct_type'] == UserService.ACCTTYPE_KERNEL):

            chal_id = int(self.get_argument('chal_id'))

            err, ret = await ChalService.inst.reset_chal(chal_id)
            err, chal = await ChalService.inst.get_chal(chal_id, self.acct)

            pro_id = chal['pro_id']
            comp_type = chal['comp_type']
            err, pro = await ProService.inst.get_pro(pro_id, self.acct)
            if err:
                self.finish(err)
                return

        else:
            self.error('Eparam')
            return

        file_ext = ChalConst.FILE_EXTENSION[comp_type]

        err, _ = await ChalService.inst.emit_chal(
            chal_id,
            pro_id,
            pro['testm_conf'],
            comp_type,
            f'/nfs/code/{chal_id}/main.{file_ext}',
            f'/nfs/problem/{pro_id}/res')
        if err:
            self.error(err)
            return

        if reqtype == 'submit' and pro['status'] == ProService.STATUS_ONLINE:
            await self.rs.publish('challist_sub', 1)

        self.finish(json.dumps(chal_id))
        return
