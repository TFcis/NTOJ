import time
import asyncio
import json

from services.contests import ContestService

from handlers.base import RequestHandler, WebSocketSubHandler, reqenv, ActionDispatcher
from handlers.contests.base import contest_require_permission

SUBJECT_MIN = 1
SUBJECT_MAX = 50
CONTENT_MIN = 1
CONTENT_MAX = 256
ASK_CD_TIME = 60 * 3

contest_qa_dispatcher = ActionDispatcher()


class ContestQAHandler(RequestHandler):
    @reqenv
    async def get(self):
        if self.contest.is_admin(self.acct):
            return self.error(("Eacces", "Permission denied"))

        if self.contest.is_start():
            err, announces = await ContestService.inst.get_all_announce(
                self.contest.contest_id
            )
            if err:
                return self.error(err)
        else:
            announces = []

        err, questions = await ContestService.inst.get_all_question(
            self.contest.contest_id, self.acct.acct_id
        )
        if err:
            return self.error(err)

        def _cmp(question):
            return (
                question["reply_acct_id"] is not None,
                question["reply_timestamp"],
                question["ask_timestamp"],
            )

        questions.sort(key=_cmp)

        await ContestService.inst.mark_notifications_as_read(
            self.contest.contest_id, self.acct.acct_id
        )

        await self.render(
            "contests/qa",
            contest=self.contest,
            announces=announces,
            questions=questions,
        )

    @contest_qa_dispatcher.action("ask")
    async def ask_question_action(self):
        last_ask_name = f"last_ask_time_{self.acct.acct_id}_{self.contest.contest_id}"
        last_ask_time = await self.rs.get(last_ask_name)
        if last_ask_time is not None:
            last_ask_time = int(str(last_ask_time)[2:-1])
            elapsed_time = int(time.time()) - last_ask_time
            if elapsed_time < ASK_CD_TIME:
                remaining_time = ASK_CD_TIME - elapsed_time
                remaining_time = max(remaining_time, 0)
                return self.error(
                    (
                        "Einternal",
                        f"Ask CD Time: {ASK_CD_TIME} Secs, Remaining: {remaining_time} Secs",
                    )
                )

        subject = self.get_argument("subject").strip()
        content = self.get_argument("content").strip()
        if err := self.len_check(subject, SUBJECT_MIN, SUBJECT_MAX, "Subject"):
            return self.error(err)
        if err := self.len_check(content, CONTENT_MIN, CONTENT_MAX, "Content"):
            return self.error(err)

        if not last_ask_time:
            await self.rs.set(
                last_ask_name, int(time.time()), ex=ASK_CD_TIME
            )  # ex means expire
        else:
            await self.rs.set(last_ask_name, int(time.time()))

        await ContestService.inst.ask_question(
            self.contest.contest_id, self.acct.acct_id, subject, content
        )
        await self.rs.publish("contestnewquessub", str(self.contest.contest_id))
        return self.error(("S", ""))

    @reqenv
    @contest_require_permission("normal")
    async def post(self):
        reqtype = self.get_argument("reqtype")
        return await contest_qa_dispatcher.dispatch(self, reqtype)


class ContestNewQAHandler(WebSocketSubHandler):
    async def listen_newqa(self):
        async for msg in self.p.listen():
            if msg["type"] != "message":
                continue

            data = json.loads(msg["data"])
            if data["contest_id"] == self.contest_id:
                if data["type"] != "reply":
                    await self.write_message(msg["data"])
                elif data["ask_acct_id"] == self.acct_id:
                    await self.write_message(msg["data"])

    async def open(self):
        self.contest_id = -1
        self.acct_id = -1
        await self.p.subscribe("contestnewqasub")

        self.task = asyncio.tasks.Task(self.listen_newqa())

    async def on_message(self, msg):
        j = json.loads(msg)
        if self.contest_id == -1 or self.acct_id == -1:
            self.contest_id = int(j["contest_id"])
            self.acct_id = int(j["acct_id"])
