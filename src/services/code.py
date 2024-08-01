import config
from services.chal import ChalConst
from services.contests import ContestService
from services.user import Account


class CodeService:
    def __init__(self, db, rs):
        self.db = db
        self.rs = rs
        CodeService.inst = self

    async def get_code(self, chal_id: int, query_acct: Account):
        chal_id = int(chal_id)

        async with self.db.acquire() as con:
            result = await con.fetch(
                'SELECT "challenge"."acct_id", "challenge"."pro_id", "challenge"."contest_id", "challenge"."compiler_type" '
                'FROM "challenge" WHERE "chal_id" = $1;',
                chal_id,
            )
            if len(result) != 1:
                return 'Enoext', None, None
            result = result[0]

            target_acct_id, pro_id, contest_id, comp_type = int(result['acct_id']), int(result['pro_id']), int(
                result['contest_id']), result['compiler_type']

        owner = await self.rs.get(f'{pro_id}_owner')
        can_see = False
        if query_acct.acct_id == target_acct_id:
            can_see = True
        elif (contest_id == 0 and query_acct.is_kernel()
              and (owner is None or query_acct.acct_id in config.lock_user_list)
              and query_acct.acct_id in config.can_see_code_user):

            can_see = True

        elif contest_id != 0:
            err, contest = await ContestService.inst.get_contest(contest_id)
            if contest.is_admin(query_acct):
                can_see = True

        if can_see:
            file_ext = ChalConst.FILE_EXTENSION[comp_type]

            try:
                with open(f'code/{chal_id}/main.{file_ext}', 'rb') as code_f:
                    code = code_f.read().decode('utf-8')

            except FileNotFoundError:
                code = 'EROOR: The code is lost on server.'

        else:
            return 'Eacces', None, None

        return None, code, comp_type
