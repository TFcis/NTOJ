# from auto import AutoHandler
from handlers.acct import SignHandler, AcctHandler
from handlers.api import ApiHandler
from handlers.board import BoardHandler
from handlers.chal import ChalHandler, ChalListHandler, ChalSubHandler, ChalStateHandler
from handlers.code import CodeHandler
from handlers.index import IndexHandler, AbouotHandler, OnlineCounterHandler, DevInfoHandler
from handlers.bulletin import BulletinHandler
from handlers.bulletin import BulletinSub
from handlers.log import LogHandler
# from handlers.manage import ManageHandler
from handlers.pro import ProsetHandler, ProStaticHandler, ProHandler, ProTagsHandler
from handlers.ques import QuestionHandler
from handlers.rank import RankHandler
from handlers.report import ReportHandler
from handlers.submit import SubmitHandler
from handlers.pack import PackHandler

from handlers.manage.url import get_manage_url

def get_url(db, rs):
    args = {
        'db': db,
        'rs': rs,
    }

    return [
        ('/index',          IndexHandler, args),
        ('/info',           BulletinHandler, args),
        ('/bulletin/(\d+)', BulletinHandler, args),
        ('/board',          BoardHandler, args),
        ('/board/(\d+)',    BoardHandler, args),
        ('/sign',           SignHandler, args),
        ('/acct/(\d+)',     AcctHandler, args),
        ('/acct',           AcctHandler, args),
        ('/proset',         ProsetHandler, args),
        ('/pro/(\d+)/(.+)', ProStaticHandler,args),
        ('/pro/(\d+)',      ProHandler,args),
        ('/submit/(\d+)',   SubmitHandler,args),
        ('/submit',         SubmitHandler,args),
        ('/chal/(\d+)',     ChalHandler,args),
        ('/chal',           ChalListHandler,args),
        ('/chalsub',        ChalSubHandler,args),
        ('/pack',           PackHandler,args),
        ('/about',          AbouotHandler, args),
        ('/question',       QuestionHandler,args),
        ('/set-tags',       ProTagsHandler,args),
        ('/log',            LogHandler,args),
        ('/rank/(\d+)',     RankHandler,args),
        # ('/auto',           AutoHandler,args),
        ('/code',           CodeHandler,args),
        ('/informsub',      BulletinSub, args),
        ('/chalstatesub',   ChalStateHandler, args),
        ('/online_count',   OnlineCounterHandler, args),
        ('/api',            ApiHandler, args),
        ('/dev-info',       DevInfoHandler, args),
        ('/report',         ReportHandler, args),
    ] + get_manage_url(db, rs)