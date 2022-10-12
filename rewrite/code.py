from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter

from req import RequestHandler, reqenv
from req import Service
from user import UserService, UserConst
from chal import ChalService

class CodeService:
    def __init__(self, db, rs):
        self.db = db
        self.rs = rs
        CodeService.inst = self

class CodeHandler(RequestHandler):
    @reqenv
    async def get(self):
        self.finish('Eacces')
        return

    @reqenv
    async def post(self):
        chal_id = int(self.get_argument('chal_id'))
        err, chal = await ChalService.inst.get_chal(chal_id, self.acct)
        if (code := chal['code']) == None:
            self.finish('')
            return

        lexer = get_lexer_by_name('c++', encoding='utf-8', stripall=True)
        formatter = HtmlFormatter(linenos=True, encoding='utf-8')
        code = highlight(code, lexer, formatter).decode('utf-8')
        code = code.replace('\t', '    ')
        self.finish(code)
        return