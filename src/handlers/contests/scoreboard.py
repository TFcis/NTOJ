import asyncio
import datetime
import json
from decimal import Decimal

import tornado.web
from msgpack import packb, unpackb

from handlers.base import RequestHandler, WebSocketSubHandler, reqenv
from services.contests import ContestService, ProblemScoreType, UserStatus
from services.user import UserService

class _JsonDatetimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime.datetime):
            return o.isoformat()

        elif isinstance(o, datetime.timedelta):
            total_seconds = int(o.total_seconds())
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}:{seconds:02}"

        elif isinstance(o, Decimal):
            return float(o)

        else:
            return json.JSONEncoder.default(self, o)


class ContestScoreboardHandler(RequestHandler):
    def _encoder(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.timestamp()

        elif isinstance(obj, Decimal):
            return str(obj)

        return obj

    @reqenv
    async def get(self):
        await self.render('contests/scoreboard', contest=self.contest)

    @reqenv
    async def post(self):
        if not self.contest.is_start() and not self.contest.is_admin(self.acct):
            return self.error(('Eacces', 'Permission denied'))
        elif not self.contest.is_public_scoreboard and not self.contest.is_member(self.acct):
            return self.error(('Eacces', 'Permission denied'))

        has_end_time = True
        start_time = self.contest.contest_start
        try:
            end_time = datetime.datetime.fromisoformat(self.get_argument('display_time'))
        except (tornado.web.MissingArgumentError, ValueError):
            has_end_time = False
            end_time = self.contest.contest_end

        if self.contest.freeze_scoreboard_period != 0 and self.contest.is_running() and not self.contest.is_admin(self.acct):
            if not has_end_time:
                end_time = datetime.datetime.now(datetime.UTC)

            total_seconds = int((end_time - self.contest.contest_start).total_seconds())
            minutes = total_seconds // 60

            if minutes >= self.contest.freeze_scoreboard_period:
                end_time = self.contest.contest_start + datetime.timedelta(
                    minutes=self.contest.freeze_scoreboard_period)

        is_ended = self.contest.is_end()

        contest_id = self.contest.contest_id

        acct_list = []
        if self.contest.is_public_scoreboard:
            acct_list = [acct_id for acct_id, v in self.contest.user_list.items() if v['status'] == UserStatus.APPROVED]
            if not self.contest.hide_admin:
                acct_list.extend(acct_id for acct_id, v in self.contest.user_list.items() if v['status'] == UserStatus.ADMIN)
        else:
            if not self.contest.is_admin(self.acct):
                acct_list = [self.acct.acct_id]
            else:
                acct_list = [acct_id for acct_id, v in self.contest.user_list.items() if v['status'] == UserStatus.APPROVED]
                if not self.contest.hide_admin:
                    acct_list.extend(acct_id for acct_id, v in self.contest.user_list.items() if v['status'] == UserStatus.ADMIN)

        s: dict[int, dict[int, dict]] = {}
        cache_name = f'contest_{contest_id}_scores'
        for pro_id, pro_options in self.contest.pro_list.items():
            if has_end_time or (scores := (await self.rs.hget(cache_name, str(pro_id)))) is None:
                if pro_options["score_type"] == ProblemScoreType.IOI2017:
                    s[pro_id] = await ContestService.inst.get_ioi2017_scores(contest_id, pro_id, end_time)
                elif pro_options["score_type"] == ProblemScoreType.IOI2013:
                    s[pro_id] = await ContestService.inst.get_ioi2013_scores(contest_id, pro_id, end_time)

                if not has_end_time:
                    await self.rs.hset(cache_name, str(pro_id), packb(s[pro_id], default=self._encoder))
            else:
                s[pro_id] = unpackb(scores, strict_map_key=False)
                for pro_score in s[pro_id].values():
                    pro_score['timestamp'] = datetime.datetime.fromtimestamp(pro_score['timestamp'])
                    pro_score['score'] = Decimal(pro_score['score'])

            if is_ended:
                await self.rs.expire(cache_name, time=60 * 60)

        all_scores = []
        for acct_id in acct_list:
            _, acct = await UserService.inst.info_acct(acct_id)
            total_score = 0
            scores = {}
            for pro_id, pro_scores in s.items():
                if acct_id not in pro_scores:
                    continue

                p = pro_scores[acct_id]
                scores[pro_id] = {
                    'pro_id': pro_id,
                    'chal_id': p['chal_id'],
                    'timestamp': p['timestamp'] - start_time,
                    'score': p['score'],
                    'fail_cnt': p['fail_cnt']
                }
                total_score += p['score']

            all_scores.append({
                'acct_id': acct_id,
                'name': acct.name,
                'scores': scores,
                'total_score': total_score
            })

        self.error(('S', all_scores), encoder=_JsonDatetimeEncoder)


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
