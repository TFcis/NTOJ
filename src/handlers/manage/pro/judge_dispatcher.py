"""
Unified judge configuration handler.
Dispatches to problem type-specific handlers.
"""
from handlers.base import RequestHandler, reqenv, require_permission
from services.pro import ProService, ProConst, ProType
from services.user import UserConst

ALLOW_STATUSES = [ProConst.STATUS_ONLINE, ProConst.STATUS_CONTEST, ProConst.STATUS_HIDDEN]


class ManageProJudgeHandler(RequestHandler):
    """Unified judge configuration handler - dispatches to type-specific handlers."""

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
        """Render judge configuration page based on problem type."""
        pro_id = int(self.get_argument('proid'))
        err, pro = await ProService.inst.get_pro(pro_id, ALLOW_STATUSES)
        if err:
            return self.error(err)

        if pro.problem_type == ProType.BATCH:
            await self.render('prospec/batch/manage/updatejudge', page='pro', pro=pro)
        elif pro.problem_type == ProType.COMMUNICATION:
            return self.error(('Enotsupport', 'Communication problem type not yet supported'))
        elif pro.problem_type == ProType.TWOSTEP:
            return self.error(('Enotsupport', 'TwoStep problem type not yet supported'))
        elif pro.problem_type == ProType.OUTPUTONLY:
            return self.error(('Enotsupport', 'OutputOnly problem type not yet supported'))
        else:
            return self.error(('Eparam', 'Invalid problem type'))

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        """Handle judge configuration update - dispatch to type-specific handler."""
        pro_id = int(self.get_argument('pro_id'))
        err, pro = await ProService.inst.get_pro(pro_id, ALLOW_STATUSES)
        if err:
            return self.error(err)

        if pro.problem_type == ProType.BATCH:
            from handlers.prospec.batch.judge import BatchJudgeHandler
            handler = BatchJudgeHandler(self.application, self.request, db=self.db, rs=self.rs)
            handler.acct = self.acct
            handler._transforms = []
            return await handler.post()
        elif pro.problem_type == ProType.COMMUNICATION:
            return self.error(('Enotsupport', 'Communication problem type not yet supported'))
        elif pro.problem_type == ProType.TWOSTEP:
            return self.error(('Enotsupport', 'TwoStep problem type not yet supported'))
        elif pro.problem_type == ProType.OUTPUTONLY:
            return self.error(('Enotsupport', 'OutputOnly problem type not yet supported'))
        else:
            return self.error(('Eparam', 'Invalid problem type'))
