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
    location: str | None = None,
    jd_url: str | None = None,
    jd_raw_text: str | None = None,
    requirements: list[str] | None = None,
) -> Application:
    """Create company (if new), role, and application in one call."""
    company = session.exec(select(Company).where(Company.name == company_name)).first()
    if company is None:
        company = Company(name=company_name)
        session.add(company)
        session.flush()

    role = Role(
        company_id=company.id,
        title=title,
        kind=kind,
        deadline_at=as_utc(deadline_at),
        location=location,
        jd_url=jd_url,
        jd_raw_text=jd_raw_text,
        requirements=requirements if requirements is not None else [],
    )
    session.add(role)
    session.flush()

    # role=role, not role_id=role.id — keeps the relationship populated
    # with this exact Python object. Otherwise, once `role` falls out of
    # scope, a later `.role` access can trigger a fresh SELECT, and
    # SQLite reads datetimes back naive (see CLAUDE.md landmines).
    application = Application(role=role)
    session.add(application)
    session.flush()
    return application


def get_application(session: Session, application_id: int) -> Application:
    """Fetch a single application by id. Raises ValueError if it doesn't exist."""
    application = session.get(Application, application_id)
    if application is None:
        raise ValueError(f"No application with id {application_id}")
    return application


def list_applications(
    session: Session,
    status: AppStatus | None = None,
    due_within_days: int | None = None,
    now: datetime | None = None,
) -> list[Application]:
    """Filter by status and/or upcoming deadline. Ordered by deadline, undated last."""
    now = now or utcnow()
    query = select(Application).join(Role)
    if status is not None:
        query = query.where(Application.status == status)
    if due_within_days is not None:
        cutoff = now + timedelta(days=due_within_days)
        query = query.where(Role.deadline_at.is_not(None)).where(Role.deadline_at <= cutoff)
    query = query.order_by(Role.deadline_at.is_(None), Role.deadline_at)
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
