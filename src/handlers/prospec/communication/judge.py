import os
import logging

from handlers.prospec.common.judge import ProblemJudgeHandler
from services.chal import Compiler
from services.pro import ProType
from services.prospec.communication import (
    CommunicationConfig,
    CommunicationIOType,
    normalize_submission_format,
)
from services.prospec.program import rename_submission_files


logger = logging.getLogger("tornado.application")


class CommunicationJudgeHandler(ProblemJudgeHandler):
    problem_type = ProType.COMMUNICATION
    problem_name = "Communication"
    config_type = CommunicationConfig
    log_action = "manage.pro.update.judge.communication"
    supports_checker_files = False

    def parse_specific_config(self):
        try:
            io_type = CommunicationIOType(
                int(self.get_argument("communication_io_type"))
            )
            num_processes = int(self.get_argument("num_processes"))
            manager_compiler = Compiler(int(self.get_argument("manager_compiler")))
            submission_format = normalize_submission_format(
                self.get_argument("submission_format").splitlines()
            )
        except ValueError as exc:
            raise ValueError("Invalid communication configuration") from exc
        if num_processes < 1:
            raise ValueError("Number of processes must be at least 1")
        return (
            io_type,
            num_processes,
            manager_compiler,
            self.get_argument("manager_compile_args", default=""),
            submission_format,
        )

    async def update_specific_config(self, pro_id, config, values):
        (
            io_type,
            num_processes,
            manager_compiler,
            manager_compile_args,
            submission_format,
        ) = values
        try:
            os.makedirs(f"problem/{pro_id}/res/grader", exist_ok=True)
        except OSError:
            return ("Eunk", "Unknown error")

        if submission_format != config.submission_format:
            try:
                async with self.db.acquire() as con:
                    challenges = await con.fetch(
                        '''
                            SELECT chal_id, compiler_type
                            FROM challenge
                            WHERE pro_id = $1;
                        ''',
                        pro_id,
                    )
                from services.chal import COMPILER_INFOS

                for challenge in challenges:
                    source_ext = COMPILER_INFOS[challenge['compiler_type']].source_ext
                    old_filenames = [
                        filename.replace("%l", source_ext)
                        for filename in config.submission_format
                    ]
                    new_filenames = [
                        filename.replace("%l", source_ext)
                        for filename in submission_format
                    ]
                    rename_submission_files(
                        challenge['chal_id'], old_filenames, new_filenames
                    )
            except FileExistsError as exc:
                return ("Econf", str(exc))
            except OSError as exc:
                logger.error(
                    "Failed to rename submitted sources for problem %s: %s",
                    pro_id,
                    exc,
                    exc_info=True,
                )
                return ("Eunk", "Failed to rename existing submitted sources")
            except Exception as exc:
                logger.error(
                    "Failed to load submissions for problem %s: %s",
                    pro_id,
                    exc,
                    exc_info=True,
                )
                return ("Eunk", "Unknown error")

        config.communication_io_type = io_type
        config.num_processes = num_processes
        config.manager_compiler = int(manager_compiler)
        config.manager_compile_args = manager_compile_args
        config.submission_format = submission_format
        return None
