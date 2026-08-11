import re
import time
import copy
import math
import hashlib

from msgpack import packb, unpackb

import config
from handlers.base import ActionDispatcher, RequestHandler, reqenv, require_permission, UnifiedWebSocketHandler
from services.log import LogService
from services.pro import ProService, ProClassService, ProClassConst, ProConst
from services.rate import RateService
from services.user import UserConst, UserService
from services.chal import ChalConst
from utils.numeric import parse_str_to_list

PERMISSION_DENIED_ERROR = ("Eacces", "Permission denied")

base_url = config.BASE_URL.removesuffix("/")
if base_url == "":
    base_url = "/"


class AcctHandler(RequestHandler):
    @reqenv
    async def get(self, acct_id: int = None):
        try:
            acct_id = int(acct_id)
        except (ValueError, TypeError):
            return self.error(("Eparam", "Invalid account ID"))
        err, acct = await UserService.inst.info_acct(acct_id)
        if err:
            return self.error(err)

        acct.acct_type = UserConst.ACCTTYPE_USER
        err, rate_data = await RateService.inst.get_acct_rate_and_chal_cnt(acct)
        if err:
            return self.error(err)

        err, prolist = await ProService.inst.list_pro(ProConst.PRO_STATUS_NORMAL_USER)
        if err:
            return self.error(err)

        err, ratemap = await RateService.inst.map_rate_acct(acct)
        acct.acct_type = UserConst.ACCTTYPE_KERNEL

        prolist2 = []

        topcoder_map = await self.rs.hgetall("pro_topcoder")

        ac_pro_cnt = 0
        for pro in prolist:
            pro_id = pro.pro_id
            try:
                topcoder_id = unpackb(topcoder_map[str(pro_id)])
            except KeyError:
                _, topcoder_id = await RateService.inst.get_pro_topcoder(pro_id)
            tmp = {"pro_id": pro_id, "score": -1, "state": None, "is_topcoder": topcoder_id == acct_id}
            if pro_id in ratemap:
                tmp["score"] = ratemap[pro_id]["rate"]
                tmp["state"] = ratemap[pro_id]["state"]
                ac_pro_cnt += ratemap[pro_id]["state"] == ChalConst.STATE_AC

            prolist2.append(tmp)

        def chunk_list(la, size):
            for i in range(0, len(la), size):
                yield la[i : i + size]

        rate_data["rate"] = math.floor(rate_data["rate"])
        rate_data["ac_pro_cnt"] = ac_pro_cnt

        # force https, add by xiplus, 2018/8/24
        acct.photo = re.sub(r"^http://", "https://", acct.photo)
        acct.cover = re.sub(r"^http://", "https://", acct.cover)

        await self.render(
            "acct/profile",
            f"{acct.name}",
            acct=acct,
            rate=rate_data,
            total_pro_cnt=len(prolist),
            prolist=chunk_list(prolist2, 10),
        )


config_dispatcher = ActionDispatcher()


