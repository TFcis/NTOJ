import datetime
import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.contests import Contest


class ContestPhase(enum.IntEnum):
    BEFORE = 0
    RUNNING = 1
    ENDED = 2


@dataclass(frozen=True, slots=True)
class ContestSession:
    """The effective contest time window for one account.

    Fixed contests currently give every account the contest's configured time
    window. Keeping that decision here gives future contest modes one place to
    provide account-specific windows without changing handlers or scoreboards.
    """

    contest_id: int
    acct_id: int | None
    start_time: datetime.datetime
    end_time: datetime.datetime

    @classmethod
    def fixed(cls, contest: "Contest", acct_id: int | None = None) -> "ContestSession":
        return cls(
            contest_id=contest.contest_id,
            acct_id=acct_id,
            start_time=contest.contest_start,
            end_time=contest.contest_end,
        )

    @property
    def duration(self) -> datetime.timedelta:
        return self.end_time - self.start_time

    def phase(self, now: datetime.datetime | None = None) -> ContestPhase:
        now = now or datetime.datetime.now(datetime.UTC)
        if now < self.start_time:
            return ContestPhase.BEFORE
        if now < self.end_time:
            return ContestPhase.RUNNING
        return ContestPhase.ENDED

    def is_started(self, now: datetime.datetime | None = None) -> bool:
        return self.phase(now) is not ContestPhase.BEFORE

    def is_running(self, now: datetime.datetime | None = None) -> bool:
        return self.phase(now) is ContestPhase.RUNNING

    def is_ended(self, now: datetime.datetime | None = None) -> bool:
        return self.phase(now) is ContestPhase.ENDED
