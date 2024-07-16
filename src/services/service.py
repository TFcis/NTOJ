import config

from .board import BoardService
from .bulletin import BulletinService
from .chal import ChalService
from .code import CodeService
from .contests import ContestService
from .group import GroupService
from .judge import JudgeServerClusterService
from .log import LogService
from .pack import PackService
from .pro import ProClassService, ProService
from .ques import QuestionService
from .rate import RateService
from .user import UserService


class Service:
    pass


def services_init(db, rs):
    Service.Acct = UserService(db, rs)
    Service.Pro = ProService(db, rs)
    Service.ProClass = ProClassService(db, rs)
    Service.Chal = ChalService(db, rs)
    Service.Contest = ContestService(db, rs)
    Service.Board = BoardService(db, rs)
    Service.Question = QuestionService(db, rs)
    Service.Inform = BulletinService(db, rs)
    Service.Pack = PackService(db, rs)
    Service.Code = CodeService(db, rs)
    Service.Group = GroupService(db, rs)
    Service.Log = LogService(db, rs)
    Service.Rate = RateService(db, rs)
    Service.Judge = JudgeServerClusterService(rs, config.JUDGE_SERVER_LIST)
