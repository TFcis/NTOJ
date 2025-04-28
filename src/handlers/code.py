import json

import tornado.escape

from handlers.base import RequestHandler, reqenv
from services.code import CodeService


class CodeHandler(RequestHandler):
    @reqenv
    async def get(self):
        self.error(('Eacces', 'Permission denied'))

    @reqenv
    async def post(self):
        chal_id = int(self.get_argument('chal_id'))

        err, code, comp_type = await CodeService.inst.get_code(chal_id, self.acct)
        if err:
            return self.error(err)

        if comp_type in ['gcc', 'g++', 'clang', 'clang++']:
            comp_type = 'cpp'
        elif comp_type == 'rustc':
            comp_type = 'rust'
        elif comp_type in ['python3', 'pypy3']:
            comp_type = 'python'
        elif comp_type == 'java':
            comp_type = 'java'
        else:
            comp_type = 'cpp'

        res = {
            'comp_type': comp_type,
            'code': tornado.escape.xhtml_escape(code),
        }
        self.error(('S', res))
