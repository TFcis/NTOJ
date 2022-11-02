from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter

from req import RequestHandler, reqenv
from user import UserConst
import config

class CodeService:
    def __init__(self, db, rs):
        self.db = db
        self.rs = rs
        CodeService.inst = self

    async def get_code(self, chal_id, acct):
        chal_id = int(chal_id)

        async with self.db.acquire() as con:
            result = await con.fetch('SELECT "challenge"."acct_id", "challenge"."pro_id" FROM "challenge" WHERE "chal_id" = $1;', chal_id)
            if result.__len__() != 1:
                return ('Enoext', None)

            acct_id, pro_id = int(result[0]['acct_id']), int(result[0]['pro_id'])

        owner = await self.rs.get(f'{pro_id}_owner')
        if (acct['acct_id'] == acct_id or
                (acct['acct_type'] == UserConst.ACCTTYPE_KERNEL and
                    (owner == None or acct['acct_id'] in config.lock_user_list) and (acct['acct_id'] in config.can_see_code_user))):

            try:
                with open(f'code/{chal_id}/main.cpp', 'rb') as code_f:
                    code = code_f.read().decode('utf-8')

            except FileNotFoundError:
                code = 'EROOR: The code is lost on server.'

        else:
            code = None

        return (None, code)

class CodeHandler(RequestHandler):
    @reqenv
    async def get(self):
        self.finish('Eacces')
        return

    @reqenv
    async def post(self):
        chal_id = int(self.get_argument('chal_id'))

        err, code = await CodeService.inst.get_code(chal_id, self.acct)
        if code == None:
            self.finish('')
            return

        lexer = get_lexer_by_name('c++', encoding='utf-8', stripall=True)
        formatter = HtmlFormatter(linenos=True, encoding='utf-8')
        code = highlight(code, lexer, formatter).decode('utf-8')
        code = code.replace('\t', '    ')
        self.finish(code)
        return
