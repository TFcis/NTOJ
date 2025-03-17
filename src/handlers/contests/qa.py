import asyncio
import json

from services.contests import ContestService

from handlers.base import RequestHandler, WebSocketSubHandler, reqenv
from handlers.contests.base import contest_require_permission

class ContestQAHandler(RequestHandler):
    @reqenv
    async def get(self):
        if self.contest.is_admin(self.acct):
            self.error(('Eacces', 'Permission denied'))
            return

        err, announces = await ContestService.inst.get_all_announce(self.contest.contest_id)
        if err:
            self.error(err)
            return

        err, questions = await ContestService.inst.get_all_question(self.contest.contest_id, self.acct.acct_id)
        if err:
            self.error(err)
            return

        def _cmp(question):
            return (question['reply_acct_id'] is not None, question['reply_timestamp'], question['ask_timestamp'])
        questions.sort(key=_cmp)

        await self.db.execute(
            '''
            UPDATE contest_users
            SET notification_read_count = sub.total_count
            FROM (
                SELECT
                    (SELECT COUNT(*) FROM contest_announcement WHERE contest_id = $1) +
                    (SELECT COUNT(*) FROM contest_question WHERE contest_id = $1 AND ask_acct_id = $2 AND reply_acct_id IS NOT NULL)
                    AS total_count
            ) AS sub
            WHERE contest_users.contest_id = $1
            AND contest_users.acct_id = $2;
            ''',
            self.contest.contest_id, self.acct.acct_id
        )

        await self.render('contests/qa', contest=self.contest, announces=announces, questions=questions)


    @reqenv
    @contest_require_permission('normal')
    async def post(self):
        reqtype = self.get_argument('reqtype')
        if reqtype == 'ask':
            subject = self.get_argument('subject').strip()
            content = self.get_argument('content').strip()

            if len(subject) == 0:
                self.error(('Eparam', 'Subject should not be empty'))
                return

            if len(content) == 0:
                self.error(('Eparam', 'Content should not be empty'))
                return

            await ContestService.inst.ask_question(self.contest.contest_id, self.acct.acct_id, subject, content)
            await self.rs.publish('contestnewquessub', str(self.contest.contest_id))
            self.error(('S', ''))

class ContestNewQAHandler(WebSocketSubHandler):
    async def listen_newqa(self):
        async for msg in self.p.listen():
            if msg['type'] != 'message':
                continue

            if json.loads(msg['data'])['contest_id'] == self.contest_id:
                await self.write_message(msg['data'])

    async def open(self):
        self.contest_id = -1
        await self.p.subscribe('contestnewqasub')

        self.task = asyncio.tasks.Task(self.listen_newqa())

    async def on_message(self, msg):
        if self.contest_id == -1 and msg.isdigit():
            self.contest_id = int(msg)
