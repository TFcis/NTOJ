import json

import tornado.escape

from services.code import CodeService
from handlers.base import RequestHandler, reqenv


class CodeHandler(RequestHandler):
    @reqenv
    async def get(self):
        await self.finish('Eacces')
        return

    @reqenv
    async def post(self):
        chal_id = int(self.get_argument('chal_id'))

        _, code, comp_type = await CodeService.inst.get_code(chal_id, self.acct)
        if code is None:
            await self.finish('')
            return

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

        await self.finish(json.dumps(res))
