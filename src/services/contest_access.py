import datetime
import enum
from dataclasses import dataclass

from services.contest_session import ContestPhase, ContestSession
from services.contests import Contest, UserStatus
from services.user import Account


class ContestPermission(enum.IntFlag):
    NONE = 0

    # Contest roles. PARTICIPANT intentionally means exactly APPROVED; admins
    # are members but are not normal participants in existing authorization.
    MEMBER = enum.auto()
    PARTICIPANT = enum.auto()
    ADMIN = enum.auto()

    # Effective capabilities. These include the current session phase and the
    # contest's visibility settings, so handlers do not repeat those rules.
    VIEW_PROBLEM_SET = enum.auto()
    VIEW_PROBLEM = enum.auto()
    SUBMIT = enum.auto()
    VIEW_SCOREBOARD = enum.auto()
    VIEW_QA = enum.auto()
    ASK_QUESTION = enum.auto()


@dataclass(frozen=True, slots=True)
class ContestAccess:
    contest: Contest
    session: ContestSession
    permissions: ContestPermission
    resolved_at: datetime.datetime

    @classmethod
    def resolve(
        cls,
        contest: Contest,
        acct: Account,
        now: datetime.datetime | None = None,
    ) -> "ContestAccess":
        now = now or datetime.datetime.now(datetime.UTC)
        session = ContestSession.fixed(contest, acct.acct_id)
        phase = session.phase(now)

        is_member = contest.is_member(acct=acct)
        is_participant = contest.member_is_status(acct, UserStatus.APPROVED)
        is_admin = contest.is_admin(acct=acct)

        permissions = ContestPermission.NONE
        if is_member:
            permissions |= ContestPermission.MEMBER
        if is_participant:
            permissions |= ContestPermission.PARTICIPANT
        if is_admin:
            permissions |= ContestPermission.ADMIN

        if (
            phase is ContestPhase.ENDED
            or (phase is ContestPhase.RUNNING and is_member)
            or (phase is ContestPhase.BEFORE and is_admin)
        ):
            permissions |= ContestPermission.VIEW_PROBLEM_SET

        if is_member and (phase is ContestPhase.RUNNING or is_admin):
            permissions |= ContestPermission.VIEW_PROBLEM | ContestPermission.SUBMIT

        if (phase is not ContestPhase.BEFORE or is_admin) and (
            contest.is_public_scoreboard or is_member
        ):
            permissions |= ContestPermission.VIEW_SCOREBOARD

        if not is_admin:
            permissions |= ContestPermission.VIEW_QA
        if is_participant:
            permissions |= ContestPermission.ASK_QUESTION

        return cls(
            contest=contest,
            session=session,
            permissions=permissions,
            resolved_at=now,
        )

    def has(self, permissions: ContestPermission) -> bool:
        return self.permissions & permissions == permissions

    @property
    def is_member(self) -> bool:
        return self.has(ContestPermission.MEMBER)

    @property
    def is_participant(self) -> bool:
        return self.has(ContestPermission.PARTICIPANT)

    @property
    def is_admin(self) -> bool:
        return self.has(ContestPermission.ADMIN)

    def visible_challenge_accounts(
        self, requested_acct_ids: list[int] | None
    ) -> list[int] | None:
        """Apply the existing challenge-list visibility rules."""
        if self.is_admin:
            return requested_acct_ids

        phase = self.session.phase(self.resolved_at)
        if phase is ContestPhase.BEFORE:
            return []
        if phase is ContestPhase.RUNNING or not self.contest.is_public_scoreboard:
            return [self.session.acct_id]

        if requested_acct_ids is None:
            return [
                acct_id
                for acct_id, options in self.contest.user_list.items()
                if options["status"] == UserStatus.APPROVED
            ]
        return [
            acct_id
            for acct_id in requested_acct_ids
            if not self.contest.is_admin(acct_id=acct_id)
        ]

    def can_view_challenge(self, owner_acct_id: int) -> bool:
        """Check the existing detail-page rule for a contest challenge."""
        if not self.is_member:
            return False

        is_owner = self.session.acct_id == owner_acct_id
        owner_is_admin = self.contest.is_admin(acct_id=owner_acct_id)
        phase = self.session.phase(self.resolved_at)

        if phase is ContestPhase.BEFORE:
            if owner_is_admin and not self.is_admin:
                return False
        elif phase is ContestPhase.RUNNING:
            if self.contest.hide_admin and owner_is_admin and not self.is_admin:
                return False
            if not self.contest.hide_admin and not (is_owner or self.is_admin):
                return False

        if phase is not ContestPhase.RUNNING and not self.contest.is_public_scoreboard:
            return is_owner or self.is_admin
        return True

    def can_view_challenge_update(self, owner_acct_id: int) -> bool:
        """Check whether a live challenge update is visible to this account."""
        if self.is_admin:
            return True

        is_owner = self.session.acct_id == owner_acct_id
        phase = self.session.phase(self.resolved_at)
        if phase is ContestPhase.RUNNING:
            return is_owner
        if phase is ContestPhase.ENDED:
            return is_owner or (
                self.contest.is_public_scoreboard
                and not self.contest.is_admin(acct_id=owner_acct_id)
            )
        return False
