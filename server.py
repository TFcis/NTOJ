#!/usr/bin/python3
import msgpack
import math
import pg
import redis
import tornadoredis
import tornado.ioloop
import tornado.netutil
import tornado.process
import tornado.httpserver
import tornado.web
import os
from tornado.gen import coroutine

import config
from inform import InformSub
from inform import InformService
from req import Service
from req import RequestHandler
from req import reqenv
from user import UserService
from acct import AcctHandler
from acct import SignHandler
from pro import ProService
from pro import ProsetHandler
from pro import ProStaticHandler
from pro import ProTagsHandler
from pro import ProHandler
from pro import SubmitHandler
from pro import ChalHandler
from pro import ChalListHandler
from pro import ChalSubHandler
from chal import ChalService
from rate import RateService
from contest import BoardHandler
from contest import ContestService
from manage import ManageHandler
from pack import PackHandler
from pack import PackService
from question import QuestionHandler
from question import QuestionService
from api import ApiService
from api import ApiHandler
from code import CodeHandler
from code import CodeService
from rank import RankService
from rank import RankHandler
from auto import AutoService
from auto import AutoHandler
from group import GroupService
from moodle import MoodleService
from moodle import MoodleHandler
from log import LogService
from log import LogHandler

class IndexHandler(RequestHandler):
    @reqenv
    def get(self):
        manage = False
        ask = False
        reply = False
        if self.acct['acct_id'] == UserService.ACCTID_GUEST:
            name = ''

        else:
            name = self.acct['name']

            if self.acct['acct_type'] == UserService.ACCTTYPE_KERNEL:
                manage = True
                if msgpack.unpackb(self.rs.get('someoneask'),encoding = 'utf-8') == True:
                    ask = True
            else:
                reply = QuestionService.inst.have_reply(self.acct['acct_id'])
        self.render('index',name = name,manage = manage,ask = ask,reply = reply)
        return

class InfoHandler(RequestHandler):
    @reqenv
    def get(self):
        inform_list = msgpack.unpackb(self.rs.get('inform'),encoding = 'utf-8')
        self.render('info',inform_list = inform_list)
class AboutHandler(RequestHandler):
    @reqenv
    def get(self):
        self.render('about')
class SignHandler(RequestHandler):
    @reqenv
    def get(self):
        self.render('sign')
        return

    @reqenv
    def post(self):
        cur = yield self.db.cursor()

        reqtype = self.get_argument('reqtype')
        if reqtype == 'signin':
            mail = self.get_argument('mail')
            pw = self.get_argument('pw')
            err,acct_id = yield from UserService.inst.sign_in(mail,pw)
            if err:
                self.finish(err)
                return

            self.set_secure_cookie('id',str(acct_id),
                    path = '/oj',httponly = True)
            self.finish('S')
            return

        elif reqtype == 'signup':
            mail = self.get_argument('mail')
            pw = self.get_argument('pw')
            name = self.get_argument('name')

            err,acct_id = yield from UserService.inst.sign_up(mail,pw,name)
            if err:
                self.finish(err)
                return

            self.set_secure_cookie('id',str(acct_id),
                    path = '/oj',httponly = True)
            self.finish('S')
            return

        elif reqtype == 'signout':
            self.clear_cookie('id',path = '/oj')
            self.finish('S')
            return


if __name__ == '__main__':
    httpsock = tornado.netutil.bind_sockets(6000)
    tornado.process.fork_processes(4)

    db = pg.AsyncPG(config.DBNAME_OJ,config.DBUSER_OJ,config.DBPW_OJ,
            dbtz = '+8')
    rs = redis.StrictRedis(host = 'localhost',port = 6379,db = 1)
    ars = tornadoredis.Client(selected_db = 1)
    ars.connect()
    Service.Acct = UserService(db,rs)
    Service.Pro = ProService(db,rs)
    Service.Chal = ChalService(db,rs)
    Service.Rate = RateService(db,rs)
    Service.Contest = ContestService(db,rs)
    Service.Pack = PackService(db,rs)
    Service.Question = QuestionService(db,rs)
    Service.Inform = InformService(db,rs)
    Service.Api = ApiService(db,rs)
    Service.Code = CodeService(db,rs)
    Service.Rank = RankService(db,rs)
    Service.Auto = AutoService(db,rs)
    Service.Group = GroupService(db,rs)
    Service.Moodle = MoodleService(db,rs)
    Service.Log = LogService(db,rs)
    args = {
        'db':db,
        'rs':rs,
        'ars':ars
    }
    app = tornado.web.Application([
        ('/index',IndexHandler,args),
        ('/info',InfoHandler,args),
        ('/board',BoardHandler,args),
        ('/sign',SignHandler,args),
        ('/acct/(\d+)',AcctHandler,args),
        ('/acct',AcctHandler,args),
        ('/proset',ProsetHandler,args),
        ('/pro/(\d+)/(.+)',ProStaticHandler,args),
        ('/pro/(\d+)',ProHandler,args),
        ('/submit/(\d+)',SubmitHandler,args),
        ('/submit',SubmitHandler,args),
        ('/chal/(\d+)',ChalHandler,args),
        ('/chal',ChalListHandler,args),
        ('/chalsub',ChalSubHandler,args),
        ('/manage/(.+)',ManageHandler,args),
        ('/manage',ManageHandler,args),
        ('/pack',PackHandler,args),
    ('/about',AboutHandler,args),
        ('/question',QuestionHandler,args),
        ('/api',ApiHandler,args),
        ('/informsub',InformSub,args),
        ('/code',CodeHandler,args),
        ('/rank/(\d+)',RankHandler,args),
        ('/auto',AutoHandler,args),
        ('/moodle/(.+)',MoodleHandler,args),
        ('/set-tags',ProTagsHandler,args),
        ('/log',LogHandler,args),
    ],cookie_secret = config.COOKIE_SEC,autoescape = 'xhtml_escape')

    httpsrv = tornado.httpserver.HTTPServer(app)
    httpsrv.add_sockets(httpsock)

    tornado.ioloop.IOLoop.instance().start()
