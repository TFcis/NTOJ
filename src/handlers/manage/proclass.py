import tornado

from handlers.base import RequestHandler, reqenv, require_permission
from services.log import LogService
from services.pro import ProClassService, ProClassConst
from services.user import UserConst
from utils.numeric import parse_list_str


class ManageProClassHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self, page=None):
        if page is None:
            try:
                pageoff = int(self.get_argument('pageoff'))
            except tornado.web.HTTPError:
                pageoff = 0

            _, proclass_list = await ProClassService.inst.get_proclass_list()
            proclass_list = list(filter(lambda proclass: proclass['type'] in [ProClassConst.OFFICIAL_PUBLIC, ProClassConst.OFFICIAL_HIDDEN],
                        proclass_list))
            proclass_total_cnt = len(proclass_list)
            proclass_list = proclass_list[pageoff: pageoff + 20]

            await self.render('manage/proclass/proclass-list', page='proclass', proclass_list=proclass_list,
                              pageoff=pageoff, proclass_total_cnt=proclass_total_cnt)

        elif page == "add":
            await self.render('manage/proclass/add', page='proclass')

        elif page == "update":
            proclass_id = int(self.get_argument('proclassid'))
            _, proclass = await ProClassService.inst.get_proclass(proclass_id)
            if proclass['type'] not in [ProClassConst.OFFICIAL_PUBLIC, ProClassConst.OFFICIAL_HIDDEN]:
                self.error(('Eacces', 'Permission denied'))
                return

            await self.render('manage/proclass/update', page='proclass', proclass_id=proclass_id, proclass=proclass)


    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self, page=None):
        reqtype = self.get_argument('reqtype')
        if page == "add" and reqtype == 'add':
            name = self.get_argument('name')
            desc = self.get_argument('desc')
            proclass_type = int(self.get_argument('type'))
            p_list_str = self.get_argument('list')
            p_list = parse_list_str(p_list_str)

            if proclass_type not in [ProClassConst.OFFICIAL_PUBLIC, ProClassConst.OFFICIAL_HIDDEN]:
                self.error(('Eparam', 'Invalid problem class type'))
                return

            if len(p_list) == 0:
                self.error(('Eparam', 'Problem list should not be empty'))
                return

            await LogService.inst.add_log(
                f"{self.acct.name} add proclass name={name}", 'manage.proclass.add',
                {
                    "list": p_list,
                    "desc": desc,
                    "proclass_type": proclass_type,
                }
            )
            err, proclass_id = await ProClassService.inst.add_proclass(name, p_list, desc, None, proclass_type)
            if err:
                self.error(err)
                return

            self.error(('S', proclass_id))

        elif page == "update" and reqtype == "update":
            proclass_id = int(self.get_argument('proclass_id'))
            name = self.get_argument('name')
            desc = self.get_argument('desc')
            proclass_type = int(self.get_argument('type'))
            p_list_str = self.get_argument('list')
            p_list = parse_list_str(p_list_str)

            _, proclass = await ProClassService.inst.get_proclass(proclass_id)
            if proclass['type'] not in [ProClassConst.OFFICIAL_PUBLIC, ProClassConst.OFFICIAL_HIDDEN]:
                await LogService.inst.add_log(
                    f"{self.acct.name} tried to update proclass name={proclass['name']}, but an admin cannot modify a user's own proclass", 'manage.proclass.update.failed'
                )
                self.error(('Eacces', 'Permission denied'))
                return

            if proclass_type not in [ProClassConst.OFFICIAL_PUBLIC, ProClassConst.OFFICIAL_HIDDEN]:
                self.error(('Eparam', 'Invalid problem class type'))
                return

            if len(p_list) == 0:
                self.error(('Eparam', 'Problem list should not be empty'))
                return

            await LogService.inst.add_log(
                f"{self.acct.name} update proclass name={name}", 'manage.proclass.update',
                {
                    "list": p_list,
                    "desc": desc,
                    "proclass_type": proclass_type,
                }
            )
            err = await ProClassService.inst.update_proclass(proclass_id, name, p_list, desc, proclass_type)
            if err:
                self.error(err)
                return

            self.error(('S', ''))

        elif page == "update" and reqtype == "remove":
            proclass_id = int(self.get_argument('proclass_id'))
            err, proclass = await ProClassService.inst.get_proclass(proclass_id)

            if err:
                self.error(err)
                return

            if proclass['type'] not in [ProClassConst.OFFICIAL_PUBLIC, ProClassConst.OFFICIAL_HIDDEN]:
                await LogService.inst.add_log(
                    f"{self.acct.name} tried to remove proclass name={proclass['name']}, but an admin cannot modify a user's own proclass", 'manage.proclass.remove.failed'
                )
                self.error(('Eacces', 'Permission denied'))
                return

            await LogService.inst.add_log(
                f"{self.acct.name} remove proclass name={proclass['name']}.", 'manage.proclass.remove'
            )
            await ProClassService.inst.remove_proclass(proclass_id)

            self.error(('S', ''))
