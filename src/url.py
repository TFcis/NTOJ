# from auto import AutoHandler
from handlers.acct import AcctHandler, AcctConfigHandler, SignHandler
from handlers.api import ApiHandler
from handlers.board import BoardHandler
from handlers.bulletin import BulletinHandler, BulletinSub
from handlers.chal import (
    ChalHandler,
    ChalListHandler,
    ChalListNewChalHandler,
    ChalListNewStateHandler,
    ChalNewStateHandler,
)
from handlers.code import CodeHandler
from handlers.index import (
    AbouotHandler,
    DevInfoHandler,
    IndexHandler,
    OnlineCounterHandler,
)
from handlers.log import LogHandler
from handlers.manage.url import get_manage_url
from handlers.pack import PackHandler

# from handlers.manage import ManageHandler
from handlers.pro import ProHandler, ProsetHandler, ProStaticHandler, ProTagsHandler
from handlers.ques import QuestionHandler
from handlers.rank import ProRankHandler, UserRankHandler
from handlers.report import ReportHandler
from handlers.submit import SubmitHandler


def get_url(db, rs, pool):
    args = {
        'db': db,
        'rs': rs,
    }

    sub_args = {
        'pool': pool
    }

    return [
        (r'/index', IndexHandler, args),
        (r'/info', BulletinHandler, args),
        (r'/bulletin/(\d+)', BulletinHandler, args),
        (r'/board', BoardHandler, args),
        (r'/board/(\d+)', BoardHandler, args),
        (r'/sign', SignHandler, args),
        (r'/acct/(\d+)', AcctHandler, args),
        (r'/acctedit', AcctConfigHandler, args),
        (r'/acctedit/(\d+)', AcctConfigHandler, args),
        (r'/proset', ProsetHandler, args),
        (r'/pro/(\d+)/(.+)', ProStaticHandler, args),
        (r'/pro/(\d+)', ProHandler, args),
        (r'/submit/(\d+)', SubmitHandler, args),
        (r'/submit', SubmitHandler, args),
        (r'/chal/(\d+)', ChalHandler, args),
        (r'/chal', ChalListHandler, args),
        (r'/challistnewchalsub', ChalListNewChalHandler, sub_args),
        (r'/challistnewstatesub', ChalListNewStateHandler, sub_args),
        (r'/chalnewstatesub', ChalNewStateHandler, sub_args),
        (r'/pack', PackHandler, args),
        (r'/about', AbouotHandler, args),
        (r'/question', QuestionHandler, args),
        (r'/set-tags', ProTagsHandler, args),
        (r'/log', LogHandler, args),
        (r'/rank/(\d+)', ProRankHandler, args),
        (r'/users', UserRankHandler, args),
        # ('/auto',                 AutoHandler,args),
        (r'/code', CodeHandler, args),
        (r'/informsub', BulletinSub, sub_args),
        (r'/online_count', OnlineCounterHandler, args),
        (r'/api', ApiHandler, args),
        (r'/dev-info', DevInfoHandler, args),
        (r'/report', ReportHandler, args),
    ] + get_manage_url(db, rs, pool)
