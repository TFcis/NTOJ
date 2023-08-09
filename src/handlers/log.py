import tornado.web

from services.log import LogService
from utils.req import RequestHandler, reqenv


class LogHandler(RequestHandler):
    @reqenv
    async def get(self):
        from services.user import UserConst
        if self.acct['acct_type'] != UserConst.ACCTTYPE_KERNEL:
            self.error('Eacces')
            return

        try:
            off = int(self.get_argument('off'))
        except tornado.web.HTTPError:
            off = 0

        try:
            logtype = str(self.get_argument('logtype'))
        except tornado.web.HTTPError:
            logtype = None

        err, logtype_list = await LogService.inst.get_log_type()

        err, log = await LogService.inst.list_log(off, 50, logtype)
        if err:
            self.error(err)
            return

        await self.render('loglist', pageoff=off, lognum=log['lognum'], loglist=log['loglist'],
                          logtype_list=logtype_list, cur_logtype=logtype)
        return
