import asyncio
import base64
import json
import os
import shutil

from msgpack import packb, unpackb

import config
from handlers.base import RequestHandler, reqenv, require_permission
from services.chal import ChalConst, ChalService
from services.judge import JudgeServerClusterService
from services.log import LogService
from services.pro import ProService
from services.user import UserConst
from services.pack import PackService


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
                testl.append(
                    {
                        'test_idx': test_idx,
                        'timelimit': test_conf['timelimit'],
                        'memlimit': test_conf['memlimit'],
                        'weight': test_conf['weight'],
                        'rate': 2000,
                    }
                )

            await self.render(
                'manage/pro/update', page='pro', pro=pro, lock=lock, testl=testl
            )

        elif page == "add":
            await self.render('manage/pro/add', page='pro')

        elif page == "reinit":
            pro_id = int(self.get_argument('proid'))

            await self.render('manage/pro/reinit', page='pro', pro_id=pro_id)

        elif page == "updatetests":
            pro_id = int(self.get_argument('proid'))
            err, pro = await ProService.inst.get_pro(pro_id, self.acct)

            await self.render('manage/pro/updatetests', page='pro', pro_id=pro_id, tests=pro['testm_conf'])

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self, page=None):
        reqtype = self.get_argument('reqtype')

        if page == "add" and reqtype == 'addpro':
            name = self.get_argument('name')
            status = int(self.get_argument('status'))
            pack_token = self.get_argument('pack_token')

            err, pro_id = await ProService.inst.add_pro(name, status, pack_token)
            await LogService.inst.add_log(
                f"{self.acct.name} had been send a request to add the problem #{pro_id}", 'manage.pro.add.pro'
            )
            if err:
                self.error(err)
                return

            self.finish(json.dumps(pro_id))

        elif page == "updatetests":
            if reqtype == "preview":
                pro_id = int(self.get_argument('pro_id'))
                idx = int(self.get_argument('idx'))
                type = self.get_argument('type')

                if type not in ["in", "out"]:
                    self.error('Eparam')
                    return

                path = f'problem/{pro_id}/res/testdata/{idx}.{type}'
                if not os.path.isfile(path):
                    self.error('Enoext')
                    return

                with open(f'problem/{pro_id}/res/testdata/{idx}.{type}', 'r') as testcase_f:
                    content = testcase_f.readlines()
                    if len(content) > 25:
                        self.error('Efile')
                        return

                    self.finish(json.dumps(''.join(content)))

            elif reqtype == "updateweight":
                # TODO
                return NotImplemented
                pro_id = int(self.get_argument('pro_id'))
                group = int(self.get_argument('group'))
                weight = int(self.get_argument('weight'))

                err, pro = await ProService.inst.get_pro(pro_id, self.acct)

                await LogService.inst.add_log(
                    f"{self.acct.name} had been send a request to add the problem #{pro_id}", 'manage.pro.update.tests'
                )

            elif reqtype == "updatesingletestcase":
                pro_id = int(self.get_argument('pro_id'))
                idx = int(self.get_argument('idx'))
                test_type = self.get_argument('type')
                pack_token = self.get_argument('pack_token')

                path = f'problem/{pro_id}/res/testdata/{idx}.{test_type}'
                if not os.path.isfile(path):
                    self.error('Enoext')
                    return

                _ = await PackService.inst.direct_copy(pack_token, path)
                await LogService.inst.add_log(
                    f"{self.acct.name} had been send a request to update a single testcase of the problem #{pro_id}",
                    'manage.pro.update.tests'
                )

                self.finish('S')

            elif reqtype == "deletesingletestcase":
                pro_id = int(self.get_argument('pro_id'))
                idx = int(self.get_argument('idx'))

                path = f'problem/{pro_id}/res/testdata'
                if not os.path.exists(f'{path}/{idx}.in') or not os.path.exists(f'{path}/{idx}.out'):
                    self.error('Enoext')
                    return

                await LogService.inst.add_log(
                    f"{self.acct.name} had been send a request to delete a single testcase of the problem #{pro_id}",
                    'manage.pro.update.tests'
                )
                os.remove(f'{path}/{idx}.in')
                os.remove(f'{path}/{idx}.out')

                err, pro = await ProService.inst.get_pro(pro_id, self.acct)
                for test_idx, test_conf in pro['testm_conf'].items():
                    tests = test_conf['metadata']['data']
                    if tests[0] <= idx <= tests[-1]:
                        tests.remove(idx)
                        break

                await ProService.inst.update_testcases(pro_id, pro['testm_conf'])

                self.finish('S')

            elif reqtype == "reorder":
                pro_id = int(self.get_argument('pro_id'))

                err, pro = await ProService.inst.get_pro(pro_id, self.acct)
                if err:
                    self.error(err)
                    return

                await self._reorder_testcases(pro_id, pro['testm_conf'])
                await ProService.inst.update_testcases(pro_id, pro['testm_conf'])
                await LogService.inst.add_log(
                    f"{self.acct.name} had been send a request to reorder all testcases of the problem #{pro_id}",
                    'manage.pro.update.tests'
                )

                self.finish('S')

        elif page == "update":
            if reqtype == 'updatepro':
                pro_id = int(self.get_argument('pro_id'))
                name = self.get_argument('name')
                status = int(self.get_argument('status'))
                pack_type = int(self.get_argument('pack_type'))
                pack_token = self.get_argument('pack_token')
                tags = self.get_argument('tags')
                allow_submit = self.get_argument('allow_submit') == "true"

                if pack_token == '':
                    pack_token = None

                err, _ = await ProService.inst.update_pro(
                    pro_id, name, status, pack_type, pack_token, tags, allow_submit
                )
                await LogService.inst.add_log(
                    f"{self.acct.name} had been send a request to update the problem #{pro_id}", 'manage.pro.update.pro'
                )
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
                    'manage.pro.update.limit',
                )
                if err:
                    self.error(err)
                    return

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

        elif page is None:  # pro-list
            is_all_chal = False
            if reqtype == 'rechal':
                pass

            elif reqtype == 'rechalall':
                pwd = self.get_argument('pwd')
                if config.unlock_pwd != base64.b64encode(packb(pwd)):
                    self.error('Eacces')
                    return
                is_all_chal = True

            else:
                self.error('Eunk')
                return

            pro_id = int(self.get_argument('pro_id'))
            can_submit = JudgeServerClusterService.inst.is_server_online()
            if not can_submit:
                self.error('Ejudge')
                return

            err, pro = await ProService.inst.get_pro(pro_id, self.acct)
            if err:
                self.error(err)
                return

            async with self.db.acquire() as con:
                if is_all_chal:
                    sql = ""
                else:
                    sql = '''AND "challenge_state"."state" IS NULL'''
                result = await con.fetch(
                    f'''
                        SELECT "challenge"."chal_id", "challenge"."compiler_type" FROM "challenge"
                        LEFT JOIN "challenge_state"
                        ON "challenge"."chal_id" = "challenge_state"."chal_id"
                        WHERE "pro_id" = $1 {sql};
                    ''',
                    pro_id,
                )
            await LogService.inst.add_log(
                f"{self.acct.name} made a request to rejudge the problem #{pro_id} with {len(result)} chals",
                'manage.chal.rechal',
            )

            # TODO: send notify to user
            async def _rechal(rechals):
                for chal_id, comp_type in rechals:
                    file_ext = ChalConst.FILE_EXTENSION[comp_type]
                    _, _ = await ChalService.inst.reset_chal(chal_id)
                    _, _ = await ChalService.inst.emit_chal(
                        chal_id,
                        pro_id,
                        pro['testm_conf'],
                        comp_type,
                        ChalConst.NORMAL_REJUDGE_PRI,
                    )

            await asyncio.create_task(_rechal(rechals=result))

            self.finish('S')

    async def _reorder_testcases(self, pro_id, tests):
        path = f'problem/{pro_id}/res/testdata'
        cnt = 1
        for test_conf in tests.values():
            new_tests = []
            for test in test_conf['metadata']['data']:
                new_tests.append(cnt)
                if test != cnt:
                    # order changed

                    shutil.move(f'{path}/{test}.in', f'{path}/{cnt}.in.tmp')
                    shutil.move(f'{path}/{test}.out', f'{path}/{cnt}.out.tmp')

                cnt += 1

            test_conf['metadata']['data'] = new_tests

        for i in range(1, cnt):
            if not os.path.exists(f'{path}/{i}.in.tmp') or not os.path.exists(f'{path}/{i}.out.tmp'):
                # order did not change
                continue

            shutil.move(f'{path}/{i}.in.tmp', f'{path}/{i}.in')
            shutil.move(f'{path}/{i}.out.tmp', f'{path}/{i}.out')
