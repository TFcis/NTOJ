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
    "gen_page_title": utils.htmlgen.gen_page_title,
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

    def error(self, err: tuple[str, Any], encoder=None):
        # TODO: need title
        self.finish(json.dumps({"status": err[0], "data": err[1]}, cls=encoder))

    async def render(self, templ, title: str | None ='', **kwargs):
        class _encoder(json.JSONEncoder):
            def default(self, o):
                if isinstance(o, datetime.datetime):
                    return o.isoformat()

                else:
                    return json.JSONEncoder.default(self, o)

        kwargs["user"] = self.acct
        kwargs["base_url"] = self.base_url

        if title is not None:
            title_header = utils.htmlgen.gen_page_title(title, config.SITE_TITLE)
            self.write(title_header)

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

    async def add_log(self, message, log_type=None, params=None):
        """Convenience method to add log with current handler context

        Automatically extracts operator_acct_id, operator_ip, and contest_id
        from the current handler instance.

        Args:
            message: Log message
            log_type: Type of log (e.g., 'manage.inform.add')
            params: Additional parameters (dict)

        Returns:
            Tuple of (error, log_id)
        """
        from services.log import LogService
        return await LogService.inst.add_log(message, log_type, params, handler=self)


class WebSocketHandler(tornado.websocket.WebSocketHandler):
    def __init__(self, *args, **kwargs):
        self.db: asyncpg.Pool = kwargs.pop("db")
        self.rs: aioredis.Redis = kwargs.pop("rs")

        super().__init__(*args, **kwargs)

