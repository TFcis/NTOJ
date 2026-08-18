from handlers.prospec.common.code import ProblemCodeHandler
from services.chal import COMPILER_INFOS
from services.pro import ProType
from services.prospec.communication import CommunicationConfig, communication_spec
from services.prospec.program import get_submission_filenames


class CommunicationCodeHandler(ProblemCodeHandler):
    problem_type = ProType.COMMUNICATION
    template = "prospec/communication/code"

    def get_code_filenames(self, chal, pro):
        config = pro.config.spec_config
        assert isinstance(config, CommunicationConfig)
        source_ext = COMPILER_INFOS[chal.compiler_type].source_ext
        return get_submission_filenames(communication_spec, config, source_ext)

    def get_template_context(self, chal, pro):
        return {'source_filenames': self.get_code_filenames(chal, pro)}
