"""Code display shared by compiled-program problem types."""
import tornado.escape

from handlers.base import RequestHandler, reqenv
from services.code import CodeService
from services.chal import ChalService, Compiler
from services.pro import ProConst, ProService


class ProblemCodeHandler(RequestHandler):
    def get_code_filenames(self, chal, pro) -> list[str] | None:
        return None

    def get_template_context(self, chal, pro) -> dict:
        return {}

    async def get_problem(self, chal):
        err, pro = await ProService.inst.get_pro(
            chal.pro_id, ProConst.PRO_STATUS_FULL
        )
        if err:
            return err, None
        if pro.problem_type != self.problem_type:
            return ('Eparam', 'Invalid problem type for this handler'), None
        return None, pro

    @reqenv
    async def get(self):
        try:
            chal_id = int(self.get_argument('chal_id'))
        except ValueError:
            return self.error(("Eparam", "Invalid challenge id"))

        err, chal = await ChalService.inst.get_chal(chal_id)
        if err:
            return self.error(err)
        assert chal is not None

        err, pro = await self.get_problem(chal)
        if err:
            return self.error(err)

        await self.render(
            self.template,
            title=None,
            chal=chal,
            **self.get_template_context(chal, pro),
        )
    @reqenv
    async def post(self):
        try:
            chal_id = int(self.get_argument('chal_id'))
        except ValueError:
            return self.error(("Eparam", "Invalid challenge id"))

        err, chal = await ChalService.inst.get_chal(chal_id)
        if err:
            return self.error(err)
        assert chal is not None
        err, pro = await self.get_problem(chal)
        if err:
            return self.error(err)

        err, code, compiler_type = await CodeService.inst.get_code(
            chal_id,
            self.acct,
            self.request.remote_ip,
            self.get_code_filenames(chal, pro),
        )
        if err:
            return self.error(err)

        # Map compiler type to prism.js language
        if compiler_type in (Compiler.GCC, Compiler.CLANG, Compiler.GPP, Compiler.CLANGPP):
            language = 'cpp'
        elif compiler_type == Compiler.RUST:
            language = 'rust'
        elif compiler_type == Compiler.PYTHON3:
            language = 'python'
        elif compiler_type == Compiler.JAVA:
            language = 'java'
        else:
            language = 'cpp'

        res = {'compiler_type': language}
        if isinstance(code, dict):
            res['files'] = [
                {
                    'filename': filename,
                    'code': tornado.escape.xhtml_escape(content),
                }
                for filename, content in code.items()
            ]
        else:
            res['code'] = tornado.escape.xhtml_escape(code)
        self.error(('S', res))
