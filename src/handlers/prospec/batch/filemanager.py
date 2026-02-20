import tornado.escape
import markdown

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

    async def _handle_list_files(self, pro_id, pro):
        config = pro.config
        assert isinstance(config.spec_config, BatchConfig)
        batch_config = config.spec_config

        # Use ProSpec to get file structure
        dirs = batch_spec.get_file_structure(batch_config, pro_id)

        await self.render('manage/pro/filemanager', page='pro', pro_id=pro_id, dirs=dirs)

    async def _render_cont_md(self, pro_id, basepath):
        file_mgr = FileManager(f'problem/{pro_id}/{basepath}')
        if not file_mgr.exists('cont.md'):
            return None

        err, md_content = file_mgr.read('cont.md', 'r')
        if err:
            await LogService.inst.add_log(
                f'Auto-render failed: Could not read cont.md for problem #{pro_id}. Error: {err}',
                'manage.pro.render.read_failed'
            )
            return ('Erender', f'Read cont.md failed: {err[1]}')

        try:
            # extra for table, etc.
            html_content = markdown.markdown(md_content, extensions=['extra'], output_format='html5')

            filepath = file_mgr.get_filepath('cont.html')
            if not filepath:
                return ('Erender', 'Invalid path for cont.html')

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)

            await LogService.inst.add_log(
                f'Auto-rendered cont.md to cont.html for problem #{pro_id}',
                'manage.pro.render.success'
            )
            return None

        except Exception as e:
            error_msg = str(e)
            await LogService.inst.add_log(
                f'Auto-render error for problem #{pro_id}: {error_msg}',
                'manage.pro.render.error'
            )
            return ('Erender', f'Markdown render failed: {error_msg}')

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
            await LogService.inst.add_log(
                f'{self.acct.name} tried to preview {filename} for problem #{pro_id}, failed with {err[0]}',
                'manage.pro.update.filemanager.preview.failed'
            )
            return self.error(err)

        await LogService.inst.add_log(f'{self.acct.name} preview {filename} for problem #{pro_id}',
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
            await LogService.inst.add_log(
                f'{self.acct.name} tried to rename {old_filename} to {new_filename} for problem #{pro_id}, failed with {err[0]}',
                'manage.pro.update.filemanager.renamesinglefile.failed'
            )
            return self.error(err)

        if new_filename == 'cont.md':
            render_err = await self._render_cont_md(pro_id, basepath)
            if render_err:
                return self.error(render_err)

        if old_filename == 'cont.html' and file_mgr.exists('cont.md'):
            render_err = await self._render_cont_md(pro_id, basepath)
            if render_err:
                if file_mgr.exists(old_filename):
                    file_mgr.delete(old_filename)

                rollback_err, _ = file_mgr.rename(new_filename, old_filename)
                if rollback_err:
                    await LogService.inst.add_log(
                        f'{self.acct.name} tried to roll back rename of {old_filename} to {new_filename} for problem #{pro_id} after render failure {render_err[0]}, but rollback failed with {rollback_err[0]}',
                        'manage.pro.update.filemanager.renamesinglefile.rollback.failed'
                    )
                else:
                    await LogService.inst.add_log(
                        f'{self.acct.name} rolled back rename of {old_filename} to {new_filename} for problem #{pro_id} after render failure {render_err[0]}',
                        'manage.pro.update.filemanager.renamesinglefile.rollback'
                    )
                return self.error(render_err)

        await LogService.inst.add_log(
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
            await LogService.inst.add_log(
                f'{self.acct.name} tried to update {filename} for problem #{pro_id}, failed with {err[0]}',
                'manage.pro.update.filemanager.updatesinglefile.failed'
            )
            return self.error(err)

        if filename == 'cont.md':
            render_err = await self._render_cont_md(pro_id, basepath)
            if render_err:
                return self.error(render_err)

        await LogService.inst.add_log(
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
            await LogService.inst.add_log(
                f'{self.acct.name} tried to add {filename} for problem #{pro_id}, failed with {err[0]}',
                'manage.pro.update.filemanager.addsinglefile.failed'
            )
            return self.error(err)

        if filename == 'cont.md':
            render_err = await self._render_cont_md(pro_id, basepath)
            if render_err:
                return self.error(render_err)

        await LogService.inst.add_log(
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

        if filename == 'cont.html' and file_mgr.exists('cont.md'):
            tmp_filename = 'cont_tmp.html'
            original_args = self.request.arguments.copy()
            self.request.arguments['old_filename'] = [filename.encode('utf-8')]
            self.request.arguments['new_filename'] = [tmp_filename.encode('utf-8')]

            ret = await self.rename_single_file_action()

            self.request.arguments = original_args

            if ret[0] == 'S':
                file_mgr.delete(tmp_filename)
                await LogService.inst.add_log(
                    f'{self.acct.name} triggered auto-restore via deletion of {filename} for problem #{pro_id}',
                    'manage.pro.update.filemanager.deletesinglefile.restore'
                )
                return self.error(('S', ''))
            else:
                return ret

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

        return self.error(('S', ''))

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        reqtype = self.get_argument('reqtype')
        return await batch_filemanager_dispatcher.dispatch(self, reqtype)
