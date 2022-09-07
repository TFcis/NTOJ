import os
import json
import msgpack
import tornado.web

from req import RequestHandler
from req import reqenv
from user import UserConst
from user import UserService

class QuestionService:
    def __init__(self, db, rs):
        self.db = db
        self.rs = rs
        QuestionService.inst = self

    def get_queslist(self, acct, acctid=None):
        if acct != None:
            if acct['acct_id'] == UserService.ACCTID_GUEST:
                return ('Elogin',None)
            if acct['acct_type'] != UserService.ACCTTYPE_USER:
                return ('Eacces',None)
            acct_id = acct['acct_id']
        else:
            if acctid == UserService.ACCTID_GUEST:
                return ('Elogin',None)
            acct_id = acctid

        active = self.rs.get(str(acct_id) + '_msg_active')
        if active == None:
            self.rs.set(str(acct_id)+'_msg_active', msgpack.packb(True))
            self.rs.set(str(acct_id)+'_msg_ask', msgpack.packb(False))
            self.rs.set(str(acct_id)+'_msg_list', msgpack.packb([]))
            return (None, [])
        else:
            return (None, msgpack.unpackb(self.rs.get(str(acct_id) + '_msg_list'), encoding='utf-8'))

    def set_ques(self, acct, ques_text):
        if acct['acct_id'] == UserService.ACCTID_GUEST:
            return 'Elogin'

        if acct['acct_type'] != UserService.ACCTTYPE_USER:
            return 'Eacces'

        acct_id = acct['acct_id']
        active = self.rs.get(str(acct_id) + '_msg_active')
        if active == None:
            self.rs.set(str(acct_id) + '_msg_active', msgpack.packb(True))
            self.rs.set(str(acct_id) + '_msg_ask', msgpack.packb(True))
            self.rs.set(str(acct_id) + '_msg_list', msgpack.packb([]))
        elif active == False:
            return 'Eacces'
        self.rs.set(str(acct_id) + '_msg_ask', msgpack.packb(True))
        ques_list = msgpack.unpackb(self.rs.get(str(acct_id) + '_msg_list'), encoding='utf-8')
        ques_list.append({'Q': ques_text,'A': None})
        while len(ques_list) > 10:
            ques_list.pop(0)
        self.rs.set('someoneask', msgpack.packb(True))
        self.rs.set(str(acct_id) + '_msg_list', msgpack.packb(ques_list))
        return None

    def reply(self, acct, qacct_id, index, rtext):
        if acct['acct_type'] != UserService.ACCTTYPE_KERNEL:
            return 'Eacces'
        err, ques_list = self.get_queslist(acct=None, acctid=qacct_id)
        if err:
            return 'Error'

        ques_list[int(index)]['A'] = rtext
        self.rs.set('someoneask', msgpack.packb(False))
        self.rs.set(str(qacct_id) + '_msg_list', msgpack.packb(ques_list, encoding='utf-8'))
        self.rs.set(str(qacct_id) + '_have_reply', msgpack.packb(True))
        return None

    def rm_ques(self, acct, index):
        if acct['acct_type'] != UserService.ACCTTYPE_USER:
            return 'Eacces'
        err,ques_list = self.get_queslist(acct=acct)
        if err:
            return 'Error'
        ques_list.pop(int(index))
        self.rs.set(str(acct['acct_id']) + '_msg_list', msgpack.packb(ques_list, encoding='utf-8'))
        return None

    def have_reply(self,acct_id):
        reply = self.rs.get(str(acct_id) + '_have_reply')
        if reply == None:
            self.rs.set(str(acct_id) + '_have_reply', msgpack.packb(False))
            return False
        return msgpack.unpackb(reply, encoding='utf-8')

class QuestionHandler(RequestHandler):
    @reqenv
    def get(self):
        if self.acct['acct_id'] == UserService.ACCTID_GUEST:
            self.finish('Elogin')
            return

        if self.acct['acct_type'] != UserService.ACCTTYPE_USER:
            self.finish('Eacces')
            return

        err,ques_list = QuestionService.inst.get_queslist(acct=self.acct, acctid = 0)
        if err:
            self.finish(err)
            return

        self.rs.set(str(self.acct['acct_id']) + '_have_reply', msgpack.packb(False))
        self.render('question', acct=self.acct, ques_list=ques_list)
        return

    @reqenv
    def post(self):
        reqtype = str(self.get_argument('reqtype'))
        if reqtype == 'ask':
            acct_id = self.get_argument('acct_id')
            qtext = str(self.get_argument('qtext'))
            err = QuestionService.inst.set_ques(self.acct, qtext)
            if err:
                self.finish(err)
                return
            self.finish('S')
            return

        elif reqtype == 'rm_ques':
            acct_id = self.get_argument('acct_id')
            index = self.get_argument('index')
            err = QuestionService.inst.rm_ques(self.acct, index)
            if err:
                self.finish(err)
                return
            self.finish('S')
            return
        return
