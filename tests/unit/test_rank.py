from datetime import UTC, datetime, timedelta
from uuid import uuid4

from chief.models import Application, AppStatus, Company, Role, RoleKind
from chief.rank import rank_applications, score

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _make_application(
    session,
    *,
    tier: int = 2,
    status: AppStatus = AppStatus.INTERESTED,
    deadline_at: datetime | None = None,
    next_action_due_at: datetime | None = None,
) -> Application:
    company = Company(name=f"Company-{uuid4().hex[:8]}", tier=tier)
    session.add(company)
    session.flush()
    role = Role(company_id=company.id, title="Some Role", kind=RoleKind.INTERN, deadline_at=deadline_at)
    session.add(role)
    session.flush()
    application = Application(role=role, status=status, next_action_due_at=next_action_due_at)
    session.add(application)
    session.flush()
    return application


def test_overdue_application_outranks_one_due_today(session):
    overdue = _make_application(session, next_action_due_at=NOW - timedelta(days=1))
    due_later_today = _make_application(session, next_action_due_at=NOW + timedelta(hours=1))

    assert score(overdue, NOW) > score(due_later_today, NOW)


def test_tier_one_company_outranks_tier_three_at_equal_urgency(session):
    due = NOW + timedelta(days=3)
    dream = _make_application(session, tier=1, next_action_due_at=due)
    safety = _make_application(session, tier=3, next_action_due_at=due)

    assert score(dream, NOW) > score(safety, NOW)


def test_deadline_six_months_out_has_near_zero_score(session):
    far_future = _make_application(session, next_action_due_at=NOW + timedelta(days=180))

    assert score(far_future, NOW) < 0.1


def test_score_does_not_raise_when_due_at_equals_now(session):
    due_now = _make_application(session, next_action_due_at=NOW)

    result = score(due_now, NOW)

    assert isinstance(result, float)


def test_undated_application_scores_above_zero_but_below_any_dated_one(session):
    undated = _make_application(session)
    dated = _make_application(session, next_action_due_at=NOW + timedelta(days=3))

    undated_score = score(undated, NOW)

    assert undated_score > 0
    assert undated_score < score(dated, NOW)


def test_score_uses_whichever_due_date_is_sooner_when_both_set(session):
    overdue_next_action_far_deadline = _make_application(
        session,
        next_action_due_at=NOW - timedelta(days=1),
        deadline_at=NOW + timedelta(days=180),
    )
    only_far_deadline = _make_application(session, deadline_at=NOW + timedelta(days=180))

    assert score(overdue_next_action_far_deadline, NOW) > score(only_far_deadline, NOW)


def test_rank_applications_sorts_descending_by_score(session):
    low = _make_application(session, next_action_due_at=NOW + timedelta(days=180))
    high = _make_application(session, next_action_due_at=NOW - timedelta(days=1))
    mid = _make_application(session, next_action_due_at=NOW + timedelta(days=3))

    ranked = rank_applications([low, mid, high], NOW)

    assert ranked == [high, mid, low]
