from handlers.prospec.common.filemanager import ProblemFilemanagerHandler
from services.prospec.batch import BatchConfig, batch_spec

class BatchFilemanagerHandler(ProblemFilemanagerHandler):
    config_type = BatchConfig
    spec = batch_spec
