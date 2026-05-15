import logging

import config
from services.chal import Compiler, COMPILER_INFOS
from services.contests import ContestService
from services.user import Account
from services.log import LogService

logger = logging.getLogger("tornado.application")

class CodeService:
    def __init__(self, db, rs):
        self.db = db
        self.rs = rs
        CodeService.inst = self

    async def get_code(self, chal_id: int, query_acct: Account):
        chal_id = int(chal_id)

        try:
            async with self.db.acquire() as con:
                result = await con.fetch(
                    'SELECT "challenge"."acct_id", "challenge"."pro_id", "challenge"."contest_id", "challenge"."compiler_type" '
                    'FROM "challenge" WHERE "chal_id" = $1;',
                    chal_id,
                )
                if len(result) != 1:
                    return ('Enoext', 'Challenge not found'), None, None
                result = result[0]

                target_acct_id, pro_id, contest_id, compiler_type = int(result['acct_id']), int(result['pro_id']), int(
                    result['contest_id']), Compiler(result['compiler_type'])
        except Exception as e:
            logger.error(f"Error fetching code for challenge {chal_id}: {e}", exc_info=True)
            return ('Eunk', 'Unknown error'), None

        owner = await self.rs.get(f'{pro_id}_owner')
        can_see = False
        if query_acct.acct_id == target_acct_id:
            can_see = True
        elif (contest_id == 0 and query_acct.is_kernel()
              and (owner is None or query_acct.acct_id in config.lock_user_list)
              and query_acct.acct_id in config.can_see_code_user):

            class Object:
                pass
            handler = Object()
            handler.acct = Object()
            handler.acct.acct_id = query_acct.acct_id
            await LogService.inst.add_log(f"{query_acct.name} viewed challenge #{chal_id}", "manage.chal.view", handler=handler)
            can_see = True

        elif contest_id != 0:
            _, contest = await ContestService.inst.get_contest(contest_id)
            if contest.is_admin(query_acct):
                can_see = True

        if can_see:
            source_ext = COMPILER_INFOS[compiler_type].source_ext

            try:
                with open(f'code/{chal_id}/main.{source_ext}', 'rb') as code_f:
                    code = code_f.read().decode('utf-8')

            except FileNotFoundError:
                code = 'ERROR: The code is lost on the server.'

            except OSError as e:
                logger.error(f"Error reading code for challenge {chal_id}: {e}", exc_info=True)
                code = 'ERROR: Failed to read the code from the server.'

        else:
            return ('Eacces', 'Permission denied'), None, None

        return None, code, compiler_type
