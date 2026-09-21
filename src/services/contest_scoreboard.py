import datetime
import json
from dataclasses import dataclass

from services.chal import ChalConst
from services.contest_session import ContestSessionType
from services.contests import UserStatus


@dataclass(frozen=True, slots=True)
class ContestScoreboardUpdate:
    contest_id: int
    chal_id: int | None = None
    elapsed: datetime.timedelta | None = None

    def dumps(self) -> str:
        return json.dumps({
            "contest_id": self.contest_id,
            "chal_id": self.chal_id,
            "elapsed_seconds": (
                self.elapsed.total_seconds() if self.elapsed is not None else None
            ),
        })

    @classmethod
    def loads(cls, data: str | bytes | int) -> "ContestScoreboardUpdate":
        if isinstance(data, bytes):
            data = data.decode()

        try:
            parsed = json.loads(data) if isinstance(data, str) else data
        except (TypeError, json.JSONDecodeError):
            parsed = data

        if not isinstance(parsed, dict):
            return cls(contest_id=int(parsed))

        elapsed_seconds = parsed.get("elapsed_seconds")
        return cls(
            contest_id=int(parsed["contest_id"]),
            chal_id=(
                int(parsed["chal_id"])
                if parsed.get("chal_id") is not None
                else None
            ),
            elapsed=(
                datetime.timedelta(seconds=float(elapsed_seconds))
                if elapsed_seconds is not None
                else None
            ),
        )


class ContestScoreboardRevealService:
    """Resolve score changes on each participant's relative contest timeline."""

    def __init__(self, db):
        self.db = db

    async def build_update(
        self,
        contest_id: int,
        chal_id: int,
    ) -> ContestScoreboardUpdate:
        elapsed = await self.db.fetchval(
            """
            SELECT challenge.timestamp - contest_sessions.start_time
            FROM challenge
            INNER JOIN contest_sessions
              ON contest_sessions.contest_id = challenge.contest_id
             AND contest_sessions.acct_id = challenge.acct_id
             AND contest_sessions.session_type = $3
            INNER JOIN contest_users
              ON contest_users.contest_id = challenge.contest_id
             AND contest_users.acct_id = challenge.acct_id
             AND contest_users.status = $4
            WHERE challenge.contest_id = $1
              AND challenge.chal_id = $2
              AND challenge.timestamp >= contest_sessions.start_time
              AND challenge.timestamp < contest_sessions.end_time
            """,
            contest_id,
            chal_id,
            int(ContestSessionType.OFFICIAL),
            int(UserStatus.APPROVED),
        )
        return ContestScoreboardUpdate(
            contest_id=contest_id,
            chal_id=chal_id,
            elapsed=elapsed,
        )

    async def get_next_elapsed(
        self,
        contest_id: int,
        after_elapsed: datetime.timedelta,
        max_elapsed: datetime.timedelta,
    ) -> datetime.timedelta | None:
        return await self.db.fetchval(
            """
            SELECT MIN(challenge.timestamp - contest_sessions.start_time)
            FROM challenge
            INNER JOIN contest_sessions
              ON contest_sessions.contest_id = challenge.contest_id
             AND contest_sessions.acct_id = challenge.acct_id
             AND contest_sessions.session_type = $4
            INNER JOIN contest_users
              ON contest_users.contest_id = challenge.contest_id
             AND contest_users.acct_id = challenge.acct_id
             AND contest_users.status = $5
            INNER JOIN total_result
              ON total_result.chal_id = challenge.chal_id
            WHERE challenge.contest_id = $1
              AND challenge.timestamp >= contest_sessions.start_time
              AND challenge.timestamp < contest_sessions.end_time
              AND challenge.timestamp - contest_sessions.start_time > $2::interval
              AND challenge.timestamp - contest_sessions.start_time <= $3::interval
              AND total_result.state NOT IN ($6, $7)
            """,
            contest_id,
            after_elapsed,
            max_elapsed,
            int(ContestSessionType.OFFICIAL),
            int(UserStatus.APPROVED),
            ChalConst.STATE_JUDGE,
            ChalConst.STATE_NOTSTARTED,
        )
