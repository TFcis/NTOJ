import re
import asyncio
import datetime
import json
from typing import Any

import asyncpg
import tornado.template
import tornado.web
import tornado.websocket
from redis import asyncio as aioredis

import config
from services.contests import ContestService, Contest
from services.user import UserService, Account
import utils.htmlgen

base_url = config.BASE_URL.removesuffix("/")

TEMPLATE_NAMESPACE = {
    "set_page_title": utils.htmlgen.set_page_title,
    "markdown_escape": utils.htmlgen.markdown_escape,
    "url": lambda path: base_url + path,
}


class ActionDispatcher:
    """Action dispatcher for handling reqtype-based routing

    Usage:
        dispatcher = ActionDispatcher()

        class MyHandler(RequestHandler):
            @dispatcher.action('myaction')
            async def my_action(self):
                # handle action logic
                return self.error(('S', data))

            async def post(self):
                reqtype = self.get_argument('reqtype')
                return await dispatcher.dispatch(self, reqtype)
    """

    def __init__(self):
        self._actions = {}

    def action(self, action_name: str):
        """Decorator to register an action handler

        Args:
            action_name: The reqtype value that triggers this action

        Returns:
            Decorated function
        """

        def decorator(func):
            self._actions[action_name] = func
            return func

        return decorator

    async def dispatch(self, handler, action_name: str):
        """Dispatch request to registered action handler

        Args:
            handler: The RequestHandler instance
            action_name: The reqtype value from request

        Returns:
            Result from action handler, or error if action not found
        """
        if action_name not in self._actions:
            return handler.error(("Eunk", f"Unknown action: {action_name}"))
        return await self._actions[action_name](handler)


class RequestHandler(tornado.web.RequestHandler):
    def __init__(self, *args, **kwargs):
        self.db: asyncpg.Pool = kwargs.pop("db")
        self.rs: aioredis.Redis = kwargs.pop("rs")
        self.tpldr = tornado.template.Loader(
            "static/templ", namespace=TEMPLATE_NAMESPACE
        )

        self.acct: Account = None
        self.contest: Contest = None
        self.base_url = base_url

        super().__init__(*args, **kwargs)

        try:
            self.get_argument("json")
            self.res_json = True

        except tornado.web.MissingArgumentError:
            self.res_json = False

    def error(self, err: tuple[str, Any], encoder=None):
        self.finish(json.dumps({"status": err[0], "data": err[1]}, cls=encoder))

    async def render(self, templ, **kwargs):
        class _encoder(json.JSONEncoder):
            def default(self, o):
                if isinstance(o, datetime.datetime):
                    return o.isoformat()

                else:
                    return json.JSONEncoder.default(self, o)

        kwargs["user"] = self.acct
        kwargs["base_url"] = self.base_url

        if self.res_json is True:
            self.finish(json.dumps(kwargs, cls=_encoder))

        else:
            data = self.tpldr.load(templ + ".html").generate(**kwargs)
            self.finish(data)

    def len_check(
        self, obj, min_len: int, max_len: int, field_name: str
    ) -> tuple[str, str] | None:
        obj_len = len(obj)
        if obj_len < min_len:
            return ("Eparam", f"{field_name} too short")
        elif obj_len > max_len:
            return ("Eparam", f"{field_name} too long")
        else:
            return None


class WebSocketHandler(tornado.websocket.WebSocketHandler):
    def __init__(self, *args, **kwargs):
        self.db: asyncpg.Pool = kwargs.pop("db")
        self.rs: aioredis.Redis = kwargs.pop("rs")

        super().__init__(*args, **kwargs)


class WebSocketSubHandler(tornado.websocket.WebSocketHandler):
    def __init__(self, *args, **kwargs):
        pool = kwargs.pop("pool")
        self.rs: aioredis.Redis = aioredis.Redis(connection_pool=pool)
        self.p = self.rs.pubsub()
        self.task: asyncio.Task = None

        super().__init__(*args, **kwargs)
        self.settings["websocket_ping_interval"] = 10

    def check_origin(self, _: str) -> bool:
        return True

    async def cleanup(self):
        await self.p.unsubscribe()
        if self.task:
            self.task.cancel()

        await self.p.aclose()
        await self.rs.aclose()

    def on_close(self) -> None:
        asyncio.create_task(self.cleanup())


def reqenv(func):
    async def wrap(self, *args, **kwargs):
        path = str(self.request.path)
        if (g := re.search(r"contests/(\d+)/?", path)) is not None:
            contest_id = g.group(1)
            if not contest_id.isnumeric():
                await self.finish(
                    json.dumps({"status": "Eparam", "data": "Invalid contest_id"})
                )
                return

            _, self.contest = await ContestService.inst.get_contest(int(contest_id))
            if self.contest is None:
                await self.finish(
                    json.dumps({"status": "Enoext", "data": "Contest not found"})
                )
                return

        _, acct_id, _ = await UserService.inst.info_sign(self)
        _, self.acct = await UserService.inst.info_acct(acct_id)

        ret = await func(self, *args, **kwargs)
        return ret

    return wrap


GOTO_SIGN = f"""
<script type="text/javascript" id="contjs">
function init() {{
    index.go('{base_url}/sign/');
}}
</script>
"""


def require_permission(acct_type):
    def decorator(func):
        async def wrap(self, *args, **kwargs):
            if isinstance(acct_type, list):
                if self.acct.acct_type not in acct_type:
                    if self.acct.is_guest():
                        self.finish(GOTO_SIGN)
                        return

                    await self.finish(
                        json.dumps({"status": "Eacces", "data": "Permission denied"})
                    )
                    return

            elif self.acct.acct_type != acct_type:
                if self.acct.is_guest():
                    self.finish(GOTO_SIGN)
                    return

                await self.finish(
                    json.dumps({"status": "Eacces", "data": "Permission denied"})
                )
                return

            ret = await func(self, *args, **kwargs)
            return ret

        return wrap

    return decorator
