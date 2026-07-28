from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import select

from chief.models import AppStatus, Company, RoleKind
from chief.services import applications


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
