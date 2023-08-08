import json
import datetime

import tornado.template
import tornado.gen
import tornado.web
import tornado.websocket

from services.user import UserService, UserConst

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

        def _mp_encoder(obj):
            if isinstance(obj, datetime.datetime):
                return obj.isoformat()

            return obj

        from services.user import UserConst
        if self.acct['acct_id'] != UserConst.ACCTID_GUEST:
            kwargs['acct_id'] = self.acct['acct_id']

        else:
            kwargs['acct_id'] = ''

        if self.res_json == True:
            self.finish(json.dumps(kwargs, cls=_encoder))

        else:
            data = self.tpldr.load(templ + '.templ').generate(**kwargs)
            self.finish(data)

        return

class WebSocketHandler(tornado.websocket.WebSocketHandler):
    def __init__(self, *args, **kwargs):
        self.db = kwargs.pop('db')
        self.rs = kwargs.pop('rs')

        super().__init__(*args, **kwargs)

def reqenv(func):
    # @tornado.gen.coroutine
    async def wrap(self, *args, **kwargs):
        err, acct_id, ip = await UserService.inst.info_sign(self)
        err, self.acct = await UserService.inst.info_acct(acct_id)

        ret = await func(self, *args, **kwargs)
        return ret

    return wrap