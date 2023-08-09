from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter

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
            comp_type = 'c++'
        elif comp_type == 'rustc':
            comp_type = 'rust'
        elif comp_type in ['python3', 'pypy3']:
            comp_type = 'python3'
        else:
            comp_type = 'c++'

        lexer = get_lexer_by_name(comp_type, encoding='utf-8', stripall=True)
        formatter = HtmlFormatter(linenos=True, encoding='utf-8')
        code = highlight(code, lexer, formatter).decode('utf-8')
        code = code.replace('\t', '    ')
        self.finish(code)
        return
