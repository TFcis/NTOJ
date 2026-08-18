import os
from dataclasses import asdict

import tornado.escape

from handlers.base import ActionDispatcher, RequestHandler, reqenv, require_permission
from services.filemanager import FileManager
from services.pack import PackService
from services.pro import ProConst, ProService, ProType
from services.prospec.communication import CommunicationTestdata
from services.user import UserConst


communication_testdata_dispatcher = ActionDispatcher()


class CommunicationTestdataHandler(RequestHandler):
    async def _get_problem(self, pro_id: int):
        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return err, None
        if pro.problem_type != ProType.COMMUNICATION:
            return ("Eparam", "Invalid problem type"), None
        return None, pro

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
        try:
            pro_id = int(self.get_argument("pro_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem ID"))
        err, pro = await self._get_problem(pro_id)
        if err:
            return self.error(err)

        if self.get_argument("download", default=None):
            try:
                testdata_id = int(self.get_argument("testdata_id"))
                testdata = pro.config.testdatas[testdata_id]
            except (ValueError, KeyError):
                return self.error(("Enoext", "Testdata not found"))
            filepath = FileManager(f"problem/{pro_id}/res/testdata").get_filepath(
                testdata.inputfile
            )
            if filepath is None or not os.path.isfile(filepath):
                return self.error(("Enoext", "Testdata file not found"))
            self.set_header("Content-Type", "application/octet-stream")
            self.set_header(
                "Content-Disposition", f'attachment; filename="{testdata.inputfile}"'
            )
            with open(filepath, "rb") as input_f:
                while chunk := input_f.read(65536):
                    self.write(chunk)
            self.finish()
            return

        await self.render(
            "prospec/communication/manage/updatetestdata",
            "Update Problem Testdatas Config",
            page="pro",
            pro_id=pro_id,
            config=pro.config,
        )

    @communication_testdata_dispatcher.action("preview")
    async def preview_action(self):
        try:
            pro_id = int(self.get_argument("pro_id"))
            testdata_id = int(self.get_argument("testdata_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem or testdata ID"))
        err, pro = await self._get_problem(pro_id)
        if err:
            return self.error(err)
        try:
            filename = pro.config.testdatas[testdata_id].inputfile
        except KeyError:
            return self.error(("Enoext", "Testdata not found"))
        err, content = FileManager(f"problem/{pro_id}/res/testdata").read(
            filename, "r"
        )
        if err:
            return self.error(err)
        if content.count("\n") > 25:
            return self.error(("Efile", "File too large"))
        return self.error(("S", tornado.escape.xhtml_escape(content)))

    @communication_testdata_dispatcher.action("updatesinglefile")
    async def update_single_file_action(self):
        try:
            pro_id = int(self.get_argument("pro_id"))
            testdata_id = int(self.get_argument("testdata_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem or testdata ID"))
        pack_token = self.get_argument("pack_token")
        err, pro = await self._get_problem(pro_id)
        if err:
            await PackService.inst.clear(pack_token)
            return self.error(err)
        try:
            testdata = pro.config.testdatas[testdata_id]
        except KeyError:
            await PackService.inst.clear(pack_token)
            return self.error(("Enoext", "Testdata not found"))
        assert isinstance(testdata, CommunicationTestdata)
        err, _ = await FileManager(
            f"problem/{pro_id}/res/testdata"
        ).update_from_pack(testdata.inputfile, pack_token)
        if err:
            return self.error(err)
        err, _ = await ProService.inst.update_pro_config(
            pro_id, pro.problem_type, pro.config
        )
        return self.error(err or ("S", ""))

    @communication_testdata_dispatcher.action("addsinglefile")
    async def add_single_file_action(self):
        try:
            pro_id = int(self.get_argument("pro_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem ID"))
        filename = os.path.basename(self.get_argument("filename"))
        pack_token = self.get_argument("input_pack_token")
        if not filename:
            await PackService.inst.clear(pack_token)
            return self.error(("Eparam", "Filename must not be empty"))
        err, pro = await self._get_problem(pro_id)
        if err:
            await PackService.inst.clear(pack_token)
            return self.error(err)
        err, _ = await FileManager(f"problem/{pro_id}/res/testdata").copy_from_pack(
            f"{filename}.in", pack_token
        )
        if err:
            return self.error(err)
        testdatas = pro.config.testdatas
        new_id = max(testdatas, default=-1) + 1
        testdatas[new_id] = CommunicationTestdata(new_id, inputfile=f"{filename}.in")
        err, _ = await ProService.inst.update_pro_config(
            pro_id, pro.problem_type, pro.config
        )
        return self.error(err or ("S", ""))

    @communication_testdata_dispatcher.action("deletesinglefile")
    async def delete_single_file_action(self):
        try:
            pro_id = int(self.get_argument("pro_id"))
            testdata_id = int(self.get_argument("testdata_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem or testdata ID"))
        err, pro = await self._get_problem(pro_id)
        if err:
            return self.error(err)
        try:
            testdata = pro.config.testdatas[testdata_id]
        except KeyError:
            return self.error(("Enoext", "Testdata not found"))
        assert isinstance(testdata, CommunicationTestdata)
        err, _ = FileManager(f"problem/{pro_id}/res/testdata").delete(
            testdata.inputfile
        )
        if err:
            return self.error(err)
        for subtask in pro.config.subtask_configs.values():
            subtask.testdatas = [
                item for item in subtask.testdatas if item.testdata_id != testdata_id
            ]
        deleted = pro.config.testdatas.pop(testdata_id)
        err, _ = await ProService.inst.update_pro_config(
            pro_id, pro.problem_type, pro.config
        )
        if err:
            return self.error(err)
        await self.add_log(
            f"{self.acct.name} deleted testdata {testdata_id} for problem #{pro_id}",
            "manage.pro.update.testdata.deletesinglefile",
            {"testdata": asdict(deleted)},
        )
        return self.error(("S", ""))

    @communication_testdata_dispatcher.action("updatemetadata")
    async def update_metadata_action(self):
        try:
            pro_id = int(self.get_argument("pro_id"))
            testdata_id = int(self.get_argument("testdata_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem or testdata ID"))
        err, pro = await self._get_problem(pro_id)
        if err:
            return self.error(err)
        if testdata_id not in pro.config.testdatas:
            return self.error(("Enoext", "Testdata not found"))
        tags = [
            tag.strip()
            for tag in self.get_argument("tags", default="").split(",")
            if tag.strip()
        ]
        pro.config.testdatas[testdata_id].metadata["tags"] = tags
        err, _ = await ProService.inst.update_pro_config(
            pro_id, pro.problem_type, pro.config
        )
        return self.error(err or ("S", ""))

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        return await communication_testdata_dispatcher.dispatch(
            self, self.get_argument("reqtype")
        )
