import os

from handlers.prospec.common.judge import ProblemJudgeHandler
from services.chal import Compiler
from services.pro import ProType
from services.prospec.communication import (
    CommunicationConfig,
    CommunicationIOType,
    normalize_submission_format,
)


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

        config.communication_io_type = io_type
        config.num_processes = num_processes
        config.manager_compiler = int(manager_compiler)
        config.manager_compile_args = manager_compile_args
        config.submission_format = submission_format
        return None
