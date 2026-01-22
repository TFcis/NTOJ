from handlers.base import RequestHandler, reqenv
from services.contests import ContestService, UserStatus
from services.ques import QuestionService
from services.judge import JudgeServerClusterService


class IndexHandler(RequestHandler):
    @reqenv
    async def get(self, page: str):
        if self.request.headers.get("req-by-frontend"):
            await self.render("404")
            return

        is_in_contest = False
        contest_manage = False
        contest = None
        contest_id = 0
        contest_ask_cnt = 0
        contest_notification_cnt = 0

        reply = False
        ask_cnt = 0

        if page.startswith("contests"):
            is_in_contest = True
            try:
                contest_id = int(page.split("/")[1])
            except:
                is_in_contest = False

            if contest_id != 0:
                _, contest = await ContestService.inst.get_contest(contest_id)
                if contest.is_admin(self.acct):
                    (
                        _,
                        contest_ask_cnt,
                    ) = await ContestService.inst.get_need_reply_question_cnt(
                        contest_id
                    )
                    contest_manage = True

                elif contest.is_member(self.acct, UserStatus.APPROVED):
                    (
                        _,
                        contest_notification_cnt,
                    ) = await ContestService.inst.get_unread_notification_cnt(
                        contest.contest_id, self.acct.acct_id
                    )

        if self.acct.is_kernel():
            _, _, ask_cnt = await QuestionService.inst.get_asklist()

        elif not self.acct.is_guest():
            reply = await QuestionService.inst.have_reply(self.acct.acct_id)

        await self.render(
            "index",
            ask_cnt=ask_cnt,
            reply=reply,
            contest_ask_cnt=contest_ask_cnt,
            contest_notification_cnt=contest_notification_cnt,
            is_in_contest=is_in_contest,
            contest_manage=contest_manage,
            contest_id=contest_id,
            contest=contest,
        )

class InfoHandler(RequestHandler):
    async def get(self):
        can_submit = JudgeServerClusterService.inst.is_server_online()
        await self.render('info', judge_server_status=can_submit)


class AbouotHandler(RequestHandler):
    @reqenv
    async def get(self):
        await self.render("about")


class DevInfoHandler(RequestHandler):
    @reqenv
    async def get(self):
        await self.render("dev-info")
