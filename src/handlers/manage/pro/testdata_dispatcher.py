from handlers.base import RequestHandler, reqenv, require_permission
from services.pro import ProService, ProConst, ProType
from services.user import UserConst


class ManageProTestdataHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
        try:
            pro_id = int(self.get_argument("pro_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem ID"))
        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        if pro.problem_type == ProType.BATCH:
            from handlers.prospec.batch.testdata import BatchTestdataHandler

            handler = BatchTestdataHandler(
                self.application, self.request, db=self.db, rs=self.rs
            )
            handler.acct = self.acct
            handler._transforms = []
            return await handler.get()
        elif pro.problem_type == ProType.COMMUNICATION:
            return self.error(
                ("Enotsupport", "Communication problem type not yet supported")
            )
        elif pro.problem_type == ProType.TWOSTEP:
            return self.error(("Enotsupport", "TwoStep problem type not yet supported"))
        elif pro.problem_type == ProType.OUTPUTONLY:
            return self.error(
                ("Enotsupport", "OutputOnly problem type not yet supported")
            )
        else:
            return self.error(("Eparam", "Invalid problem type"))

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        try:
            pro_id = int(self.get_argument("pro_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem ID"))
        err, pro = await ProService.inst.get_pro(pro_id, ProConst.PRO_STATUS_FULL)
        if err:
            return self.error(err)

        if pro.problem_type == ProType.BATCH:
            from handlers.prospec.batch.testdata import BatchTestdataHandler

            handler = BatchTestdataHandler(
                self.application, self.request, db=self.db, rs=self.rs
            )
            handler.acct = self.acct
            handler._transforms = []
            return await handler.post()
        elif pro.problem_type == ProType.COMMUNICATION:
            return self.error(
                ("Enotsupport", "Communication problem type not yet supported")
            )
        elif pro.problem_type == ProType.TWOSTEP:
            return self.error(("Enotsupport", "TwoStep problem type not yet supported"))
        elif pro.problem_type == ProType.OUTPUTONLY:
            return self.error(
                ("Enotsupport", "OutputOnly problem type not yet supported")
            )
        else:
            return self.error(("Eparam", "Invalid problem type"))
