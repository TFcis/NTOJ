from handlers.prospec.common.judge import ProblemJudgeHandler
from services.pro import ProType
from services.prospec.batch import BatchConfig


class BatchJudgeHandler(ProblemJudgeHandler):
    problem_type = ProType.BATCH
    problem_name = "Batch"
    config_type = BatchConfig
    log_action = "manage.pro.update.judge.batch"
