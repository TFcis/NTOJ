import tornado

from handlers.base import RequestHandler, reqenv, require_permission
from services.group import GroupService, GroupConst
from services.log import LogService
from services.user import UserConst


class ManageGroupHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self):
        try:
            gname = str(self.get_argument('gname'))

            async with self.db.acquire() as con:
                result = await con.fetchrow(
                    '''
                        SELECT "group"."group_type", "group"."group_class"
                        FROM "group"
                        WHERE "group"."group_name" = $1
                    ''',
                    gname
                )
            gtype = int(result['group_type'])
            gclas = int(result['group_class'])

        except tornado.web.HTTPError:
            gname = None
            gtype = None
            gclas = None

        glist = await GroupService.inst.list_group()
        if gname is not None:
            gacct = await GroupService.inst.list_acct_in_group(gname)
        else:
            gacct = None

        await self.render('manage/group', page='group', gname=gname, glist=glist, gacct=gacct, gtype=gtype,
                          gclas=gclas)

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        reqtype = str(self.get_argument('reqtype'))
        if reqtype == 'edit':
            gname = str(self.get_argument('gname'))
            gtype = int(self.get_argument('gtype'))
            gclas = int(self.get_argument('gclas'))
            if gname == GroupConst.KERNEL_GROUP:
                self.error('Ekernel')
                return

            await LogService.inst.add_log(
                f"{self.acct.name} updated group={gname} group_type={gtype} group_class={gclas}.",
                'manage.group.update')
            err = await GroupService.inst.update_group(gname, gtype, gclas)
            if err:
                self.error(err)
                return

            self.finish('S')

        elif reqtype == 'add_group':
            gname = str(self.get_argument('gname'))
            gtype = int(self.get_argument('gtype'))
            gclas = int(self.get_argument('gclas'))

            await LogService.inst.add_log(
                f"{self.acct.name} added group={gname} group_type={gtype} group_class={gclas}.",
                'manage.group.add')
            err = await GroupService.inst.add_group(gname, gtype, gclas)
            if err:
                self.error(err)
                return

            self.finish('S')

        elif reqtype == 'del_group':
            gname = str(self.get_argument('gname'))
            if gname in [GroupConst.KERNEL_GROUP, GroupConst.DEFAULT_GROUP]:
                self.error('Ekernel')
                return

            await LogService.inst.add_log(f"{self.acct.name} deleted group={gname}", 'manage.group.delete')
            err = await GroupService.inst.del_group(gname)
            if err:
                self.error(err)
                return

            self.finish('S')
            return
