import asyncio
import base64
from dataclasses import asdict
import json
import os
from collections import defaultdict

import tornado.escape
from msgpack import packb
from natsort import natsorted

import config
from handlers.base import RequestHandler, reqenv, require_permission
from services.chal import ChalConst, ChalService, Compiler, COMPILER_INFOS
from services.judge import JudgeServerClusterService
from services.log import LogService
from services.pro import Limit, ProService, ProConst, SubtaskConfig, Testdata, CheckerType, SummaryType
from services.user import UserConst
from services.pack import PackService
from utils.numeric import parse_str_to_list

# TODO: Remove unnecessary security check

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
            err, pro = await ProService.inst.get_pro(pro_id, ALLOW_STATUSES)
            if err:
                return self.error(err)

            download = self.get_argument('download', default=None)
            if download:
                basepath = self.get_argument('path')
                filename = self.get_argument('filename')
                ALLOW_PATH = ['http', 'res/checker', 'res/grader']
                if pro.config.has_grader:
                    used_grader = set()
                    for compiler in pro.config.allow_compilers:
                        grader_name = COMPILER_INFOS[compiler].grader_name
                        if grader_name in used_grader:
                            continue
                        grader_path = os.path.join("problem", str(pro_id), "res", "grader", grader_name)
                        if not os.path.exists(grader_path):
                            continue
                        ALLOW_PATH.append(f'res/grader/{grader_name}')
                        used_grader.add(grader_name)
                if basepath not in ALLOW_PATH:
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


            config = pro.config
            dirs = []
            if config.has_grader:
                used_grader = set()

                for compiler in pro.config.allow_compilers:
                    grader_name = COMPILER_INFOS[compiler].grader_name
                    if grader_name in used_grader:
                        continue

                    grader_path = os.path.join("problem", str(pro_id), "res", "grader", grader_name)
                    if not os.path.exists(grader_path):
                        continue

                    files = list(natsorted(filter(lambda name: os.path.isfile(os.path.join(grader_path, name)), os.listdir(grader_path))))
                    dirs.append({
                        'path': f'res/grader/{grader_name}',
                        'files': files,
                    })
                    used_grader.add(grader_name)

                files = list(natsorted(filter(lambda name: os.path.isfile(f"problem/{pro_id}/res/grader/{name}"), os.listdir(f"problem/{pro_id}/res/grader"))))
                dirs.append({
                    'path': 'res/grader',
                    'files': files,
                })

            if config.checker_type in CheckerType.need_build_checkers():
                files = list(natsorted(filter(lambda name: os.path.isfile(f'problem/{pro_id}/res/checker/{name}'), os.listdir(f'problem/{pro_id}/res/checker'))))
                dirs.append({
                    'path': 'res/checker',
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
                config=pro.config,
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
                if testdata_id not in pro.config.testdatas:
                    self.error(('Enoext', 'Testdata not found'))
                    return

                if testdata_type == "input":
                    file = pro.config.testdatas[testdata_id].inputfile
                else:
                    file = pro.config.testdatas[testdata_id].outputfile

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
                config=pro.config,
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

                if testdata_id not in pro.config.testdatas:
                    return self.error(('Enoext', 'Testdata not found'))

                if testdata_type not in ['output', 'input']:
                    return self.error(('Eparam', 'Invalid testdata file type'))

                if testdata_type == "input":
                    filename = pro.config.testdatas[testdata_id].inputfile
                else:
                    filename = pro.config.testdatas[testdata_id].outputfile

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
                    testdatas = pro.config.testdatas
                    if testdata_id not in testdatas:
                        return self.error(('Enoext', 'Testdata not found'))

                    if testdata_type not in ['output', 'input']:
                        return self.error(('Eparam', 'Invalid testdata file type'))

                    if testdata_type == 'input':
                        filename = testdatas[testdata_id].inputfile
                    else:
                        filename = testdatas[testdata_id].outputfile

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

                await ProService.inst.update_pro_config(pro_id, pro.config)
                await LogService.inst.add_log(
                    f'{self.acct.name} has sent a request to update testdata {testdata_id} with {testdata_type} type for problem #{pro_id}',
                    'manage.pro.update.testdata.updatesinglefile',
                )

                self.error(('S', ''))

            elif reqtype == "addsinglefile":
                filename = self.get_argument('filename')
                input_pack_token = self.get_argument('input_pack_token')
                output_pack_token = self.get_argument('output_pack_token')

                testdatas = pro.config.testdatas
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
                testdatas[new_testdata_id] = Testdata(new_testdata_id, f'{filename}.in', f'{filename}.out')
                await ProService.inst.update_pro_config(pro_id, pro.config)

                await LogService.inst.add_log(
                    f'{self.acct.name} has sent a request to add testdata {new_testdata_id} named {filename} for problem #{pro_id}',
                    'manage.pro.update.testdata.addsinglefile',
                )

                self.error(('S', ''))

            elif reqtype == 'deletesinglefile':
                testdata_id = int(self.get_argument('testdata_id'))
                testdatas: dict[int, dict] = pro.config.testdatas

                if testdata_id not in testdatas:
                    return self.error(('Enoext', 'Testdata not found'))

                inputfile = testdatas[testdata_id].inputfile
                outputfile = testdatas[testdata_id].outputfile

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

                for subtask_config in pro.config.subtask_configs.values():
                    try:
                        subtask_config.testdatas.remove(pro.config.testdatas[testdata_id])
                    except ValueError:
                        continue

                deleted_testdata = pro.config.testdatas.pop(testdata_id)

                await ProService.inst.update_pro_config(pro_id, pro.config)
                await LogService.inst.add_log(
                    f'{self.acct.name} has sent a request to delete testdata {testdata_id} for problem #{pro_id}',
                    'manage.pro.update.tests.deletesinglefile',
                    {
                        'testdata': asdict(deleted_testdata)
                    }
                )

                self.error(('S', ''))

        elif page == "updatetests":
            pro_id = int(self.get_argument('pro_id'))
            err, pro = await ProService.inst.get_pro(pro_id, ALLOW_STATUSES)
            if err:
                return self.error(err)

            if reqtype == "updaterate":
                subtask_id = int(self.get_argument('subtask'))
                rate = int(self.get_argument('rate'))

                subtask_configs = pro.config.subtask_configs
                if subtask_id not in subtask_configs:
                    return self.error(('Enoext', 'Subtask not found'))

                subtask_configs[subtask_id].rate = rate
                await ProService.inst.update_pro_config(pro_id, pro.config)
                await LogService.inst.add_log(
                    f'{self.acct.name} has sent a request to update rate of subtask#{subtask_id} for problem #{pro_id}',
                    'manage.pro.update.tests.updaterate',
                    {
                        'rate': rate,
                    }
                )
                self.error(('S', ''))

            elif reqtype == "setdepsubtasks":
                subtask_id = int(self.get_argument('subtask'))
                dep_subtasks = set(map(lambda x: x - 1, parse_str_to_list(self.get_argument('dep_subtasks'))))

                subtask_configs = pro.config.subtask_configs
                if subtask_id not in subtask_configs:
                    return self.error(('Enoext', 'Subtask not found'))

                subtask_configs[subtask_id].dependency_subtasks = set(dep_subtasks)

                if self.have_cycle(subtask_configs):
                    return self.error(('Eparam', 'Dependency subtasks have cycle'))

                await ProService.inst.update_pro_config(pro_id, pro.config)
                await LogService.inst.add_log(
                    f'{self.acct.name} has sent a request to set dependency subtasks to subtask#{subtask_id} for problem #{pro_id}',
                    'manage.pro.update.tests.setdepsubtasks',
                    {
                        'dependency_subtasks': list(dep_subtasks)
                    }
                )
                self.error(('S', ''))

            elif reqtype == "addsubtask":
                rate = int(self.get_argument('rate'))

                subtask_configs = pro.config.subtask_configs
                subtask_configs[len(subtask_configs)] = SubtaskConfig(len(subtask_configs), [], set(), rate)

                await ProService.inst.update_pro_config(pro_id, pro.config)
                await LogService.inst.add_log(
                    f'{self.acct.name} has sent a request to add a new subtask for problem #{pro_id}',
                    'manage.pro.update.tests.addsubtask',
                    {
                        'rate': rate,
                        'subtask_id': len(subtask_configs) - 1
                    }
                )
                self.error(('S', ''))

            elif reqtype == 'deletesubtask':
                subtask_id = int(self.get_argument('subtask'))

                subtask_configs = pro.config.subtask_configs
                if subtask_id not in subtask_configs:
                    return self.error(('Enoext', 'Subtask not found'))

                subtask_configs.pop(subtask_id)
                remain_subtasks = list(subtask_configs.values())
                subtask_configs.clear()

                for new_subtask_id, subtask in enumerate(remain_subtasks):
                    subtask_configs[new_subtask_id] = subtask

                await ProService.inst.update_pro_config(pro_id, pro.config)
                await LogService.inst.add_log(
                    f'{self.acct.name} has sent a request to delete a subtask for problem #{pro_id}',
                    'manage.pro.update.tests.deletesubtask',
                )
                self.error(('S', ''))

            elif reqtype == 'settestdata':
                subtask_id = int(self.get_argument('subtask'))
                testdatas = parse_str_to_list(self.get_argument('testdatas'))

                subtask_configs = pro.config.subtask_configs
                if subtask_id not in subtask_configs:
                    return self.error(('Enoext', 'Subtask not found'))

                subtask_configs[subtask_id].testdatas.clear()
                for testdata_id in testdatas:
                    if testdata_id not in pro.config.testdatas:
                        continue

                    subtask_configs[subtask_id].testdatas.append(pro.config.testdatas[testdata_id])

                await ProService.inst.update_pro_config(pro_id, pro.config)
                await LogService.inst.add_log(
                    f'{self.acct.name} has sent a request to set testdatas to subtask#{subtask_id} for problem #{pro_id}',
                    'manage.pro.update.tests.settestdata',
                    {
                        'testdatas': [testdata.testdata_id for testdata in subtask_configs[subtask_id].testdatas]
                    }
                )
                self.error(('S', ''))

        elif page == "filemanager":
            pro_id = int(self.get_argument('pro_id'))
            basepath = self.get_argument('path')
            err, pro = await ProService.inst.get_pro(pro_id, ALLOW_STATUSES)
            if err:
                return self.error(err)
            ALLOW_PATH = ['http', 'res/checker', 'res/grader']
            if pro.config.has_grader:
                used_grader = set()
                for compiler in pro.config.allow_compilers:
                    grader_name = COMPILER_INFOS[compiler].grader_name
                    if grader_name in used_grader:
                        continue
                    ALLOW_PATH.append(f'res/grader/{grader_name}')
                    used_grader.add(grader_name)

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
                filename = self.get_argument('filename') # TODO: os.path.basename()
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
            if reqtype == 'updategeneral':
                pro_id = int(self.get_argument('pro_id'))
                name = self.get_argument('name')
                status = int(self.get_argument('status'))
                tags = self.get_argument('tags')
                allow_submit = self.get_argument('allow_submit') == "true"

                err, pro = await ProService.inst.get_pro(pro_id, ALLOW_STATUSES)
                if err:
                    return self.error(err)
                assert pro
                pro.name = name
                pro.status = status
                pro.tags = tags
                pro.allow_submit = allow_submit
                err, _ = await ProService.inst.update_pro(pro)

                await LogService.inst.add_log(
                    f"{self.acct.name} has sent a request to update the problem #{pro_id}", 'manage.pro.update.general',
                    {
                        'name': name,
                        'status': status,
                        'tags': tags,
                        'allow_submit': allow_submit,
                    }
                )
                if err:
                    return self.error(err)

                self.error(('S', ''))

            elif reqtype == "updatejudge":
                # TODO: Exception handle
                pro_id = int(self.get_argument('pro_id'))
                rate_precision = int(self.get_argument('rate_precision'))
                if rate_precision > ProConst.RATE_PRECISION_MAX or rate_precision < ProConst.RATE_PRECISION_MIN:
                    return self.error(('Eparam', 'Invalid rate precision'))

                has_grader = self.get_argument('has_grader') == "true"
                userprog_compile_args = self.get_argument('userprog_compile_args')
                checker_type = int(self.get_argument('checker_type'))
                checker_compiler = self.get_argument('checker_compiler')
                if checker_compiler:
                    checker_compiler = Compiler(int(checker_compiler))
                else:
                    checker_compiler = None
                checker_compile_args = self.get_argument('checker_compile_args')
                summary_type = SummaryType(int(self.get_argument('summary_type')))
                summary_compiler = self.get_argument('summary_compiler')
                if summary_compiler:
                    summary_compiler = Compiler(int(summary_compiler))
                else:
                    summary_compiler = None
                summary_compile_args = self.get_argument('summary_compile_args')
                allow_compilers = self.get_arguments("allow_compilers[]")
                allow_compilers = set(map(lambda x: Compiler(int(x)),
                                          filter(lambda compiler: int(compiler) in Compiler._value2member_map_, allow_compilers)))

                chalmeta = ''
                if checker_type == CheckerType.IOREDIR:
                    chalmeta = self.get_argument('chalmeta')
                    try:
                        json.loads(chalmeta)
                    except json.JSONDecodeError:
                        return self.error(('Econf', 'Challenge metadata json syntax error'))

                err, pro = await ProService.inst.get_pro(pro_id, ALLOW_STATUSES)
                if err:
                    return self.error(err)
                assert pro

                config = pro.config
                assert config
                if has_grader:
                    grader_path = os.path.join("problem", str(pro_id), "res", "grader")
                    if not os.path.exists(grader_path):
                        os.mkdir(grader_path)

                    used_grader = set()
                    for compiler in pro.config.allow_compilers:
                        grader_name = COMPILER_INFOS[compiler].grader_name
                        if grader_name in used_grader:
                            continue
                        grader_compiler_path = os.path.join(grader_path, grader_name)
                        if not os.path.exists(grader_compiler_path):
                            os.mkdir(grader_compiler_path)
                        used_grader.add(grader_name)
                config.has_grader = has_grader

                config.userprog_compile_args = userprog_compile_args
                need_build_checkers = CheckerType.need_build_checkers()
                if checker_type in need_build_checkers:
                    if not os.path.exists(f'problem/{pro_id}/res/checker'):
                        os.mkdir(f'problem/{pro_id}/res/checker')
                config.checker_type = CheckerType(checker_type)
                config.checker_compiler = checker_compiler
                config.checker_compile_args = checker_compile_args

                if summary_type == SummaryType.CUSTOM:
                    if not os.path.exists(f'problem/{pro_id}/res/summary'):
                        os.mkdir(f'problem/{pro_id}/res/summary')
                config.summary_type = summary_type
                config.summary_compiler = summary_compiler
                config.summary_compile_args = summary_compile_args
                config.allow_compilers = allow_compilers

                if checker_type == CheckerType.IOREDIR:
                    config.chalmeta = chalmeta
                config.rate_precision = rate_precision
                await ProService.inst.update_pro_config(pro_id, config)
                await LogService.inst.add_log(
                    f"{self.acct.name} has sent a request to update the problem #{pro_id} judge config", 'manage.pro.update.judge',
                    {
                        # TODO: add missing parameter
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
                assert pro

                ALLOW_COMPILERS = pro.config.allow_compilers.copy()
                ALLOW_COMPILERS.add('default')

                new_limits: dict[str, Limit] = {}
                for compiler_type, limit in limits.items():
                    if compiler_type != "default":
                        compiler_type = Compiler(int(compiler_type))
                    if compiler_type not in ALLOW_COMPILERS:
                        continue
                    new_limits[compiler_type] = Limit(0, 0, 0)
                    try:
                        new_limits[compiler_type].time = max(int(limit['time']), 0)
                        new_limits[compiler_type].memory = max(int(limit['memory']), 0)
                        new_limits[compiler_type].output = max(int(limit['output']), 0)
                    except (ValueError, KeyError):
                        new_limits.pop(compiler_type)
                        continue

                if 'default' not in new_limits:
                    return self.error(('Eparam', 'Missing default limit config'))

                pro.config.limits = new_limits
                await ProService.inst.update_pro_config(pro_id, pro.config)

                await LogService.inst.add_log(
                    f"{self.acct.name} has sent a request to update the problem #{pro_id} limit config",
                    'manage.pro.update.limit',
                    {
                        'limits': {
                            comp: asdict(limit)
                            for comp, limit in pro.config.limits.items()
                        }
                    }
                )

                self.error(('S', ''))

        elif page is None:  # pro-list
            if reqtype not in ['rechal', 'rechalall']:
                return self.error(('Eunk', 'Unknown error'))

            is_all_chal = False
            if reqtype == 'rechalall':
                pwd = self.get_argument('pwd')
                import config
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
                    sql = f'AND "total_result"."state" = {ChalConst.STATE_NOTSTARTED}'
                    log_type = "manage.chal.rechal"
                result = await con.fetch(
                    f'''
                        SELECT "challenge"."chal_id", "challenge"."compiler_type" FROM "challenge"
                        INNER JOIN "total_result"
                        ON "challenge"."chal_id" = "total_result"."chal_id"
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
                _, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
                for chal_id, compiler_type in rechals:
                    _, _ = await ChalService.inst.reset_chal(chal_id)
                    _, _ = await ChalService.inst.emit_chal(chal_id, pro.config, compiler_type, ChalConst.NORMAL_REJUDGE_PRI, skip_nonac=False)

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

    def have_cycle(self, subtask_configs: dict[int, SubtaskConfig]) -> bool:
        vis = defaultdict(int)
        graph = defaultdict(list)

        for u, sconfig in subtask_configs.items():
            for v in sconfig.dependency_subtasks:
                graph[u].append(v)

        def dfs(u) -> bool:
            nonlocal vis
            vis[u] = 1
            for v in graph[u]:
                if vis[v] == 1:
                    return False
                elif vis[v] == 0:
                    if not dfs(v):
                        return False
            vis[u] = 2
            return True

        for u in subtask_configs.keys():
            if vis[u] == 0:
                if not dfs(u):
                    return True

        return False
