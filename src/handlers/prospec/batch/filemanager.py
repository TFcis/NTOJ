from handlers.base import RequestHandler, reqenv, require_permission, ActionDispatcher
from services.log import LogService
from services.pro import ProService, ProConst
from services.user import UserConst
from services.filemanager import FileManager
from services.prospec.batch import BatchConfig, batch_spec

PERMISSION_DENIED_ERROR = ('Eacces', 'Permission denied')

batch_filemanager_dispatcher = ActionDispatcher()


class BatchFilemanagerHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
        try:
            pro_id = int(self.get_argument("proid"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem ID"))

        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        download = self.get_argument('download', default=None)
        if download:
            return await self._handle_download(pro_id, pro)

        return await self._handle_list_files(pro_id, pro)

    async def _handle_download(self, pro_id, pro):
        basepath = self.get_argument('path')
        filename = self.get_argument('filename')

        assert isinstance(pro.config.spec_config, BatchConfig)
        batch_config = pro.config.spec_config

        # Use ProSpec to get allowed paths
        allowed_paths = batch_spec.get_allowed_file_paths(batch_config, pro_id)

        if basepath not in allowed_paths:
            return self.error(('Eparam', 'Invalid basepath'))

        # Use FileManager for secure file access
        file_mgr = FileManager(f'problem/{pro_id}/{basepath}')

        # Check if file exists and is safe to access
        if not file_mgr.exists(filename):
            await self.add_log(
                f'{self.acct.name} tried to download {filename} for problem #{pro_id} but not found',
                'manage.pro.update.filemanager.download.failed'
            )
            return self.error(('Enoext', 'File not found'))

        # Get safe filepath
        filepath = file_mgr.get_filepath(filename)
        if filepath is None:
            await self.add_log(
                f'{self.acct.name} tried to download {filename} for problem #{pro_id}, but it was suspicious',
                'manage.pro.update.filemanager.download.failed'
            )
            return self.error(PERMISSION_DENIED_ERROR)

        await self.add_log(f'{self.acct.name} download {filename} for problem #{pro_id}',
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
                await self.add_log(
                    f'{self.acct.name} download {filename} for problem #{pro_id} failed: {str(e)}',
                    'manage.pro.update.filemanager.download.failed'
                )
                return self.error(('Eunk', 'Unknown error'))

    async def _handle_list_files(self, pro_id, pro):
        config = pro.config
        assert isinstance(config.spec_config, BatchConfig)
        batch_config = config.spec_config

        # Use ProSpec to get file structure
        dirs = batch_spec.get_file_structure(batch_config, pro_id)

        await self.render('manage/pro/filemanager', 'Update Problem File', page='pro', pro_id=pro_id, dirs=dirs)

    @batch_filemanager_dispatcher.action('preview')
    async def preview_action(self):
        try:
            pro_id = int(self.get_argument("pro_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem ID"))

        basepath = self.get_argument('path')
        filename = self.get_argument('filename')

        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        assert isinstance(pro.config.spec_config, BatchConfig)
        batch_config = pro.config.spec_config

        # Use ProSpec to get allowed paths
        allowed_paths = batch_spec.get_allowed_file_paths(batch_config, pro_id)

        if basepath not in allowed_paths:
            return self.error(('Eparam', 'Invalid basepath'))

        # Create FileManager for the specific path
        file_mgr = FileManager(f'problem/{pro_id}/{basepath}')

        err, content = file_mgr.read(filename, 'r')
        if err:
            await self.add_log(
                f'{self.acct.name} tried to preview {filename} for problem #{pro_id}, failed with {err[0]}',
                'manage.pro.update.filemanager.preview.failed'
            )
            return self.error(err)

        await self.add_log(f'{self.acct.name} preview {filename} for problem #{pro_id}',
                                      'manage.pro.update.filemanager.preview')
        return self.error(('S', content))

    @batch_filemanager_dispatcher.action('renamesinglefile')
    async def rename_single_file_action(self):
        try:
            pro_id = int(self.get_argument("pro_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem ID"))

        basepath = self.get_argument('path')
        old_filename = self.get_argument('old_filename')
        new_filename = self.get_argument('new_filename')

        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        assert isinstance(pro.config.spec_config, BatchConfig)
        batch_config = pro.config.spec_config

        allowed_paths = batch_spec.get_allowed_file_paths(batch_config, pro_id)

        if basepath not in allowed_paths:
            return self.error(('Eparam', 'Invalid basepath'))

        file_mgr = FileManager(f'problem/{pro_id}/{basepath}')

        err, _ = file_mgr.rename(old_filename, new_filename)
        if err:
            await self.add_log(
                f'{self.acct.name} tried to rename {old_filename} to {new_filename} for problem #{pro_id}, failed with {err[0]}',
                'manage.pro.update.filemanager.renamesinglefile.failed'
            )
            return self.error(err)

        await self.add_log(
            f'{self.acct.name} has sent a request to rename {old_filename} to {new_filename} for problem #{pro_id}',
            'manage.pro.update.filemanager.renamesinglefile',
        )
        return self.error(('S', ''))

    @batch_filemanager_dispatcher.action('updatesinglefile')
    async def update_single_file_action(self):
        try:
            pro_id = int(self.get_argument("pro_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem ID"))

        basepath = self.get_argument('path')
        filename = self.get_argument('filename')
        pack_token = self.get_argument('pack_token')

        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        assert isinstance(pro.config.spec_config, BatchConfig)
        batch_config = pro.config.spec_config

        allowed_paths = batch_spec.get_allowed_file_paths(batch_config, pro_id)

        if basepath not in allowed_paths:
            return self.error(('Eparam', 'Invalid basepath'))

        file_mgr = FileManager(f'problem/{pro_id}/{basepath}')

        err, _ = await file_mgr.update_from_pack(filename, pack_token)
        if err:
            await self.add_log(
                f'{self.acct.name} tried to update {filename} for problem #{pro_id}, failed with {err[0]}',
                'manage.pro.update.filemanager.updatesinglefile.failed'
            )
            return self.error(err)

        await self.add_log(
            f'{self.acct.name} has sent a request to update {filename} for problem #{pro_id}',
            'manage.pro.update.filemanager.updatesinglefile',
        )

        return self.error(('S', ''))

    @batch_filemanager_dispatcher.action('addsinglefile')
    async def add_single_file_action(self):
        try:
            pro_id = int(self.get_argument("pro_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem ID"))

        basepath = self.get_argument('path')
        filename = self.get_argument('filename')  # TODO: os.path.basename()
        pack_token = self.get_argument('pack_token')

        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        assert isinstance(pro.config.spec_config, BatchConfig)
        batch_config = pro.config.spec_config

        allowed_paths = batch_spec.get_allowed_file_paths(batch_config, pro_id)

        if basepath not in allowed_paths:
            return self.error(('Eparam', 'Invalid basepath'))

        file_mgr = FileManager(f'problem/{pro_id}/{basepath}')

        err, _ = await file_mgr.copy_from_pack(filename, pack_token)
        if err:
            await self.add_log(
                f'{self.acct.name} tried to add {filename} for problem #{pro_id}, failed with {err[0]}',
                'manage.pro.update.filemanager.addsinglefile.failed'
            )
            return self.error(err)

        await self.add_log(
            f'{self.acct.name} has sent a request to add {filename} for problem #{pro_id}',
            'manage.pro.update.filemanager.addsinglefile',
        )

        return self.error(('S', ''))

    @batch_filemanager_dispatcher.action('deletesinglefile')
    async def delete_single_file_action(self):
        try:
            pro_id = int(self.get_argument("pro_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem ID"))

        basepath = self.get_argument('path')
        filename = self.get_argument('filename')

        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        assert isinstance(pro.config.spec_config, BatchConfig)
        batch_config = pro.config.spec_config

        allowed_paths = batch_spec.get_allowed_file_paths(batch_config, pro_id)

        if basepath not in allowed_paths:
            return self.error(('Eparam', 'Invalid basepath'))

        file_mgr = FileManager(f'problem/{pro_id}/{basepath}')

        err, _ = file_mgr.delete(filename)
        if err:
            await self.add_log(
                f'{self.acct.name} tried to delete {filename} for problem #{pro_id}, failed with {err[0]}',
                'manage.pro.update.filemanager.deletesinglefile.failed'
            )
            return self.error(err)

        await self.add_log(
            f'{self.acct.name} has sent a request to delete {filename} for problem #{pro_id}',
            'manage.pro.update.filemanager.deletesinglefile',
        )

        return self.error(('S', ''))

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        reqtype = self.get_argument('reqtype')
        return await batch_filemanager_dispatcher.dispatch(self, reqtype)
