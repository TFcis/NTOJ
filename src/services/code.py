import logging
import os

import config
from services.chal import Compiler, COMPILER_INFOS
from services.contests import ContestService
from services.user import Account
from services.log import LogService

logger = logging.getLogger("tornado.application")


def resolve_challenge_code_path(chal_id: int, filename: str) -> str:
    """Resolve one source filename without allowing it to escape code/<chal_id>."""
    if (
        not isinstance(filename, str)
        or not filename
        or "\\" in filename
        or "\x00" in filename
        or filename in (".", "..")
        or filename != os.path.basename(filename)
    ):
        raise ValueError("Invalid source filename")

    challenge_root = os.path.realpath(os.path.join("code", str(chal_id)))
    source_path = os.path.realpath(os.path.join(challenge_root, filename))
    if os.path.commonpath((challenge_root, source_path)) != challenge_root:
        raise ValueError("Invalid source filename")
    return source_path


class CodeService:
    def __init__(self, db, rs):
        self.db = db
        self.rs = rs
        CodeService.inst = self

    async def get_code(
        self,
        chal_id: int,
        query_acct: Account,
        query_acct_ip: str,
        filenames: list[str] | None = None,
    ):
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
            return ('Eunk', 'Unknown error'), None, None

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
            handler.request = Object()
            handler.request.remote_ip = query_acct_ip
            await LogService.inst.add_log(f"{query_acct.name} viewed challenge #{chal_id}", "manage.chal.view", handler=handler)
            can_see = True

        elif contest_id != 0:
            _, contest = await ContestService.inst.get_contest(contest_id)
            if contest.is_admin(query_acct):
                can_see = True
                class Object:
                    pass
                handler = Object()
                handler.acct = Object()
                handler.acct.acct_id = query_acct.acct_id
                handler.request = Object()
                handler.request.remote_ip = query_acct_ip
                handler.contest = contest
                await LogService.inst.add_log(f"{query_acct.name} viewed challenge #{chal_id}", "manage.chal.view", handler=handler)

        if can_see:
            source_ext = COMPILER_INFOS[compiler_type].source_ext
            return_file_mapping = filenames is not None
            if filenames is None:
                filenames = [f"main.{source_ext}"]
            if not isinstance(filenames, (list, tuple)) or not filenames:
                return ('Eparam', 'Invalid source filename'), None, None
            try:
                if len(filenames) != len(set(filenames)):
                    raise ValueError("Duplicate source filename")
                source_paths = [
                    (filename, resolve_challenge_code_path(chal_id, filename))
                    for filename in filenames
                ]
            except (TypeError, ValueError):
                return ('Eparam', 'Invalid source filename'), None, None
            codes = {}

            for filename, source_path in source_paths:
                try:
                    with open(source_path, 'rb') as code_f:
                        codes[filename] = code_f.read().decode('utf-8')

                except FileNotFoundError:
                    codes[filename] = 'ERROR: The code is lost on the server.'

                except OSError as e:
                    logger.error(f"Error reading code for challenge {chal_id}: {e}", exc_info=True)
                    codes[filename] = 'ERROR: Failed to read the code from the server.'

            code = codes if return_file_mapping else next(iter(codes.values()))

        else:
            return ('Eacces', 'Permission denied'), None, None

        return None, code, compiler_type
