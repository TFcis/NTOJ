# from auto import AutoHandler
from handlers.acct import SignHandler, AcctHandler
from handlers.api import ApiHandler
from handlers.board import BoardHandler
from handlers.chal import ChalHandler, ChalListHandler, ChalSubHandler, ChalStateHandler
from handlers.code import CodeHandler
from handlers.index import IndexHandler, InfoHandler, AbouotHandler, OnlineCounterHandler, DevInfoHandler
from handlers.inform import InformSub
from handlers.log import LogHandler
from handlers.manage import ManageHandler
from handlers.pro import ProsetHandler, ProStaticHandler, ProHandler, ProTagsHandler
from handlers.ques import QuestionHandler
from handlers.rank import RankHandler
from handlers.report import ReportHandler
from handlers.submit import SubmitHandler
from handlers.pack import PackHandler


def get_url(db, rs):
    args = {
        'db': db,
        'rs': rs,
    }

    return [
        ('/index',          IndexHandler, args),
        ('/info',           InfoHandler, args),
        ('/board',          BoardHandler, args),
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
        ('/manage/(.+)',    ManageHandler,args),
        ('/manage',         ManageHandler,args),
        ('/pack',           PackHandler,args),
        ('/about',          AbouotHandler, args),
        ('/question',       QuestionHandler,args),
        ('/set-tags',       ProTagsHandler,args),
        ('/log',            LogHandler,args),
        ('/rank/(\d+)',     RankHandler,args),
        # ('/auto',           AutoHandler,args),
        ('/code',           CodeHandler,args),
        ('/informsub',      InformSub,args),
        ('/chalstatesub',   ChalStateHandler, args),
        ('/online_count',   OnlineCounterHandler, args),
        ('/api',            ApiHandler, args),
        ('/dev-info',       DevInfoHandler, args),
        ('/report',         ReportHandler, args),
    ]