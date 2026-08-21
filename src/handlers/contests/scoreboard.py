import asyncio
import datetime
import json
from dataclasses import dataclass
from decimal import Decimal

import tornado.web
from msgpack import packb, unpackb

from handlers.base import RequestHandler, UnifiedWebSocketHandler, reqenv
from services.contest_access import ContestPermission
from services.contest_scoreboard import (
    ContestScoreboardRevealService,
    ContestScoreboardUpdate,
)
from services.contest_session import ContestScoreboardContext
from services.contests import (
    ContestMode,
    ContestService,
    ContestTimeMode,
    ProblemScoreType,
    UserStatus,
)
from services.user import UserService


@dataclass(slots=True)
class _ContestScoreboardConnectionState:
    contest_id: int | None = None
    is_scoreboard: bool = False
    forward_updates: bool = True
    viewer_relative: bool = False
    session_start: datetime.datetime | None = None
    session_end: datetime.datetime | None = None
    scheduled_elapsed: datetime.timedelta | None = None
    timer_task: asyncio.Task | None = None
    generation: int = 0


class ContestScoreboardCallback:
    """Route score updates and reveal delayed Flexible results on time."""

    def __init__(self, reveal_service_factory=None, now=None):
        self.conn_state: dict[object, _ContestScoreboardConnectionState] = {}
        self._reveal_service_factory = reveal_service_factory or (
            lambda: ContestScoreboardRevealService(ContestService.inst.db)
        )
        self._now = now or (lambda: datetime.datetime.now(datetime.UTC))

    async def register(self, conn):
        await self.unregister(conn)
        self.conn_state[conn] = _ContestScoreboardConnectionState()

    def _cancel_timer(self, state):
        state.generation += 1
        task = state.timer_task
        state.timer_task = None
        state.scheduled_elapsed = None
        if task is not None and task is not asyncio.current_task():
            task.cancel()

    def _viewer_elapsed(self, state):
        visible_time = min(self._now(), state.session_end)
        return max(
            visible_time - state.session_start,
            datetime.timedelta(),
        )

    async def _send_refresh(self, conn, contest_id):
        await conn.write_message(json.dumps({
            "type": "contestnewchalsub",
            "data": str(contest_id),
        }))

    def _arm_elapsed(self, conn, state, elapsed):
        if elapsed is None or elapsed > state.session_end - state.session_start:
            return
        if (
            state.scheduled_elapsed is not None
            and state.scheduled_elapsed <= elapsed
        ):
            return

        self._cancel_timer(state)
        state.scheduled_elapsed = elapsed
        generation = state.generation
        delay = max(
            (state.session_start + elapsed - self._now()).total_seconds(),
            0,
        )
        state.timer_task = asyncio.create_task(
            self._notify_at_elapsed(conn, state, elapsed, generation, delay)
        )

    async def _schedule_next(self, conn, state, after_elapsed=None):
        if not state.viewer_relative:
            return
        generation = state.generation
        after_elapsed = max(
            after_elapsed or datetime.timedelta(),
            self._viewer_elapsed(state),
        )
        next_elapsed = await self._reveal_service_factory().get_next_elapsed(
            state.contest_id,
            after_elapsed,
            state.session_end - state.session_start,
        )
        if self.conn_state.get(conn) is state and state.generation == generation:
            self._arm_elapsed(conn, state, next_elapsed)

    async def _notify_at_elapsed(
        self,
        conn,
        state,
        elapsed,
        generation,
        delay,
    ):
        try:
            await asyncio.sleep(delay)
            if (
                self.conn_state.get(conn) is not state
                or state.generation != generation
            ):
                return

            state.timer_task = None
            state.scheduled_elapsed = None
            await self._send_refresh(conn, state.contest_id)
            if state.generation == generation:
                await self._schedule_next(conn, state, elapsed)
        except asyncio.CancelledError:
            return
        except Exception:
            await self.unregister(conn)

    async def _configure_scoreboard(self, conn, state):
        self._cancel_timer(state)
        state.forward_updates = True
        state.viewer_relative = False
        state.session_start = None
        state.session_end = None
        err, contest = await ContestService.inst.get_contest(state.contest_id)
        if err or contest is None:
            state.forward_updates = False
            return

        now = self._now()
        if contest.contest_time_mode is not ContestTimeMode.FLEXIBLE:
            return
        if contest.is_admin(acct_id=conn.acct_id):
            return
        if contest.configured_session().is_ended(now):
            return

        options = contest.user_list.get(conn.acct_id)
        if (
            options is None
            or options["status"] is not UserStatus.APPROVED
            or options.get("session_start") is None
        ):
            state.forward_updates = False
            return

        state.viewer_relative = True
        state.session_start = options["session_start"]
        state.session_end = options["session_end"]
        await self._schedule_next(conn, state)

    async def message(self, conn, data):
        try:
            state = self.conn_state.get(conn)
            if state is None or state.contest_id is None:
                return None

            update = ContestScoreboardUpdate.loads(data)
            if update.contest_id != state.contest_id:
                return None
            if not state.is_scoreboard:
                return str(update.contest_id)
            if not state.forward_updates:
                return None
            if not state.viewer_relative:
                return str(update.contest_id)
            if update.elapsed is None:
                return None

            if update.elapsed <= self._viewer_elapsed(state):
                return str(update.contest_id)
            self._arm_elapsed(conn, state, update.elapsed)
            return None
        except Exception:
            return None

    async def unregister(self, conn):
        state = self.conn_state.pop(conn, None)
        if state is not None:
            self._cancel_timer(state)

    async def handle_custom_message(self, conn, msg_type, msg_data):
        if msg_type == 'contestnewchalsub_init':
            try:
                state = self.conn_state.get(conn)
                if state is None:
                    return True

                if isinstance(msg_data, dict):
                    contest_id = int(msg_data["contest_id"])
                    purpose = msg_data.get("purpose")
                else:
                    try:
                        parsed = json.loads(msg_data)
                    except (TypeError, json.JSONDecodeError):
                        parsed = msg_data
                    if isinstance(parsed, dict):
                        contest_id = int(parsed["contest_id"])
                        purpose = parsed.get("purpose")
                    else:
                        contest_id = int(parsed)
                        purpose = None

                state.contest_id = contest_id
                state.is_scoreboard = purpose == "scoreboard"
                if state.is_scoreboard:
                    await self._configure_scoreboard(conn, state)
                return True
            except Exception:
                return True

        return False


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

    @reqenv
    async def get(self):
        await self.render('contests/scoreboard', f"{self.contest.name} - Scoreboard", contest=self.contest)

    @reqenv
    async def post(self):
        if not self.contest_access.has(ContestPermission.VIEW_SCOREBOARD):
            return self.error(('Eacces', 'Permission denied'))

        has_end_time = True
        try:
            end_time = datetime.datetime.fromisoformat(self.get_argument('display_time'))
        except (tornado.web.MissingArgumentError, ValueError):
            has_end_time = False
            end_time = self.contest.contest_end

        freeze_applied = False
        if (
            self.contest.contest_time_mode is ContestTimeMode.FIXED
            and self.contest.freeze_scoreboard_period != 0
            and self.contest_session.is_running()
            and not self.contest_access.is_admin
        ):
            if not has_end_time:
                end_time = datetime.datetime.now(datetime.UTC)

            total_seconds = int((end_time - self.contest_session.start_time).total_seconds())
            minutes = total_seconds // 60

            if minutes >= self.contest.freeze_scoreboard_period:
                end_time = self.contest_session.start_time + datetime.timedelta(
                    minutes=self.contest.freeze_scoreboard_period)
                freeze_applied = True

        is_ended = self.contest.configured_session().is_ended()

        visible_elapsed = None
        if (
            self.contest.contest_time_mode is ContestTimeMode.FLEXIBLE
            and self.contest_access.is_participant
            and not self.contest_access.is_admin
            and not is_ended
        ):
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=datetime.UTC)
            end_time = min(end_time, self.contest_access.resolved_at)
            visible_time = min(end_time, self.contest_session.end_time)
            visible_elapsed = max(
                visible_time - self.contest_session.start_time,
                datetime.timedelta(),
            )

        contest_id = self.contest.contest_id
        score_context = ContestScoreboardContext.official(visible_elapsed)

        acct_list = []
        if self.contest.is_public_scoreboard:
            acct_list = [acct_id for acct_id, v in self.contest.user_list.items() if v['status'] == UserStatus.APPROVED]
            if not self.contest.hide_admin:
                acct_list.extend(acct_id for acct_id, v in self.contest.user_list.items() if v['status'] == UserStatus.ADMIN)
        else:
            if not self.contest_access.is_admin:
                acct_list = [self.acct.acct_id]
            else:
                acct_list = [acct_id for acct_id, v in self.contest.user_list.items() if v['status'] == UserStatus.APPROVED]
                if not self.contest.hide_admin:
                    acct_list.extend(acct_id for acct_id, v in self.contest.user_list.items() if v['status'] == UserStatus.ADMIN)

        s: dict[int, dict[int, dict]] = {}
        cache_name = score_context.cache_name(contest_id)
        cacheable = (
            not has_end_time
            and not freeze_applied
            and not score_context.is_viewer_relative
        )
        for pro_id, pro_options in self.contest.pro_list.items():
            scores = await self.rs.hget(cache_name, str(pro_id)) if cacheable else None
            if scores is None:
                score_type = pro_options["score_type"]
                if score_type == ProblemScoreType.ICPC:
                    s[pro_id] = await ContestService.inst.get_icpc_scores(
                        contest_id, pro_id, end_time, score_context
                    )
                    assert self.contest.contest_mode == ContestMode.ACM
                elif score_type == ProblemScoreType.IOI2017:
                    s[pro_id] = await ContestService.inst.get_ioi2017_scores(
                        contest_id, pro_id, end_time, score_context
                    )
                elif score_type == ProblemScoreType.IOI2013:
                    s[pro_id] = await ContestService.inst.get_ioi2013_scores(
                        contest_id, pro_id, end_time, score_context
                    )

                if cacheable:
                    await self.rs.hset(cache_name, str(pro_id), packb(s[pro_id], default=self._encoder))
            else:
                s[pro_id] = unpackb(scores, strict_map_key=False)
                for pro_score in s[pro_id].values():
                    if pro_score['timestamp'] is not None:
                        pro_score['timestamp'] = datetime.datetime.fromtimestamp(
                            pro_score['timestamp'], tz=datetime.UTC
                        )
                    pro_score['score'] = Decimal(pro_score['score'])

            if is_ended:
                await self.rs.expire(cache_name, time=60 * 60)

        all_scores = []
        for acct_id in acct_list:
            _, acct = await UserService.inst.info_acct(acct_id)
            account_options = self.contest.user_list[acct_id]
            if (
                self.contest.contest_time_mode is ContestTimeMode.FLEXIBLE
                and account_options["status"] is UserStatus.APPROVED
            ):
                score_start_time = account_options.get("session_start")
            else:
                score_start_time = self.contest.contest_start
            total_score = 0
            scores = {}
            for pro_id, pro_scores in s.items():
                if acct_id not in pro_scores:
                    continue

                p = pro_scores[acct_id]
                if score_start_time is None:
                    continue
                scores[pro_id] = {
                    'pro_id': pro_id,
                    'chal_id': p['chal_id'],
                    'timestamp': (p['timestamp'] - score_start_time),
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
