import datetime
import json

import tornado.gen
import tornado.template
import tornado.web
import tornado.websocket

from services.user import UserService


class RequestHandler(tornado.web.RequestHandler):
    def __init__(self, *args, **kwargs):
        self.db = kwargs.pop('db')
        self.rs = kwargs.pop('rs')
        self.tpldr = tornado.template.Loader('static/templ')

        super().__init__(*args, **kwargs)

        try:
            self.get_argument('json')
            self.res_json = True

        except tornado.web.HTTPError:
            self.res_json = False

    def error(self, err):
        self.finish(err)
        return

    async def render(self, templ, **kwargs):

        class _encoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, datetime.datetime):
                    return obj.isoformat()

                else:
                    return json.JSONEncoder.default(self, obj)

        from services.user import UserConst

        if not self.acct.is_guest():
            kwargs['acct_id'] = self.acct.acct_id

        else:
            kwargs['acct_id'] = ''

        if self.res_json is True:
            self.finish(json.dumps(kwargs, cls=_encoder))

        else:
            data = self.tpldr.load(templ + '.html').generate(**kwargs)
            self.finish(data)


class WebSocketHandler(tornado.websocket.WebSocketHandler):
    def __init__(self, *args, **kwargs):
        self.db = kwargs.pop('db')
        self.rs = kwargs.pop('rs')

        super().__init__(*args, **kwargs)


def reqenv(func):
    # @tornado.gen.coroutine
    async def wrap(self, *args, **kwargs):
        _, acct_id, _ = await UserService.inst.info_sign(self)
        _, self.acct = await UserService.inst.info_acct(acct_id)

        ret = await func(self, *args, **kwargs)
        return ret

    return wrap


def require_permission(acct_type):
    def decorator(func):
        async def wrap(self, *args, **kwargs):
            if isinstance(acct_type, list):
                if self.acct.acct_type not in acct_type:
                    await self.finish('Eacces')
                    return

            elif self.acct.acct_type != acct_type:
                await self.finish('Eacces')
                return

            ret = await func(self, *args, **kwargs)
            return ret

        return wrap

    return decorator
