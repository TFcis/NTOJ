import tornado

from handlers.base import RequestHandler, reqenv, require_permission
from services.log import LogService
from services.pro import ProClassService

from services.user import UserConst


class ManageProClassHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self, page=None):
        if page is None:
            _, pubclass_list = await ProClassService.inst.get_pubclass_list()
            await self.render('manage/proclass/proclass-list', page='proclass',
                              pubclass_list=pubclass_list)

        elif page == "add":
            await self.render('manage/proclass/add', page='proclass')

        elif page == "update":
            pubclass_id = int(self.get_argument('pubclassid'))
            _, pubclass = await ProClassService.inst.get_pubclass(pubclass_id)

            await self.render('manage/proclass/update', page='proclass', pubclass_id=pubclass_id,
                              pubclass=pubclass)

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self, page=None):
        reqtype = self.get_argument('reqtype')
        if page == "add" and reqtype == 'add':
            name = self.get_argument('name')
            p_list_str = self.get_argument('list')
            p_list_str = p_list_str.replace(' ', '').split(',')
            p_list = []
            for p_id in p_list_str:
                try:
                    p_list.append(int(p_id))

                except ValueError:
                    pass

            if len(p_list) == 0:
                await self.error('E')
                return

            await LogService.inst.add_log(f"{self.acct.name} add proclass name={name} list={p_list}", 'manage.proclass.add')
            err, pubclass_id = await ProClassService.inst.add_pubclass(name, p_list)
            if err:
                self.error(err)
                return

            self.finish(str(pubclass_id))

        elif page == "update" and reqtype == "update":
            pubclass_id = int(self.get_argument('pubclass_id'))
            name = self.get_argument('name')
            p_list_str = self.get_argument('list')
            p_list_str = p_list_str.replace(' ', '').split(',')
            p_list = []
            for p_id in p_list_str:
                try:
                    p_list.append(int(p_id))

                except ValueError:
                    pass

            if len(p_list) == 0:
                await self.error('E')
                return

            await LogService.inst.add_log(f"{self.acct.name} update proclass name={name} list={p_list}", 'manage.proclass.update')
            err = await ProClassService.inst.update_pubclass(pubclass_id, name, p_list)
            if err:
                await self.error(err)
                return

            self.finish('S')

        elif page == "update" and reqtype == "remove":
            pubclass_id = int(self.get_argument('pubclass_id'))
            _, pubclass = await ProClassService.inst.get_pubclass(pubclass_id)

            await LogService.inst.add_log(
                f"{self.acct.name} remove proclass name={pubclass['name']}.", 'manage.proclass.remove')
            await ProClassService.inst.remove_pubclass(pubclass_id)

            self.finish('S')
