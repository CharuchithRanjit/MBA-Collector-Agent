from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlmodel import select

from chief.models import Application, AppStatus, Company, Role, RoleKind
from chief.services import applications


def _make_application_with_tier(session, *, tier: int, deadline_at: datetime) -> Application:
    company = Company(name=f"Co-{uuid4().hex[:8]}", tier=tier)
    session.add(company)
    session.flush()
    role = Role(company_id=company.id, title="Role", kind=RoleKind.FULLTIME, deadline_at=deadline_at)
    session.add(role)
    session.flush()
    application = Application(role=role)
    session.add(application)
    session.flush()
    return application


def test_add_application_reuses_existing_company(session):
    applications.add_application(session, "Acme", "SWE Intern", RoleKind.INTERN)
    applications.add_application(session, "Acme", "PM Intern", RoleKind.INTERN)

    companies = session.exec(select(Company).where(Company.name == "Acme")).all()
    assert len(companies) == 1


def test_due_within_days_excludes_far_future_deadlines(session):
    now = datetime.now(UTC)
    applications.add_application(
        session, "Soon Co", "SWE", RoleKind.FULLTIME, deadline_at=now + timedelta(days=3)
    )
    applications.add_application(
        session, "Later Co", "SWE", RoleKind.FULLTIME, deadline_at=now + timedelta(days=30)
    )

    results = applications.list_applications(session, due_within_days=7)

    companies = {a.role.company.name for a in results}
    assert companies == {"Soon Co"}


def test_move_to_applied_sets_applied_at(session):
    application = applications.add_application(session, "Acme", "SWE Intern", RoleKind.INTERN)

    moved = applications.move_application(session, application.id, status=AppStatus.APPLIED)

    assert moved.status == AppStatus.APPLIED
    assert moved.applied_at is not None


def test_move_application_with_bad_id_raises_value_error(session):
    with pytest.raises(ValueError):
        applications.move_application(session, 9999, status=AppStatus.APPLIED)


def test_undated_roles_sort_last(session):
    applications.add_application(session, "No Deadline Co", "SWE", RoleKind.FULLTIME)
    applications.add_application(
        session,
        "Urgent Co",
        "SWE",
        RoleKind.FULLTIME,
        deadline_at=datetime.now(UTC) + timedelta(days=1),
    )

    results = applications.list_applications(session)

    assert [a.role.company.name for a in results] == ["Urgent Co", "No Deadline Co"]


def test_due_within_days_respects_injected_now(session):
    real_now = datetime.now(UTC)
    applications.add_application(
        session, "Acme", "SWE", RoleKind.FULLTIME, deadline_at=real_now + timedelta(days=3)
    )
    injected_now = real_now - timedelta(days=100)

    results = applications.list_applications(session, due_within_days=7, now=injected_now)

    assert results == []


def test_add_application_persists_jd_url_and_location(session):
    application = applications.add_application(
        session,
        "Acme",
        "SWE Intern",
        RoleKind.INTERN,
        location="Remote",
        jd_url="https://example.com/job/1",
        jd_raw_text="raw jd text",
    )

    assert application.role.location == "Remote"
    assert application.role.jd_url == "https://example.com/job/1"
    assert application.role.jd_raw_text == "raw jd text"


def test_list_applications_ranked_excludes_rejected_and_withdrawn(session):
    now = datetime.now(UTC)
    active = applications.add_application(
        session, "Active Co", "SWE", RoleKind.FULLTIME, deadline_at=now + timedelta(days=3)
    )
    rejected = applications.add_application(
        session, "Rejected Co", "SWE", RoleKind.FULLTIME, deadline_at=now + timedelta(days=1)
    )
    applications.move_application(session, rejected.id, status=AppStatus.REJECTED)
    withdrawn = applications.add_application(
        session, "Withdrawn Co", "SWE", RoleKind.FULLTIME, deadline_at=now + timedelta(days=1)
    )
    applications.move_application(session, withdrawn.id, status=AppStatus.WITHDRAWN)

    results = applications.list_applications_ranked(session, now=now)

    assert [a.id for a in results] == [active.id]


def test_list_applications_ranked_orders_by_score_descending(session):
    now = datetime.now(UTC)
    low = applications.add_application(
        session, "Later Co", "SWE", RoleKind.FULLTIME, deadline_at=now + timedelta(days=180)
    )
    high = applications.add_application(
        session, "Soon Co", "SWE", RoleKind.FULLTIME, deadline_at=now - timedelta(days=1)
    )

    results = applications.list_applications_ranked(session, now=now)

    assert [a.id for a in results] == [high.id, low.id]


def test_list_applications_ranked_respects_injected_now(session):
    # Near-term but tier-3 (safety) beats far-off tier-1 (dream) today; once
    # `now` passes both deadlines they're both "overdue" (urgency saturates
    # identically), and tier alone decides the order. If this function
    # ignored `now` and computed its own, the ranking couldn't flip like this.
    now = datetime.now(UTC)
    near_safety = _make_application_with_tier(session, tier=3, deadline_at=now + timedelta(days=2))
    far_dream = _make_application_with_tier(session, tier=1, deadline_at=now + timedelta(days=10))

    soon_order = applications.list_applications_ranked(session, now=now)
    assert [a.id for a in soon_order] == [near_safety.id, far_dream.id]

    later_now = now + timedelta(days=100)
    later_order = applications.list_applications_ranked(session, now=later_now)
    assert [a.id for a in later_order] == [far_dream.id, near_safety.id]
