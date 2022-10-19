from msgpack import packb, unpackb

from req import RequestHandler, reqenv
from user import UserService, UserConst

from dbg import dbg_print

class QuestionService:
    def __init__(self, db, rs) -> None:
        self.db = db
        self.rs = rs
        QuestionService.inst = self

    async def get_queslist(self, acct, acctid=None):
        if acct != None:
            if acct['acct_id'] == UserConst.ACCTID_GUEST:
                return ('Esign', None)

            if acct['acct_type'] != UserConst.ACCTTYPE_USER:
                return ('Eacces', None)
            acct_id = acct['acct_id']

        else:
            if acctid == UserConst.ACCTID_GUEST:
                return ('Esign', None)

            acct_id = acctid

        if (active := (await self.rs.get(f'{acct_id}_msg_active'))) == None:
            await self.rs.set(f'{acct_id}_msg_active', packb(True))
            await self.rs.set(f'{acct_id}_msg_ask', packb(False))
            await self.rs.set(f'{acct_id}_msg_list', packb([]))
            return (None, [])

        else:
            return (None, unpackb((await self.rs.get(f'{acct_id}_msg_list'))))

    async def set_ques(self, acct, ques_text):
        if acct['acct_id'] == UserConst.ACCTID_GUEST:
            return 'Esign'

        if acct['acct_id'] != UserConst.ACCTTYPE_USER:
            return 'Eacces'

        acct_id = acct['acct_id']
        active = None
        if (active := (await self.rs.get(f'{acct_id}_msg_active'))) == None:
            await self.rs.set(f'{acct_id}_msg_active', packb(True))
            await self.rs.set(f'{acct_id}_msg_ask', packb(False))
            await self.rs.set(f'{acct_id}_msg_list', packb([]))

        elif active == False:
            return 'Eacces'

        await self.rs.set(f'{acct_id}_msg_ask', packb(True))
        ques_list = unpackb((await self.rs.get(f'{acct_id}_msg_list')))
        ques_list.append({
            'Q' : ques_text,
            'A' : None,
        })

        while len(ques_list) > 10:
            ques_list.pop(0)

        #TODO: someoneask處理
        await self.rs.set('someoneask', packb(True))
        await self.rs.set(f'{acct_id}_msg_list', packb(ques_list))
        return None

    async def reply(self, acct, qacct_id, index, rtext):
        if acct['acct_type'] != UserService.ACCTTYPE_KERNEL:
            return 'Eacces'

        err, ques_list = await self.get_queslist(acct=None, acctid=qacct_id)
        if err:
            return err

        ques_list[int(index)]['A'] = rtext
        await self.rs.set('someoneask', packb(False))
        await self.rs.set(f'{qacct_id}_msg_list', packb(ques_list))
        await self.rs.set(f'{qacct_id}_have_reply', packb(True))

    async def rm_ques(self, acct, index: int):
        if acct['acct_type'] != UserService.ACCTTYPE_USER:
            return 'Eacces'

        err, ques_list = await self.get_queslist(acct=acct)
        if err:
            return err

        ques_list.pop(int(index))
        await self.rs.set(f"{acct['acct_id']}_msg_list", packb(ques_list))
        return None

    async def have_reply(self, acct_id):
        if (reply := (await self.rs.get(f'{acct_id}_have_reply'))) == None:
            await self.rs.set(f'{acct_id}_have_reply', packb(False))
            return False

        return unpackb(reply)


class QuestionHandler(RequestHandler):
    @reqenv
    async def get(self):
        if self.acct['acct_id'] == UserConst.ACCTID_GUEST:
            self.error('Esign')
            return

        if self.acct['acct_type'] != UserService.ACCTTYPE_USER:
            self.error('Eacces')
            return

        err, ques_list = await QuestionService.inst.get_queslist(acct=self.acct, acctid=0)
        if err:
            self.error(err)
            return

        await self.rs.set(f"{self.acct['acct_id']}_have_reply", packb(False))
        await self.render('question', acct=self.acct, ques_list=ques_list)
        return

    @reqenv
    async def post(self):
        reqtype = str(self.get_argument('reqtype'))

        if reqtype == 'ask':
            acct_id = self.get_argument('acct_id')
            qtext = str(self.get_argument('qtext'))
            err = await QuestionService.inst.set_ques(self.acct, qtext)
            if err:
                self.error(err)
                return

            self.finish('S')
            return

        elif reqtype == 'rm_ques':
            acct_id = self.get_argument('acct_id')
            index = self.get_argument('index')
            err = await QuestionService.inst.rm_ques(self.acct, index)
            if err:
                self.error(err)
                return

            self.finish('S')
            return
        return
