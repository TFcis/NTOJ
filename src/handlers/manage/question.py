from msgpack import unpackb

from handlers.base import RequestHandler, reqenv, require_permission
from services.log import LogService
from services.ques import QuestionService
from services.user import UserConst, UserService


class ManageQuestionHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self, page=None):
        if page is None:
            _, acctlist = await UserService.inst.list_acct(UserConst.ACCTTYPE_KERNEL, True)
            asklist = {}
            for acct in acctlist:
                acct_id = acct.acct_id
                if (ask := (await self.rs.get(f"{acct_id}_msg_ask"))) is None:
                    asklist.update({acct_id: False})
                else:
                    asklist.update({acct_id: unpackb(ask)})

            await self.render('manage/question/question-list', page='question', acctlist=acctlist, asklist=asklist)

        elif page == "reply":
            qacct_id = int(self.get_argument('qacct'))
            _, ques_list = await QuestionService.inst.get_queslist(acct_id=qacct_id)
            await self.render('manage/question/reply', page='question', qacct_id=qacct_id, ques_list=ques_list)

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self, page=None):
        if page == "reply":
            reqtype = self.get_argument('reqtype')
            if reqtype == 'rpl':
                rtext = self.get_argument('rtext')
                await LogService.inst.add_log(
                    f"{self.acct.name} replyed a question from user #{self.get_argument('qacct_id')}.",
                    'manage.question.reply',
                    {
                        'reply_message': rtext
                    }
                )

                index = self.get_argument('index')
                qacct_id = int(self.get_argument('qacct_id'))
                await QuestionService.inst.reply(qacct_id, index, rtext)
                self.finish('S')

            elif reqtype == 'rrpl':
                rtext = self.get_argument('rtext')
                await LogService.inst.add_log(
                    f"{self.acct.name} re-replyed a question from user #{self.get_argument('qacct_id')}.",
                    'manage.question.re-reply',
                    {
                        'reply_message': rtext
                    }
                )

                index = self.get_argument('index')
                qacct_id = int(self.get_argument('qacct_id'))
                await QuestionService.inst.reply(qacct_id, index, rtext)
                self.finish('S')
