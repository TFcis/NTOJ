from handlers.base import RequestHandler, reqenv
from handlers.contests.base import contest_require_permission
from services.contest_access import ContestPermission
from services.log import LogService


class ContestManageLogHandler(RequestHandler):
    @reqenv
    @contest_require_permission(ContestPermission.ADMIN)
    async def get(self, log_id=None):
        """Display logs for the current contest

        Args:
            log_id: Optional log ID to view specific log details
        """
        if log_id is None:
            # List logs for this contest
            try:
                pageoff = int(self.get_argument('pageoff', default="0"))
                if pageoff < 0:
                    pageoff = 0
            except ValueError:
                return self.error(('Eparam', 'Invalid page offset'))

            logtype = str(self.get_argument('logtype', default=''))
            if not logtype:
                logtype = None

            # Get log types for filtering
            err, logtype_list = await LogService.inst.get_log_type()
            if err:
                return self.error(err)

            # Get logs for this contest
            err, log_data = await LogService.inst.list_log(
                pageoff,
                50,
                log_type=logtype,
                contest_id=self.contest.contest_id
            )
            if err or log_data is None:
                return self.error(err if err else ('Eunk', 'Unknown error'))

            await self.render(
                'contests/manage/log-list',
                f"{self.contest.name} - Logs",
                page='log',
                contest_id=self.contest.contest_id,
                pageoff=pageoff,
                lognum=log_data['lognum'],
                loglist=log_data['loglist'],
                logtype_list=logtype_list,
                cur_logtype=logtype,
            )
            return

        # View specific log
        try:
            log_id = int(log_id)
            if log_id <= 0:
                raise ValueError()
        except ValueError:
            return self.error(('Eparam', 'Invalid log ID'))

        err, log_detail = await LogService.inst.view_log(log_id)
        if err or log_detail is None:
            return self.error(err if err else ('Eunk', 'Unknown error'))

        # Verify the log belongs to this contest
        if log_detail['contest_id'] != self.contest.contest_id:
            return self.error(('Eacces', 'This log does not belong to this contest'))

        await self.render(
            'contests/manage/log',
            f"{self.contest.name} - Log {log_id}",
            page='log',
            contest_id=self.contest.contest_id,
            log=log_detail
        )
