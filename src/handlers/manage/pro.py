import asyncio
import base64
import json
import os

import tornado.web
import tornado.escape
from msgpack import packb, unpackb

import config
from handlers.base import RequestHandler, reqenv, require_permission
from services.chal import ChalConst, ChalService
from services.judge import JudgeServerClusterService
from services.log import LogService
from services.pro import ProService, ProConst
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
            if err:
                self.error(err)
                return

            lock = await self.rs.get(f"{pro['pro_id']}_owner")

            await self.render(
                'manage/pro/update', page='pro', pro=pro, lock=lock
            )

        elif page == "add":
            await self.render('manage/pro/add', page='pro')

        elif page == "filemanager":
            pro_id = int(self.get_argument('proid'))
            err, pro = await ProService.inst.get_pro(pro_id, self.acct)

            testm_conf = pro['testm_conf']
            dirs = []
            if testm_conf['is_makefile']:
                files = list(sorted(filter(lambda name: os.path.isfile(f'problem/{pro_id}/res/make/{name}'), os.listdir(f'problem/{pro_id}/res/make'))))
                dirs.append({
                    'path': 'res/make',
                    'files': files,
                })

            if testm_conf['check_type'] in [ProConst.CHECKER_IOREDIR, ProConst.CHECKER_CMS]:
                files = list(sorted(filter(lambda name: os.path.isfile(f'problem/{pro_id}/res/check/{name}'), os.listdir(f'problem/{pro_id}/res/check'))))
                dirs.append({
                    'path': 'res/check',
                    'files': files,
                })

            files = list(sorted(filter(lambda name: os.path.isfile(f'problem/{pro_id}/http/{name}'), os.listdir(f'problem/{pro_id}/http'))))
            dirs.append({
                'path': 'http',
                'files': files,
            })

            await self.render('manage/pro/filemanager', page='pro', pro_id=pro_id, dirs=dirs)

        elif page == "updatetests":
            pro_id = int(self.get_argument('proid'))

            try:
                download = self.get_argument('download')
            except tornado.web.HTTPError:
                download = None

            if download:
                return NotImplemented
                basepath = f'problem/{pro_id}/res/testdata'
                filepath = f'{basepath}/{download}'
                if not self._is_file_access_safe(basepath, download):
                    # TODO: log illegal action
                    self.error('Eacces')
                    return

                if not os.path.exists(filepath):
                    self.error('Enoext')
                    return

                # TODO: log

                self.set_header('Content-Type', 'application/octet-stream')
                self.set_header('Content-Disposition', f'attachment; filename="{download}"')
                with open(filepath, 'rb') as f:
                    try:
                        while True:
                            buffer = f.read(65536)
                            if buffer:
                                self.write(buffer)
                            else:
                                f.close()
                                self.finish()
                                return
                    except:
                        self.error('Eunk')

                return


            err, pro = await ProService.inst.get_pro(pro_id, self.acct)
            files = sorted(set(map(lambda file: file.replace('.in', '').replace('.out', ''),
                        filter(lambda file: file.endswith('.in') or file.endswith('.out'), os.listdir(f'problem/{pro_id}/res/testdata')))))

            await self.render(
                'manage/pro/updatetests',
                page='pro',
                pro_id=pro_id,
                tests=pro['testm_conf'],
                files=files
            )

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self, page=None):
        reqtype = self.get_argument('reqtype')

        if page == "add" and reqtype == 'addpro':
            name = self.get_argument('name')
            status = int(self.get_argument('status'))
            mode = self.get_argument('mode')

            pack_token = None
            if mode == "upload":
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
                filename = self.get_argument('filename')
                test_type = self.get_argument('type')

                if test_type not in ['out', 'in']:
                    self.error('Eparam')
                    return

                filename += f".{test_type}"
                basepath = f'problem/{pro_id}/res/testdata'
                if not self._is_file_access_safe(basepath, filename):
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to preview file:{filename} of the problem #{pro_id}, but it was suspicious',
                        'manage.pro.update.tests.preview.failed'
                    )
                    self.error('Eacces')
                    return

                filepath = os.path.join(basepath, filename)

                if not os.path.exists(filepath):
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to preview file:{filename} of the problem #{pro_id} but not found',
                        'manage.pro.update.tests.preview.failed'
                    )
                    self.error('Enoext')
                    return

                await LogService.inst.add_log(f'{self.acct.name} preview file:{filename} of the problem #{pro_id}',
                                            'manage.pro.update.tests.preview')
                with open(filepath, 'r') as testcase_f:
                    content = testcase_f.readlines()
                    if len(content) > 25:
                        self.error('Efile')
                        return

                    self.finish(json.dumps(''.join(content)))

            elif reqtype == "updateweight":
                pro_id = int(self.get_argument('pro_id'))
                group = int(self.get_argument('group'))
                weight = int(self.get_argument('weight'))

                err, pro = await ProService.inst.get_pro(pro_id, self.acct)
                test_group = pro['testm_conf']['test_group']

                if group not in test_group:
                    self.error('Enoext')
                    return

                test_group[group]['weight'] = weight
                await ProService.inst.update_test_config(pro_id, pro['testm_conf'])
                await LogService.inst.add_log(
                    f'{self.acct.name} had been send a request to update weight of subtask#{group} of the problem #{pro_id}',
                    'manage.pro.update.tests.updateweight',
                    {
                        'weight': weight,
                    }
                )
                self.finish('S')

            elif reqtype == "addtaskgroup":
                pro_id = int(self.get_argument('pro_id'))
                weight = int(self.get_argument('weight'))

                err, pro = await ProService.inst.get_pro(pro_id, self.acct)
                test_group = pro['testm_conf']['test_group']

                test_group[len(test_group)] = {
                    'weight': weight,
                    'metadata': {'data': []}
                }

                await ProService.inst.update_test_config(pro_id, pro['testm_conf'])
                await LogService.inst.add_log(
                    f'{self.acct.name} had been send a request to add a new subtask of the problem #{pro_id}',
                    'manage.pro.update.tests.addtaskgroup',
                    {
                        'weight': weight,
                        'test_group_idx': len(test_group) - 1
                    }
                )
                self.finish('S')

            elif reqtype == 'deletetaskgroup':
                pro_id = int(self.get_argument('pro_id'))
                group = int(self.get_argument('group'))

                err, pro = await ProService.inst.get_pro(pro_id, self.acct)
                test_group = pro['testm_conf']['test_group']
                if group not in test_group:
                    self.error('Enoext')
                    return

                test_group.pop(group)
                remain_groups = list(test_group.values())
                test_group.clear()

                for group_idx, group in enumerate(remain_groups):
                    test_group[group_idx] = group

                await ProService.inst.update_test_config(pro_id, pro['testm_conf'])
                await LogService.inst.add_log(
                    f'{self.acct.name} had been send a request to delete a subtask of the problem #{pro_id}',
                    'manage.pro.update.tests.deletetaskgroup',
                )
                self.finish('S')

            elif reqtype == 'addsingletestcase':
                pro_id = int(self.get_argument('pro_id'))
                group = int(self.get_argument('group'))
                testcase = self.get_argument('testcase')

                basepath = f'problem/{pro_id}/res/testdata'
                if not os.path.exists(f'{basepath}/{testcase}.in') or not os.path.exists(f'{basepath}/{testcase}.out'):
                    self.error('Enoext')
                    return

                err, pro = await ProService.inst.get_pro(pro_id, self.acct)
                test_group = pro['testm_conf']['test_group']
                if group not in test_group:
                    self.error('Enoext')
                    return

                for t in test_group[group]['metadata']['data']:
                    if testcase == str(t):
                        await LogService.inst.add_log(
                            f'{self.acct.name} tried to add testcase:{testcase} for problem #{pro_id} but already exists',
                            'manage.pro.update.tests.addsingletestcase',
                        )
                        self.error('Eexist')
                        return

                test_group[group]['metadata']['data'].append(testcase)
                await ProService.inst.update_test_config(pro_id, pro['testm_conf'])
                await LogService.inst.add_log(
                    f'{self.acct.name} had been send a request to add a testcase:{testcase} to group#{group} of the problem #{pro_id}',
                    'manage.pro.update.tests.addsingletestcase',
                )
                self.finish('S')

            elif reqtype == 'deletesingletestcase':
                pro_id = int(self.get_argument('pro_id'))
                group = int(self.get_argument('group'))
                testcase = self.get_argument('testcase')

                err, pro = await ProService.inst.get_pro(pro_id, self.acct)
                test_group = pro['testm_conf']['test_group']
                if group not in test_group:
                    self.error('Enoext')
                    return

                try:
                    test_group[group]['metadata']['data'].remove(testcase)
                except ValueError:
                    self.error('Enoext')
                    return

                await ProService.inst.update_test_config(pro_id, pro['testm_conf'])
                await LogService.inst.add_log(
                    f'{self.acct.name} had been send a request to delete a testcase:{testcase} to group#{group} for problem #{pro_id}',
                    'manage.pro.update.tests.deletesingletestcase',
                )
                self.finish('S')

            elif reqtype == 'renamesinglefile':
                pro_id = int(self.get_argument('pro_id'))
                old_filename = self.get_argument('old_filename')
                new_filename = self.get_argument('new_filename')

                # check filename
                basepath = f'problem/{pro_id}/res/testdata'
                old_inputfile_path = f'{basepath}/{old_filename}.in'
                old_outputfile_path = f'{basepath}/{old_filename}.out'
                new_inputfile_path = f'{basepath}/{new_filename}.in'
                new_outputfile_path = f'{basepath}/{new_filename}.out'
                if not self._is_file_access_safe(basepath, f'{old_filename}.in') or not self._is_file_access_safe(basepath, f'{new_filename}.in'):
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to rename {old_filename} to {new_filename} for problem #{pro_id}, but it was suspicious',
                        'manage.pro.update.tests.renamesinglefile.failed'
                    )
                    self.error('Eacces')
                    return

                if not os.path.exists(old_inputfile_path) or not os.path.exists(old_outputfile_path):
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to rename {old_filename} to {new_filename} for problem #{pro_id} but {old_filename} not found',
                        'manage.pro.update.tests.renamesinglefile.failed'
                    )
                    self.error('Enoext')
                    return

                if os.path.exists(new_inputfile_path) or os.path.exists(new_outputfile_path):
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to rename {old_filename} to {new_filename} for problem #{pro_id} but {new_filename} already exists',
                        'manage.pro.update.tests.renamesinglefile.failed'
                    )
                    self.error('Eexist')
                    return

                os.rename(old_inputfile_path, new_inputfile_path)
                os.rename(old_outputfile_path, new_outputfile_path)

                err, pro = await ProService.inst.get_pro(pro_id, self.acct)
                is_modified = False
                for test_group in pro['testm_conf']['test_group'].values():
                    test = test_group['metadata']['data']

                    for i in range(len(test)):
                        if test[i] == old_filename:
                            is_modified = True
                            test[i] = new_filename

                if is_modified:
                    await ProService.inst.update_test_config(pro_id, pro['testm_conf'])
                await LogService.inst.add_log(
                    f'{self.acct.name} had been send a request to rename {old_filename} to {new_filename} for problem #{pro_id}',
                    'manage.pro.update.tests.renamesinglefile',
                )
                self.finish('S')

            elif reqtype == 'updatesinglefile':
                pro_id = int(self.get_argument('pro_id'))
                filename = self.get_argument('filename')
                test_type = self.get_argument('type')
                pack_token = self.get_argument('pack_token')

                if test_type not in ['output', 'input']:
                    PackService.inst.clear(pack_token)
                    self.error('Eparam')
                    return

                basepath = f'problem/{pro_id}/res/testdata'
                filepath = f'{basepath}/{filename}.{test_type[0:-3]}'

                if not self._is_file_access_safe(basepath, f"{filename}.{test_type[0:-3]}"):
                    PackService.inst.clear(pack_token)
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to update {filename} of the problem #{pro_id}, but it was suspicious',
                        'manage.pro.update.tests.updatesinglefile.failed'
                    )
                    self.error('Eacces')
                    return

                if not os.path.exists(filepath):
                    PackService.inst.clear(pack_token)
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to update {filename}.{test_type[0:-3]} for problem #{pro_id} but not found',
                        'manage.pro.update.tests.updatesinglefile.failed'
                    )
                    self.error('Enoext')
                    return

                _ = await PackService.inst.direct_copy(pack_token, filepath)
                await LogService.inst.add_log(
                    f'{self.acct.name} had been send a request to update a single file:{filename} of the problem #{pro_id}',
                    'manage.pro.update.tests.updatesinglefile',
                )

                self.finish('S')

            elif reqtype == "addsinglefile":
                pro_id = int(self.get_argument('pro_id'))
                filename = self.get_argument('filename')
                input_pack_token = self.get_argument('input_pack_token')
                output_pack_token = self.get_argument('output_pack_token')

                basepath = f'problem/{pro_id}/res/testdata'
                inputfile_path = f'{basepath}/{filename}.in'
                outputfile_path = f'{basepath}/{filename}.out'

                if not self._is_file_access_safe(
                    basepath, f'{filename}.in'
                ) or not self._is_file_access_safe(basepath, f'{filename}.out'):
                    PackService.inst.clear(input_pack_token)
                    PackService.inst.clear(output_pack_token)
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to add a single file:{filename} for problem #{pro_id}, but it was suspicious',
                        'manage.pro.update.tests.addsinglefile.failed'
                    )
                    self.error('Eacces')
                    return

                if os.path.exists(inputfile_path) or os.path.exists(outputfile_path):
                    PackService.inst.clear(input_pack_token)
                    PackService.inst.clear(output_pack_token)
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to add single file:{filename} for problem #{pro_id} but {filename} already exists',
                        'manage.pro.update.tests.addsinglefile.failed'
                    )
                    self.error('Eexist')
                    return

                _ = await PackService.inst.direct_copy(input_pack_token, inputfile_path)
                _ = await PackService.inst.direct_copy(output_pack_token, outputfile_path)

                await LogService.inst.add_log(
                    f'{self.acct.name} had been send a request to add a single file:{filename} for problem #{pro_id}',
                    'manage.pro.update.tests.addsinglefile',
                )

                self.finish('S')

            elif reqtype == 'deletesinglefile':
                pro_id = int(self.get_argument('pro_id'))
                filename = self.get_argument('filename')

                basepath = f'problem/{pro_id}/res/testdata'
                if not self._is_file_access_safe(basepath, f'{filename}.in'):
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to delete a single file:{filename} for problem #{pro_id}, but it was suspicious',
                        'manage.pro.update.tests.deletesinglefile.failed'
                    )
                    self.error('Eacces')
                    return

                if not os.path.exists(f'{basepath}/{filename}.in') or not os.path.exists(f'{basepath}/{filename}.out'):
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to delete a single file:{filename} for problem #{pro_id} but not found',
                        'manage.pro.update.tests.deletesinglefile.failed'
                    )
                    self.error('Enoext')
                    return

                os.remove(f'{basepath}/{filename}.in')
                os.remove(f'{basepath}/{filename}.out')

                err, pro = await ProService.inst.get_pro(pro_id, self.acct)
                for test_group in pro['testm_conf']['test_group'].values():
                    test = test_group['metadata']['data']

                    try:
                        test.remove(filename)
                    except ValueError:
                        pass

                await ProService.inst.update_test_config(pro_id, pro['testm_conf'])
                await LogService.inst.add_log(
                                        f'{self.acct.name} had been send a request to delete a single file:{filename} of the problem #{pro_id}',
                    'manage.pro.update.tests.deletesinglefile',
                )

                self.finish('S')

        elif page == "filemanager":
            if reqtype == "preview":
                pro_id = int(self.get_argument('pro_id'))
                filename = self.get_argument('filename')
                basepath = self.get_argument('path')

                if basepath not in ['http', 'res/check', 'res/make']:
                    self.error('Eparam')
                    return

                basepath = f'problem/{pro_id}/{basepath}'
                if not self._is_file_access_safe(basepath, filename):
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to preview {filename} for problem #{pro_id}, but it was suspicious',
                        'manage.pro.update.filemanager.preview.failed'
                    )
                    self.error('Eacces')
                    return

                filepath = os.path.join(basepath, filename)

                if not os.path.exists(filepath):
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to preview {filename} for problem #{pro_id} but not found',
                        'manage.pro.update.filemanager.preview.failed'
                    )
                    self.error('Enoext')
                    return

                await LogService.inst.add_log(f'{self.acct.name} preview {filename} for problem #{pro_id}',
                                              'manage.pro.update.filemanager.preview')
                with open(filepath, 'r') as f:
                    try:
                        content = tornado.escape.xhtml_escape(f.read())
                    except UnicodeDecodeError:
                        self.error('Eunicode')
                        return

                    self.finish(json.dumps(content))

            elif reqtype == 'renamesinglefile':
                pro_id = int(self.get_argument('pro_id'))
                old_filename = self.get_argument('old_filename')
                new_filename = self.get_argument('new_filename')
                basepath = self.get_argument('path')

                if basepath not in ['http', 'res/check', 'res/make']:
                    self.error('Eparam')
                    return

                basepath = f'problem/{pro_id}/{basepath}'
                old_filepath = f'{basepath}/{old_filename}'
                new_filepath = f'{basepath}/{new_filename}'
                if not self._is_file_access_safe(basepath, new_filename):
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to rename {old_filename} to {new_filename} for problem #{pro_id}, but it was suspicious',
                        'manage.pro.update.filemanager.renamesinglefile.failed'
                    )
                    self.error('Eacces')
                    return

                if not os.path.exists(old_filepath):
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to rename {old_filename} to {new_filename} for problem #{pro_id} but {old_filename} not found',
                        'manage.pro.update.filemanager.renamesinglefile.failed'
                    )
                    self.error('Enoext')
                    return

                if os.path.exists(new_filepath):
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to rename {old_filename} to {new_filename} for problem #{pro_id} but {new_filename} already exists',
                        'manage.pro.update.filemanager.renamesinglefile.failed'
                    )
                    self.error('Eexist')
                    return

                os.rename(old_filepath, new_filepath)
                await LogService.inst.add_log(
                    f'{self.acct.name} had been send a request to rename {old_filename} to {new_filename} for problem #{pro_id}',
                    'manage.pro.update.filemanager.renamesinglefile',
                )
                self.finish('S')

            elif reqtype == 'updatesinglefile':
                pro_id = int(self.get_argument('pro_id'))
                filename = self.get_argument('filename')
                pack_token = self.get_argument('pack_token')
                basepath = self.get_argument('path')

                if basepath not in ['http', 'res/check', 'res/make']:
                    self.error('Eparam')
                    return

                basepath = f'problem/{pro_id}/{basepath}'
                filepath = f'{basepath}/{filename}'

                if not self._is_file_access_safe(basepath, filename):
                    PackService.inst.clear(pack_token)
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to update {filename} for problem #{pro_id}, but it was suspicious',
                        'manage.pro.update.filemanager.updatesinglefile.failed'
                    )
                    self.error('Eacces')
                    return

                if not os.path.exists(filepath):
                    PackService.inst.clear(pack_token)
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to update {filename} for problem #{pro_id} but not found',
                        'manage.pro.update.filemanager.updatesinglefile.failed'
                    )
                    self.error('Enoext')
                    return

                _ = await PackService.inst.direct_copy(pack_token, filepath)
                await LogService.inst.add_log(
                    f'{self.acct.name} had been send a request to update {filename} for problem #{pro_id}',
                    'manage.pro.update.filemanager.updatesinglefile',
                )

                self.finish('S')

            elif reqtype == 'addsinglefile':
                pro_id = int(self.get_argument('pro_id'))
                filename = self.get_argument('filename')
                pack_token = self.get_argument('pack_token')
                basepath = self.get_argument('path')

                if basepath not in ['http', 'res/check', 'res/make']:
                    self.error('Eparam')
                    return

                basepath = f'problem/{pro_id}/{basepath}'
                filepath = f'{basepath}/{filename}'

                if not self._is_file_access_safe(basepath, filename):
                    PackService.inst.clear(pack_token)
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to add {filename} for problem #{pro_id}, but it was suspicious',
                        'manage.pro.update.filemanager.addsinglefile.failed'
                    )
                    self.error('Eacces')
                    return

                if os.path.exists(filepath):
                    PackService.inst.clear(pack_token)
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to add {filename} for problem #{pro_id} but {filename} already exists',
                        'manage.pro.update.filemanager.addsinglefile.failed'
                    )
                    self.error('Eexist')
                    return

                _ = await PackService.inst.direct_copy(pack_token, filepath)
                await LogService.inst.add_log(
                    f'{self.acct.name} had been send a request to add {filename} for problem #{pro_id}',
                    'manage.pro.update.filemanager.addsinglefile',
                )

                self.finish('S')

            elif reqtype == 'deletesinglefile':
                pro_id = int(self.get_argument('pro_id'))
                filename = self.get_argument('filename')
                basepath = self.get_argument('path')

                if basepath not in ['http', 'res/check', 'res/make']:
                    self.error('Eparam')
                    return

                basepath = f'problem/{pro_id}/{basepath}'
                filepath = f'{basepath}/{filename}'
                if not self._is_file_access_safe(basepath, filename):
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to delete {filename} for problem #{pro_id}, but it was suspicious',
                        'manage.pro.update.filemanager.addsinglefile.failed'
                    )
                    self.error('Eacces')
                    return

                if not os.path.exists(filepath):
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to delete {filename} for problem #{pro_id} but not found',
                        'manage.pro.update.filemanager.addsinglefile.failed'
                    )
                    self.error('Enoext')
                    return

                os.remove(f'{basepath}/{filename}')

                await LogService.inst.add_log(
                    f'{self.acct.name} had been send a request to delete {filename} for problem #{pro_id}',
                    'manage.pro.update.filemanager.deletesinglefile',
                )

                self.finish('S')

        elif page == "update":
            if reqtype == 'updatepro':
                pro_id = int(self.get_argument('pro_id'))
                name = self.get_argument('name')
                status = int(self.get_argument('status'))
                tags = self.get_argument('tags')
                allow_submit = self.get_argument('allow_submit') == "true"
                is_makefile = self.get_argument('is_makefile') == "true"
                check_type = int(self.get_argument('check_type'))

                chalmeta = ''
                if check_type == ProConst.CHECKER_IOREDIR:
                    chalmeta = self.get_argument('chalmeta')
                    try:
                        chalmeta = json.loads(chalmeta)
                    except json.JSONDecodeError:
                        self.error('Econf')
                        return

                err, _ = await ProService.inst.update_pro(
                    pro_id, name, status, None, None, tags, allow_submit
                )
                err, pro = await ProService.inst.get_pro(pro_id, self.acct)
                old_is_makefile = pro['testm_conf']['is_makefile']
                old_check_type = pro['testm_conf']['check_type']
                custom_check_type = [ProConst.CHECKER_IOREDIR, ProConst.CHECKER_CMS]
                if not old_is_makefile and is_makefile:
                    if not os.path.exists(f'problem/{pro_id}/res/make'):
                        os.mkdir(f'problem/{pro_id}/res/make')
                pro['testm_conf']['is_makefile'] = is_makefile

                if old_check_type not in custom_check_type and check_type in custom_check_type:
                    if not os.path.exists(f'problem/{pro_id}/res/check'):
                        os.mkdir(f'problem/{pro_id}/res/check')
                pro['testm_conf']['check_type'] = check_type

                if check_type == ProConst.CHECKER_IOREDIR:
                    chalmeta = json.dumps(chalmeta)

                await ProService.inst.update_test_config(pro_id, pro['testm_conf'])
                await LogService.inst.add_log(
                    f"{self.acct.name} had been send a request to update the problem #{pro_id}", 'manage.pro.update.pro',
                    {
                        'name': name,
                        'status': status,
                        'tags': tags,
                        'allow_submit': allow_submit,
                        'is_makefile': is_makefile,
                        'chalmeta': chalmeta,
                        'check_type': check_type,
                    }
                )
                if err:
                    self.error(err)
                    return

                self.finish('S')

            elif reqtype == "uploadpackage":
                # TODO: file update need self password verification
                pro_id = int(self.get_argument('pro_id'))
                pack_token = self.get_argument('pack_token')

                err, pro = await ProService.inst.get_pro(pro_id, self.acct)
                err, _ = await ProService.inst.update_pro(
                    pro_id, pro['name'], pro['status'], ProService.PACKTYPE_FULL, pack_token, pro['tags'], pro['allow_submit']
                )

                if err:
                    PackService.inst.clear(pack_token)
                    await LogService.inst.add_log(
                        f"{self.acct.name} tried to update the problem #{pro_id} by uploading problem package but failed",
                        'manage.pro.update.pro.package.failed',
                        {
                            'err': err
                        }
                    )
                    self.error(err)
                    return

                suspicious_files = []
                for file in os.listdir(f"problem/{pro_id}/res/testdata"):
                    if os.path.islink(file):
                        suspicious_files.append((file, os.path.realpath(file)))

                if suspicious_files:
                    await LogService.inst.add_log(f'There are some suspicious files that may have been uploaded by {self.acct.name}', 'manage.pro.update.suspicious', {
                        'suspicious_files': suspicious_files,
                        'uploader': self.acct.acct_id,
                    })

                await LogService.inst.add_log(
                    f"{self.acct.name} had been send a request to update the problem #{pro_id} by uploading problem package",
                    'manage.pro.update.pro.package',
                )

                self.finish('S')

            elif reqtype == 'updatelimit':
                pro_id = int(self.get_argument('pro_id'))
                limits = json.loads(self.get_argument('limits'))

                err, pro = await ProService.inst.get_pro(pro_id, self.acct)

                ALLOW_COMPILERS = ChalConst.ALLOW_COMPILERS
                if pro['testm_conf']['is_makefile']:
                    ALLOW_COMPILERS = ['gcc', 'g++', 'clang', 'clang++', 'default']

                def _check(comp_type, limit):
                    if comp_type not in ALLOW_COMPILERS and comp_type != "default":
                        return False

                    if 'timelimit' not in limit:
                        return False
                    try:
                        int(limit['timelimit'])
                    except ValueError:
                        return False

                    if 'memlimit' not in limit:
                        return False

                    try:
                        int(limit['memlimit'])
                    except ValueError:
                        return False

                    return True

                limits = { comp_type:limit for comp_type, limit in limits.items() if _check(comp_type, limit) }
                if 'default' not in limits:
                    self.error('Eparam')
                    return

                for _, limit in limits.items():
                    limit['timelimit'] = int(limit['timelimit'])
                    limit['memlimit'] = int(limit['memlimit']) * 1024

                    if limit['timelimit'] < 0:
                        limit['timelimit'] = 0

                    if limit['memlimit'] < 0:
                        limit['memlimit'] = 0

                pro['testm_conf']['limit'] = limits
                await ProService.inst.update_test_config(pro_id, pro['testm_conf'])

                await LogService.inst.add_log(
                    f"{self.acct.name} had been send a request to update the problem #{pro_id}",
                    'manage.pro.update.limit',
                    {
                        'limits': limits
                    }
                )

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

    def _is_file_access_safe(self, basedir, filename):
        absolute_basepath = os.path.abspath(basedir)
        absolute_filepath = os.path.abspath(os.path.join(basedir, filename))
        if os.path.commonpath([absolute_basepath]) != os.path.commonpath([absolute_basepath, absolute_filepath]):
            return False
        if os.path.exists(absolute_filepath):
            return os.path.isfile(absolute_filepath) and not os.path.islink(absolute_filepath)
        return True

