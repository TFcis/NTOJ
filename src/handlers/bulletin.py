from handlers.base import RequestHandler, UnifiedWebSocketHandler, reqenv
from services.bulletin import BulletinService
from services.judge import JudgeServerClusterService


class BulletinCallback:
    """Callback for bulletin updates - simple message forwarding"""

    async def register(self, conn):
        """Registering does not require special handling"""
        pass

    async def message(self, conn, data):
        """Directly forward the bulletin ID"""
        return data

    async def unregister(self, conn):
        """Unsubscribing does not require special handling"""
        pass


_bulletin_callback = BulletinCallback()
UnifiedWebSocketHandler.register_channel_callback("bulletinsub", _bulletin_callback)


class BulletinHandler(RequestHandler):
    @reqenv
    async def get(self, bulletin_id=None):
        if bulletin_id is None:
            can_submit = JudgeServerClusterService.inst.is_server_online()
            _, bulletin_list = await BulletinService.inst.list_bulletin()
            bulletin_list.sort(key=lambda b: (b['pinned'], b['timestamp']), reverse=True)

            await self.render('info', bulletin_list=bulletin_list, judge_server_status=can_submit)
            return

        bulletin_id = int(bulletin_id)
        err, bulletin = await BulletinService.inst.get_bulletin(bulletin_id)
        if err:
            return self.error(err)

        await self.render('bulletin', bulletin=bulletin)