class AcctConfigHandler(RequestHandler):
    @reqenv
    @require_permission([UserConst.ACCTTYPE_USER, UserConst.ACCTTYPE_KERNEL])
    async def get(self, acct_id: int = None):
        try:
            acct_id = int(acct_id)
        except (ValueError, TypeError):
            return self.error(("Eparam", "Invalid account ID"))

        err, acct = await UserService.inst.info_acct(acct_id)
        if err:
            return self.error(err)

        session_keys = {}
        current_session_key = None
        if self.acct.acct_id == acct_id:
            current_session_key = hashlib.md5(self.get_cookie("id").encode()).hexdigest()
            for session_key, v in (
                await self.rs.hgetall(f"account_session@{acct_id}")
            ).items():
                session_key = hashlib.md5(session_key).hexdigest()
                session_keys[session_key] = unpackb(v)

        await self.render(
            "acct/acct-config",
            f"{self.acct.name}'s Account Config",
            acct=acct,
            session_keys=session_keys,
            current_session_key=current_session_key,
        )

    @reqenv
    @require_permission([UserConst.ACCTTYPE_USER, UserConst.ACCTTYPE_KERNEL])
    async def post(self):
        reqtype = self.get_argument("reqtype")
        try:
            self.target_acct_id = int(self.get_argument("acct_id"))
        except (ValueError, TypeError):
            return self.error(("Eparam", "Invalid account ID"))
        return await config_dispatcher.dispatch(self, reqtype)

    @config_dispatcher.action("profile")
    async def update_profile(self):
        name = self.get_argument("name")
        photo = self.get_argument("photo")
        cover = self.get_argument("cover")
        motto = self.get_argument("motto")

        if self.target_acct_id != self.acct.acct_id:
            return self.error(PERMISSION_DENIED_ERROR)

        self.acct.name = name
        self.acct.photo = photo
        self.acct.cover = cover
        self.acct.motto = motto
        err, _ = await UserService.inst.update_acct(self.acct)
        if err:
            return self.error(err)

        return self.error(("S", ""))

    @config_dispatcher.action("reset")
    async def reset_password(self):
        old = self.get_argument("old")
        pw = self.get_argument("pw")

        if not (self.acct.acct_id == self.target_acct_id or self.acct.is_kernel()):
            return self.error(PERMISSION_DENIED_ERROR)

        isadmin = self.acct.is_kernel() and (self.acct.acct_id != self.target_acct_id)
        err, _ = await UserService.inst.update_pw(self.target_acct_id, old, pw, isadmin)
        if err:
            return self.error(err)

        if not err and self.target_acct_id != self.acct.acct_id:
            await self.add_log(
                f"{self.acct.name} changed the password of account #{self.target_acct_id}",
                "manage.acct.update.pwd",
            )

        return self.error(("S", ""))

    @config_dispatcher.action("remote-logout")
    async def remote_logout(self):
        if self.target_acct_id != self.acct.acct_id:
            return self.error(PERMISSION_DENIED_ERROR)

        hashed_session_key = self.get_argument("hashed_session_key")
        found = False
        for session_key in await self.rs.hgetall(f"account_session@{self.target_acct_id}"):
            if hashlib.md5(session_key).hexdigest() == hashed_session_key:
                found = True
                await self.rs.hdel(f"account_session@{self.target_acct_id}", session_key)
                # notify websocket handlers to close connections matching this session
                await self.rs.publish(UnifiedWebSocketHandler._LOGOUT_EVENT_CHANNEL, session_key)
                break

        if found:
            return self.error(("S", ""))

        return self.error(("Enoext", "Session not found"))

    @config_dispatcher.action("remote-logout-all")
    async def remote_logout_all(self):
        if self.target_acct_id != self.acct.acct_id:
            return self.error(PERMISSION_DENIED_ERROR)

        # publish all session keys to logout channel so websocket connections close
        for session_key in await self.rs.hgetall(f"account_session@{self.target_acct_id}"):
            await self.rs.publish(UnifiedWebSocketHandler._LOGOUT_EVENT_CHANNEL, session_key.decode())
        await self.rs.delete(f"account_session@{self.target_acct_id}")
        self.clear_cookie("id")
        return self.error(("S", ""))


proclass_dispatcher = ActionDispatcher()


