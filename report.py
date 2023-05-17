from msgpack import packb, unpackb

from req import RequestHandler, reqenv
from user import UserService, UserConst

from dbg import dbg_print

class ReportHandler(RequestHandler):
    @reqenv
    async def get(self):
        if self.acct['acct_id'] == UserConst.ACCTID_GUEST:
            self.error('Esign')
            return

        # if self.acct['acct_type'] != UserService.ACCTTYPE_USER:
        #     self.error('Eacces')
        #     return

        chal_id = int(self.get_argument('chal_id'))

        await self.render('report-problem', chal_id=chal_id, acct=self.acct)
        return