class UnifiedWebSocketHandler(tornado.websocket.WebSocketHandler):
    """Unified WebSocket handler with shared Redis pubsub connection

    This handler replaces multiple individual WebSocket handlers with a single
    unified handler that uses type-based message routing. All connections share
    a single Redis pubsub connection to reduce resource usage.

    Features:
    - Shared Redis pubsub connection (1 connection for all WebSocket connections)
    - Type-based message routing with register/unregister mechanism
    - Ping-pong health check (30s interval, 60s timeout)
    - Proper connection pool management
    - Error isolation (one connection failure doesn't affect others)
    """

    # Shared Redis pubsub connection (class-level)
    _PING_INTERVAL = 30  # seconds
    _PING_TIMEOUT = 60  # seconds
    _PING_DATA = {"type": "ping", "data": ""}
    _LOGOUT_EVENT_CHANNEL = "logout_acct_sub"
    _MAX_RETRY_DELAY = 60
    _shared_pubsub: aioredis.client.PubSub = None
    _pubsub_lock = asyncio.Lock()
    _pubsub_task: asyncio.Task = None
    _redis_pool = None

    # Connection pool tracking
    active_connections: set = set()  # All active WebSocket connections

    # Subscription tracking: connection -> set of subscribed types
    subscriptions: dict = {}

    # Locks to protect subscription and connection collections
    _subscriptions_lock = asyncio.Lock()
    _connections_lock = asyncio.Lock()

    # Message type callbacks: channel -> callback class instance
    # Callback class should have: register(), message(data), unregister() methods
    _channel_callbacks: dict = {}
    _channel_callbacks_lock = asyncio.Lock()

    def __init__(self, *args, **kwargs):
        self.db: asyncpg.Pool = kwargs.pop("db")
        pool = kwargs.pop("pool")
        if UnifiedWebSocketHandler._redis_pool is None:
            UnifiedWebSocketHandler._redis_pool = pool

        self.rs: aioredis.Redis = aioredis.Redis(connection_pool=pool)
        self.acct_id: int = 0
        self.session_id = None

        self.last_pong = 0.0
        self.last_ping = 0.0
        self.ping_callback = None

        super().__init__(*args, **kwargs)

    def check_origin(self, _: str) -> bool:
        return True

    @classmethod
    async def get_shared_pubsub(cls):
        """Get or create the shared Redis pubsub connection"""
        async with cls._pubsub_lock:
            if cls._shared_pubsub is None:
                rs = aioredis.Redis(connection_pool=cls._redis_pool)
                cls._shared_pubsub = rs.pubsub()

                # Subscribe to all registered channels using a snapshot
                async with cls._channel_callbacks_lock:
                    channels = list(cls._channel_callbacks.keys())
                if channels:
                    await cls._shared_pubsub.subscribe(*channels)
                await cls._shared_pubsub.subscribe(cls._LOGOUT_EVENT_CHANNEL)

                # Start listener task
                cls._pubsub_task = asyncio.create_task(cls._listen_redis_messages())

        return cls._shared_pubsub

    @classmethod
    async def _resubscribe_all_channels(cls):
        """Resubscribe to all registered channels after reconnection"""
        if cls._shared_pubsub:
            async with cls._channel_callbacks_lock:
                channels = list(cls._channel_callbacks.keys())
            if channels:
                await cls._shared_pubsub.subscribe(*channels)
            # Ensure logout channel is subscribed too
            await cls._shared_pubsub.subscribe(cls._LOGOUT_EVENT_CHANNEL)

    @classmethod
    def register_channel_callback(cls, channel: str, callback_class):
        """Register a callback class for a specific channel

        Args:
            channel: The Redis channel name
            callback_class: A class that implements the callback interface:
                - channel_name (class attribute): The Redis channel name
                - register(conn): Called when client registers to this channel
                - message(conn, data): Called when message received, returns formatted data or None
                - unregister(conn): Called when client unregisters from this channel

        Example:
            class MyChannelCallback:
                def __init__(self):
                    self.conn_state = {}

                async def register(self, conn):
                    self.conn_state[conn] = {}
                    # Initialize connection-specific state

                async def message(self, conn, data):
                    # Process message with connection state
                    if should_skip(conn, data):
                        return None
                    return format_data(data)

                async def unregister(self, conn):
                    # Cleanup connection state
                    self.conn_state.pop(conn, None)

            UnifiedWebSocketHandler.register_channel_callback("my_channel", MyChannelCallback())
        """
        # Register synchronously (typically called at import time). However, if the
        # shared pubsub is already running, schedule a background coroutine to
        # subscribe this channel in the shared pubsub. We still protect the
        # callback dict with a lock for safety when concurrent modifications may
        # occur (rare at runtime).
        # Helper: async registration method (safe for runtime registration)
        async def _register_async():
            async with cls._channel_callbacks_lock:
                cls._channel_callbacks[channel] = callback_class
            if cls._shared_pubsub is not None:
                # shared pubsub exists and is likely subscribed; subscribe new channel
                await cls._shared_pubsub.subscribe(channel)
        # Perform sync registration first (fast and works during import)
        # and rely on async task to perform subscribe when loop is available
        async def _sync_register():
            async with cls._channel_callbacks_lock:
                cls._channel_callbacks[channel] = callback_class

        loop = None
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # No loop available; just set value without lock (import time)
            cls._channel_callbacks[channel] = callback_class
            return

        if loop.is_running():
            # schedule asynchronous subscription/register to avoid blocking
            asyncio.create_task(_register_async())
        else:
            # not running: we can create loop and run now
            loop.run_until_complete(_register_async())
        # Now schedule asynchronous subscribe task if loop is running
        # Done: registration scheduling performed above

    @classmethod
    async def register_channel_callback_async(cls, channel: str, callback_class):
        """Async-friendly registration API: sets callback and subscribes

        This can be awaited at runtime to ensure subscribe happens before
        continuing. Works both when `UnifiedWebSocketHandler` _shared_pubsub
        is not initialized yet or is already active.
        """
        async with cls._channel_callbacks_lock:
            cls._channel_callbacks[channel] = callback_class
        if cls._shared_pubsub is not None:
            await cls._shared_pubsub.subscribe(channel)

    @classmethod
    async def _listen_redis_messages(cls):
        """Listen to Redis messages and distribute to subscribed connections

        This runs as a single background task that receives all Redis pubsub
        messages and distributes them to the appropriate WebSocket connections
        based on their subscriptions.
        """
        retry_delay = 1

        while True:
            try:
                if cls._shared_pubsub is None:
                    await cls.get_shared_pubsub()
                    await cls._resubscribe_all_channels()
                    retry_delay = 1

                async for msg in cls._shared_pubsub.listen():
                    if msg["type"] != "message":
                        continue

                    channel = (
                        msg["channel"].decode()
                        if isinstance(msg["channel"], bytes)
                        else msg["channel"]
                    )
                    data = (
                        msg["data"].decode()
                        if isinstance(msg["data"], bytes)
                        else msg["data"]
                    )

                    if channel == cls._LOGOUT_EVENT_CHANNEL:
                        # data is expected to be a session key (cookie id).
                        # Find all connections that match this session_id and close them.
                        session_key = data
                        close_failed = []
                        # Build set of candidate connections: subscriptions + active
                        async with cls._subscriptions_lock:
                            subs_keys = list(cls.subscriptions.keys())
                        async with cls._connections_lock:
                            active_keys = list(cls.active_connections)
                        candidates = set(subs_keys)
                        candidates.update(active_keys)

                        for conn in list(candidates):
                            try:
                                if getattr(conn, "session_id", None) == session_key:
                                    try:
                                        conn.close(code=4000, reason="Logout")
                                    except Exception:
                                        # fallback to cleanup if close fails
                                        close_failed.append(conn)
                            except Exception as e:
                                pass

                        for conn in close_failed:
                            try:
                                await conn.cleanup()
                            except Exception as e:
                                pass

                        continue

                    failed_conns = []
                    # Take a snapshot of current subscriptions to avoid races
                    async with cls._subscriptions_lock:
                        snapshot = list(cls.subscriptions.items())
                    for conn, types in snapshot:
                        if not types:
                            continue
                        if channel not in types:
                            continue

                        try:
                            # obtain callback instance under lock to avoid race
                            async with cls._channel_callbacks_lock:
                                callback = cls._channel_callbacks.get(channel)
                            if callback is None:
                                # no callback found, send raw data
                                await conn.write_message(
                                    json.dumps({"type": channel, "data": data})
                                )
                                continue

                            formatted_data = await callback.message(conn, data)
                            if formatted_data is None:
                                continue  # Callback decided to skip this connection

                            await conn.write_message(
                                json.dumps({"type": channel, "data": formatted_data})
                            )
                        except Exception as e:
                            failed_conns.append(conn)

                    for conn in failed_conns:
                        try:
                            await conn.cleanup()
                        except Exception as e:
                            pass

            except Exception as e:
                cls._shared_pubsub = None

                # Exponential backoff
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, cls._MAX_RETRY_DELAY)

    async def open(self):
        """Called when WebSocket connection is opened"""
        # Ensure shared pubsub is initialized
        await self.get_shared_pubsub()

        acct_id_cookie = self.get_secure_cookie("id")
        self.acct_id = int(acct_id_cookie) if acct_id_cookie is not None else 0
        self.session_id = self.get_cookie("id")

        self.start_ping()

    def start_ping(self):
        """Start ping-pong health check mechanism"""
        now = tornado.ioloop.IOLoop.current().time()
        self.last_pong = now
        self.last_ping = now
        self.ping_callback = tornado.ioloop.PeriodicCallback(
            self.periodic_ping,
            self._PING_INTERVAL * 1000,  # 30 seconds
        )
        self.ping_callback.start()

    def periodic_ping(self):
        """Send periodic ping and check for timeout"""
        now = tornado.ioloop.IOLoop.current().time()

        if self.last_pong > 0 and (now - self.last_pong) > self._PING_TIMEOUT:
            try:
                self.close(code=1000, reason="Ping timeout")
            except Exception as e:
                pass
            return

        try:
            self.write_message(json.dumps(self._PING_DATA))
            self.last_ping = now
        except Exception as e:
            try:
                self.close()
            except:
                pass

    async def on_message(self, message):
        """Handle incoming WebSocket messages

        Message format: {"type": "...", "data": "..."}

        Supported message types:
        - pong: Response to ping (health check)
        - register: Subscribe to a message type
        - unregister: Unsubscribe from a message type
        """

        try:
            msg = json.loads(message)
            msg_type = msg.get("type")
            msg_data = msg.get("data")

            if msg_type == "pong":
                self.last_pong = tornado.ioloop.IOLoop.current().time()
                return


            elif msg_type == "register":
                channel = msg_data
                # Make subscription/active connection modifications safe
                async with self.__class__._subscriptions_lock:
                    self.__class__.subscriptions.setdefault(self, set()).add(channel)
                async with self.__class__._connections_lock:
                    self.__class__.active_connections.add(self)

                # Protect callback access with a lock
                async with self.__class__._channel_callbacks_lock:
                    callback = self.__class__._channel_callbacks.get(channel)
                if callback is not None:
                    await callback.register(self)

            elif msg_type == "unregister":
                channel = msg_data
                async with self.__class__._subscriptions_lock:
                    if self in self.__class__.subscriptions:
                        self.__class__.subscriptions[self].discard(channel)

                    async with self.__class__._channel_callbacks_lock:
                        callback = self.__class__._channel_callbacks.get(channel)
                    if callback is not None:
                        await callback.unregister(self)

            else:
                # Handle custom message types
                # Check all registered callbacks for custom message handlers
                handled = False
                # iterate channel callbacks with a snapshot under lock
                async with self.__class__._channel_callbacks_lock:
                    callback_items = list(self._channel_callbacks.items())
                for channel, callback in callback_items:
                    if hasattr(callback, "handle_custom_message"):
                        # Let callback decide if it handles this message type
                        result = await callback.handle_custom_message(
                            self, msg_type, msg_data
                        )
                        if (
                            result is not False
                        ):  # callback can return False to indicate "not handled"
                            handled = True
                            break

                if not handled:
                    pass

        except json.JSONDecodeError as e:
            pass
        except Exception as e:
            pass

    async def cleanup(self):
        """Clean up connection resources"""

        try:
            if self.ping_callback:
                self.ping_callback.stop()

            async with self.__class__._subscriptions_lock:
                if self in self.__class__.subscriptions:
                    del self.__class__.subscriptions[self]
            async with self.__class__._connections_lock:
                self.__class__.active_connections.discard(self)

        except Exception as e:
            pass

    def on_close(self) -> None:
        """Called when WebSocket connection is closed"""
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