class AcctProClassHandler(RequestHandler):
    @reqenv
    @require_permission([UserConst.ACCTTYPE_USER, UserConst.ACCTTYPE_KERNEL])
    async def get(self, acct_id: int = None):
        try:
            acct_id = int(acct_id)
        except (ValueError, TypeError):
            return self.error(("Eparam", "Invalid account ID"))
        page = self.get_argument("page", default=None)

        if page is None:
            _, proclass_list = await ProClassService.inst.get_proclass_list()
            proclass_list = filter(
                lambda proclass: proclass["acct_id"] == self.acct.acct_id, proclass_list
            )
            await self.render("acct/proclass-list", f"{self.acct.name}'s ProClass List", proclass_list=proclass_list)

        elif page == "add":
            await self.render("acct/proclass-add", "Add ProClass", user=self.acct)

        elif page == "update":
            try:
                proclass_id = int(self.get_argument("proclass_id"))
            except (ValueError, TypeError):
                return self.error(("Eparam", "Invalid proclass ID"))
            _, proclass = await ProClassService.inst.get_proclass(proclass_id)
            if proclass["acct_id"] != self.acct.acct_id:
                return self.error(PERMISSION_DENIED_ERROR)

            await self.render(
                "acct/proclass-update", f"Config {proclass['name']}", proclass_id=proclass_id, proclass=proclass
            )

    @reqenv
    @require_permission([UserConst.ACCTTYPE_USER, UserConst.ACCTTYPE_KERNEL])
    async def post(self, acct_id: int = None):
        reqtype = self.get_argument("reqtype")
        try:
            acct_id = int(acct_id)
        except (ValueError, TypeError):
            return self.error(("Eparam", "Invalid account ID"))
        return await proclass_dispatcher.dispatch(self, reqtype)

    @proclass_dispatcher.action("add")
    async def add_proclass(self):
        try:
            proclass_type = int(self.get_argument("type"))
            if proclass_type not in (ProClassConst.USER_PUBLIC, ProClassConst.USER_HIDDEN):
                return self.error(("Eparam", "Invalid problem class type"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem class type"))

        p_list = parse_str_to_list(self.get_argument("list"))
        if len(p_list) == 0:
            return self.error(("Eparam", "Problem list should not be empty"))

        name = self.get_argument("name").strip()
        if err := self.len_check(
            name, ProClassConst.NAME_MIN, ProClassConst.NAME_MAX, "Name"
        ):
            return self.error(err)

        desc = self.get_argument("desc").strip()
        if err := self.len_check(
            desc, ProClassConst.DESC_MIN, ProClassConst.DESC_MAX, "Desc"
        ):
            return self.error(err)

        await self.add_log(
            f"{self.acct.name} added problem class '{name}'",
            "user.proclass.add",
            {
                "list": p_list,
                "desc": desc,
                "proclass_type": proclass_type,
            },
        )
        err, proclass_id = await ProClassService.inst.add_proclass(
            name, p_list, desc, self.acct.acct_id, proclass_type
        )
        if err:
            return self.error(err)

        self.error(("S", proclass_id))

    @proclass_dispatcher.action("update")
    async def update_proclass(self):
        try:
            proclass_id = int(self.get_argument("proclass_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid proclass ID"))

        try:
            proclass_type = int(self.get_argument("type"))
            if proclass_type not in (ProClassConst.USER_PUBLIC, ProClassConst.USER_HIDDEN):
                return self.error(("Eparam", "Invalid problem class type"))
        except ValueError:
            return self.error(("Eparam", "Invalid problem class type"))

        p_list = parse_str_to_list(self.get_argument("list"))
        if len(p_list) == 0:
            return self.error(("Eparam", "Problem list should not be empty"))

        name = self.get_argument("name").strip()
        if err := self.len_check(
            name, ProClassConst.NAME_MIN, ProClassConst.NAME_MAX, "Name"
        ):
            return self.error(err)

        desc = self.get_argument("desc").strip()
        if err := self.len_check(
            desc, ProClassConst.DESC_MIN, ProClassConst.DESC_MAX, "Desc"
        ):
            return self.error(err)

        _, proclass = await ProClassService.inst.get_proclass(proclass_id)
        if proclass["acct_id"] != self.acct.acct_id:
            await self.add_log(
                f"{self.acct.name} tried to update problem class '{proclass['name']}', but the problem class is not owned by them",
                "user.proclass.update.failed",
            )
            return self.error(PERMISSION_DENIED_ERROR)

        await self.add_log(
            f"{self.acct.name} updated problem class '{name}'",
            "user.proclass.update",
            {
                "list": p_list,
                "desc": desc,
                "proclass_type": proclass_type,
            },
        )
        if err := await ProClassService.inst.update_proclass(
            proclass_id, name, p_list, desc, proclass_type
        ):
            return self.error(err)

        self.error(("S", ""))

    @proclass_dispatcher.action("remove")
    async def remove_proclass(self):
        try:
            proclass_id = int(self.get_argument("proclass_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid proclass ID"))

        err, proclass = await ProClassService.inst.get_proclass(proclass_id)
        if err:
            return self.error(err)

        if proclass["acct_id"] != self.acct.acct_id:
            await self.add_log(
                f"{self.acct.name} tried to remove problem class '{proclass['name']}', but the problem class is not owned by them",
                "user.proclass.remove.failed",
            )
            return self.error(PERMISSION_DENIED_ERROR)

        await self.add_log(
            f"{self.acct.name} removed problem class '{proclass['name']}'",
            "user.proclass.remove",
        )
        await ProClassService.inst.remove_proclass(proclass_id)

        self.error(("S", ""))


GOTO_PREV_PAGE = f"""
<script type="text/javascript" id="contjs">
function init() {{
    if (index.prev_url)
        index.go('{base_url}/' + index.prev_url);
    else
        index.go('{base_url}/info');
}}
</script>
"""

sign_dispatcher = ActionDispatcher()


class SignHandler(RequestHandler):
    @reqenv
    async def get(self):
        if not self.acct.is_guest():
            return self.write(GOTO_PREV_PAGE)

        await self.render("sign", "Sign In / Sign Up")

    @reqenv
    async def post(self):
        reqtype = self.get_argument("reqtype")
        return await sign_dispatcher.dispatch(self, reqtype)

    @sign_dispatcher.action("signin")
    async def sign_in(self):
        if not self.acct.is_guest():
            return self.error(("Esign", "Already signed in"))

        mail = self.get_argument("mail")
        pw = self.get_argument("pw")

        err, acct_id = await UserService.inst.sign_in(mail, pw, self.request.remote_ip)
        if err:
            await self.add_log(
                f"{mail} tried to sign in but failed: {err}",
                "signin.failure",
                {
                    "type": "signin.failure",
                    "mail": mail,
                    "err": err,
                },
            )
            return self.error(err)

        self.acct = copy.deepcopy(self.acct)
        self.acct.acct_id = acct_id
        await self.add_log(
            f"Account #{acct_id} signed in",
            "signin.success",
            {"type": "signin.success", "acct_id": acct_id},
        )

        session_key = self.create_signed_value("id", str(acct_id))
        await self.rs.hset(
            f"account_session@{acct_id}",
            session_key.decode(),
            packb(
                {
                    "ip": self.request.remote_ip,
                    "time": time.time(),
                    "user-agent": self.request.headers.get("User-Agent", ""),
                }
            ),
        )
        await self.rs.expire(f"account_session@{acct_id}", 30 * 24 * 60 * 60)
        self.set_cookie(
            "id", session_key, path=base_url, httponly=True, expires_days=30
        )
        self.error(("S", ""))

    @sign_dispatcher.action("signup")
    async def sign_up(self):
        if not self.acct.is_guest():
            return self.error(("Esign", "Already signed in"))

        mail = self.get_argument("mail")
        pw = self.get_argument("pw")
        name = self.get_argument("name")

        err, acct_id = await UserService.inst.sign_up(mail, pw, name)
        if err:
            return self.error(err)

        session_key = self.create_signed_value("id", str(acct_id))
        await self.rs.hset(
            f"account_session@{acct_id}",
            session_key.decode(),
            packb(
                {
                    "ip": self.request.remote_ip,
                    "time": time.time(),
                    "user-agent": self.request.headers.get("User-Agent", ""),
                }
            ),
        )
        await self.rs.expire(f"account_session@{acct_id}", 30 * 24 * 60 * 60)
        self.set_cookie(
            "id", session_key, path=base_url, httponly=True, expires_days=30
        )
        self.error(("S", ""))

    @sign_dispatcher.action("signout")
    async def sign_out(self):
        if self.acct.is_guest():
            return self.error(("Esign", "Not signed in"))

        await self.add_log(
            f"{self.acct.name}(#{self.acct.acct_id}) sign out",
            "signout",
            {
                "type": "signout",
                "name": self.acct.name,
                "acct_id": self.acct.acct_id,
            },
        )

        if (session_key := self.get_cookie("id")) is not None:
            await self.rs.hdel(f"account_session@{self.acct.acct_id}", session_key)
            await self.rs.publish(UnifiedWebSocketHandler._LOGOUT_EVENT_CHANNEL, session_key)
        self.clear_cookie("id", path=base_url)
        self.error(("S", ""))
