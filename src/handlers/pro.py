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

        proclass_id = self.get_argument("proclass_id", default=None)
        try:
            proclass_id = int(proclass_id)
            flt["proclass_id"] = proclass_id
        except ValueError:
            return self.error(("Eparam", "Invalid problem class ID"))
        except TypeError:
            pass

        if topcoder_filter == "myself":
            if self.acct.is_guest():
                topcoder_filter = "ignore"
            else:
                topcoder_filter = str(self.acct.acct_id)
        elif topcoder_filter != "ignore":
            try:
                tf_id = int(topcoder_filter)
                if tf_id <= GUEST_ACCOUNT.acct_id:
                    topcoder_filter = "ignore"
            except (ValueError, TypeError):
                topcoder_filter = "ignore"

        flt["topcoder_filter"] = topcoder_filter

        allow_statuses = ProConst.PRO_STATUS_NORMAL_USER
        if self.acct.is_kernel():
            allow_statuses = ProConst.PRO_STATUS_KERNEL_USER

        err, prolist = await ProService.inst.list_filtered_pro(
            self.acct.acct_id, flt, allow_statuses
        )
        if err:
            return self.error(err)

        proclass = None
        if proclass_id:
            err, proclass = await ProClassService.inst.get_proclass(proclass_id)
            if err:
                return self.error(err)
            proclass = dict(proclass)
            if proclass["acct_id"]:
                _, creator = await UserService.inst.info_acct(proclass["acct_id"])
                proclass["creator_name"] = creator.name

        _, acct_states = await RateService.inst.map_rate_acct(self.acct)
        ac_pro_cnt = sum(
            1 for pro in prolist if acct_states.get(pro.pro_id, {}).get("state") == ChalConst.STATE_AC
        )

        all_pro_ids = [pro.pro_id for pro in prolist]
        pro_total_cnt = len(all_pro_ids)

        prolist = prolist[pageoff : pageoff + 40]

        score_map: dict[int, dict] = {}
        acct_cache = {}
        for pro in prolist:
            pro_id = pro.pro_id
            pro_state = acct_states.get(pro_id, {}).get("state")

            topcoder, topcoder_id = None, None
            err, topcoder_id = await RateService.inst.get_pro_topcoder(pro_id)

            if topcoder_id is not None:
                try:
                    topcoder = acct_cache[topcoder_id]
                except KeyError:
                    err, topcoder = await UserService.inst.info_acct(topcoder_id)
                    if err is None:
                        acct_cache[topcoder_id] = topcoder

            _, rate = await RateService.inst.get_pro_ac_rate(pro_id)
            score_map[pro_id] = {
                "state": pro_state,
                "rate_data": rate,
                "topcoder": topcoder,
            }

        await self.render(
            "proset",
            "Problems",
            user=self.acct,
            pro_total_cnt=pro_total_cnt,
            ac_pro_cnt=ac_pro_cnt,
            all_pro_ids=all_pro_ids,
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
        all_pro_ids = []

        if self.contest:
            pro_ids = list(self.contest.pro_list.keys())
            idx = pro_ids.index(pro_id)
            if idx > 0:
                prev_pro_id = pro_ids[idx - 1]
            if idx < len(pro_ids) - 1:
                next_pro_id = pro_ids[idx + 1]
        else:
            proclass_id = self.get_argument("proclass_id", default=None)
            order = self.get_argument("order", default=None)
            problem_show = self.get_argument("show", default="all")
            show_only_online_pro = self.get_argument("online", default=None)
            order_reverse = self.get_argument("reverse", default=None)
            search_name = self.get_argument("name", default=None)
            search_tags = self.get_argument("tags", default=None)
            topcoder_filter = self.get_argument("topcoder", default="ignore")

            clean_flt = {}
            if order and order != "None": clean_flt["order"] = str(order)
            if problem_show and problem_show != "all": clean_flt["show"] = str(problem_show)
            if show_only_online_pro: clean_flt["online"] = str(show_only_online_pro)
            if order_reverse: clean_flt["reverse"] = str(order_reverse)
            if search_name and search_name.strip(): clean_flt["name"] = str(search_name).strip()
            if search_tags and search_tags.strip(): clean_flt["tags"] = str(search_tags).strip()
            if topcoder_filter and str(topcoder_filter) != "ignore": clean_flt["topcoder"] = str(topcoder_filter)
            if proclass_id and str(proclass_id) != "None": clean_flt["proclass_id"] = str(proclass_id)

            current_query_key = "&".join(f"{k}={v}" for k, v in sorted(clean_flt.items()))
            cached_query_key = self.get_cookie("cached_filter_query")

            if not clean_flt:
                prev_pro_id, next_pro_id = await ProService.inst.get_pro_neighbours(pro_id, allow_statuses)
            elif cached_query_key is not None and cached_query_key == current_query_key:
                pass
            else:
                flt = {
                    "order": order,
                    "problem_show": problem_show,
                    "online": show_only_online_pro,
                    "reverse": order_reverse,
                    "name": search_name,
                    "tags": search_tags,
                    "topcoder_filter": topcoder_filter,
                }
                if proclass_id:
                    try:
                        flt["proclass_id"] = int(proclass_id)
                    except ValueError:
                        pass

                try:
                    if topcoder_filter != "ignore":
                        topcoder_filter = int(topcoder_filter)
                        if topcoder_filter <= GUEST_ACCOUNT.acct_id:
                            return self.error(("Eparam", "Invalid topcoder filter"))
                        flt["topcoder_filter"] = topcoder_filter
                except ValueError:
                    pass

                err, filtered_prolist = await ProService.inst.list_filtered_pro(self.acct.acct_id, flt, allow_statuses)
                if not err and filtered_prolist:
                    all_pro_ids = [p.pro_id for p in filtered_prolist]
                    if pro_id in all_pro_ids:
                        idx = all_pro_ids.index(pro_id)
                        if idx > 0:
                            prev_pro_id = all_pro_ids[idx - 1]
                        if idx < len(all_pro_ids) - 1:
                            next_pro_id = all_pro_ids[idx + 1]

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
            all_pro_ids=all_pro_ids,
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
