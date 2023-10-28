import json

import tornado.escape

from services.code import CodeService
from handlers.base import RequestHandler, reqenv


class CodeHandler(RequestHandler):
    @reqenv
    async def get(self):
        self.finish('Eacces')
        return

    @reqenv
    async def post(self):
        chal_id = int(self.get_argument('chal_id'))

        err, code, comp_type = await CodeService.inst.get_code(chal_id, self.acct)
        if code is None:
            self.finish('')
            return

        if comp_type in ['gcc', 'g++', 'clang++']:
            comp_type = 'cpp'
        elif comp_type == 'rustc':
            comp_type = 'rust'
        elif comp_type in ['python3', 'pypy3']:
            comp_type = 'python'
        else:
            comp_type = 'cpp'

        res = {
            'comp_type': comp_type,
            'code': tornado.escape.xhtml_escape(code),
        }

        self.finish(json.dumps(res))
