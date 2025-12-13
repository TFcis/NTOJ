import tornado.web

from handlers.acct import AcctConfigHandler, AcctHandler, AcctProClassHandler, SignHandler
from handlers.base import UnifiedWebSocketHandler
from handlers.board import BoardHandler
from handlers.bulletin import BulletinHandler
from handlers.chal import (
    ChalHandler,
    ChalListHandler,
)
from handlers.code import CodeHandler
from handlers.contests.url import get_contests_url
from handlers.index import (
    AbouotHandler,
    DevInfoHandler,
    IndexHandler,
)
from handlers.log import LogHandler
from handlers.manage.url import get_manage_url
from handlers.pack import PackHandler

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

    unified_ws_args = {
        'db': db,
        'pool': pool,
    }

    return [
        (r'/be/info', BulletinHandler, args),
        (r'/be/bulletin/(\d+)', BulletinHandler, args),
        (r'/be/board', BoardHandler, args),
        (r'/be/board/(\d+)', BoardHandler, args),
        (r'/be/sign', SignHandler, args),
        (r'/be/acct/(\d+)', AcctHandler, args),
        (r'/be/acct/proclass/(\d+)', AcctProClassHandler, args),
        (r'/be/acctedit', AcctConfigHandler, args),
        (r'/be/acctedit/(\d+)', AcctConfigHandler, args),
        (r'/be/proset', ProsetHandler, args),
        (r'/pro/(\d+)/(.+)', ProStaticHandler, {'db': db, 'rs': rs, 'path': 'problem'}),
        (r'/be/pro/(\d+)', ProHandler, args),
        (r'/be/submit/(\d+)', SubmitHandler, args),
        (r'/be/submit', SubmitHandler, args),
        (r'/be/chal/(\d+)', ChalHandler, args),
        (r'/be/chal', ChalListHandler, args),
        (r'/be/ws', UnifiedWebSocketHandler, unified_ws_args),
        (r'/be/pack', PackHandler, args),
        (r'/be/about', AbouotHandler, args),
        (r'/be/question', QuestionHandler, args),
        (r'/be/set-tags', ProTagsHandler, args),
        (r'/be/log', LogHandler, args),
        (r'/be/log/(\d+)', LogHandler, args),
        (r'/be/rank/(\d+)', ProRankHandler, args),
        (r'/be/users', UserRankHandler, args),
        (r'/be/code', CodeHandler, args),
        (r'/be/dev-info', DevInfoHandler, args),
        (r'/be/report', ReportHandler, args),

        (r'/src/(.*)', tornado.web.StaticFileHandler, {"path": "./static"}),

    ] + get_manage_url(db, rs, pool) + get_contests_url(db, rs, pool) + [
        (r'/(.*)', IndexHandler, args),
    ]
