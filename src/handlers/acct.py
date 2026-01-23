import re
import time
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
    async def get(self, acct_id):
        acct_id = int(acct_id)
        err, acct = await UserService.inst.info_acct(acct_id)
        if err:
            return self.error(err)

        acct.acct_type = UserConst.ACCTTYPE_USER

        err, prolist = await ProService.inst.list_pro(ProConst.PRO_STATUS_NORMAL_USER)
        if err:
            return self.error(err)

        acct.acct_type = UserConst.ACCTTYPE_KERNEL

        def chunk_list(la, size):
            for i in range(0, len(la), size):
                yield la[i : i + size]

        # force https, add by xiplus, 2018/8/24
        acct.photo = re.sub(r"^http://", "https://", acct.photo)
        acct.cover = re.sub(r"^http://", "https://", acct.cover)

        await self.render(
            "acct/profile",
            acct=acct,
            prolist=chunk_list(prolist, 10),
        )


config_dispatcher = ActionDispatcher()


class AcctConfigHandler(RequestHandler):
    @reqenv
    async def get(self, acct_id=None):
        if acct_id is None:
            return self.error(("Enoext", "Missing parameter acct_id"))
        acct_id = int(acct_id)
        err, acct = await UserService.inst.info_acct(acct_id)
        if err:
            return self.error(err)

        session_keys = {}
        current_session_key = hashlib.md5(self.get_cookie("id").encode()).hexdigest()
        for session_key, v in (
            await self.rs.hgetall(f"account_session@{acct_id}")
        ).items():
            session_key = hashlib.md5(session_key).hexdigest()
            session_keys[session_key] = unpackb(v)

        await self.render(
            "acct/acct-config",
            acct=acct,
            session_keys=session_keys,
            current_session_key=current_session_key,
        )

    @reqenv
    @require_permission([UserConst.ACCTTYPE_USER, UserConst.ACCTTYPE_KERNEL])
    async def post(self):
        reqtype = self.get_argument("reqtype")
        return await config_dispatcher.dispatch(self, reqtype)

    @config_dispatcher.action("profile")
    async def update_profile(self):
        name = self.get_argument("name")
        photo = self.get_argument("photo")
        cover = self.get_argument("cover")
        motto = self.get_argument("motto")
        target_acct_id = self.get_argument("acct_id")

        if target_acct_id != str(self.acct.acct_id):
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
        target_acct_id = int(self.get_argument("acct_id"))

        if not (self.acct.acct_id == target_acct_id or self.acct.is_kernel()):
            return self.error(PERMISSION_DENIED_ERROR)

        isadmin = self.acct.is_kernel() and (self.acct.acct_id != target_acct_id)
        err, _ = await UserService.inst.update_pw(target_acct_id, old, pw, isadmin)
        if err:
            return self.error(err)

        if not err and target_acct_id != self.acct.acct_id:
            await LogService.inst.add_log(
                f"{self.acct.name} was changing the password of user #{target_acct_id}.",
                "manage.acct.update.pwd",
            )

        return self.error(("S", ""))

    @config_dispatcher.action("remote-logout")
    async def remote_logout(self):
        target_acct_id = self.get_argument("acct_id")

        if target_acct_id != str(self.acct.acct_id):
            return self.error(PERMISSION_DENIED_ERROR)

        hashed_session_key = self.get_argument("hashed_session_key")
        found = False
        for session_key in await self.rs.hgetall(f"account_session@{target_acct_id}"):
            if hashlib.md5(session_key).hexdigest() == hashed_session_key:
                found = True
                await self.rs.hdel(f"account_session@{target_acct_id}", session_key)
                # notify websocket handlers to close connections matching this session
                await self.rs.publish(UnifiedWebSocketHandler._LOGOUT_EVENT_CHANNEL, session_key)
                break

        if found:
            return self.error(("S", ""))

        return self.error(("Enoext", "Session not found"))

    @config_dispatcher.action("remote-logout-all")
    async def remote_logout_all(self):
        target_acct_id = self.get_argument("acct_id")

        if target_acct_id != str(self.acct.acct_id):
            return self.error(PERMISSION_DENIED_ERROR)

        # publish all session keys to logout channel so websocket connections close
        for session_key in await self.rs.hgetall(f"account_session@{target_acct_id}"):
            await self.rs.publish(UnifiedWebSocketHandler._LOGOUT_EVENT_CHANNEL, session_key.decode())
        await self.rs.delete(f"account_session@{target_acct_id}")
        self.clear_cookie("id")
        return self.error(("S", ""))


sign_dispatcher = ActionDispatcher()


class SignHandler(RequestHandler):
    @reqenv
    async def get(self):
        await self.render("sign")

    @reqenv
    async def post(self):
        reqtype = self.get_argument("reqtype")
        return await sign_dispatcher.dispatch(self, reqtype)

    @sign_dispatcher.action("signin")
    async def sign_in(self):
        mail = self.get_argument("mail")
        pw = self.get_argument("pw")

        err, acct_id = await UserService.inst.sign_in(mail, pw, self.request.remote_ip)
        if err:
            await LogService.inst.add_log(
                f"{mail} try to sign in but failed: {err}",
                "signin.failure",
                {
                    "type": "signin.failure",
                    "mail": mail,
                    "err": err,
                },
            )
            return self.error(err)

        await LogService.inst.add_log(
            f"#{acct_id} sign in successfully",
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
        await LogService.inst.add_log(
            f"{self.acct.name}(#{self.acct.acct_id}) sign out",
            "signout",
            {
                "type": "signin.failure",
                "name": self.acct.name,
                "acct_id": self.acct.acct_id,
            },
        )

        if (session_key := self.get_cookie("id")) is not None:
            await self.rs.hdel(f"account_session@{self.acct.acct_id}", session_key)
            await self.rs.publish(UnifiedWebSocketHandler._LOGOUT_EVENT_CHANNEL, session_key)
        self.clear_cookie("id", path=base_url)
        self.error(("S", ""))
