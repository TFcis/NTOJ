import json
import asyncio

from services.contests import ContestService
from services.user import UserService
from handlers.base import RequestHandler, WebSocketSubHandler, reqenv
from handlers.contests.base import contest_require_permission

class ContestManageQuestionHandler(RequestHandler):
    @reqenv
    @contest_require_permission('admin')
    async def get(self):
        err, questions = await ContestService.inst.get_all_question(self.contest.contest_id)
        if err:
            self.error(err)
            return


        cache = {}
        questions2 = []
        for question in questions:
            question = dict(question)
            ask_acct_id, reply_acct_id = question['ask_acct_id'], question['reply_acct_id']
            if ask_acct_id not in cache:
                _, acct = await UserService.inst.info_acct(ask_acct_id)
                cache[ask_acct_id] = acct
            else:
                acct = cache[ask_acct_id]

            question['ask_acct'] = acct

            if reply_acct_id:
                if reply_acct_id not in cache:
                    _, acct = await UserService.inst.info_acct(reply_acct_id)
                    cache[reply_acct_id] = acct
                else:
                    acct = cache[reply_acct_id]

                question['reply_acct'] = acct
            questions2.append(question)
        def _cmp(question):
            return (question['reply_acct_id'] is None, question['ask_timestamp'], question['reply_timestamp'])

        questions2.sort(key=_cmp)


        await self.render('contests/manage/question', page='question', contest_id=self.contest.contest_id,
                          contest=self.contest, questions=questions2)

    @reqenv
    @contest_require_permission('admin')
    async def post(self):
        reqtype = self.get_argument('reqtype')
        if reqtype == 'reply':
            question_id = int(self.get_argument('question_id'))
            content = self.get_argument('content').strip()

            if len(content) == 0:
                self.error(('Eparam', 'Content should not be empty'))
                return

            await ContestService.inst.reply_question(self.contest.contest_id, question_id, self.acct.acct_id, content)
            await self.rs.publish('contestnewqasub', json.dumps({
                'contest_id': self.contest.contest_id,
                'type': 'reply'
            }))
            self.error(('S', ''))

class ContestManageAnnounceHandler(RequestHandler):
    @reqenv
    @contest_require_permission('admin')
    async def get(self):
        err, announces = await ContestService.inst.get_all_announce(self.contest.contest_id)
        if err:
            self.error(err)
            return

        await self.render('contests/manage/announce', page='announce', contest_id=self.contest.contest_id,
                          contest=self.contest, announces=announces)

    @reqenv
    @contest_require_permission('admin')
    async def post(self):
        reqtype = self.get_argument('reqtype')

        if reqtype == 'add-announce':
            subject = self.get_argument('subject').strip()
            content = self.get_argument('content').strip()

            if len(subject) == 0:
                self.error(('Eparam', 'Subject should not be empty'))
                return

            if len(content) == 0:
                self.error(('Eparam', 'Content should not be empty'))
                return

            await ContestService.inst.add_announce(self.contest.contest_id, self.acct.acct_id, subject, content)
            await self.rs.publish('contestnewqasub', json.dumps({
                'contest_id': self.contest.contest_id,
                'type': 'add-announce'
            }))
            self.error(('S', ''))

        elif reqtype == 'edit-announce':
            announce_id = int(self.get_argument('announce_id'))
            subject = self.get_argument('subject')
            content = self.get_argument('content')

            if len(subject) == 0:
                self.error(('Eparam', 'Subject should not be empty'))
                return

            if len(content) == 0:
                self.error(('Eparam', 'Content should not be empty'))
                return

            await ContestService.inst.edit_announce(self.contest.contest_id, announce_id, subject, content)
            await self.rs.publish('contestnewqasub', json.dumps({
                'contest_id': self.contest.contest_id,
                'type': 'edit-announce'
            }))
            self.error(('S', ''))

        elif reqtype == 'popup-announce':
            announce_id = int(self.get_argument('announce_id'))
            err, announce = await ContestService.inst.get_announce(self.contest.contest_id, announce_id)
            if err:
                self.error(err)
                return

            await self.rs.publish('contestnewqasub', json.dumps({
                'contest_id': self.contest.contest_id,
                'type': 'popup-announce',
                'subject': announce['subject'],
                'content': announce['content'],
                'timestamp': announce['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
            }))
            self.error(('S', ''))

class ContestManageQANewQuesHandler(WebSocketSubHandler):
    async def listen_newques(self):
        async for msg in self.p.listen():
            if msg['type'] != 'message':
                continue

            if int(msg['data']) == self.contest_id:
                await self.write_message(str(int(msg['data'])))

    async def open(self):
        self.contest_id = -1
        await self.p.subscribe('contestnewquessub')

        self.task = asyncio.tasks.Task(self.listen_newques())

    async def on_message(self, msg):
        if self.contest_id == -1 and msg.isdigit():
            self.contest_id = int(msg)
