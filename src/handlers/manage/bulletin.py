import tornado.web

from handlers.base import RequestHandler, reqenv, require_permission
from services.bulletin import BulletinService
from services.log import LogService
from services.user import UserConst


class ManageBulletinHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self, page=None):
        if page is None:
            _, bulletin_list = await BulletinService.inst.list_bulletin()
            await self.render('manage/bulletin/bulletin-list', page='bulletin', bulletin_list=bulletin_list)

        elif page == "update":
            bulletin_id = int(self.get_argument('bulletinid'))
            _, bulletin = await BulletinService.inst.get_bulletin(bulletin_id)

            await self.render('manage/bulletin/update', page='bulletin', bulletin_id=bulletin_id, bulletin=bulletin)

        elif page == "add":
            await self.render('manage/bulletin/add', page='bulletin')

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self, page=None):
        reqtype = self.get_argument('reqtype')

        if page == 'add' and reqtype == 'add':
            title = self.get_argument('title')
            content = self.get_argument('content')
            pinned = self.get_argument('pinned')
            if pinned == "false":
                pinned = False
            elif pinned == "true":
                pinned = True
            else:
                pinned = False

            color = self.get_argument('color')
            await BulletinService.inst.add_bulletin(title, content, self.acct.acct_id, color, pinned)

            await LogService.inst.add_log(
                f"{self.acct.name} added a line on bulletin: \"{title}\".", 'manage.inform.add'
            )

        elif page == 'update' and reqtype == 'update':
            bulletin_id = int(self.get_argument('bulletin_id'))
            title = self.get_argument('title')
            content = self.get_argument('content')
            pinned = self.get_argument('pinned')
            if pinned == "false":
                pinned = False
            elif pinned == "true":
                pinned = True
            else:
                pinned = False
            color = self.get_argument('color')

            await LogService.inst.add_log(
                f"{self.acct.name} updated a line on bulletin: \"{title}\" which id is #{bulletin_id}.",
                'manage.inform.update',
            )
            await BulletinService.inst.edit_bulletin(bulletin_id, title, content, self.acct.acct_id, color, pinned)

        elif page == 'update' and reqtype == 'remove':
            bulletin_id = int(self.get_argument('bulletin_id'))
            await LogService.inst.add_log(
                f"{self.acct.name} removed a line on bulletin which id is #{bulletin_id}.", 'manage.inform.remove'
            )
            await BulletinService.inst.del_bulletin(bulletin_id)
