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


class ContestSessionType(enum.IntEnum):
    """A session category; VIRTUAL can be added without changing consumers."""

    OFFICIAL = 0


@dataclass(frozen=True, slots=True)
class ContestScoreboardContext:
    """Select which session family owns scoreboard time windows and caches."""

    session_type: ContestSessionType
    use_stored_sessions: bool
    visible_elapsed: datetime.timedelta | None = None

    @classmethod
    def official(
        cls,
        visible_elapsed: datetime.timedelta | None = None,
    ) -> "ContestScoreboardContext":
        return cls(
            session_type=ContestSessionType.OFFICIAL,
            use_stored_sessions=False,
            visible_elapsed=visible_elapsed,
        )

    @property
    def is_viewer_relative(self) -> bool:
        return self.visible_elapsed is not None

    def cache_name(self, contest_id: int) -> str:
        if self.session_type is ContestSessionType.OFFICIAL:
            return f"contest_{contest_id}_scores"
        return f"contest_{contest_id}_{int(self.session_type)}_scores"


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
    session_id: int | None = None
    session_type: ContestSessionType = ContestSessionType.OFFICIAL
    activated: bool = True

    @classmethod
    def fixed(cls, contest: "Contest", acct_id: int | None = None) -> "ContestSession":
        return cls(
            contest_id=contest.contest_id,
            acct_id=acct_id,
            start_time=contest.contest_start,
            end_time=contest.contest_end,
        )

    @classmethod
    def for_account(cls, contest: "Contest", acct_id: int | None) -> "ContestSession":
        """Resolve the official effective window from already-loaded contest data."""
        from services.contests import ContestTimeMode, UserStatus

        if contest.contest_time_mode is ContestTimeMode.FIXED:
            return cls.fixed(contest, acct_id)

        options = contest.user_list.get(acct_id)
        if options is not None and options["status"] is UserStatus.APPROVED:
            if options.get("session_start") is not None:
                return cls(
                    contest_id=contest.contest_id,
                    acct_id=acct_id,
                    start_time=options["session_start"],
                    end_time=options["session_end"],
                    session_id=options["session_id"],
                )
            return cls(
                contest_id=contest.contest_id,
                acct_id=acct_id,
                start_time=contest.contest_start,
                end_time=contest.contest_end,
                activated=False,
            )

        # Admins and non-participants use the configured window for page state;
        # capabilities still come from ContestAccess.
        return cls.fixed(contest, acct_id)

    @property
    def duration(self) -> datetime.timedelta:
        return self.end_time - self.start_time

    def phase(self, now: datetime.datetime | None = None) -> ContestPhase:
        if not self.activated:
            return ContestPhase.BEFORE
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
