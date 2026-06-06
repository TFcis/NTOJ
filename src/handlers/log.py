from handlers.base import RequestHandler, reqenv, require_permission
from services.log import LogService


class LogHandler(RequestHandler):
    from services.user import UserConst

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self, log_id=None):
        if log_id is None:
            try:
                pageoff = int(self.get_argument('pageoff', default="0"))
                if pageoff < 0:
                    pageoff = 0
            except ValueError:
                return self.error(('Eparam', 'Invalid page offset'))

            logtype = str(self.get_argument('logtype', default=''))
            if not logtype:
                logtype = None

            err, logtype_list = await LogService.inst.get_log_type()

            err, log = await LogService.inst.list_log(pageoff, 50, logtype)
            if err:
                return self.error(err)

            await self.render(
                'loglist',
                "Logs",
                pageoff=pageoff,
                lognum=log['lognum'],
                loglist=log['loglist'],
                logtype_list=logtype_list,
                cur_logtype=logtype,
            )
            return

        try:
            log_id = int(log_id)
            if log_id <= 0:
                raise ValueError()
        except ValueError:
            return self.error(('Eparam', 'Invalid log ID'))
        err, log = await LogService.inst.view_log(log_id)
        if err:
            return self.error(err)

        await self.render('log', f"Log - {log_id}",
                          log=log)

