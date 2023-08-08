from msgpack import packb, unpackb

from utils.req import RequestHandler, reqenv
from services.ques import QuestionService
from services.user import UserConst


class QuestionHandler(RequestHandler):
    @reqenv
    async def get(self):
        if self.acct['acct_id'] == UserConst.ACCTID_GUEST:
            self.error('Esign')
            return

        if self.acct['acct_type'] != UserConst.ACCTTYPE_USER:
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
            qtext = str(self.get_argument('qtext'))
            if len(qtext.strip()) == 0:
                self.error('Equesempty')
                return

            err = await QuestionService.inst.set_ques(self.acct, qtext)
            if err:
                self.error(err)
                return

            self.finish('S')
            return

        elif reqtype == 'rm_ques':
            index = int(self.get_argument('index'))
            err = await QuestionService.inst.rm_ques(self.acct, index)
            if err:
                self.error(err)
                return

            self.finish('S')
            return
        return
