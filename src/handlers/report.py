from handlers.base import RequestHandler, reqenv, require_permission
from services.user import UserConst


class ReportHandler(RequestHandler):
    @reqenv
    @require_permission([UserConst.ACCTTYPE_USER, UserConst.ACCTTYPE_KERNEL])
    async def get(self):
        chal_id = int(self.get_argument('chal_id'))

        await self.render('report-problem', chal_id=chal_id, acct=self.acct)
