import os

from handlers.base import ActionDispatcher, RequestHandler, reqenv, require_permission
from services.log import LogService
from services.pro import ProService, ProConst
from services.user import UserConst

update_dispatcher = ActionDispatcher()


class ManageProUpdateHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
        pro_id = int(self.get_argument("proid"))
        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        await self.render("manage/pro/updategeneral", page="pro", pro=pro)

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        reqtype = self.get_argument("reqtype")
        return await update_dispatcher.dispatch(self, reqtype)

    @update_dispatcher.action("updategeneral")
    async def update_general(self):
        pro_id = int(self.get_argument("pro_id"))
        name = self.get_argument("name")
        status = int(self.get_argument("status"))
        tags = self.get_argument("tags")
        allow_submit = self.get_argument("allow_submit") == "true"

        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        assert pro
        pro.name = name
        pro.status = status
        pro.tags = tags
        pro.allow_submit = allow_submit
        err, _ = await ProService.inst.update_pro(pro)

        await LogService.inst.add_log(
            f"{self.acct.name} has sent a request to update the problem #{pro_id}",
            "manage.pro.update.general",
            {
                "name": name,
                "status": status,
                "tags": tags,
                "allow_submit": allow_submit,
            },
        )
        if err:
            return self.error(err)

        self.error(("S", ""))

    @update_dispatcher.action("uploadpackage")
    async def upload_package(self):
        pro_id = int(self.get_argument("pro_id"))
        pack_token = self.get_argument("pack_token")

        err, _ = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        err, _ = await ProService.inst.unpack_pro(pro_id, pack_token)
        if err:
            await LogService.inst.add_log(
                f"{self.acct.name} tried to update the problem #{pro_id} by uploading problem package but failed",
                "manage.pro.update.pro.package.failed",
                {"err": err},
            )
            return self.error(err)

        suspicious_files = []
        for file in os.listdir(f"problem/{pro_id}/res/testdata"):
            if os.path.islink(file):
                suspicious_files.append((file, os.path.realpath(file)))

        if suspicious_files:
            await LogService.inst.add_log(
                f"There are some suspicious files that may have been uploaded by {self.acct.name}",
                "manage.pro.update.pro.package.suspicious",
                {
                    "suspicious_files": suspicious_files,
                    "uploader": self.acct.acct_id,
                },
            )

        await LogService.inst.add_log(
            f"{self.acct.name} has sent a request to update the problem #{pro_id} by uploading problem package",
            "manage.pro.update.pro.package",
        )
        self.error(("S", ""))
