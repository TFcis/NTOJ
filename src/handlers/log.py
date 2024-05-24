import tornado.web

from handlers.base import RequestHandler, reqenv, require_permission
from services.log import LogService


class LogHandler(RequestHandler):
    from services.user import UserConst

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
        try:
            pageoff = int(self.get_argument('pageoff'))
        except tornado.web.HTTPError:
            pageoff = 0

        try:
            logtype = str(self.get_argument('logtype'))
        except tornado.web.HTTPError:
            logtype = None

        err, logtype_list = await LogService.inst.get_log_type()

        err, log = await LogService.inst.list_log(pageoff, 50, logtype)
        if err:
            self.error(err)
            return

        await self.render(
            'loglist',
            pageoff=pageoff,
            lognum=log['lognum'],
            loglist=log['loglist'],
            logtype_list=logtype_list,
            cur_logtype=logtype,
        )
