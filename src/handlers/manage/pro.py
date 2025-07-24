import asyncio
import base64
import json
import os

import tornado.escape
from msgpack import packb, unpackb
from natsort import natsorted

import config
from handlers.base import RequestHandler, reqenv, require_permission
from services.chal import ChalConst, ChalService
from services.judge import JudgeServerClusterService
from services.log import LogService
from services.pro import ProService, ProConst
from services.user import UserConst
from services.pack import PackService
from utils.numeric import parse_str_to_list

PERMISSION_DENIED_ERROR = ('Eacces', 'Permission denied')
ALLOW_STATUSES = [ProConst.STATUS_ONLINE, ProConst.STATUS_CONTEST, ProConst.STATUS_HIDDEN]

class ManageProHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self, page=None):
        if page is None:
            pageoff = int(self.get_argument('pageoff', default=0))

            err, prolist = await ProService.inst.list_pro(ALLOW_STATUSES)
            pro_total_cnt = len(prolist)
            prolist = prolist[pageoff: pageoff + 40]

            await self.render('manage/pro/pro-list', page='pro', prolist=prolist,
                            pageoff=pageoff, pro_total_cnt=pro_total_cnt)

        elif page == "update":
            pro_id = int(self.get_argument('proid'))

            err, pro = await ProService.inst.get_pro(pro_id, ALLOW_STATUSES)
            if err:
                return self.error(err)

            await self.render(
                'manage/pro/update', page='pro', pro=pro
            )

        elif page == "add":
            await self.render('manage/pro/add', page='pro')

        elif page == "filemanager":
            pro_id = int(self.get_argument('proid'))
            download = self.get_argument('download', default=None)
            if download:
                basepath = self.get_argument('path')
                filename = self.get_argument('filename')
                if basepath not in ['http', 'res/check', 'res/make']:
                    return self.error(('Eparam', 'Invalid basepath'))


                basepath = f'problem/{pro_id}/{basepath}'
                if not self._is_file_access_safe(basepath, filename):
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to download {filename} for problem #{pro_id}, but it was suspicious',
                        'manage.pro.update.filemanager.download.failed'
                    )
                    return self.error(PERMISSION_DENIED_ERROR)

                filepath = os.path.join(basepath, filename)

                if not os.path.exists(filepath):
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to download {filename} for problem #{pro_id} but not found',
                        'manage.pro.update.filemanager.download.failed'
                    )
                    return self.error(('Enoext', 'File not found'))

                await LogService.inst.add_log(f'{self.acct.name} download {filename} for problem #{pro_id}',
                                              'manage.pro.update.filemanager.download')

                self.set_header('Content-Type', 'application/octet-stream')
                self.set_header('Content-Disposition', f'attachment; filename="{filename}"')
                with open(filepath, 'rb') as f:
                    try:
                        while True:
                            buffer = f.read(65536)
                            if buffer:
                                self.write(buffer)
                            else:
                                self.finish()
                                return
                    except:
                        self.error(('Eunk', 'Unknown error'))
                return

            err, pro = await ProService.inst.get_pro(pro_id, ALLOW_STATUSES)
            if err:
                return self.error(err)

            testm_conf = pro['testm_conf']
            dirs = []
            if testm_conf['is_makefile']:
                files = list(natsorted(filter(lambda name: os.path.isfile(f'problem/{pro_id}/res/make/{name}'), os.listdir(f'problem/{pro_id}/res/make'))))
                dirs.append({
                    'path': 'res/make',
                    'files': files,
                })

            if testm_conf['check_type'] in [ProConst.CHECKER_IOREDIR, ProConst.CHECKER_CMS]:
                files = list(natsorted(filter(lambda name: os.path.isfile(f'problem/{pro_id}/res/check/{name}'), os.listdir(f'problem/{pro_id}/res/check'))))
                dirs.append({
                    'path': 'res/check',
                    'files': files,
                })

            files = list(natsorted(filter(lambda name: os.path.isfile(f'problem/{pro_id}/http/{name}'), os.listdir(f'problem/{pro_id}/http'))))
            dirs.append({
                'path': 'http',
                'files': files,
            })

            await self.render('manage/pro/filemanager', page='pro', pro_id=pro_id, dirs=dirs)

        elif page == "updatetests":
            pro_id = int(self.get_argument('proid'))
            err, pro = await ProService.inst.get_pro(pro_id, ALLOW_STATUSES)
            if err:
                return self.error(err)

            await self.render(
                'manage/pro/updatetests',
                page='pro',
                pro_id=pro_id,
                tests=pro['testm_conf'],
            )

        elif page == "updatetestdata":
            pro_id = int(self.get_argument('proid'))
            err, pro = await ProService.inst.get_pro(pro_id, ALLOW_STATUSES)
            if err:
                return self.error(err)

            download = self.get_argument('download', default=None)

            if download:
                testdata_type = self.get_argument('type')
                if testdata_type not in ['input', 'output']:
                    return self.error(('Eparam', 'Invalid testdata file type'))

                testdata_id = int(self.get_argument('testdata_id'))
                if testdata_id not in pro['testm_conf']['testdatas']:
                    self.error(('Enoext', 'Testdata not found'))
                    return

                if testdata_type == "input":
                    file = pro['testm_conf']['testdatas'][testdata_id]['inputfile']
                else:
                    file = pro['testm_conf']['testdatas'][testdata_id]['outputfile']

                basepath = f'problem/{pro_id}/res/testdata'
                filepath = f'{basepath}/{file}'
                if not os.path.exists(filepath):
                    return self.error(('Enoext', 'Testdata file not found'))

                await LogService.inst.add_log(f'{self.acct.name} download testdata {testdata_id} with {testdata_type} type for problem #{pro_id}',
                                            'manage.pro.update.testdata.download')

                self.set_header('Content-Type', 'application/octet-stream')
                self.set_header('Content-Disposition', f'attachment; filename="{file}"')
                with open(filepath, 'rb') as f:
                    try:
                        while True:
                            buffer = f.read(65536)
                            if buffer:
                                self.write(buffer)
                            else:
                                self.finish()
                                return
                    except:
                        self.error(('Eunk', 'Unknown error'))
                return

            await self.render(
                'manage/pro/updatetestdata',
                page='pro',
                pro_id=pro_id,
                tests=pro['testm_conf'],
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

            err, pro_id = await ProService.inst.add_pro(name, status)
            await LogService.inst.add_log(
                f"{self.acct.name} has sent a request to add the problem #{pro_id}", 'manage.pro.add.pro',
                {
                    'acct_id': self.acct.acct_id
                }
            )
            if err:
                return self.error(err)

            if mode == "upload":
                err, _ = await ProService.inst.unpack_pro(pro_id, pack_token)
                if err:
                    return self.error(err)

            self.error(('S', pro_id))

        elif page == "updatetestdata":
            pro_id = int(self.get_argument('pro_id'))
            err, pro = await ProService.inst.get_pro(pro_id, ALLOW_STATUSES)
            if err:
                return self.error(err)

            if reqtype == "preview":
                testdata_id = int(self.get_argument('testdata_id'))
                testdata_type = self.get_argument('type')

                if testdata_id not in pro['testm_conf']['testdatas']:
                    return self.error(('Enoext', 'Testdata not found'))

                if testdata_type not in ['output', 'input']:
                    return self.error(('Eparam', 'Invalid testdata file type'))

                if testdata_type == 'input':
                    filename = pro['testm_conf']['testdatas'][testdata_id]['inputfile']
                else:
                    filename = pro['testm_conf']['testdatas'][testdata_id]['outputfile']

                basepath = f'problem/{pro_id}/res/testdata'
                filepath = os.path.join(basepath, filename)

                if not os.path.exists(filepath):
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to preview file:{filename} for problem #{pro_id} but not found',
                        'manage.pro.update.testdata.preview.failed'
                    )
                    return self.error(('Enoext', 'File not found'))

                await LogService.inst.add_log(f'{self.acct.name} preview testdata {testdata_id} with {testdata_type} type for problem #{pro_id}',
                                            'manage.pro.update.testdata.preview')
                with open(filepath, 'r') as testdata_f:
                    content = testdata_f.readlines()
                    if len(content) > 25:
                        return self.error(('Efile', 'File too large'))

                    self.error(('S', tornado.escape.xhtml_escape(''.join(content))))

            elif reqtype == 'updatesinglefile':
                testdata_id = int(self.get_argument('testdata_id'))
                testdata_type = self.get_argument('type')
                pack_token = self.get_argument('pack_token')

                failed = True
                try:
                    testdatas: dict[int, dict] = pro['testm_conf']['testdatas']
                    if testdata_id not in testdatas:
                        return self.error(('Enoext', 'Testdata not found'))

                    if testdata_type not in ['output', 'input']:
                        return self.error(('Eparam', 'Invalid testdata file type'))

                    if testdata_type == 'input':
                        filename = testdatas[testdata_id]['inputfile']
                    else:
                        filename = testdatas[testdata_id]['outputfile']

                    basepath = f'problem/{pro_id}/res/testdata'
                    filepath = f'{basepath}/{filename}'

                    if not self._is_file_access_safe(basepath, filename):
                        await LogService.inst.add_log(
                            f'{self.acct.name} tried to update testdata {testdata_id} with {testdata_type} type for problem #{pro_id}, but it was suspicious',
                            'manage.pro.update.testdata.updatesinglefile.failed',
                            {
                                'testdata': testdatas[testdata_id]
                            }
                        )
                        return self.error(PERMISSION_DENIED_ERROR)

                    if not os.path.exists(filepath):
                        await LogService.inst.add_log(
                            f'{self.acct.name} tried to update testdata {testdata_id} with {testdata_type} type for problem #{pro_id} but not found',
                            'manage.pro.update.testdata.updatesinglefile.failed',
                            {
                                'testdata': testdatas[testdata_id]
                            }
                        )
                        return self.error(('Enoext', 'Testdata file not found'))
                    failed = False

                finally:
                    # NOTE: Like golang defer
                    if failed:
                        await PackService.inst.clear(pack_token)

                _ = await PackService.inst.direct_copy(pack_token, filepath)

                await ProService.inst.update_test_config(pro_id, pro['testm_conf'])
                await LogService.inst.add_log(
                    f'{self.acct.name} has sent a request to update testdata {testdata_id} with {testdata_type} type for problem #{pro_id}',
                    'manage.pro.update.testdata.updatesinglefile',
                )

                self.error(('S', ''))

            elif reqtype == "addsinglefile":
                filename = self.get_argument('filename')
                input_pack_token = self.get_argument('input_pack_token')
                output_pack_token = self.get_argument('output_pack_token')

                testm_conf = pro['testm_conf']
                testdatas: dict[int, dict] = testm_conf['testdatas']
                try:
                    new_testdata_id = max(testdatas.keys()) + 1
                except ValueError:
                    new_testdata_id = 0


                basepath = f'problem/{pro_id}/res/testdata'
                inputfile_path = f'{basepath}/{filename}.in'
                outputfile_path = f'{basepath}/{filename}.out'

                if not self._is_file_access_safe(
                    basepath, f'{filename}.in'
                ) or not self._is_file_access_safe(basepath, f'{filename}.out'):
                    await PackService.inst.clear(input_pack_token)
                    await PackService.inst.clear(output_pack_token)
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to add a single file:{filename} for problem #{pro_id}, but it was suspicious',
                        'manage.pro.update.testdata.addsinglefile.failed'
                    )
                    return self.error(PERMISSION_DENIED_ERROR)

                if os.path.exists(inputfile_path) or os.path.exists(outputfile_path):
                    await PackService.inst.clear(input_pack_token)
                    await PackService.inst.clear(output_pack_token)
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to add single file:{filename} for problem #{pro_id} but {filename} already exists',
                        'manage.pro.update.testdata.addsinglefile.failed'
                    )
                    return self.error(('Eexist', 'File already exists'))

                _ = await PackService.inst.direct_copy(input_pack_token, inputfile_path)
                _ = await PackService.inst.direct_copy(output_pack_token, outputfile_path)
                testdatas[new_testdata_id] = {
                    'id': new_testdata_id,
                    'inputfile': f'{filename}.in',
                    'outputfile': f'{filename}.out',
                }
                await ProService.inst.update_test_config(pro_id, pro['testm_conf'])

                await LogService.inst.add_log(
                    f'{self.acct.name} has sent a request to add testdata {new_testdata_id} named {filename} for problem #{pro_id}',
                    'manage.pro.update.testdata.addsinglefile',
                )

                self.error(('S', ''))

            elif reqtype == 'deletesinglefile':
                testdata_id = int(self.get_argument('testdata_id'))
                testm_conf = pro['testm_conf']
                testdatas: dict[int, dict] = testm_conf['testdatas']

                if testdata_id not in testdatas:
                    return self.error(('Enoext', 'Testdata not found'))

                inputfile = testdatas[testdata_id]['inputfile']
                outputfile = testdatas[testdata_id]['outputfile']

                basepath = f'problem/{pro_id}/res/testdata'
                if not os.path.exists(f'{basepath}/{inputfile}') or not os.path.exists(f'{basepath}/{outputfile}'):
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to delete testdata {testdata_id} for problem #{pro_id} but not found',
                        'manage.pro.update.testdata.deletesinglefile.failed',
                        {
                            'testdata': testdatas[testdata_id]
                        }
                    )
                    return self.error(('Enoext', 'Testdata file not found'))

                os.remove(f'{basepath}/{inputfile}')
                os.remove(f'{basepath}/{outputfile}')

                for test_group in pro['testm_conf']['test_group'].values():
                    try:
                        test_group['testdatas'].remove(testdata_id)
                    except ValueError:
                        pass
                deleted_testdata = pro['testm_conf']['testdatas'].pop(testdata_id)

                await ProService.inst.update_test_config(pro_id, pro['testm_conf'])
                await LogService.inst.add_log(
                    f'{self.acct.name} has sent a request to delete testdata {testdata_id} for problem #{pro_id}',
                    'manage.pro.update.tests.deletesinglefile',
                    {
                        'testdata': deleted_testdata
                    }
                )

                self.error(('S', ''))

        elif page == "updatetests":
            pro_id = int(self.get_argument('pro_id'))
            err, pro = await ProService.inst.get_pro(pro_id, ALLOW_STATUSES)
            if err:
                return self.error(err)

            if reqtype == "updateweight":
                group = int(self.get_argument('group'))
                weight = int(self.get_argument('weight'))

                test_group = pro['testm_conf']['test_group']

                if group not in test_group:
                    return self.error(('Enoext', 'Group not found'))

                test_group[group]['weight'] = weight
                await ProService.inst.update_test_config(pro_id, pro['testm_conf'])
                await LogService.inst.add_log(
                    f'{self.acct.name} has sent a request to update weight of subtask#{group} for problem #{pro_id}',
                    'manage.pro.update.tests.updateweight',
                    {
                        'weight': weight,
                    }
                )
                self.error(('S', ''))

            elif reqtype == "addtaskgroup":
                weight = int(self.get_argument('weight'))

                test_group = pro['testm_conf']['test_group']

                test_group[len(test_group)] = {
                    'weight': weight,
                    'testdatas': []
                }

                await ProService.inst.update_test_config(pro_id, pro['testm_conf'])
                await LogService.inst.add_log(
                    f'{self.acct.name} has sent a request to add a new subtask for problem #{pro_id}',
                    'manage.pro.update.tests.addtaskgroup',
                    {
                        'weight': weight,
                        'test_group_idx': len(test_group) - 1
                    }
                )
                self.error(('S', ''))

            elif reqtype == 'deletetaskgroup':
                group = int(self.get_argument('group'))

                test_group = pro['testm_conf']['test_group']
                if group not in test_group:
                    return self.error(('Enoext', 'Group not found'))

                test_group.pop(group)
                remain_groups = list(test_group.values())
                test_group.clear()

                for group_idx, group in enumerate(remain_groups):
                    test_group[group_idx] = group

                await ProService.inst.update_test_config(pro_id, pro['testm_conf'])
                await LogService.inst.add_log(
                    f'{self.acct.name} has sent a request to delete a subtask for problem #{pro_id}',
                    'manage.pro.update.tests.deletetaskgroup',
                )
                self.error(('S', ''))

            elif reqtype == 'settestdata':
                group = int(self.get_argument('group'))
                testdatas = parse_str_to_list(self.get_argument('testdatas'))

                test_group = pro['testm_conf']['test_group']
                if group not in test_group:
                    return self.error(('Enoext', 'Group not found'))

                test_group[group]['testdatas'] = []
                for testdata_id in testdatas:
                    if testdata_id not in pro['testm_conf']['testdatas']:
                        continue
                    test_group[group]['testdatas'].append(testdata_id)

                await ProService.inst.update_test_config(pro_id, pro['testm_conf'])
                await LogService.inst.add_log(
                    f'{self.acct.name} has sent a request to set testdatas to group#{group} for problem #{pro_id}',
                    'manage.pro.update.tests.settestdata',
                    {
                        'testdatas': testdatas
                    }
                )
                self.error(('S', ''))

        elif page == "filemanager":
            ALLOW_PATH = ['http', 'res/check', 'res/make']
            pro_id = int(self.get_argument('pro_id'))
            basepath = self.get_argument('path')
            err, pro = await ProService.inst.get_pro(pro_id, ALLOW_STATUSES)
            if err:
                return self.error(err)
            if basepath not in ALLOW_PATH:
                return self.error(('Eparam', 'Invalid basepath'))

            if reqtype == "preview":
                filename = self.get_argument('filename')

                basepath = f'problem/{pro_id}/{basepath}'
                if not self._is_file_access_safe(basepath, filename):
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to preview {filename} for problem #{pro_id}, but it was suspicious',
                        'manage.pro.update.filemanager.preview.failed'
                    )
                    return self.error(PERMISSION_DENIED_ERROR)

                filepath = os.path.join(basepath, filename)

                if not os.path.exists(filepath):
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to preview {filename} for problem #{pro_id} but not found',
                        'manage.pro.update.filemanager.preview.failed'
                    )
                    return self.error(('Enoext', 'File not found'))

                await LogService.inst.add_log(f'{self.acct.name} preview {filename} for problem #{pro_id}',
                                              'manage.pro.update.filemanager.preview')
                with open(filepath, 'r') as f:
                    try:
                        content = tornado.escape.xhtml_escape(f.read())
                    except UnicodeDecodeError:
                        return self.error(('Eunicode', 'That even use like unicode shit that make your programs not compile.'))

                    self.error(('S', ''.join(content)))

            elif reqtype == 'renamesinglefile':
                old_filename = self.get_argument('old_filename')
                new_filename = self.get_argument('new_filename')

                basepath = f'problem/{pro_id}/{basepath}'
                old_filepath = f'{basepath}/{old_filename}'
                new_filepath = f'{basepath}/{new_filename}'
                if not self._is_file_access_safe(basepath, new_filename) or not self._is_file_access_safe(basepath, old_filename):
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to rename {old_filename} to {new_filename} for problem #{pro_id}, but it was suspicious',
                        'manage.pro.update.filemanager.renamesinglefile.failed'
                    )
                    return self.error(PERMISSION_DENIED_ERROR)

                if not os.path.exists(old_filepath):
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to rename {old_filename} to {new_filename} for problem #{pro_id} but {old_filename} not found',
                        'manage.pro.update.filemanager.renamesinglefile.failed'
                    )
                    return self.error(('Enoext', 'Old filename not found'))

                if os.path.exists(new_filepath):
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to rename {old_filename} to {new_filename} for problem #{pro_id} but {new_filename} already exists',
                        'manage.pro.update.filemanager.renamesinglefile.failed'
                    )
                    return self.error(('Eexist', 'New filename already exists'))

                os.rename(old_filepath, new_filepath)
                await LogService.inst.add_log(
                    f'{self.acct.name} has sent a request to rename {old_filename} to {new_filename} for problem #{pro_id}',
                    'manage.pro.update.filemanager.renamesinglefile',
                )
                self.error(('S', ''))

            elif reqtype == 'updatesinglefile':
                filename = self.get_argument('filename')
                pack_token = self.get_argument('pack_token')

                basepath = f'problem/{pro_id}/{basepath}'
                filepath = f'{basepath}/{filename}'

                if not self._is_file_access_safe(basepath, filename):
                    await PackService.inst.clear(pack_token)
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to update {filename} for problem #{pro_id}, but it was suspicious',
                        'manage.pro.update.filemanager.updatesinglefile.failed'
                    )
                    return self.error(PERMISSION_DENIED_ERROR)

                if not os.path.exists(filepath):
                    await PackService.inst.clear(pack_token)
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to update {filename} for problem #{pro_id} but not found',
                        'manage.pro.update.filemanager.updatesinglefile.failed'
                    )
                    return self.error(('Enoext', 'File not found'))

                _ = await PackService.inst.direct_copy(pack_token, filepath)
                await LogService.inst.add_log(
                    f'{self.acct.name} has sent a request to update {filename} for problem #{pro_id}',
                    'manage.pro.update.filemanager.updatesinglefile',
                )

                self.error(('S', ''))

            elif reqtype == 'addsinglefile':
                filename = self.get_argument('filename')
                pack_token = self.get_argument('pack_token')

                basepath = f'problem/{pro_id}/{basepath}'
                filepath = f'{basepath}/{filename}'

                if not self._is_file_access_safe(basepath, filename):
                    await PackService.inst.clear(pack_token)
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to add {filename} for problem #{pro_id}, but it was suspicious',
                        'manage.pro.update.filemanager.addsinglefile.failed'
                    )
                    return self.error(PERMISSION_DENIED_ERROR)

                if os.path.exists(filepath):
                    await PackService.inst.clear(pack_token)
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to add {filename} for problem #{pro_id} but {filename} already exists',
                        'manage.pro.update.filemanager.addsinglefile.failed'
                    )
                    return self.error(('Eexist', 'File already exists'))

                _ = await PackService.inst.direct_copy(pack_token, filepath)
                await LogService.inst.add_log(
                    f'{self.acct.name} has sent a request to add {filename} for problem #{pro_id}',
                    'manage.pro.update.filemanager.addsinglefile',
                )

                self.error(('S', ''))

            elif reqtype == 'deletesinglefile':
                filename = self.get_argument('filename')

                basepath = f'problem/{pro_id}/{basepath}'
                filepath = f'{basepath}/{filename}'
                if not self._is_file_access_safe(basepath, filename):
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to delete {filename} for problem #{pro_id}, but it was suspicious',
                        'manage.pro.update.filemanager.deletesinglefile.failed'
                    )
                    return self.error(PERMISSION_DENIED_ERROR)

                if not os.path.exists(filepath):
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to delete {filename} for problem #{pro_id} but not found',
                        'manage.pro.update.filemanager.deletesinglefile.failed'
                    )
                    return self.error(('Enoext', 'File not found'))

                os.remove(f'{basepath}/{filename}')

                await LogService.inst.add_log(
                    f'{self.acct.name} has sent a request to delete {filename} for problem #{pro_id}',
                    'manage.pro.update.filemanager.deletesinglefile',
                )

                self.error(('S', ''))

        elif page == "update":
            if reqtype == 'updatepro':
                pro_id = int(self.get_argument('pro_id'))
                name = self.get_argument('name')
                status = int(self.get_argument('status'))
                tags = self.get_argument('tags')
                allow_submit = self.get_argument('allow_submit') == "true"
                # NOTE: test config
                rate_precision = int(self.get_argument('rate_precision'))
                if rate_precision > ProConst.RATE_PRECISION_MAX or rate_precision < ProConst.RATE_PRECISION_MIN:
                    return self.error(('Eparam', 'Invalid rate precision'))

                is_makefile = self.get_argument('is_makefile') == "true"
                check_type = int(self.get_argument('check_type'))

                chalmeta = ''
                if check_type == ProConst.CHECKER_IOREDIR:
                    chalmeta = self.get_argument('chalmeta')
                    try:
                        chalmeta = json.loads(chalmeta)
                    except json.JSONDecodeError:
                        return self.error(('Econf', 'Challenge metadata json syntax error'))

                err, _ = await ProService.inst.update_pro(
                    pro_id, name, status, tags, allow_submit
                )
                err, pro = await ProService.inst.get_pro(pro_id, ALLOW_STATUSES)
                if err:
                    return self.error(err)

                conf = pro['testm_conf']
                if (
                    conf['is_makefile'] != is_makefile
                    or conf['check_type'] != check_type
                    or conf['rate_precision'] != rate_precision
                ):
                    old_is_makefile = conf['is_makefile']
                    old_check_type = conf['check_type']
                    custom_check_type = [ProConst.CHECKER_IOREDIR, ProConst.CHECKER_CMS]
                    if not old_is_makefile and is_makefile:
                        if not os.path.exists(f'problem/{pro_id}/res/make'):
                            os.mkdir(f'problem/{pro_id}/res/make')
                    conf['is_makefile'] = is_makefile

                    if old_check_type not in custom_check_type and check_type in custom_check_type:
                        if not os.path.exists(f'problem/{pro_id}/res/check'):
                            os.mkdir(f'problem/{pro_id}/res/check')
                    conf['check_type'] = check_type

                    if check_type == ProConst.CHECKER_IOREDIR:
                        chalmeta = json.dumps(chalmeta)

                    conf['rate_precision'] = rate_precision
                    await ProService.inst.update_test_config(pro_id, conf)
                await LogService.inst.add_log(
                    f"{self.acct.name} has sent a request to update the problem #{pro_id}", 'manage.pro.update.pro',
                    {
                        'name': name,
                        'status': status,
                        'tags': tags,
                        'allow_submit': allow_submit,
                        'is_makefile': is_makefile,
                        'chalmeta': chalmeta,
                        'check_type': check_type,
                        'rate_precision': rate_precision,
                    }
                )
                if err:
                    return self.error(err)

                self.error(('S', ''))

            elif reqtype == "uploadpackage":
                # TODO: file update need self password verification
                pro_id = int(self.get_argument('pro_id'))
                pack_token = self.get_argument('pack_token')

                err, pro = await ProService.inst.get_pro(pro_id, ALLOW_STATUSES)
                if err:
                    return self.error(err)

                err, _ = await ProService.inst.unpack_pro(pro_id, pack_token)
                if err:
                    await PackService.inst.clear(pack_token)
                    await LogService.inst.add_log(
                        f"{self.acct.name} tried to update the problem #{pro_id} by uploading problem package but failed",
                        'manage.pro.update.pro.package.failed',
                        {
                            'err': err
                        }
                    )
                    return self.error(err)

                suspicious_files = []
                for file in os.listdir(f"problem/{pro_id}/res/testdata"):
                    if os.path.islink(file):
                        suspicious_files.append((file, os.path.realpath(file)))

                if suspicious_files:
                    await LogService.inst.add_log(f'There are some suspicious files that may have been uploaded by {self.acct.name}', 'manage.pro.update.pro.package.suspicious', {
                        'suspicious_files': suspicious_files,
                        'uploader': self.acct.acct_id,
                    })

                await LogService.inst.add_log(
                    f"{self.acct.name} has sent a request to update the problem #{pro_id} by uploading problem package",
                    'manage.pro.update.pro.package',
                )

                self.error(('S', ''))

            elif reqtype == 'updatelimit':
                pro_id = int(self.get_argument('pro_id'))
                limits = json.loads(self.get_argument('limits'))

                err, pro = await ProService.inst.get_pro(pro_id, ALLOW_STATUSES)
                if err:
                    return self.error(err)

                ALLOW_COMPILERS = set(list(ChalConst.ALLOW_COMPILERS) + ['default'])
                if pro['testm_conf']['is_makefile']:
                    ALLOW_COMPILERS = {'gcc', 'g++', 'clang', 'clang++', 'default'}

                new_limits = {}
                for comp_type, limit in limits.items():
                    if comp_type not in ALLOW_COMPILERS:
                        continue
                    try:
                        limit['timelimit'] = max(int(limit['timelimit']), 0)
                        limit['memlimit'] = max(int(limit['memlimit']) * 1024, 0)
                    except (ValueError, KeyError):
                        continue

                    new_limits[comp_type] = limit

                if 'default' not in new_limits:
                    return self.error(('Eparam', 'Missing default limit config'))

                pro['testm_conf']['limit'] = new_limits
                await ProService.inst.update_test_config(pro_id, pro['testm_conf'])

                await LogService.inst.add_log(
                    f"{self.acct.name} has sent a request to update the problem #{pro_id}",
                    'manage.pro.update.limit',
                    {
                        'limits': new_limits
                    }
                )

                self.error(('S', ''))

        elif page is None:  # pro-list
            if reqtype not in ['rechal', 'rechalall']:
                return self.error(('Eunk', 'Unknown error'))

            is_all_chal = False
            if reqtype == 'rechalall':
                pwd = self.get_argument('pwd')
                if config.unlock_pwd != base64.b64encode(packb(pwd)):
                    return self.error(('Eacces', 'Wrong password'))
                is_all_chal = True

            pro_id = int(self.get_argument('pro_id'))
            can_submit = JudgeServerClusterService.inst.is_server_online()
            if not can_submit:
                return self.error(('Ejudge', 'No available judge'))

            err, pro = await ProService.inst.get_pro(pro_id, ALLOW_STATUSES)
            if err:
                return self.error(err)

            log_type = ""
            async with self.db.acquire() as con:
                if is_all_chal:
                    sql = ""
                    log_type = "manage.chal.rechalall"
                else:
                    sql = '''AND "challenge_state"."chal_id" IS NULL'''
                    log_type = "manage.chal.rechal"
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
                log_type,
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

            self.error(('S', ''))

    def _is_file_access_safe(self, basedir, filename):
        absolute_basepath = os.path.abspath(basedir)
        absolute_filepath = os.path.abspath(os.path.join(basedir, filename))
        if os.path.commonpath([absolute_basepath]) != os.path.commonpath([absolute_basepath, absolute_filepath]):
            return False
        if os.path.exists(absolute_filepath):
            return os.path.isfile(absolute_filepath) and not os.path.islink(absolute_filepath)
        return True

