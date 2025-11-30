import json
import asyncio

import config
from services.contests import ContestService
from services.user import UserService
from handlers.base import RequestHandler, WebSocketSubHandler, reqenv, ActionDispatcher
from handlers.contests.base import contest_require_permission

SUBJECT_MIN = 1
SUBJECT_MAX = 50
CONTENT_MIN = 1
CONTENT_MAX = 256

contest_manage_question_dispatcher = ActionDispatcher()


class ContestManageQuestionHandler(RequestHandler):
    @reqenv
    @contest_require_permission("admin")
    async def get(self):
        err, questions = await ContestService.inst.get_all_question(
            self.contest.contest_id
        )
        if err:
            return self.error(err)

        cache = {}
        questions2 = []
        for question in questions:
            question = dict(question)
            ask_acct_id, reply_acct_id = (
                question["ask_acct_id"],
                question["reply_acct_id"],
            )
            if ask_acct_id not in cache:
                _, acct = await UserService.inst.info_acct(ask_acct_id)
                cache[ask_acct_id] = acct
            else:
                acct = cache[ask_acct_id]

            question["ask_acct"] = acct

            if reply_acct_id:
                if reply_acct_id not in cache:
                    _, acct = await UserService.inst.info_acct(reply_acct_id)
                    cache[reply_acct_id] = acct
                else:
                    acct = cache[reply_acct_id]

                question["reply_acct"] = acct
            questions2.append(question)

        def _cmp(question):
            return (
                question["reply_acct_id"] is None,
                question["ask_timestamp"],
                question["reply_timestamp"],
            )

        questions2.sort(key=_cmp, reverse=True)

        await self.render(
            "contests/manage/question",
            page="question",
            contest_id=self.contest.contest_id,
            contest=self.contest,
            questions=questions2,
        )

    @contest_manage_question_dispatcher.action("reply")
    async def reply_action(self):
        question_id = int(self.get_argument("question_id"))
        content = self.get_argument("content").strip()
        if err := self.len_check(content, CONTENT_MIN, CONTENT_MAX, "Content"):
            return self.error(err)

        err, question = await ContestService.inst.get_question(
            self.contest.contest_id, question_id
        )
        if err:
            return self.error(err)

        await ContestService.inst.reply_question(
            self.contest.contest_id, question_id, self.acct.acct_id, content
        )
        await self.rs.publish(
            "contestnewqasub",
            json.dumps(
                {
                    "contest_id": self.contest.contest_id,
                    "ask_acct_id": question["ask_acct_id"],
                    "type": "reply",
                }
            ),
        )
        return self.error(("S", ""))

    @reqenv
    @contest_require_permission("admin")
    async def post(self):
        reqtype = self.get_argument("reqtype")
        return await contest_manage_question_dispatcher.dispatch(self, reqtype)


# Create dispatcher for announce handler
contest_manage_announce_dispatcher = ActionDispatcher()


class ContestManageAnnounceHandler(RequestHandler):
    @reqenv
    @contest_require_permission("admin")
    async def get(self):
        err, announces = await ContestService.inst.get_all_announce(
            self.contest.contest_id
        )
        if err:
            return self.error(err)

        await self.render(
            "contests/manage/announce",
            page="announce",
            contest_id=self.contest.contest_id,
            contest=self.contest,
            announces=announces,
        )

    @contest_manage_announce_dispatcher.action("add-announce")
    async def add_announce_action(self):
        subject = self.get_argument("subject").strip()
        content = self.get_argument("content").strip()
        if err := self.len_check(subject, SUBJECT_MIN, SUBJECT_MAX, "Subject"):
            return self.error(err)
        if err := self.len_check(content, CONTENT_MIN, CONTENT_MAX, "Content"):
            return self.error(err)

        await ContestService.inst.add_announce(
            self.contest.contest_id, self.acct.acct_id, subject, content
        )
        if self.contest.is_start():
            await self.rs.publish(
                "contestnewqasub",
                json.dumps(
                    {"contest_id": self.contest.contest_id, "type": "add-announce"}
                ),
            )
        return self.error(("S", ""))

    @contest_manage_announce_dispatcher.action("edit-announce")
    async def edit_announce_action(self):
        announce_id = int(self.get_argument("announce_id"))
        subject = self.get_argument("subject").strip()
        content = self.get_argument("content").strip()
        if err := self.len_check(subject, SUBJECT_MIN, SUBJECT_MAX, "Subject"):
            return self.error(err)
        if err := self.len_check(content, CONTENT_MIN, CONTENT_MAX, "Content"):
            return self.error(err)

        await ContestService.inst.edit_announce(
            self.contest.contest_id, announce_id, subject, content
        )
        if self.contest.is_start():
            await self.rs.publish(
                "contestnewqasub",
                json.dumps(
                    {"contest_id": self.contest.contest_id, "type": "edit-announce"}
                ),
            )
        return self.error(("S", ""))

    @contest_manage_announce_dispatcher.action("popup-announce")
    async def popup_announce_action(self):
        announce_id = int(self.get_argument("announce_id"))
        err, announce = await ContestService.inst.get_announce(
            self.contest.contest_id, announce_id
        )
        if err:
            return self.error(err)

        await self.rs.publish(
            "contestnewqasub",
            json.dumps(
                {
                    "contest_id": self.contest.contest_id,
                    "type": "popup-announce",
                    "subject": announce["subject"],
                    "content": announce["content"],
                    "timestamp": announce["timestamp"]
                    .astimezone(config.TIMEZONE)
                    .strftime("%Y-%m-%d %H:%M:%S"),
                }
            ),
        )
        return self.error(("S", ""))

    @reqenv
    @contest_require_permission("admin")
    async def post(self):
        reqtype = self.get_argument("reqtype")
        return await contest_manage_announce_dispatcher.dispatch(self, reqtype)


class ContestManageQANewQuesHandler(WebSocketSubHandler):
    async def listen_newques(self):
        async for msg in self.p.listen():
            if msg["type"] != "message":
                continue

            if int(msg["data"]) == self.contest_id:
                await self.write_message(str(int(msg["data"])))

    async def open(self):
        self.contest_id = -1
        await self.p.subscribe("contestnewquessub")

        self.task = asyncio.tasks.Task(self.listen_newques())

    async def on_message(self, msg):
        if self.contest_id == -1 and msg.isdigit():
            self.contest_id = int(msg)
