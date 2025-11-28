import os

import tornado.escape
from natsort import natsorted

from handlers.base import RequestHandler, reqenv, require_permission
from services.chal import COMPILER_INFOS
from services.log import LogService
from services.pro import ProService, ProConst
from services.user import UserConst
from services.filemanager import FileManager

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

            # Use FileManager for secure file access
            file_mgr = FileManager(f'problem/{pro_id}/{basepath}')

            # Check if file exists and is safe to access
            if not file_mgr.exists(filename):
                await LogService.inst.add_log(
                    f'{self.acct.name} tried to download {filename} for problem #{pro_id} but not found',
                    'manage.pro.update.filemanager.download.failed'
                )
                return self.error(('Enoext', 'File not found'))

            # Get safe filepath
            filepath = file_mgr.get_filepath(filename)
            if filepath is None:
                await LogService.inst.add_log(
                    f'{self.acct.name} tried to download {filename} for problem #{pro_id}, but it was suspicious',
                    'manage.pro.update.filemanager.download.failed'
                )
                return self.error(PERMISSION_DENIED_ERROR)

            await LogService.inst.add_log(f'{self.acct.name} download {filename} for problem #{pro_id}',
                                          'manage.pro.update.filemanager.download')

            self.set_header('Content-Type', 'application/octet-stream')
            self.set_header('Content-Disposition', f'attachment; filename="{filename}"')

            # Stream file in chunks to handle large files
            with open(filepath, 'rb') as f:
                try:
                    while True:
                        buffer = f.read(65536)
                        if buffer:
                            self.write(buffer)
                        else:
                            self.finish()
                            return
                except Exception as e:
                    await LogService.inst.add_log(
                        f'{self.acct.name} download {filename} for problem #{pro_id} failed: {str(e)}',
                        'manage.pro.update.filemanager.download.failed'
                    )
                    return self.error(('Eunk', 'Unknown error'))
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

                grader_file_mgr = FileManager(grader_path)
                files = list(natsorted(grader_file_mgr.listdir(only_files=True)))
                dirs.append({
                    'path': f'res/grader/{grader_name}',
                    'files': files,
                })
                used_grader.add(grader_name)

            grader_base_mgr = FileManager(f"problem/{pro_id}/res/grader")
            files = list(natsorted(grader_base_mgr.listdir(only_files=True)))
            dirs.append({
                'path': 'res/grader',
                'files': files,
            })

        from services.pro import CheckerType
        if batch_config.checker_type in CheckerType.need_build_checkers():
            checker_file_mgr = FileManager(f'problem/{pro_id}/res/checker')
            files = list(natsorted(checker_file_mgr.listdir(only_files=True)))
            dirs.append({
                'path': 'res/checker',
                'files': files,
            })

        http_file_mgr = FileManager(f'problem/{pro_id}/http')
        files = list(natsorted(http_file_mgr.listdir(only_files=True)))
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

        # Create FileManager for the specific path
        file_mgr = FileManager(f'problem/{pro_id}/{basepath}')

        if reqtype == "preview":
            filename = self.get_argument('filename')

            err, content = file_mgr.read(filename, 'r')
            if err:
                await LogService.inst.add_log(
                    f'{self.acct.name} tried to preview {filename} for problem #{pro_id}, failed with {err[0]}',
                    'manage.pro.update.filemanager.preview.failed'
                )
                return self.error(err)

            await LogService.inst.add_log(f'{self.acct.name} preview {filename} for problem #{pro_id}',
                                          'manage.pro.update.filemanager.preview')
            self.error(('S', tornado.escape.xhtml_escape(content)))

        elif reqtype == 'renamesinglefile':
            old_filename = self.get_argument('old_filename')
            new_filename = self.get_argument('new_filename')

            err, _ = file_mgr.rename(old_filename, new_filename)
            if err:
                await LogService.inst.add_log(
                    f'{self.acct.name} tried to rename {old_filename} to {new_filename} for problem #{pro_id}, failed with {err[0]}',
                    'manage.pro.update.filemanager.renamesinglefile.failed'
                )
                return self.error(err)

            await LogService.inst.add_log(
                f'{self.acct.name} has sent a request to rename {old_filename} to {new_filename} for problem #{pro_id}',
                'manage.pro.update.filemanager.renamesinglefile',
            )
            self.error(('S', ''))

        elif reqtype == 'updatesinglefile':
            filename = self.get_argument('filename')
            pack_token = self.get_argument('pack_token')

            err, _ = await file_mgr.update_from_pack(filename, pack_token)
            if err:
                await LogService.inst.add_log(
                    f'{self.acct.name} tried to update {filename} for problem #{pro_id}, failed with {err[0]}',
                    'manage.pro.update.filemanager.updatesinglefile.failed'
                )
                return self.error(err)

            await LogService.inst.add_log(
                f'{self.acct.name} has sent a request to update {filename} for problem #{pro_id}',
                'manage.pro.update.filemanager.updatesinglefile',
            )

            self.error(('S', ''))

        elif reqtype == 'addsinglefile':
            filename = self.get_argument('filename')  # TODO: os.path.basename()
            pack_token = self.get_argument('pack_token')

            err, _ = await file_mgr.copy_from_pack(filename, pack_token)
            if err:
                await LogService.inst.add_log(
                    f'{self.acct.name} tried to add {filename} for problem #{pro_id}, failed with {err[0]}',
                    'manage.pro.update.filemanager.addsinglefile.failed'
                )
                return self.error(err)

            await LogService.inst.add_log(
                f'{self.acct.name} has sent a request to add {filename} for problem #{pro_id}',
                'manage.pro.update.filemanager.addsinglefile',
            )

            self.error(('S', ''))

        elif reqtype == 'deletesinglefile':
            filename = self.get_argument('filename')

            err, _ = file_mgr.delete(filename)
            if err:
                await LogService.inst.add_log(
                    f'{self.acct.name} tried to delete {filename} for problem #{pro_id}, failed with {err[0]}',
                    'manage.pro.update.filemanager.deletesinglefile.failed'
                )
                return self.error(err)

            await LogService.inst.add_log(
                f'{self.acct.name} has sent a request to delete {filename} for problem #{pro_id}',
                'manage.pro.update.filemanager.deletesinglefile',
            )

            self.error(('S', ''))
