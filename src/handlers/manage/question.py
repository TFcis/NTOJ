from msgpack import unpackb

from handlers.base import ActionDispatcher, RequestHandler, reqenv, require_permission
from services.log import LogService
from services.ques import QuestionConst, QuestionService
from services.user import UserConst, UserService


question_dispatcher = ActionDispatcher()


class ManageQuestionHandler(RequestHandler):
    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def get(self, page=None):
        if page is None:
            _, acctlist = await UserService.inst.list_acct(
                UserConst.ACCTTYPE_KERNEL, True
            )
            asklist = {}
            for acct in acctlist:
                acct_id = acct.acct_id
                if (ask := (await self.rs.get(f"{acct_id}_msg_ask"))) is None:
                    asklist.update({acct_id: False})
                else:
                    asklist.update({acct_id: unpackb(ask)})

            await self.render(
                "manage/question/question-list",
                page="question",
                acctlist=acctlist,
                asklist=asklist,
            )

        elif page == "reply":
            try:
                qacct_id = int(self.get_argument("qacct"))
            except ValueError:
                return self.error(("Eparam", "Invalid question account ID"))

            _, ques_list = await QuestionService.inst.get_queslist(acct_id=qacct_id)
            await self.render(
                "manage/question/reply",
                page="question",
                qacct_id=qacct_id,
                ques_list=ques_list,
            )

    @reqenv
    @require_permission(UserConst.ACCTTYPE_KERNEL)
    async def post(self, page=None):
        if page == "reply":
            reqtype = self.get_argument("reqtype")
            return await question_dispatcher.dispatch(self, reqtype)

    @question_dispatcher.action("rpl")
    async def reply_question(self):
        rtext = self.get_argument("rtext").strip()
        if err := self.len_check(
            rtext, QuestionConst.QUESTION_MIN, QuestionConst.QUESTION_MAX, "Reply"
        ):
            return self.error(err)

        await LogService.inst.add_log(
            f"{self.acct.name} replyed a question from user #{self.get_argument('qacct_id')}.",
            "manage.question.reply",
            {"reply_message": rtext},
        )

        try:
            index = int(self.get_argument("index"))
        except ValueError:
            return self.error(("Eparam", "Invalid index"))

        try:
            qacct_id = int(self.get_argument("qacct_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid question account ID"))

        await QuestionService.inst.reply(qacct_id, index, rtext)
        self.error(("S", ""))

    @question_dispatcher.action("rrpl")
    async def re_reply_question(self):
        rtext = self.get_argument("rtext").strip()
        if err := self.len_check(
            rtext, QuestionConst.QUESTION_MIN, QuestionConst.QUESTION_MAX, "Reply"
        ):
            return self.error(err)

        await LogService.inst.add_log(
            f"{self.acct.name} re-replyed a question from user #{self.get_argument('qacct_id')}.",
            "manage.question.re-reply",
            {"reply_message": rtext},
        )

        try:
            index = int(self.get_argument("index"))
        except ValueError:
            return self.error(("Eparam", "Invalid index"))

        try:
            qacct_id = int(self.get_argument("qacct_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid question account ID"))

        await QuestionService.inst.reply(qacct_id, index, rtext)
        self.error(("S", ""))
