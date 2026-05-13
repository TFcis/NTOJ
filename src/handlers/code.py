"""
Unified code display handler.
Dispatches to problem type-specific handlers.
"""

from handlers.base import RequestHandler, reqenv
from services.chal import ChalService
from services.pro import ProService, ProType, ProConst


class CodeHandler(RequestHandler):
    @reqenv
    async def post(self):
        try:
            chal_id = int(self.get_argument('chal_id'))
        except ValueError:
            return self.error(('Eparam', 'Invalid challenge id'))

        # Get challenge to determine problem type
        err, chal = await ChalService.inst.get_chal(chal_id)
        if err:
            return self.error(err)

        # Determine allowed pro statuses based on contest and user type
        allow_statuses = ProConst.PRO_STATUS_NORMAL_USER
        if chal.contest_id:
            allow_statuses = ProConst.PRO_STATUS_CONTEST_USER
        elif self.acct.is_kernel():
            allow_statuses = ProConst.PRO_STATUS_KERNEL_USER

        err, pro = await ProService.inst.get_pro(chal.pro_id, allow_statuses)
        if err:
            return self.error(err)

        # Dispatch to problem type-specific handler
        if pro.problem_type == ProType.BATCH:
            from handlers.prospec.batch.code import BatchCodeHandler
            handler = BatchCodeHandler(self.application, self.request, db=self.db, rs=self.rs)
            handler.acct = self.acct
            handler._transforms = []
            return await handler.post()
        elif pro.problem_type == ProType.COMMUNICATION:
            # Future: Communication code display
            return self.error(('Enotsupport', 'Communication problem type not yet supported'))
        elif pro.problem_type == ProType.TWOSTEP:
            # Future: TwoStep code display (might show two code sections)
            return self.error(('Enotsupport', 'TwoStep problem type not yet supported'))
        elif pro.problem_type == ProType.OUTPUTONLY:
            # Future: OutputOnly code display (show uploaded files)
            return self.error(('Enotsupport', 'OutputOnly problem type not yet supported'))
        else:
            return self.error(('Eparam', 'Invalid problem type'))
