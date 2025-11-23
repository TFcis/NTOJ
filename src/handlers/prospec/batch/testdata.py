"""
Batch problem type testdata management handler.
"""
import os

import tornado.escape
from dataclasses import asdict

from handlers.base import RequestHandler, reqenv, require_permission
from services.log import LogService
from services.pro import ProService, ProConst, Testdata
from services.user import UserConst
from services.pack import PackService

PERMISSION_DENIED_ERROR = ('Eacces', 'Permission denied')
ALLOW_STATUSES = [ProConst.STATUS_ONLINE, ProConst.STATUS_CONTEST, ProConst.STATUS_HIDDEN]


# TODO: We refactor this as a testdata manager, problem type only need write what files they need to manage
class BatchTestdataHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
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

            await LogService.inst.add_log(
                f'{self.acct.name} download testdata {testdata_id} with {testdata_type} type for problem #{pro_id}',
                'manage.pro.update.testdata.download'
            )

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
            'prospec/batch/manage/updatetestdata',
            page='pro',
            pro_id=pro_id,
            config=pro.config,
        )

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        reqtype = self.get_argument('reqtype')
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

            await LogService.inst.add_log(
                f'{self.acct.name} preview testdata {testdata_id} with {testdata_type} type for problem #{pro_id}',
                'manage.pro.update.testdata.preview'
            )
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

            await ProService.inst.update_pro_config(pro_id, pro.problem_type, pro.config)
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
            await ProService.inst.update_pro_config(pro_id, pro.problem_type, pro.config)

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

            await ProService.inst.update_pro_config(pro_id, pro.problem_type, pro.config)
            await LogService.inst.add_log(
                f'{self.acct.name} has sent a request to delete testdata {testdata_id} for problem #{pro_id}',
                'manage.pro.update.testdata.deletesinglefile',
                {
                    'testdata': asdict(deleted_testdata)
                }
            )

            self.error(('S', ''))

    def _is_file_access_safe(self, basedir, filename):
        absolute_basepath = os.path.abspath(basedir)
        absolute_filepath = os.path.abspath(os.path.join(basedir, filename))
        if os.path.commonpath([absolute_basepath]) != os.path.commonpath([absolute_basepath, absolute_filepath]):
            return False
        if os.path.exists(absolute_filepath):
            return os.path.isfile(absolute_filepath) and not os.path.islink(absolute_filepath)
        return True
