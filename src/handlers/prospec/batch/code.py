from handlers.prospec.common.code import ProblemCodeHandler
from services.pro import ProType


class BatchCodeHandler(ProblemCodeHandler):
    problem_type = ProType.BATCH
    template = "prospec/common/code"
