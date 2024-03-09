import base64
import json

from msgpack import packb, unpackb

import config
from handlers.base import RequestHandler, reqenv, require_permission
from services.chal import ChalConst, ChalService
from services.judge import JudgeServerClusterService
from services.log import LogService
from services.pro import ProService
from services.user import UserConst


class ManageProHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self, page=None):
        if page is None:
            err, prolist = await ProService.inst.list_pro(self.acct)

            if (lock_list := (await self.rs.get('lock_list'))) is not None:
                lock_list = unpackb(lock_list)
            else:
                lock_list = []

            await self.render('manage/pro/pro-list', page='pro', prolist=prolist, lock_list=lock_list)
        elif page == "update":
            pro_id = int(self.get_argument('proid'))

            err, pro = await ProService.inst.get_pro(pro_id, self.acct)
            if err == 'Econf':
                self.finish(
                    '''
                        <script type="text/javascript" id="contjs">
                            function init() {
                    '''
                    f"index.go('/oj/manage/pro/reinit/?proid={pro_id}')"
                    '''
                            }
                        </script>
                    '''
                )
                return
            elif err is not None:
                self.error(err)
                return

            lock = await self.rs.get(f"{pro['pro_id']}_owner")

            testl = []
            for test_idx, test_conf in pro['testm_conf'].items():
                testl.append({
                    'test_idx': test_idx,
                    'timelimit': test_conf['timelimit'],
                    'memlimit': test_conf['memlimit'],
                    'weight': test_conf['weight'],
                    'rate': 2000
                })

            try:
                with open(f"problem/{pro_id}/conf.json", 'r') as conf_file:
                    conf_content = conf_file.read()
            except FileNotFoundError:
                conf_content = ''

            await self.render('manage/pro/update', page='pro', pro=pro, lock=lock, testl=testl,
                              problem_config_json=conf_content)

        elif page == "add":
            await self.render('manage/pro/add', page='pro')

        elif page == "reinit":
            pro_id = int(self.get_argument('proid'))

            await self.render('manage/pro/reinit', page='pro', pro_id=pro_id)

        elif page == "updatetests":
            pro_id = int(self.get_argument('proid'))

            await self.render('manage/pro/updatetests', page='pro', pro_id=pro_id)

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self, page=None):
        reqtype = self.get_argument('reqtype')

        if page == "add" and reqtype == 'addpro':
            name = self.get_argument('name')
            status = int(self.get_argument('status'))
            clas = int(self.get_argument('class'))
            expire = None
            pack_token = self.get_argument('pack_token')

            err, pro_id = await ProService.inst.add_pro(
                name, status, clas, expire, pack_token)
            await LogService.inst.add_log(
                f"{self.acct.name} had been send a request to add the problem #{pro_id}", 'manage.pro.add.pro')
            if err:
                self.error(err)
                return

            self.finish(json.dumps(pro_id))

        elif page == "update":
            if reqtype == 'updatepro':
                pro_id = int(self.get_argument('pro_id'))
                name = self.get_argument('name')
                status = int(self.get_argument('status'))
                clas = int(self.get_argument('class'))
                expire = None
                pack_type = int(self.get_argument('pack_type'))
                pack_token = self.get_argument('pack_token')
                tags = self.get_argument('tags')

                if pack_token == '':
                    pack_token = None

                err, _ = await ProService.inst.update_pro(
                    pro_id, name, status, clas, expire, pack_type, pack_token, tags)
                await LogService.inst.add_log(
                    f"{self.acct.name} had been send a request to update the problem #{pro_id}",
                    'manage.pro.update.pro')
                if err:
                    self.error(err)
                    return

                self.finish('S')

            elif reqtype == 'reinitpro':
                pro_id = int(self.get_argument('pro_id'))
                pack_token = self.get_argument('pack_token')
                pack_type = ProService.inst.PACKTYPE_FULL
                err, _ = await ProService.inst.unpack_pro(pro_id, pack_type, pack_token)
                if err:
                    self.error(err)
                    return

                self.finish('S')

            elif reqtype == 'updatelimit':
                pro_id = int(self.get_argument('pro_id'))
                timelimit = int(self.get_argument('timelimit'))
                memlimit = int(self.get_argument('memlimit'))

                err, _ = await ProService.inst.update_limit(pro_id, timelimit, memlimit)
                await LogService.inst.add_log(
                    f"{self.acct.name} had been send a request to update the problem #{pro_id}",
                    'manage.pro.update.limit')
                if err:
                    self.error(err)
                    return

                self.finish('S')

            elif reqtype == 'updateconf':
                pro_id = int(self.get_argument('pro_id'))
                conf_json_text = self.get_argument('conf')

                try:
                    conf_json = json.loads(conf_json_text)
                except json.decoder.JSONDecodeError:
                    self.error('Econf')
                    return

                with open(f'problem/{pro_id}/conf.json', 'w') as conf_f:
                    conf_f.write(conf_json_text)

                comp_type = conf_json['compile']
                score_type = conf_json['score']
                check_type = conf_json['check']
                timelimit = conf_json['timelimit']
                memlimit = conf_json['memlimit'] * 1024
                chalmeta = conf_json['metadata']

                async with self.db.acquire() as con:
                    await con.execute('DELETE FROM "test_config" WHERE "pro_id" = $1;', int(pro_id))

                    for test_idx, test_conf in enumerate(conf_json['test']):
                        metadata = {'data': test_conf['data']}

                        await con.execute(
                            '''
                                INSERT INTO "test_config"
                                ("pro_id", "test_idx", "compile_type", "score_type", "check_type",
                                "timelimit", "memlimit", "weight", "metadata", "chalmeta")
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10);
                            ''',
                            int(pro_id), int(test_idx), comp_type, score_type, check_type,
                            int(timelimit), int(memlimit), int(test_conf['weight']), json.dumps(metadata),
                            json.dumps(chalmeta)
                        )

                await LogService.inst.add_log(
                    f"{self.acct.name} had been send a request to update the problem #{pro_id}",
                    'manage.pro.update.conf')

                self.finish('S')

            elif reqtype == 'pro-lock':
                pro_id = int(self.get_argument('pro_id'))
                await self.rs.set(f'{pro_id}_owner', packb(1))

                if (lock_list := (await self.rs.get('lock_list'))) is not None:
                    lock_list = unpackb(lock_list)
                else:
                    lock_list = []

                if pro_id not in lock_list:
                    lock_list.append(pro_id)

                await self.rs.set('lock_list', packb(lock_list))
                self.finish('S')

            elif reqtype == 'pro-unlock':
                pro_id = int(self.get_argument('pro_id'))
                pwd = str(self.get_argument('pwd'))

                if config.unlock_pwd != base64.b64encode(packb(pwd)):
                    self.error('Eacces')
                    return

                lock_list = unpackb((await self.rs.get('lock_list')))
                lock_list.remove(pro_id)
                await self.rs.set('lock_list', packb(lock_list))
                await self.rs.delete(f"{pro_id}_owner")
                self.finish('S')

        elif page is None: # pro-list
            if reqtype == 'rechal':
                pro_id = int(self.get_argument('pro_id'))

                can_submit = await JudgeServerClusterService.inst.is_server_online()
                if not can_submit:
                    self.error('Ejudge')
                    return

                err, pro = await ProService.inst.get_pro(pro_id, self.acct)
                if err:
                    self.error(err)
                    return

                async with self.db.acquire() as con:
                    result = await con.fetch(
                        '''
                            SELECT "challenge"."chal_id", "challenge"."compile_type" FROM "challenge"
                            LEFT JOIN "challenge_state"
                            ON "challenge"."chal_id" = "challenge_state"."chal_id"
                            WHERE "pro_id" = $1 AND "challenge_state"."state" IS NULL;
                        ''',
                        pro_id
                    )
                await LogService.inst.add_log(
                    f"{self.acct.name} made a request to rejudge the problem #{pro_id} with {len(result)} chals",
                    'manage.chal.rechal')

                for chal_id, comp_type in result:
                    file_ext = ChalConst.FILE_EXTENSION[comp_type]
                    err, _ = await ChalService.inst.reset_chal(chal_id)
                    err, _ = await ChalService.inst.emit_chal(
                        chal_id,
                        pro_id,
                        pro['testm_conf'],
                        comp_type,
                        f"/nfs/code/{chal_id}/main.{file_ext}",
                        f"/nfs/problem/{pro_id}/res"
                    )

                self.finish('S')
