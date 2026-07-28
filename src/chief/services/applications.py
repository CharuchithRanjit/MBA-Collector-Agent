"""Application tracker. No LLM anywhere in this file."""

from datetime import datetime, timedelta

from sqlmodel import Session, select

from chief.models import Application, AppStatus, Company, Role, RoleKind, as_utc, utcnow


def add_application(
    session: Session,
    company_name: str,
    title: str,
    kind: RoleKind,
    deadline_at: datetime | None = None,
    tier: int = 2,
) -> Application:
    """Create company (if new), role, and application in one call."""
    company = session.exec(select(Company).where(Company.name == company_name)).first()
    if company is None:
        company = Company(name=company_name, tier=tier)
        session.add(company)
        session.flush()

    role = Role(company_id=company.id, title=title, kind=kind, deadline_at=as_utc(deadline_at))
    session.add(role)
    session.flush()

    application = Application(role_id=role.id)
    session.add(application)
    session.flush()
    return application


def list_applications(
    session: Session,
    status: AppStatus | None = None,
    due_within_days: int | None = None,
) -> list[Application]:
    """Filter by status and/or upcoming deadline. Ordered by deadline."""
    query = select(Application).join(Role)
    if status is not None:
        query = query.where(Application.status == status)
    if due_within_days is not None:
        cutoff = utcnow() + timedelta(days=due_within_days)
        query = query.where(Role.deadline_at.is_not(None)).where(Role.deadline_at <= cutoff)
    query = query.order_by(Role.deadline_at)
    return list(session.exec(query).all())


def move_application(
    session: Session,
    application_id: int,
    status: AppStatus | None = None,
    next_action: str | None = None,
    next_action_due_at: datetime | None = None,
) -> Application:
    """Update status and/or next action. Sets applied_at on first move to APPLIED."""
    application = session.get(Application, application_id)
    if application is None:
        raise ValueError(f"No application with id {application_id}")

    if status is not None:
        if status == AppStatus.APPLIED and application.applied_at is None:
            application.applied_at = utcnow()
        application.status = status
    if next_action is not None:
        application.next_action = next_action
    if next_action_due_at is not None:
        application.next_action_due_at = as_utc(next_action_due_at)

    session.add(application)
    session.flush()
    return application
