import os
import json
import msgpack
import tornado.web
import tornado.gen
import tornadoredis
import datetime
from req import reqenv
from req import RequestHandler
from user import UserConst
from user import UserService
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter
from req import Service

class CodeService:
    def __init__(self,db,rs):
        self.db = db
        self.rs = rs
        CodeService.inst = self

class CodeHandler(RequestHandler):
    @reqenv
    def get(self):
        self.finish('Eacces')
        return
    @reqenv
    def post(self):
        chal_id = self.get_argument('chal_id')
        fcode = open('/srv/oj/backend/code/'+str(chal_id)+'/main.cpp')
        code = fcode.read()
        fcode.close()
        lexer = get_lexer_by_name('c++',encoding = 'utf-8',stripall = True)
        formatter = HtmlFormatter(linenos = True,
                    encoding = 'utf-8')
        code = highlight(code,lexer,formatter).decode('utf-8')
        code = code.replace('\t','    ')
        self.finish(code) 
        return
