"""Deterministic scoring for the daily briefing's focus item.

No I/O — takes `now`. The LLM never picks what's shown, only phrases it
(render.py, a later slice). See CLAUDE.md's "Ranking is deterministic"
rule and the SQLite-naive-datetime landmine this module is the stated
landing spot for.
"""

from datetime import datetime

from chief.models import Application, AppStatus, as_utc

STAGE_WEIGHTS: dict[AppStatus, float] = {
    AppStatus.INTERESTED: 1.0,
    AppStatus.APPLIED: 2.0,
    AppStatus.OA: 3.0,
    AppStatus.PHONE: 4.0,
    AppStatus.ONSITE: 5.0,
    AppStatus.OFFER: 5.0,
}


def _urgency(due_at: datetime | None, now: datetime) -> float:
    if due_at is None:
        return 0.1  # low but nonzero — undated shouldn't vanish entirely
    days = (due_at - now).total_seconds() / 86400
    return 1 / max(days, 0.5)  # division-by-zero guard at due_at == now


def _driving_due_at(application: Application, now: datetime) -> datetime | None:
    """Whichever of next_action_due_at / role.deadline_at is more urgent.

    An overdue next action and a close deadline are both maximally
    urgent — taking the soonest of the two means neither signal gets
    silently ignored just because the other happens to be set.
    """
    # as_utc() here is the landmine CLAUDE.md flags — SQLite reads these
    # back naive; without this, subtraction against `now` raises.
    candidates = [
        d
        for d in (as_utc(application.next_action_due_at), as_utc(application.role.deadline_at))
        if d is not None
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda d: abs((d - now).total_seconds()))


def score(application: Application, now: datetime) -> float:
    due_at = _driving_due_at(application, now)
    urgency = _urgency(due_at, now)
    stage = STAGE_WEIGHTS.get(application.status, 1.0)
    tier_weight = 4 - application.role.company.tier  # tier 1 (dream) -> 3, tier 3 (safety) -> 1
    overdue = 3.0 if due_at and due_at < now else 1.0
    return urgency * stage * tier_weight * overdue


def rank_applications(applications: list[Application], now: datetime) -> list[Application]:
    """Applications sorted by score(), most urgent first.

    Callers are expected to have already excluded terminal statuses
    (REJECTED/WITHDRAWN) — this function scores whatever it's given.
    """
    return sorted(applications, key=lambda a: score(a, now), reverse=True)
