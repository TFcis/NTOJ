from handlers.prospec.common.filemanager import ProblemFilemanagerHandler
from services.prospec.communication import CommunicationConfig, communication_spec


class CommunicationFilemanagerHandler(ProblemFilemanagerHandler):
    config_type = CommunicationConfig
    spec = communication_spec
