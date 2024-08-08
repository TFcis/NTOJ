import asyncio
import datetime
import json
from decimal import Decimal

import tornado.web

from handlers.base import RequestHandler, WebSocketSubHandler, reqenv
from services.contests import ContestService
from services.user import UserService


class _JsonDatetimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()

        elif isinstance(obj, datetime.timedelta):
            total_seconds = int(obj.total_seconds())
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}:{seconds:02}"

        elif isinstance(obj, Decimal):
            return int(obj)

        else:
            return json.JSONEncoder.default(self, obj)


class ContestScoreboardHandler(RequestHandler):
    @reqenv
    async def get(self):
        await self.render('contests/scoreboard', contest=self.contest)

    @reqenv
    async def post(self):
        if self.contest.is_running() and not self.contest.is_public_scoreboard and not self.contest.is_admin(self.acct):
            self.error('Eacces')
            return

        has_end_time = True
        start_time = self.contest.contest_start
        try:
            end_time = datetime.datetime.fromisoformat(self.get_argument('display_time'))
        except (tornado.web.HTTPError, ValueError):
            has_end_time = False
            end_time = self.contest.contest_end

        if self.contest.freeze_scoreboard_period != 0 and self.contest.is_running():
            if has_end_time:
                total_seconds = int((end_time - self.contest.contest_start).total_seconds())
                minutes = total_seconds // 60

                if minutes >= self.contest.freeze_scoreboard_period:
                    end_time = self.contest.contest_start + datetime.timedelta(minutes=self.contest.freeze_scoreboard_period)
            else:
                now = datetime.datetime.now().replace(tzinfo=datetime.timezone(datetime.timedelta(hours=+8)))
                total_seconds = int((now - self.contest.contest_start).total_seconds())
                minutes = total_seconds // 60

                if minutes >= self.contest.freeze_scoreboard_period:
                    end_time = self.contest.contest_start + datetime.timedelta(minutes=self.contest.freeze_scoreboard_period)

        contest_id = self.contest.contest_id

        # TODO: 並行
        acct_list = self.contest.acct_list
        if not self.contest.hide_admin or (self.contest.hide_admin and self.contest.is_admin(self.acct)):
            acct_list.extend(self.contest.admin_list)

        all_scores = []
        for acct_id in acct_list:
            _, acct = await UserService.inst.info_acct(acct_id)
            scores, total_score = await ContestService.inst.get_ioi_style_score_data(contest_id, acct_id, end_time)
            for score in scores.values():
                score['timestamp'] -= start_time

            all_scores.append({
                'acct_id': acct_id,
                'name': acct.name,
                'scores': scores,
                'total_score': total_score
            })

        self.finish(json.dumps(all_scores, cls=_JsonDatetimeEncoder))


class ContestScoreboardNewChalHandler(WebSocketSubHandler):
    async def listen_newchal(self):
        async for msg in self.p.listen():
            if msg['type'] != 'message':
                continue

            if int(msg['data']) == self.contest_id:
                await self.write_message(str(int(msg['data'])))

    async def open(self):
        self.contest_id = -1
        await self.p.subscribe('contestnewchalsub')

        self.task = asyncio.tasks.Task(self.listen_newchal())

    async def on_message(self, msg):
        if self.contest_id == -1 and msg.isdigit():
            self.contest_id = int(msg)
