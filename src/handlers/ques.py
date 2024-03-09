from msgpack import packb

from handlers.base import RequestHandler, reqenv, require_permission
from services.ques import QuestionService
from services.user import UserConst


class QuestionHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_USER)
    async def get(self):
        err, ques_list = await QuestionService.inst.get_queslist(self.acct.acct_id)
        if err:
            self.error(err)
            return

        await self.rs.set(f"{self.acct.acct_id}_have_reply", packb(False))
        await self.render('question', acct=self.acct, ques_list=ques_list)

    @reqenv
    @require_permission([UserConst.ACCTTYPE_USER])
    async def post(self):
        reqtype = str(self.get_argument('reqtype'))

        if reqtype == 'ask':
            qtext = str(self.get_argument('qtext'))
            if len(qtext.strip()) == 0:
                self.error('Equesempty')
                return

            err = await QuestionService.inst.set_ques(self.acct.acct_id, qtext)
            if err:
                self.error(err)
                return

            self.finish('S')

        elif reqtype == 'rm_ques':
            index = int(self.get_argument('index'))
            err = await QuestionService.inst.rm_ques(self.acct.acct_id, index)
            if err:
                self.error(err)
                return

            self.finish('S')
