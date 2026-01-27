import datetime
import json
from decimal import Decimal

import tornado.web
from msgpack import packb, unpackb

import config
from handlers.base import RequestHandler, UnifiedWebSocketHandler, reqenv
from services.contests import ContestService, ProblemScoreType, UserStatus, ContestMode
from services.user import UserService


class ContestScoreboardCallback:
    """Callback for contest scoreboard new challenge updates

    Manages per-connection state for filtering contest-specific updates.
    """
    def __init__(self):
        # Store connection-specific state: {conn: {'contest_id': int}}
        self.conn_state = {}

    async def register(self, conn):
        """Called when a connection subscribes to contestnewchalsub"""
        # Initialize connection state with no contest_id
        self.conn_state[conn] = {'contest_id': None}

    async def message(self, conn, data):
        """Called when a message is received on contestnewchalsub channel

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
        if msg_type == 'contestnewchalsub_init':
            try:
                contest_id = int(msg_data)
                state = self.conn_state.get(conn)
                if state:
                    state['contest_id'] = contest_id
                return True  # Handled
            except Exception as e:
                return True  # Handled (but failed)

        return False  # Not handled by this callback


_contest_scoreboard_callback = ContestScoreboardCallback()
UnifiedWebSocketHandler.register_channel_callback("contestnewchalsub", _contest_scoreboard_callback)


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

    async def random_set_scoreboard(self):
        contest = self.contest
        acct = self.acct
        if contest.is_member(acct) and not contest.is_admin(acct) and not contest.is_randomset_pro_allocated(acct):
            return self.error(('Etodo', 'TODO: Assign problem set for out of range IP not implemented. Call Yushiuan9499.'))

        if self.contest.is_public_scoreboard:
            acct_list = [acct_id for acct_id, v in self.contest.user_list.items() if v['status'] == UserStatus.APPROVED]
        else:
            acct_list = [self.acct.acct_id]

        scoreboard_key = f'contest_{self.contest.contest_id}_randomset_scoreboard'
        pro_sets_len = len(self.contest.pro_sets)
        keys = [f'{acct_id}_{pro_order}' for acct_id in acct_list for pro_order in range(pro_sets_len)]
        score_values = await self.rs.hmget(scoreboard_key, keys)

        start_time = self.contest.contest_start
        all_scores = []
        for acct_cnt, acct_id in enumerate(acct_list):
            _, acct = await UserService.inst.info_acct(acct_id)
            assert acct
            prolist = self.contest.get_randomset_prolist_from_acct_by_ip(acct)
            if prolist is None:
                continue

            total_score = Decimal('0')
            scores = {}
            for pro_order, pro_id in enumerate(prolist):
                idx = acct_cnt * pro_sets_len + pro_order
                assert 0 <= idx < len(score_values)

                best_record = score_values[idx]
                if best_record is None:
                    continue

                best_record = unpackb(best_record)
                best_record['timestamp'] = datetime.datetime.fromtimestamp(best_record['timestamp'])
                best_record['score'] = Decimal(best_record['score'])
                scores[pro_order] = {
                    'pro_id': pro_id,
                    'chal_id': best_record['chal_id'],
                    'timestamp': best_record['timestamp'].astimezone(config.TIMEZONE) - start_time,
                    'score': best_record['score'],
                    'state': best_record['state'],
                    'fail_count': best_record['fail_count']
                }
                total_score += best_record['score']

            all_scores.append({
                'acct_id': acct_id,
                'name': acct.name,
                'scores': scores,
                'total_score': total_score
            })

        self.error(('S', all_scores), encoder=_JsonDatetimeEncoder)

    @reqenv
    async def get(self):
        await self.render('contests/scoreboard', contest=self.contest)

    @reqenv
    async def post(self):
        if not self.contest.is_start() and not self.contest.is_admin(self.acct):
            return self.error(('Eacces', 'Permission denied'))
        elif not self.contest.is_public_scoreboard and not self.contest.is_member(self.acct):
            return self.error(('Eacces', 'Permission denied'))

        if self.contest.contest_mode == ContestMode.RANDOM_SET:
            return await self.random_set_scoreboard()

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
                    'timestamp': p['timestamp'].astimezone(config.TIMEZONE) - start_time,
                    'score': p['score'],
                    'fail_count': p['fail_count']
                }
                total_score += p['score']

            all_scores.append({
                'acct_id': acct_id,
                'name': acct.name,
                'scores': scores,
                'total_score': total_score
            })

        self.error(('S', all_scores), encoder=_JsonDatetimeEncoder)
