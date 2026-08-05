"""CLI entrypoint. Commands parse, call a service, and render. Nothing else."""

import sys
from datetime import UTC, datetime
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from chief import notify
from chief.config import settings
from chief.db import get_session, init_db
from chief.fetch import FetchError
from chief.llm.factory import get_llm_provider
from chief.models import Application, AppStatus, Feed, RoleKind, as_utc
from chief.notify import NotifyError
from chief.render import render_full, render_push
from chief.services import applications, briefing, feeds, jobs, summarize

app = typer.Typer(pretty_exceptions_show_locals=False)
app_cmd = typer.Typer()
app.add_typer(app_cmd, name="app")
jd_cmd = typer.Typer()
app.add_typer(jd_cmd, name="jd")
feed_cmd = typer.Typer()
app.add_typer(feed_cmd, name="feed")

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


def _render_requirements(application: Application) -> None:
    role = application.role
    deadline = as_utc(role.deadline_at)
    console.print(f"{role.company.name} — {role.title}", highlight=False)
    console.print(f"Location: {role.location or '—'}", highlight=False)
    console.print(f"Deadline: {deadline.date().isoformat() if deadline else '—'}", highlight=False)
    console.print("Requirements:", highlight=False)
    for requirement in role.requirements:
        console.print(f"  • {requirement}", highlight=False)
    if not role.requirements:
        console.print("  (none extracted)", highlight=False)


def _render_feeds(rows: list[Feed]) -> None:
    table = Table("ID", "Name", "Category", "Last Fetched", "Etag")
    for f in rows:
        last_fetched = as_utc(f.last_fetched_at)
        table.add_row(
            str(f.id),
            f.name,
            f.category or "",
            last_fetched.isoformat() if last_fetched else "",
            "yes" if f.etag else "no",
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
    ranked: Annotated[bool, typer.Option("--ranked")] = False,
) -> None:
    with get_session() as session:
        rows = (
            applications.list_applications_ranked(session)
            if ranked
            else applications.list_applications(session, status, due_within_days)
        )
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
    try:
        with get_session() as session:
            result = jobs.ingest_jd(session, get_llm_provider(), url=url, pasted_text=pasted_text)
    except FetchError as e:
        console.print(f"{e}. Copy the page text and run:\n  chief jd add --paste", highlight=False)
        raise typer.Exit(code=1) from None
    console.print(f"Added application {result.id}")


@jd_cmd.command("show")
def jd_show(application_id: int) -> None:
    with get_session() as session:
        application = applications.get_application(session, application_id)
        _render_requirements(application)


@feed_cmd.command("add")
def feed_add(
    url: str,
    name: Annotated[str, typer.Option("--name")],
    category: Annotated[str | None, typer.Option("--category")] = None,
) -> None:
    with get_session() as session:
        result = feeds.add_feed(session, url, name, category)
    console.print(f"Added feed {result.id}: {result.name}")


@feed_cmd.command("list")
def feed_list() -> None:
    with get_session() as session:
        rows = feeds.list_feeds(session)
        _render_feeds(rows)


@feed_cmd.command("poll")
def feed_poll(
    feed_id: Annotated[int | None, typer.Argument()] = None,
    all_: Annotated[bool, typer.Option("--all")] = False,
) -> None:
    if feed_id is None and not all_:
        console.print("Specify a feed id or --all", highlight=False)
        raise typer.Exit(code=1)
    try:
        with get_session() as session:
            if all_:
                results = feeds.poll_all_feeds(session)
                total = sum(len(items) for items in results.values())
                console.print(f"Polled {len(results)} feeds, {total} new items")
            else:
                feed = feeds.get_feed(session, feed_id)
                new_items = feeds.poll_feed(session, feed)
                console.print(f"Polled {feed.name}: {len(new_items)} new items")
    except FetchError as e:
        console.print(str(e), highlight=False)
        raise typer.Exit(code=1) from None


@feed_cmd.command("summarize")
def feed_summarize(
    limit: Annotated[int, typer.Option("--limit")] = summarize.DEFAULT_BATCH_LIMIT,
) -> None:
    with get_session() as session:
        updated = summarize.summarize_pending_items(session, get_llm_provider(), limit=limit)
    console.print(f"Summarized {len(updated)} items")


@app.command("brief")
def brief(send: Annotated[bool, typer.Option("--send")] = False) -> None:
    with get_session() as session:
        ctx = briefing.build_briefing_context(session, get_llm_provider())
    print(render_full(ctx, ctx.for_date))

    if not send:
        return
    if not settings.ntfy_topic:
        console.print("Set NTFY_TOPIC in .env to use --send", highlight=False)
        raise typer.Exit(code=1)
    try:
        notify.send_push(render_push(ctx, ctx.for_date), settings.ntfy_topic)
    except NotifyError as e:
        console.print(str(e), highlight=False)
        raise typer.Exit(code=1) from None
    console.print("Pushed to phone", highlight=False)
