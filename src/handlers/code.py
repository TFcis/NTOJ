import tornado.escape

from handlers.base import RequestHandler, reqenv
from services.code import CodeService
from services.chal import Compiler


class CodeHandler(RequestHandler):
    @reqenv
    async def get(self):
        self.error(('Eacces', 'Permission denied'))

    @reqenv
    async def post(self):
        chal_id = int(self.get_argument('chal_id'))

        err, code, compiler_type = await CodeService.inst.get_code(chal_id, self.acct)
        if err:
            return self.error(err)

        if compiler_type in [Compiler.GCC, Compiler.CLANG, Compiler.GPP, Compiler.CLANGPP]:
            compiler_type = 'cpp'
        elif compiler_type == Compiler.RUST:
            compiler_type = 'rust'
        elif compiler_type == Compiler.PYTHON3:
            compiler_type = 'python'
        elif compiler_type == Compiler.JAVA:
            compiler_type = 'java'
        else:
            compiler_type = 'cpp'

        res = {
            'compiler_type': compiler_type,
            'code': tornado.escape.xhtml_escape(code),
        }
        self.error(('S', res))
