from handlers.prospec.common.submit import ProblemSubmitHandler
from services.pro import ProType
from services.prospec.batch import BatchConfig


class BatchSubmitHandler(ProblemSubmitHandler):
    problem_type = ProType.BATCH
    config_type = BatchConfig
    problem_name = "Batch"
    template = "prospec/common/submit"
