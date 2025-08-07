import msgpack

from handlers.base import RequestHandler, reqenv
from services.contests import ContestService, UserStatus
from services.ques import QuestionService

class IndexHandler(RequestHandler):
    @reqenv
    async def get(self, page: str):
        is_in_contest = False
        contest_manage = False
        contest = None
        contest_id = 0
        contest_ask_cnt = 0
        contest_notification_cnt = 0

        reply = False
        ask_cnt = 0

        if page.startswith('contests'):
            is_in_contest = True
            try:
                contest_id = int(page.split('/')[1])
            except:
                is_in_contest = False

            if contest_id != 0:
                _, contest = await ContestService.inst.get_contest(contest_id)
                if contest.is_admin(self.acct):
                    res = await self.db.fetch('SELECT COUNT(*) FROM contest_question WHERE contest_id = $1 AND reply_acct_id IS NULL;', contest_id)
                    contest_ask_cnt = res[0]['count']
                    contest_manage = True

                elif contest.is_member(self.acct, UserStatus.APPROVED):
                    new_cnt = await self.db.fetch('''
                    SELECT
                        (SELECT COUNT(*) FROM contest_announcement WHERE contest_id = $1) +
                        (SELECT COUNT(*) FROM contest_question WHERE contest_id = $1 AND ask_acct_id = $2 AND reply_acct_id IS NOT NULL)
                    AS total_count;
                    ''', contest.contest_id, self.acct.acct_id)
                    new_cnt = new_cnt[0]['total_count']

                    old_cnt = await self.db.fetch('SELECT notification_read_count FROM contest_users WHERE contest_id = $1 AND acct_id = $2',
                                                  contest.contest_id, self.acct.acct_id)
                    old_cnt = old_cnt[0]['notification_read_count']
                    contest_notification_cnt = max(new_cnt - old_cnt, 0)

        if self.acct.is_kernel():
            _, _, ask_cnt = await QuestionService.inst.get_asklist()

        elif not self.acct.is_guest():
            reply = await QuestionService.inst.have_reply(self.acct.acct_id)

        await self.render('index', ask_cnt=ask_cnt, reply=reply, contest_ask_cnt=contest_ask_cnt, contest_notification_cnt=contest_notification_cnt,
                          is_in_contest=is_in_contest, contest_manage=contest_manage, contest_id=contest_id, contest=contest)


class AbouotHandler(RequestHandler):
    @reqenv
    async def get(self):
        await self.render('about')


class DevInfoHandler(RequestHandler):
    @reqenv
    async def get(self):
        await self.render('dev-info')
