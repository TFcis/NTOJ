from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter

from req import RequestHandler, reqenv
from user import UserConst
from chal import ChalConst
import config

class CodeService:
    def __init__(self, db, rs):
        self.db = db
        self.rs = rs
        CodeService.inst = self

    async def get_code(self, chal_id, acct):
        chal_id = int(chal_id)

        async with self.db.acquire() as con:
            result = await con.fetch('SELECT "challenge"."acct_id", "challenge"."pro_id", "challenge"."compiler_type" FROM "challenge" WHERE "chal_id" = $1;', chal_id)
            if result.__len__() != 1:
                return ('Enoext', None, None)

            acct_id, pro_id, comp_type = int(result[0]['acct_id']), int(result[0]['pro_id']), result[0]['compiler_type']

        owner = await self.rs.get(f'{pro_id}_owner')
        if (acct['acct_id'] == acct_id or
                (acct['acct_type'] == UserConst.ACCTTYPE_KERNEL and
                    (owner == None or acct['acct_id'] in config.lock_user_list) and (acct['acct_id'] in config.can_see_code_user))):

            file_ext = ChalConst.FILE_EXTENSION[comp_type]

            try:
                with open(f'code/{chal_id}/main.{file_ext}', 'rb') as code_f:
                    code = code_f.read().decode('utf-8')

            except FileNotFoundError:
                code = 'EROOR: The code is lost on server.'

        else:
            code = None

        return (None, code, comp_type)

class CodeHandler(RequestHandler):
    @reqenv
    async def get(self):
        self.finish('Eacces')
        return

    @reqenv
    async def post(self):
        chal_id = int(self.get_argument('chal_id'))

        err, code, comp_type = await CodeService.inst.get_code(chal_id, self.acct)
        if code == None:
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
