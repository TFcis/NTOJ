"""
Batch problem type code display handler.
Handles code display for Batch problem submissions.
"""
import tornado.escape

from handlers.base import RequestHandler, reqenv
from services.code import CodeService
from services.chal import ChalService, Compiler
from services.pro import ProType


class BatchCodeHandler(RequestHandler):
    @reqenv
    async def get(self):
        try:
            chal_id = int(self.get_argument('chal_id'))
        except ValueError:
            return self.error(("Eparam", "Invalid challenge id"))

        err, chal = await ChalService.inst.get_chal(chal_id, self.acct)
        if err:
            return self.error(err)
        assert chal is not None

        if chal.pro.problem_type != ProType.BATCH:
            return self.error(('Eparam', 'Invalid problem type for this handler'))

        await self.render(
            'prospec/batch/code',
            chal=chal
        )


    @reqenv
    async def post(self):
        try:
            chal_id = int(self.get_argument('chal_id'))
        except ValueError:
            return self.error(("Eparam", "Invalid challenge id"))

        err, code, compiler_type = await CodeService.inst.get_code(chal_id, self.acct)
        if err:
            return self.error(err)

        # Map compiler type to prism.js language
        if compiler_type in (Compiler.GCC, Compiler.CLANG, Compiler.GPP, Compiler.CLANGPP):
            language = 'cpp'
        elif compiler_type == Compiler.PYTHON3:
            language = 'python'
        else:
            language = 'cpp'

        res = {
            'compiler_type': language,
            'code': tornado.escape.xhtml_escape(code),
        }
        self.error(('S', res))
