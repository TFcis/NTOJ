from handlers.base import RequestHandler, reqenv, require_permission
from services.pro import ProService, ProConst, ProType
from services.user import UserConst

ALLOW_STATUSES = [ProConst.STATUS_ONLINE, ProConst.STATUS_CONTEST, ProConst.STATUS_HIDDEN]


class ManageProFilemanagerHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
        pro_id = int(self.get_argument('proid'))
        err, pro = await ProService.inst.get_pro(pro_id, ALLOW_STATUSES)
        if err:
            return self.error(err)

        # Dispatch to problem type specific handler
        if pro.problem_type == ProType.BATCH:
            from handlers.prospec.batch.filemanager import BatchFilemanagerHandler
            handler = BatchFilemanagerHandler(self.application, self.request, db=self.db, rs=self.rs)
            handler.acct = self.acct
            handler._transforms = []
            return await handler.get()
        elif pro.problem_type == ProType.COMMUNICATION:
            return self.error(('Enotsupport', 'Communication problem type not yet supported'))
        elif pro.problem_type == ProType.TWOSTEP:
            return self.error(('Enotsupport', 'Twostep problem type not yet supported'))
        elif pro.problem_type == ProType.OUTPUTONLY:
            return self.error(('Enotsupport', 'OutputOnly problem type not yet supported'))
        else:
            return self.error(('Enotsupport', 'File manager for this problem type is not yet supported'))

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        pro_id = int(self.get_argument('pro_id'))
        err, pro = await ProService.inst.get_pro(pro_id, ALLOW_STATUSES)
        if err:
            return self.error(err)

        # Dispatch to problem type specific handler
        if pro.problem_type == ProType.BATCH:
            from handlers.prospec.batch.filemanager import BatchFilemanagerHandler
            handler = BatchFilemanagerHandler(self.application, self.request, db=self.db, rs=self.rs)
            handler.acct = self.acct
            handler._transforms = []
            return await handler.post()
        elif pro.problem_type == ProType.COMMUNICATION:
            from handlers.prospec.communication.filemanager import CommunicationFilemanagerHandler
            handler = CommunicationFilemanagerHandler(self.application, self.request, db=self.db, rs=self.rs)
            handler.acct = self.acct
            handler._transforms = []
            return await handler.post()
        elif pro.problem_type == ProType.TWOSTEP:
            from handlers.prospec.twostep.filemanager import TwoStepFilemanagerHandler
            handler = TwoStepFilemanagerHandler(self.application, self.request, db=self.db, rs=self.rs)
            handler.acct = self.acct
            handler._transforms = []
            return await handler.post()
        elif pro.problem_type == ProType.OUTPUTONLY:
            from handlers.prospec.outputonly.filemanager import OutputOnlyFilemanagerHandler
            handler = OutputOnlyFilemanagerHandler(self.application, self.request, db=self.db, rs=self.rs)
            handler.acct = self.acct
            handler._transforms = []
            return await handler.post()
        else:
            return self.error(('Enotsupport', 'File manager for this problem type is not yet supported'))
