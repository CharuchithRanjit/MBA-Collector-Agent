"""CLI entrypoint. Commands parse, call a service, and render. Nothing else."""

import sys
from datetime import UTC, datetime
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from chief.db import get_session, init_db
from chief.llm.factory import get_llm_provider
from chief.models import Application, AppStatus, RoleKind, as_utc
from chief.services import applications, jobs

app = typer.Typer(pretty_exceptions_show_locals=False)
app_cmd = typer.Typer()
app.add_typer(app_cmd, name="app")
jd_cmd = typer.Typer()
app.add_typer(jd_cmd, name="jd")

console = Console()


def _parse_deadline(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)


def _render(rows: list[Application]) -> None:
    table = Table("ID", "Company", "Title", "Status", "Deadline", "Next Action")
    for a in rows:
        deadline = as_utc(a.role.deadline_at)
        table.add_row(
            str(a.id),
            a.role.company.name,
            a.role.title,
            a.status,
            deadline.date().isoformat() if deadline else "",
            a.next_action or "",
        )
    console.print(table)


@app_cmd.command("add")
def add(
    company: str,
    title: str,
    kind: RoleKind,
    deadline: Annotated[str | None, typer.Option("--deadline")] = None,
) -> None:
    with get_session() as session:
        result = applications.add_application(session, company, title, kind, _parse_deadline(deadline))
    console.print(f"Added application {result.id}")


@app_cmd.command("list")
def list_(
    status: Annotated[AppStatus | None, typer.Option("--status")] = None,
    due_within_days: Annotated[int | None, typer.Option("--due-within-days")] = None,
) -> None:
    with get_session() as session:
        rows = applications.list_applications(session, status, due_within_days)
        _render(rows)

@app.callback()
def _bootstrap() -> None:
    """Runs before any command. Idempotent."""
    init_db()


@app_cmd.command("move")
def move(
    application_id: int,
    status: Annotated[AppStatus | None, typer.Option("--status")] = None,
    next_action: Annotated[str | None, typer.Option("--next-action")] = None,
    next_action_due: Annotated[str | None, typer.Option("--next-action-due")] = None,
) -> None:
    with get_session() as session:
        applications.move_application(
            session, application_id, status, next_action, _parse_deadline(next_action_due)
        )
    console.print(f"Moved application {application_id}")


@jd_cmd.command("add")
def jd_add(
    url: Annotated[str | None, typer.Argument()] = None,
    paste: Annotated[bool, typer.Option("--paste")] = False,
) -> None:
    pasted_text = sys.stdin.read() if paste else None
    with get_session() as session:
        result = jobs.ingest_jd(session, get_llm_provider(), url=url, pasted_text=pasted_text)
    console.print(f"Added application {result.id}")
