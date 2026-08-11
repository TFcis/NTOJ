from handlers.base import ActionDispatcher, RequestHandler, reqenv, require_permission
from services.bulletin import BulletinConst, BulletinService
from services.user import UserConst


bulletin_dispatcher = ActionDispatcher()


class ManageBulletinHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self, page=None):
        if page is None:
            _, bulletin_list = await BulletinService.inst.list_bulletin()
            await self.render('manage/bulletin/bulletin-list', "Manage Bulletins",
                              page='bulletin', bulletin_list=bulletin_list)

        elif page == "update":
            try:
                bulletin_id = int(self.get_argument('bulletin_id'))
            except ValueError:
                return self.error(('Eparam', 'Invalid bulletin ID'))
            err, bulletin = await BulletinService.inst.get_bulletin(bulletin_id)
            if err:
                return self.error(err)

            await self.render('manage/bulletin/update', f"Update Bulletin {bulletin['title']}(#{bulletin_id})",
                              page='bulletin', bulletin_id=bulletin_id, bulletin=bulletin)

        elif page == "add":
            await self.render('manage/bulletin/add', "Add Bulletin", page='bulletin')

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self, page=None):
        reqtype = self.get_argument('reqtype')
        return await bulletin_dispatcher.dispatch(self, reqtype)

    @bulletin_dispatcher.action('add')
    async def add_bulletin(self):
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
        if err := self.len_check(title, BulletinConst.TITLE_MIN, BulletinConst.TITLE_MAX, 'Title'):
            return self.error(err)

        if err := self.len_check(content, BulletinConst.CONTENT_MIN, BulletinConst.CONTENT_MAX, 'Content'):
            return self.error(err)

        err, bulletin_id = await BulletinService.inst.add_bulletin(title, content, self.acct.acct_id, color, pinned)
        if err:
            return self.error(err)

        await self.add_log(
            f"{self.acct.name} added bulletin entry: \"{title}\"", 'manage.inform.add',
            {
                "content": content,
                "is_pinned": pinned,
                "color": color,
            }
        )
        await self.rs.publish('bulletinsub', 1)
        self.error(('S', bulletin_id))

    @bulletin_dispatcher.action('update')
    async def update_bulletin(self):
        try:
            bulletin_id = int(self.get_argument('bulletin_id'))
        except ValueError:
            return self.error(('Eparam', 'Invalid bulletin ID'))

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
        if err := self.len_check(title, BulletinConst.TITLE_MIN, BulletinConst.TITLE_MAX, 'Title'):
            return self.error(err)

        if err := self.len_check(content, BulletinConst.CONTENT_MIN, BulletinConst.CONTENT_MAX, 'Content'):
            return self.error(err)

        await self.add_log(
            f"{self.acct.name} updated bulletin entry #{bulletin_id}: \"{title}\"",
            'manage.inform.update',
            {
                "content": content,
                "is_pinned": pinned,
                "color": color,
            }
        )
        err, _ = await BulletinService.inst.edit_bulletin(bulletin_id, title, content, self.acct.acct_id, color, pinned)
        if err:
            return self.error(err)

        await self.rs.publish('bulletinsub', 1)
        self.error(('S', ''))

    @bulletin_dispatcher.action('remove')
    async def remove_bulletin(self):
        try:
            bulletin_id = int(self.get_argument('bulletin_id'))
        except ValueError:
            return self.error(('Eparam', 'Invalid bulletin ID'))

        await self.add_log(
            f"{self.acct.name} removed bulletin entry #{bulletin_id}", 'manage.inform.remove'
        )
        err, _ = await BulletinService.inst.del_bulletin(bulletin_id)
        if err:
            return self.error(err)

        await self.rs.publish('bulletinsub', 1)
        self.error(('S', ''))
