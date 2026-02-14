import json

import config
from services.contests import ContestService
from services.user import UserService
from handlers.base import RequestHandler, UnifiedWebSocketHandler, reqenv, ActionDispatcher
from handlers.contests.base import contest_require_permission

SUBJECT_MIN = 1
SUBJECT_MAX = 50
CONTENT_MIN = 1
CONTENT_MAX = 256


class ContestManageQACallback:
    """Callback for contest management new question notifications

    Manages per-connection state for filtering contest-specific new question notifications.
    Only used by contest administrators.
    """

    def __init__(self):
        # Store connection-specific state: {conn: {'contest_id': int}}
        self.conn_state = {}

    async def register(self, conn):
        """Called when a connection subscribes to contestnewquessub"""
        # Initialize connection state with no contest_id
        self.conn_state[conn] = {'contest_id': None}

    async def message(self, conn, data):
        """Called when a message is received on contestnewquessub channel

        Args:
            conn: WebSocket connection instance
            data: Contest ID as string

        Returns:
            str: Contest ID if it matches the subscribed contest
            None: Skip this connection if contest_id doesn't match
        """
        try:
            state = self.conn_state.get(conn)
            if not state or state['contest_id'] is None:
                return None

            # Check if message contest_id matches subscribed contest
            contest_id = int(data)
            if contest_id == state['contest_id']:
                return str(contest_id)  # Forward message to this connection

            return None  # Skip this connection
        except Exception as e:
            return None

    async def unregister(self, conn):
        """Called when a connection unsubscribes or closes"""
        self.conn_state.pop(conn, None)

    async def handle_custom_message(self, conn, msg_type, msg_data):
        """Handle custom initialization message

        Expects a plain integer string as the contest_id
        """
        if msg_type == 'contestnewquessub_init':
            try:
                contest_id = int(msg_data)
                state = self.conn_state.get(conn)
                if state:
                    state['contest_id'] = contest_id
                return True  # Handled
            except Exception as e:
                return True  # Handled (but failed)

        return False  # Not handled by this callback


# Create and register callback instance
_contest_manage_qa_callback = ContestManageQACallback()
UnifiedWebSocketHandler.register_channel_callback("contestnewquessub", _contest_manage_qa_callback)


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
        try:
            question_id = int(self.get_argument("question_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid question ID"))
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
        try:
            announce_id = int(self.get_argument("announce_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid announce ID"))
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
        try:
            announce_id = int(self.get_argument("announce_id"))
        except ValueError:
            return self.error(("Eparam", "Invalid announce ID"))
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
