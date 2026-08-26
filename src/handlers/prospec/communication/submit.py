import json

from handlers.prospec.common.submit import ProblemSubmitHandler
from services.chal import COMPILER_INFOS
from services.pro import ProType
from services.prospec.communication import CommunicationConfig


class CommunicationSubmitHandler(ProblemSubmitHandler):
    problem_type = ProType.COMMUNICATION
    config_type = CommunicationConfig
    problem_name = "Communication"
    template = "prospec/common/submit"

    def parse_submission(self):
        value = json.loads(self.get_argument("codes"))
        if not isinstance(value, dict):
            raise ValueError("codes must be an object")
        return value

    def prepare_submission(self, code, compiler_type, pro):
        config = pro.config.spec_config
        if set(code) != set(config.submission_format):
            raise ValueError("source filenames do not match submission_format")
        source_ext = COMPILER_INFOS[compiler_type].source_ext
        return {
            filename.replace("%l", source_ext): code[filename]
            for filename in config.submission_format
        }
