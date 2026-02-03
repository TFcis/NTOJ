import os
import tornado.web

from handlers.base import ActionDispatcher, RequestHandler, reqenv, require_permission
from services.chal import ChalConst
from services.judge import JudgeServerClusterService
from services.log import LogService
from services.pro import ProClassService, ProClassConst, ProConst, ProService, Problem
from services.rate import RateService
from services.user import UserService, UserConst
from services.contests import ContestMode

PERMISSION_DENIED_ERROR = ("Eacces", "Permission denied")

pro_dispatcher = ActionDispatcher()


class ProsetHandler(RequestHandler):
    @reqenv
    async def get(self):
        pageoff = int(self.get_argument("pageoff", default=0))
        problem_show = self.get_argument("show", default="all")
        show_only_online_pro = self.get_argument("online", default=False)
        order_reverse = self.get_argument("reverse", default=False)
        search_name = self.get_argument("name", default=None)

        flt = {
            "problem_show": problem_show,
            "online": show_only_online_pro,
            "reverse": order_reverse,
            "name": search_name,
        }
        if search_name:
            search_name = search_name.lower()

        proclass_id = int(self.get_argument("proclass_id", default=0))
        if proclass_id == 0:
            proclass_id = None

        allow_statuses = ProConst.PRO_STATUS_NORMAL_USER
        if self.acct.is_kernel():
            allow_statuses = ProConst.PRO_STATUS_KERNEL_USER
        err, prolist = await ProService.inst.list_pro(allow_statuses)

        proclass = None
        if proclass_id:
            if not self.acct.is_kernel():
                return self.error(PERMISSION_DENIED_ERROR)

            err, proclass = await ProClassService.inst.get_proclass(proclass_id)
            if err:
                return self.error(err)
            proclass = dict(proclass)

            p_list = proclass["list"]
            prolist = list(filter(lambda pro: pro.pro_id in p_list, prolist))
            if proclass["acct_id"]:
                _, creator = await UserService.inst.info_acct(proclass["acct_id"])
                proclass["creator_name"] = creator.name

        _, acct_states = await RateService.inst.map_rate_acct(self.acct)
        score_map: dict[int, dict] = {}
        ac_pro_cnt = 0
        new_prolist: list[Problem] = []
        for pro in prolist:
            pro_id = pro.pro_id
            pro_state = acct_states.get(pro_id, {}).get("state")
            ac_pro_cnt += pro_state == ChalConst.STATE_AC

            if show_only_online_pro and pro.status != ProConst.STATUS_ONLINE:
                continue

            if problem_show == "onlyac" and pro_state != ChalConst.STATE_AC:
                continue

            elif problem_show == "notac" and pro_state == ChalConst.STATE_AC:
                continue

            if search_name and pro.name.lower().find(search_name) == -1:
                continue

            score_map[pro_id] = {"state": pro_state}
            new_prolist.append(pro)

        prolist = new_prolist

        if order_reverse:
            prolist = reversed(prolist)

        prolist = list(prolist)
        pro_total_cnt = len(prolist)
        prolist = prolist[pageoff : pageoff + 40]

        await self.render(
            "proset",
            user=self.acct,
            pro_total_cnt=pro_total_cnt,
            ac_pro_cnt=ac_pro_cnt,
            prolist=prolist,
            score_map=score_map,
            cur_proclass=proclass,
            pageoff=pageoff,
            flt=flt,
        )

    @reqenv
    async def post(self):
        reqtype = self.get_argument("reqtype")
        if reqtype == "listproclass":
            if not self.acct.is_kernel():
                self.error(PERMISSION_DENIED_ERROR)
                return

            proclass_type = self.get_argument("proclass_type")
            _, proclass_list = await ProClassService.inst.get_proclass_list()

            _, accts = await UserService.inst.list_acct(UserConst.ACCTTYPE_KERNEL)
            accts = {acct.acct_id: acct.name for acct in accts}

            if proclass_type == "official":
                if self.acct.is_kernel():
                    proclass_list = list(
                        filter(
                            lambda proclass: proclass["type"]
                            in (
                                ProClassConst.OFFICIAL_PUBLIC,
                                ProClassConst.OFFICIAL_HIDDEN,
                            ),
                            proclass_list,
                        )
                    )
                else:
                    proclass_list = list(
                        filter(
                            lambda proclass: proclass["type"]
                            == ProClassConst.OFFICIAL_PUBLIC,
                            proclass_list,
                        )
                    )
            else:
                self.error(("Eparam", "Wrong proclass_type"))
                return

            _, acct_states = await RateService.inst.map_rate_acct(self.acct)
            for i in range(len(proclass_list)):
                proclass_list[i] = dict(proclass_list[i])
                proclass = proclass_list[i]
                ac_cnt = 0
                err, p = await ProClassService.inst.get_proclass(
                    proclass["proclass_id"]
                )
                if proclass["acct_id"]:
                    proclass["creator_name"] = accts[proclass["acct_id"]]

                for pro_id in p["list"]:
                    if pro_id in acct_states:
                        ac_cnt += acct_states[pro_id]["state"] == ChalConst.STATE_AC

                proclass["ac_cnt"] = ac_cnt
                proclass["total_cnt"] = len(p["list"])
                proclass["list"] = p["list"]  # Include problem list for frontend use

            self.error(("S", proclass_list))

