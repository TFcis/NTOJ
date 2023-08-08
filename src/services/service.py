import config
from .user import UserService
from .pro import ProService
from .chal import ChalService
from .contest import ContestService
from .ques import QuestionService
from .inform import InformService
from .pack import PackService
from .code import CodeService
from .group import GroupService
from .log import LogService
from .rate import RateService
from .judge import JudgeServerClusterService


class Service:
    pass


def services_init(db, rs):
    Service.Acct = UserService(db, rs)
    Service.Pro = ProService(db, rs)
    Service.Chal = ChalService(db, rs)
    Service.Contest = ContestService(db, rs)
    Service.Question = QuestionService(db, rs)
    Service.Inform = InformService(db, rs)
    Service.Pack = PackService(db, rs)
    Service.Code = CodeService(db, rs)
    # Service.Rank     = RankService(db, rs)
    # Service.Auto     = AutoService(db, rs)
    Service.Group = GroupService(db, rs)
    Service.Log = LogService(db, rs)
    Service.Rate = RateService(db, rs)
    Service.Judge = JudgeServerClusterService(rs, config.JUDGE_SERVER_LIST)
