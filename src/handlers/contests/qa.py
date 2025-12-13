import time
import json

from services.contests import ContestService

from handlers.base import RequestHandler, UnifiedWebSocketHandler, reqenv, ActionDispatcher
from handlers.contests.base import contest_require_permission

SUBJECT_MIN = 1
SUBJECT_MAX = 50
CONTENT_MIN = 1
CONTENT_MAX = 256
ASK_CD_TIME = 60 * 3


class ContestQACallback:
    """Callback for contest Q&A updates

    Manages per-connection state for filtering contest-specific Q&A messages.
    Handles both announcements/questions and replies, with proper routing.
    """

    def __init__(self):
        # Store connection-specific state: {conn: {'contest_id': int, 'acct_id': int}}
        self.conn_state = {}

    async def register(self, conn):
        """Called when a connection subscribes to contestnewqasub"""
        # Initialize connection state
        self.conn_state[conn] = {'contest_id': None, 'acct_id': None}

    async def message(self, conn, data):
        """Called when a message is received on contestnewqasub channel

        Args:
            conn: WebSocket connection instance
            data: JSON string containing message data

        Returns:
            str: Message data if it should be forwarded
            None: Skip this connection
        """
        try:
            state = self.conn_state.get(conn)
            if not state or state['contest_id'] is None or state['acct_id'] is None:
                return None

            # Parse message
            msg_data = json.loads(data)

            # Check contest_id matches
            if msg_data.get('contest_id') != state['contest_id']:
                return None

            # For non-reply messages, send to all subscribers of this contest
            if msg_data.get('type') != 'reply':
                return data

            # For reply messages, only send to the person who asked
            if msg_data.get('ask_acct_id') == state['acct_id']:
                return data

            return None  # Skip this connection
        except Exception as e:
            return None

    async def unregister(self, conn):
        """Called when a connection unsubscribes or closes"""
        self.conn_state.pop(conn, None)

    async def handle_custom_message(self, conn, msg_type, msg_data):
        """Handle custom initialization message

        Expects JSON: {"contest_id": int, "acct_id": int}
        """
        if msg_type == 'contestnewqasub_init':
            try:
                init_data = json.loads(msg_data)
                contest_id = int(init_data.get('contest_id'))
                acct_id = int(init_data.get('acct_id'))

                state = self.conn_state.get(conn)
                if state:
                    state['contest_id'] = contest_id
                    state['acct_id'] = acct_id
                return True  # Handled
            except Exception as e:
                return True  # Handled (but failed)

        return False  # Not handled by this callback


_contest_qa_callback = ContestQACallback()
UnifiedWebSocketHandler.register_channel_callback("contestnewqasub", _contest_qa_callback)


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
