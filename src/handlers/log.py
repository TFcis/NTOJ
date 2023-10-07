import tornado.web

from services.log import LogService
from handlers.base import RequestHandler, reqenv, require_permission


class LogHandler(RequestHandler):
    from services.user import UserConst

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
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
