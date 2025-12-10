import os

import tornado.escape
from dataclasses import asdict

from handlers.base import RequestHandler, reqenv, require_permission, ActionDispatcher
from services.log import LogService
from services.pro import ProService, ProConst
from services.prospec.batch import BatchTestdata
from services.user import UserConst
from services.pack import PackService
from services.filemanager import FileManager

PERMISSION_DENIED_ERROR = ("Eacces", "Permission denied")

batch_testdata_dispatcher = ActionDispatcher()


class BatchTestdataHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
        pro_id = int(self.get_argument("proid"))
        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        download = self.get_argument("download", default=None)

        if download:
            testdata_type = self.get_argument("type")
            if testdata_type not in ("input", "output"):
                return self.error(("Eparam", "Invalid testdata file type"))

            testdata_id = int(self.get_argument("testdata_id"))
            if testdata_id not in pro.config.testdatas:
                self.error(("Enoext", "Testdata not found"))
                return

            if testdata_type == "input":
                file = pro.config.testdatas[testdata_id].inputfile
            else:
                file = pro.config.testdatas[testdata_id].outputfile

            basepath = f"problem/{pro_id}/res/testdata"
            filepath = f"{basepath}/{file}"
            if not os.path.exists(filepath):
                return self.error(("Enoext", "Testdata file not found"))

            await LogService.inst.add_log(
                f"{self.acct.name} download testdata {testdata_id} with {testdata_type} type for problem #{pro_id}",
                "manage.pro.update.testdata.download",
            )

            self.set_header("Content-Type", "application/octet-stream")
            self.set_header("Content-Disposition", f'attachment; filename="{file}"')
            with open(filepath, "rb") as f:
                try:
                    while True:
                        buffer = f.read(65536)
                        if buffer:
                            self.write(buffer)
                        else:
                            self.finish()
                            return
                except Exception:
                    self.error(("Eunk", "Unknown error"))
            return

        await self.render(
            "prospec/batch/manage/updatetestdata",
            page="pro",
            pro_id=pro_id,
            config=pro.config,
        )

    @batch_testdata_dispatcher.action("preview")
    async def preview_action(self):
        pro_id = int(self.get_argument("pro_id"))
        testdata_id = int(self.get_argument("testdata_id"))
        testdata_type = self.get_argument("type")

        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        if testdata_id not in pro.config.testdatas:
            return self.error(("Enoext", "Testdata not found"))

        if testdata_type not in ("output", "input"):
            return self.error(("Eparam", "Invalid testdata file type"))

        if testdata_type == "input":
            filename = pro.config.testdatas[testdata_id].inputfile
        else:
            filename = pro.config.testdatas[testdata_id].outputfile

        basepath = f"problem/{pro_id}/res/testdata"
        filepath = os.path.join(basepath, filename)

        if not os.path.exists(filepath):
            await LogService.inst.add_log(
                f"{self.acct.name} tried to preview file:{filename} for problem #{pro_id} but not found",
                "manage.pro.update.testdata.preview.failed",
            )
            return self.error(("Enoext", "File not found"))

        await LogService.inst.add_log(
            f"{self.acct.name} preview testdata {testdata_id} with {testdata_type} type for problem #{pro_id}",
            "manage.pro.update.testdata.preview",
        )
        with open(filepath, "r") as testdata_f:
            content = testdata_f.readlines()
            if len(content) > 25:
                return self.error(("Efile", "File too large"))

            return self.error(("S", tornado.escape.xhtml_escape("".join(content))))

    @batch_testdata_dispatcher.action("updatesinglefile")
    async def update_single_file_action(self):
        pro_id = int(self.get_argument("pro_id"))
        testdata_id = int(self.get_argument("testdata_id"))
        testdata_type = self.get_argument("type")
        pack_token = self.get_argument("pack_token")

        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        testdatas = pro.config.testdatas
        if testdata_id not in testdatas:
            await PackService.inst.clear(pack_token)
            return self.error(("Enoext", "Testdata not found"))

        testdata = testdatas[testdata_id]
        assert isinstance(testdata, BatchTestdata)

        if testdata_type not in ("output", "input"):
            await PackService.inst.clear(pack_token)
            return self.error(("Eparam", "Invalid testdata file type"))

        if testdata_type == "input":
            filename = testdata.inputfile
        else:
            filename = testdata.outputfile

        file_mgr = FileManager(f"problem/{pro_id}/res/testdata")
        err, _ = await file_mgr.update_from_pack(filename, pack_token)
        if err:
            await LogService.inst.add_log(
                f"{self.acct.name} tried to update testdata {testdata_id} with {testdata_type} type for problem #{pro_id}, failed with {err[0]}",
                "manage.pro.update.testdata.updatesinglefile.failed",
                {"testdata": testdatas[testdata_id]},
            )
            return self.error(err)

        await ProService.inst.update_pro_config(pro_id, pro.problem_type, pro.config)
        await LogService.inst.add_log(
            f"{self.acct.name} has sent a request to update testdata {testdata_id} with {testdata_type} type for problem #{pro_id}",
            "manage.pro.update.testdata.updatesinglefile",
        )

        return self.error(("S", ""))

    @batch_testdata_dispatcher.action("addsinglefile")
    async def add_single_file_action(self):
        pro_id = int(self.get_argument("pro_id"))
        filename = self.get_argument("filename")
        input_pack_token = self.get_argument("input_pack_token")
        output_pack_token = self.get_argument("output_pack_token")

        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        testdatas = pro.config.testdatas
        try:
            new_testdata_id = max(testdatas.keys()) + 1
        except ValueError:
            new_testdata_id = 0

        file_mgr = FileManager(f"problem/{pro_id}/res/testdata")

        # Try to add input file
        err, _ = await file_mgr.copy_from_pack(f"{filename}.in", input_pack_token)
        if err:
            await PackService.inst.clear(output_pack_token)
            await LogService.inst.add_log(
                f"{self.acct.name} tried to add input file:{filename}.in for problem #{pro_id}, failed with {err[0]}",
                "manage.pro.update.testdata.addsinglefile.failed",
            )
            return self.error(err)

        # Try to add output file
        err, _ = await file_mgr.copy_from_pack(f"{filename}.out", output_pack_token)
        if err:
            # Clean up input file if output file fails
            file_mgr.delete(f"{filename}.in")
            await LogService.inst.add_log(
                f"{self.acct.name} tried to add output file:{filename}.out for problem #{pro_id}, failed with {err[0]}",
                "manage.pro.update.testdata.addsinglefile.failed",
            )
            return self.error(err)

        testdatas[new_testdata_id] = BatchTestdata(
            new_testdata_id, f"{filename}.in", f"{filename}.out"
        )
        await ProService.inst.update_pro_config(pro_id, pro.problem_type, pro.config)

        await LogService.inst.add_log(
            f"{self.acct.name} has sent a request to add testdata {new_testdata_id} named {filename} for problem #{pro_id}",
            "manage.pro.update.testdata.addsinglefile",
        )

        return self.error(("S", ""))

    @batch_testdata_dispatcher.action("deletesinglefile")
    async def delete_single_file_action(self):
        pro_id = int(self.get_argument("pro_id"))
        testdata_id = int(self.get_argument("testdata_id"))

        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        testdatas = pro.config.testdatas

        if testdata_id not in testdatas:
            return self.error(("Enoext", "Testdata not found"))

        testdata = testdatas[testdata_id]
        assert isinstance(testdata, BatchTestdata)
        inputfile = testdata.inputfile
        outputfile = testdata.outputfile

        file_mgr = FileManager(f"problem/{pro_id}/res/testdata")

        # Try to delete both files
        err, _ = file_mgr.multiple_delete([inputfile, outputfile])
        if err:
            await LogService.inst.add_log(
                f"{self.acct.name} tried to delete testdata {testdata_id} for problem #{pro_id}, failed with {err[0]}",
                "manage.pro.update.testdata.deletesinglefile.failed",
                {"testdata": testdatas[testdata_id]},
            )
            return self.error(err)

        for subtask_config in pro.config.subtask_configs.values():
            try:
                subtask_config.testdatas.remove(pro.config.testdatas[testdata_id])
            except ValueError:
                continue

        deleted_testdata = pro.config.testdatas.pop(testdata_id)

        await ProService.inst.update_pro_config(pro_id, pro.problem_type, pro.config)
        await LogService.inst.add_log(
            f"{self.acct.name} has sent a request to delete testdata {testdata_id} for problem #{pro_id}",
            "manage.pro.update.testdata.deletesinglefile",
            {"testdata": asdict(deleted_testdata)},
        )

        return self.error(("S", ""))

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        reqtype = self.get_argument("reqtype")
        return await batch_testdata_dispatcher.dispatch(self, reqtype)
