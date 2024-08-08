import asyncio
import datetime
import json
from decimal import Decimal

import tornado.web
from msgpack import packb, unpackb

from handlers.base import RequestHandler, WebSocketSubHandler, reqenv
from services.contests import ContestService
from services.user import UserService

UTC8 = datetime.timezone(datetime.timedelta(hours=8))


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
    def _encoder(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.timestamp()

        return obj

    @reqenv
    async def get(self):
        await self.render('contests/scoreboard', contest=self.contest)

    @reqenv
    async def post(self):
        if not self.contest.is_end() and not self.contest.is_public_scoreboard and not self.contest.is_admin(self.acct):
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
                    end_time = self.contest.contest_start + datetime.timedelta(
                        minutes=self.contest.freeze_scoreboard_period)
            else:
                now = datetime.datetime.now().replace(tzinfo=datetime.timezone(datetime.timedelta(hours=+8)))
                total_seconds = int((now - self.contest.contest_start).total_seconds())
                minutes = total_seconds // 60

                if minutes >= self.contest.freeze_scoreboard_period:
                    end_time = self.contest.contest_start + datetime.timedelta(
                        minutes=self.contest.freeze_scoreboard_period)
        is_ended = self.contest.is_end()

        contest_id = self.contest.contest_id

        # TODO: 並行
        acct_list = self.contest.acct_list
        if not self.contest.hide_admin:
            acct_list.extend(self.contest.admin_list)

        s: dict[int, dict[int, dict]] = {}
        cache_name = f'contest_{contest_id}_scores'
        for pro_id in self.contest.pro_list:
            if has_end_time or (scores := (await self.rs.hget(cache_name, str(pro_id)))) is None:
                s[pro_id] = await ContestService.inst.get_ioi2017_scores(contest_id, pro_id, end_time)

                if not has_end_time:
                    await self.rs.hset(cache_name, str(pro_id), packb(s[pro_id], default=self._encoder))
            else:
                s[pro_id] = unpackb(scores, strict_map_key=False)
                for pro_score in s[pro_id].values():
                    pro_score['timestamp'] = datetime.datetime.fromtimestamp(pro_score['timestamp']).replace(
                        tzinfo=UTC8)

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