class ProStaticHandler(RequestHandler, tornado.web.StaticFileHandler):
    @reqenv
    async def get(self, pro_id: int, path: str):
        pro_id = int(pro_id)
        allow_statuses = ProConst.PRO_STATUS_NORMAL_USER
        if self.contest:
            if not self.contest.is_pro(pro_id):
                self.set_status(404)
                self.finish("Problem not in contest")
                return

            if not self.contest.is_member(self.acct):
                self.set_status(403)
                self.finish(PERMISSION_DENIED_ERROR[1])
                return

            if not self.contest.is_admin(self.acct) and not self.contest.is_running():
                self.set_status(403)
                self.finish(PERMISSION_DENIED_ERROR[1])
                return

            if self.contest.contest_mode == ContestMode.RANDOM_SET and not self.contest.is_admin(self.acct):
                contest_prolist = self.contest.get_randomset_prolist(self.acct)
                if contest_prolist is None:
                    self.set_status(500)
                    self.finish("Problem set not allocated yet. Please contact admin.")
                    return

                if pro_id not in contest_prolist:
                    self.set_status(403)
                    self.finish(PERMISSION_DENIED_ERROR[1])
                    return

            allow_statuses = ProConst.PRO_STATUS_CONTEST_USER
        else:
            if self.acct.is_kernel():
                allow_statuses = ProConst.PRO_STATUS_KERNEL_USER

        err, _ = await ProService.inst.get_pro(pro_id, allow_statuses)
        if err:
            if err[0] == 'Enoext':
                self.set_status(404)
            elif err[0] == 'Eacces':
                self.set_status(403)
            else:
                self.set_status(500)
            self.finish(err[1])
            return

        if path.endswith("pdf"):
            self.set_header("Pragma", "public")
            self.set_header("Expires", "0")
            self.set_header(
                "Cache-Control", "must-revalidate, post-check=0, pre-check=0"
            )
            self.set_header("Content-Type", "application/pdf")

            download = self.get_argument("download", default=None)
            if download:
                self.set_header(
                    "Content-Disposition", f'attachment; filename="pro{pro_id}.pdf"'
                )
            else:
                self.set_header("Content-Disposition", "inline")

        if not self._is_file_access_safe(f"problem/{pro_id}/http/", path):
            self.set_status(403)
            self.finish(PERMISSION_DENIED_ERROR[1])
            return

        await super().get(f"{pro_id}/http/{path}")

    def _is_file_access_safe(self, basedir, filename):
        absolute_basepath = os.path.abspath(basedir)
        absolute_filepath = os.path.abspath(os.path.join(basedir, filename))
        if os.path.commonpath([absolute_basepath]) != os.path.commonpath(
            [absolute_basepath, absolute_filepath]
        ):
            return False
        if os.path.exists(absolute_filepath):
            return os.path.isfile(absolute_filepath) and not os.path.islink(
                absolute_filepath
            )
        return True


class ProHandler(RequestHandler):
    @reqenv
    async def get(self, pro_id):
        pro_id = int(pro_id)
        allow_statuses = ProConst.PRO_STATUS_NORMAL_USER

        if self.contest:
            if not self.contest.is_pro(pro_id):
                return self.error(("Enoext", "Problem not in contest"))

            if not self.contest.is_member(self.acct):
                return self.error(PERMISSION_DENIED_ERROR)

            if not self.contest.is_admin(self.acct) and not self.contest.is_running():
                return self.error(PERMISSION_DENIED_ERROR)

            if self.contest.contest_mode == ContestMode.RANDOM_SET and not self.contest.is_admin(self.acct):
                contest_prolist = self.contest.get_randomset_prolist(self.acct)
                if contest_prolist is None:
                    return self.error(('Enopro', 'Problem set not allocated yet. Please contact admin.'))
                if pro_id not in contest_prolist:
                    return self.error(PERMISSION_DENIED_ERROR)

            allow_statuses = ProConst.PRO_STATUS_CONTEST_USER

        else:
            if self.acct.is_kernel():
                allow_statuses = ProConst.PRO_STATUS_KERNEL_USER

        err, pro = await ProService.inst.get_pro(pro_id, allow_statuses)
        if err:
            return self.error(err)

        can_submit = JudgeServerClusterService.inst.is_server_online()
        await self.render(
            "pro",
            pro=pro,
            can_submit=can_submit,
            contest=self.contest,
        )
