import os

import tornado.escape
from natsort import natsorted

from handlers.base import RequestHandler, reqenv, require_permission
from services.chal import COMPILER_INFOS
from services.log import LogService
from services.pro import ProService, ProConst
from services.user import UserConst
from services.pack import PackService

PERMISSION_DENIED_ERROR = ('Eacces', 'Permission denied')
ALLOW_STATUSES = [ProConst.STATUS_ONLINE, ProConst.STATUS_CONTEST, ProConst.STATUS_HIDDEN]


# TODO: res/checker and res/grader is batch specific
# TODO: We should refactor this as a common filemanger, problem type only need specific what folder path is used
class ManageProFilemanagerHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
        pro_id = int(self.get_argument('proid'))
        err, pro = await ProService.inst.get_pro(pro_id, ALLOW_STATUSES)
        if err:
            return self.error(err)

        download = self.get_argument('download', default=None)
        if download:
            basepath = self.get_argument('path')
            filename = self.get_argument('filename')
            ALLOW_PATH = ['http', 'res/checker', 'res/grader']
            # TODO: Support different problem types
            from services.prospec.batch import BatchConfig
            assert isinstance(pro.config.spec_config, BatchConfig)
            batch_config = pro.config.spec_config
            if batch_config.has_grader:
                used_grader = set()
                for compiler in batch_config.allow_compilers:
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
        # TODO: Support different problem types
        from services.prospec.batch import BatchConfig
        assert isinstance(config.spec_config, BatchConfig)
        batch_config = config.spec_config
        dirs = []
        if batch_config.has_grader:
            used_grader = set()

            for compiler in batch_config.allow_compilers:
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

        from services.pro import CheckerType
        if batch_config.checker_type in CheckerType.need_build_checkers():
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

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        reqtype = self.get_argument('reqtype')
        pro_id = int(self.get_argument('pro_id'))
        basepath = self.get_argument('path')
        err, pro = await ProService.inst.get_pro(pro_id, ALLOW_STATUSES)
        if err:
            return self.error(err)
        ALLOW_PATH = ['http', 'res/checker', 'res/grader']
        # TODO: Support different problem types
        from services.prospec.batch import BatchConfig
        assert isinstance(pro.config.spec_config, BatchConfig)
        batch_config = pro.config.spec_config
        if batch_config.has_grader:
            used_grader = set()
            for compiler in batch_config.allow_compilers:
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
            filename = self.get_argument('filename')  # TODO: os.path.basename()
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

    def _is_file_access_safe(self, basedir, filename):
        absolute_basepath = os.path.abspath(basedir)
        absolute_filepath = os.path.abspath(os.path.join(basedir, filename))
        if os.path.commonpath([absolute_basepath]) != os.path.commonpath([absolute_basepath, absolute_filepath]):
            return False
        if os.path.exists(absolute_filepath):
            return os.path.isfile(absolute_filepath) and not os.path.islink(absolute_filepath)
        return True
