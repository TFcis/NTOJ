import os
import tornado.web

from handlers.base import ActionDispatcher, RequestHandler, reqenv, require_permission
from services.chal import ChalConst
from services.judge import JudgeServerClusterService
from services.pro import ProClassService, ProClassConst, ProConst, ProService, Problem
from services.rate import RateService
from services.user import UserService, UserConst, GUEST_ACCOUNT

PERMISSION_DENIED_ERROR = ("Eacces", "Permission denied")

pro_dispatcher = ActionDispatcher()


class ProsetHandler(RequestHandler):
    @reqenv
    async def get(self):
        try:
            pageoff = int(self.get_argument("pageoff", default="0"))
            if pageoff < 0:
                pageoff = 0
        except ValueError:
            return self.error(("Eparam", "Invalid page offset"))

        order = self.get_argument("order", default=None)
        problem_show = self.get_argument("show", default="all")
        show_only_online_pro = self.get_argument("online", default=None)
        order_reverse = self.get_argument("reverse", default=None)
        search_name = self.get_argument("name", default=None)
        search_tags = self.get_argument("tags", default=None)
        topcoder_filter = self.get_argument("topcoder", default="ignore")

        flt = {
            "order": order,
            "problem_show": problem_show,
            "online": show_only_online_pro,
            "reverse": order_reverse,
            "name": search_name,
            "tags": search_tags,
            "topcoder_filter": topcoder_filter,
        }
        if search_name:
            search_name = search_name.lower()
        if search_tags:
            search_tags = search_tags.lower()

        proclass_id = self.get_argument("proclass_id", default=None)
        try:
            proclass_id = int(proclass_id)
        except ValueError:
            return self.error(("Eparam", "Invalid problem class ID"))
        except TypeError:
            pass

        try:
            topcoder_filter = int(topcoder_filter)
            if topcoder_filter <= GUEST_ACCOUNT.acct_id:
                return self.error(("Eparam", "Invalid topcoder filter"))
        except ValueError:
            pass

        allow_statuses = ProConst.PRO_STATUS_NORMAL_USER
        if self.acct.is_kernel():
            allow_statuses = ProConst.PRO_STATUS_KERNEL_USER
        err, prolist = await ProService.inst.list_pro(allow_statuses)

        proclass = None
        if proclass_id:
            err, proclass = await ProClassService.inst.get_proclass(proclass_id)
            if err:
                return self.error(err)
            proclass = dict(proclass)

            if (
                proclass["type"] == ProClassConst.OFFICIAL_HIDDEN
                and not self.acct.is_kernel()
            ):
                return self.error(PERMISSION_DENIED_ERROR)
            elif (
                proclass["type"] == ProClassConst.USER_HIDDEN
                and proclass["acct_id"] != self.acct.acct_id
            ):
                return self.error(PERMISSION_DENIED_ERROR)

            p_list = proclass["list"]
            prolist = list(filter(lambda pro: pro.pro_id in p_list, prolist))
            if proclass["acct_id"]:
                _, creator = await UserService.inst.info_acct(proclass["acct_id"])
                proclass["creator_name"] = creator.name

        _, acct_states = await RateService.inst.map_rate_acct(self.acct)
        score_map: dict[int, dict] = {}
        ac_pro_cnt = 0
        new_prolist: list[Problem] = []
        pro_2_topcoder: dict[int, int] = {}
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

            if (self.acct.is_guest()) or (
                not self.acct.is_kernel() and pro_state != ChalConst.STATE_AC
            ):
                pro.tags = ""

            if search_tags and pro.tags.lower().find(search_tags) == -1:
                continue

            if topcoder_filter != "ignore":
                _, topcoder_id = await RateService.inst.get_pro_topcoder(pro_id)
                pro_2_topcoder[pro_id] = topcoder_id
                if topcoder_filter == "myself":
                    if topcoder_id != self.acct.acct_id:
                        continue

                elif topcoder_filter == "other":
                    if topcoder_id == self.acct.acct_id:
                        continue

                elif topcoder_filter != topcoder_id:
                    continue

            rate = None
            if order is not None:
                _, rate = await RateService.inst.get_pro_ac_rate(pro_id)
            score_map[pro_id] = {"state": pro_state, "rate_data": rate}
            new_prolist.append(pro)

        prolist = new_prolist

        def user_ac_cmp(pro: Problem):
            pro_id = pro.pro_id
            user_ac_chal_cnt = score_map[pro_id]["rate_data"]["user_ac_chal_cnt"]
            user_all_chal_cnt = score_map[pro_id]["rate_data"]["user_all_chal_cnt"]

            if user_ac_chal_cnt and user_all_chal_cnt:
                return user_ac_chal_cnt / user_all_chal_cnt
            else:
                return -1

        def chal_ac_cmp(pro: Problem):
            pro_id = pro.pro_id
            ac_chal_cnt = score_map[pro_id]["rate_data"]["ac_chal_cnt"]
            all_chal_cnt = score_map[pro_id]["rate_data"]["all_chal_cnt"]

            if ac_chal_cnt and all_chal_cnt:
                return ac_chal_cnt / all_chal_cnt
            else:
                return -1

        def cmp(pro: Problem, key: str):
            return score_map[pro.pro_id]["rate_data"][key]

        if order == "chal":
            prolist = sorted(prolist, key=chal_ac_cmp)
        elif order == "user":
            prolist = sorted(prolist, key=user_ac_cmp)
        elif order == "chalcnt":
            prolist = sorted(prolist, key=lambda pro: cmp(pro, "all_chal_cnt"))
        elif order == "chalaccnt":
            prolist = sorted(prolist, key=lambda pro: cmp(pro, "ac_chal_cnt"))
        elif order == "usercnt":
            prolist = sorted(prolist, key=lambda pro: cmp(pro, "user_all_chal_cnt"))
        elif order == "useraccnt":
            prolist = sorted(prolist, key=lambda pro: cmp(pro, "user_ac_chal_cnt"))

        if order_reverse:
            prolist = reversed(prolist)

        prolist = list(prolist)
        pro_total_cnt = len(prolist)
        prolist = prolist[pageoff : pageoff + 40]

        acct_cache = {}
        for pro in prolist:
            pro_id = pro.pro_id

            topcoder, topcoder_id = None, None
            try:
                topcoder_id = pro_2_topcoder[pro_id]
            except KeyError:
                err, topcoder_id = await RateService.inst.get_pro_topcoder(pro_id)

            if topcoder_id is not None:
                try:
                    topcoder = acct_cache[topcoder_id]
                except KeyError:
                    err, topcoder = await UserService.inst.info_acct(topcoder_id)
                    if err is None:
                        acct_cache[topcoder_id] = topcoder

            score_map[pro_id]["topcoder"] = topcoder
            if order is None:
                _, rate = await RateService.inst.get_pro_ac_rate(pro_id)
                score_map[pro_id]["rate_data"] = rate

        await self.render(
            "proset",
            "Problems",
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

            elif proclass_type == "shared":
                proclass_list = list(
                    filter(
                        lambda proclass: proclass["type"] == ProClassConst.USER_PUBLIC,
                        proclass_list,
                    )
                )

            elif proclass_type == "collection":
                proclass_list = list(
                    filter(
                        lambda proclass: proclass["proclass_id"]
                        in self.acct.proclass_collection,
                        proclass_list,
                    )
                )

            elif proclass_type == "own":
                proclass_list = list(
                    filter(
                        lambda proclass: proclass["acct_id"] == self.acct.acct_id,
                        proclass_list,
                    )
                )

            else:
                self.error(("Eparam", "Wrong proclass_type"))
                return

            _, acct_states = await RateService.inst.map_rate_acct(self.acct)
            err, prolist = await ProService.inst.list_pro(
                self.acct.is_kernel()
                and ProConst.PRO_STATUS_KERNEL_USER
                or ProConst.PRO_STATUS_NORMAL_USER
            )
            if err:
                return self.error(err)
            pro_exists = {pro.pro_id for pro in prolist}
            for i in range(len(proclass_list)):
                proclass_list[i] = dict(proclass_list[i])
                proclass = proclass_list[i]
                ac_cnt = 0
                err, p = await ProClassService.inst.get_proclass(
                    proclass["proclass_id"]
                )
                if proclass["acct_id"]:
                    proclass["creator_name"] = accts[proclass["acct_id"]]

                total_cnt = len(p["list"])
                for pro_id in p["list"]:
                    if pro_id not in pro_exists:
                        total_cnt -= 1
                        continue
                    if pro_id in acct_states:
                        ac_cnt += acct_states[pro_id]["state"] == ChalConst.STATE_AC

                proclass["ac_cnt"] = ac_cnt
                proclass["total_cnt"] = total_cnt

            self.error(("S", proclass_list))

        elif reqtype == "collect":
            if self.acct.is_guest():
                return self.error(("Eacces", "Please login"))

            try:
                proclass_id = int(self.get_argument("proclass_id"))
            except ValueError:
                return self.error(("Eparam", "Invalid problem class ID"))

            if proclass_id in self.acct.proclass_collection:
                return self.error(("Eexist", "Problem class is already collected"))

            self.acct.proclass_collection.append(proclass_id)
            self.acct.proclass_collection.sort()
            await UserService.inst.update_acct(self.acct)
            self.error(("S", ""))

        elif reqtype == "decollect":
            if self.acct.is_guest():
                return self.error(("Eacces", "Please login"))

            try:
                proclass_id = int(self.get_argument("proclass_id"))
            except ValueError:
                return self.error(("Eparam", "Invalid problem class ID"))

            if proclass_id not in self.acct.proclass_collection:
                return self.error(("Enoext", "Problem class is not in your collection"))

            self.acct.proclass_collection.remove(proclass_id)
            self.acct.proclass_collection.sort()
            await UserService.inst.update_acct(self.acct)
            self.error(("S", ""))


class ProStaticHandler(RequestHandler, tornado.web.StaticFileHandler):
    @reqenv
    async def get(self, pro_id: int = None, path: str = None):
        if path is None:
            return self.error(("Eparam", "Path is required"))

        try:
            pro_id = int(pro_id)
        except (ValueError, TypeError):
            return self.error(("Eparam", "Invalid problem ID"))

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

            allow_statuses = ProConst.PRO_STATUS_CONTEST_USER
        else:
            if self.acct.is_kernel():
                allow_statuses = ProConst.PRO_STATUS_KERNEL_USER

        err, _ = await ProService.inst.get_pro(pro_id, allow_statuses)
        if err:
            if err[0] == "Enoext":
                self.set_status(404)
            elif err[0] == "Eacces":
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
    async def get(self, pro_id: int = None):
        try:
            pro_id = int(pro_id)
        except (ValueError, TypeError):
            return self.error(("Eparam", "Invalid problem ID"))
        allow_statuses = ProConst.PRO_STATUS_NORMAL_USER

        if self.contest:
            if not self.contest.is_pro(pro_id):
                return self.error(("Enoext", "Problem not in contest"))

            if not self.contest.is_member(self.acct):
                return self.error(PERMISSION_DENIED_ERROR)

            if not self.contest.is_admin(self.acct) and not self.contest.is_running():
                return self.error(PERMISSION_DENIED_ERROR)

            allow_statuses = ProConst.PRO_STATUS_CONTEST_USER

        else:
            if self.acct.is_kernel():
                allow_statuses = ProConst.PRO_STATUS_KERNEL_USER

        err, pro = await ProService.inst.get_pro(pro_id, allow_statuses)
        if err:
            return self.error(err)

        prev_pro_id = None
        next_pro_id = None

        proclass_id = self.get_argument("proclass_id", default=None)
        cur_proclass = None

        if self.contest:
            pro_ids = list(self.contest.pro_list.keys())
            idx = pro_ids.index(pro_id)
            if idx > 0:
                prev_pro_id = pro_ids[idx - 1]
            if idx < len(pro_ids) - 1:
                next_pro_id = pro_ids[idx + 1]
        elif proclass_id:
            try:
                proclass_id = int(proclass_id)
                err, cur_proclass = await ProClassService.inst.get_proclass(proclass_id)
                if not err and cur_proclass:
                    cur_proclass = dict(cur_proclass)
                    p_list = cur_proclass.get("list", [])

                    if pro_id in p_list:
                        _, valid_pros = await ProService.inst.list_pro(allow_statuses)
                        valid_pro_ids = {p.pro_id for p in valid_pros}

                        ordered_ids = [pid for pid in p_list if pid in valid_pro_ids]

                        if pro_id in ordered_ids:
                            idx = ordered_ids.index(pro_id)
                            if idx > 0:
                                prev_pro_id = ordered_ids[idx - 1]
                            if idx < len(ordered_ids) - 1:
                                next_pro_id = ordered_ids[idx + 1]
                    else:
                        cur_proclass = None
            except ValueError:
                cur_proclass = None
        else:
            prev_pro_id, next_pro_id = await ProService.inst.get_pro_neighbours(pro_id, allow_statuses)

        # NOTE: Guest cannot see tags
        # NOTE: Admin can see tags
        # NOTE: User get ac can see tags

        if self.acct.is_guest():
            pro.tags = ""

        elif not self.acct.is_kernel():
            from services.chal import ChalService

            err, state = await ChalService.inst.check_acct_pro_state(
                self.acct.acct_id, pro.pro_id
            )
            if err:
                return self.error(err)

            if state is None or state != ChalConst.STATE_AC:
                pro.tags = ""

        can_submit = JudgeServerClusterService.inst.is_server_online()
        topcoder = None
        if not self.contest:
            err, topcoder_id = await RateService.inst.get_pro_topcoder(pro_id)
            if err:
                return self.error(err)

            if topcoder_id:
                err, topcoder = await UserService.inst.info_acct(topcoder_id)
                if err:
                    return self.error(err)

        await self.render(
            "pro",
            f"{pro_id} - {pro.name}",
            pro=pro,
            can_submit=can_submit,
            contest=self.contest,
            topcoder=topcoder,
            prev_pro_id=prev_pro_id,
            next_pro_id=next_pro_id,
            cur_proclass=cur_proclass,
        )


class ProTagsHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self):
        tags = self.get_argument("tags")
        pro_id = int(self.get_argument("pro_id"))

        allow_statuses = ProConst.PRO_STATUS_KERNEL_USER
        if self.contest:
            allow_statuses = ProConst.PRO_STATUS_CONTEST_USER

        err, pro = await ProService.inst.get_pro(pro_id, allow_statuses)
        if err:
            return self.error(err)

        await self.add_log(
            (
                self.acct.name
                + " updated the tag of problem #"
                + str(pro_id)
                + ' to: "'
                + str(tags)
                + '".'
            ),
            "manage.pro.update.tag",
        )

        pro.tags = tags
        err, _ = await ProService.inst.update_pro(pro)

        if err:
            return self.error(err)

        self.error(("S", ""))
