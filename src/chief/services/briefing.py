"""Assembles a real BriefingContext. The only place all four pieces
(rank, the focus-line LLM call, news selection, render) meet."""

from datetime import date, datetime

from sqlmodel import Session, select

from chief.draft.focus_line import write_focus_line
from chief.llm.base import LLMProvider
from chief.models import Briefing, utcnow
from chief.render import (
    BriefingContext,
    BriefingFooter,
    DeadlineRow,
    NewsItem,
    NextActionRow,
    PipelineCounts,
    render_full,
    render_html,
    render_push,
)
from chief.services import applications, feeds

NEWS_READ_WPM = 200


def _read_time(raw_text: str | None) -> str:
    if not raw_text:
        return "skim"
    minutes = max(1, len(raw_text.split()) // NEWS_READ_WPM)
    return f"{minutes} min"


def build_briefing_context(
    session: Session, llm: LLMProvider, now: datetime | None = None
) -> BriefingContext:
    now = now or utcnow()
    ranked = applications.list_applications_ranked(session, now=now)

    if ranked:
        top, *rest = ranked
        focus_line = write_focus_line(top, rest[:2], now, llm)
        focus, cost_usd, prompt_versions = focus_line.text, focus_line.cost_usd, ["focus_line.v1"]
    else:
        focus = "Nothing is due. Add a role: chief jd add <url>"
        cost_usd, prompt_versions = 0.0, []

    deadlines = [
        DeadlineRow(a.role.deadline_at, a.role.company.name, a.role.title, a.status.value)
        for a in applications.list_applications(session, due_within_days=7, now=now)
        if a.role.deadline_at is not None
    ]
    next_actions = [
        NextActionRow(a.next_action_due_at, a.role.company.name, a.next_action)
        for a in applications.list_next_actions_due(session, now=now)
    ]
    pipeline = PipelineCounts(**applications.get_pipeline_summary(session, now=now))

    news_items = feeds.get_top_news_items(session)
    news = [
        NewsItem(
            item.feed.category or "News",
            item.summary,
            item.feed.name,
            _read_time(item.raw_text),
            title=item.title,
        )
        for item in news_items
    ]

    footer = BriefingFooter(
        generated_at=now,
        items_scanned=feeds.count_summarized_items(session),
        items_kept=len(news),
        cost_usd=cost_usd,
        prompt_versions=prompt_versions,
    )
    return BriefingContext(now, focus, deadlines, next_actions, pipeline, news, footer)


def get_or_create_briefing(
    session: Session, llm: LLMProvider, now: datetime | None = None
) -> Briefing:
    """One row per calendar day. Cache hit skips the LLM call entirely."""
    now = now or utcnow()
    today = now.date()
    existing = session.exec(select(Briefing).where(Briefing.for_date == today)).first()
    if existing:
        return existing

    ctx = build_briefing_context(session, llm, now=now)
    row = Briefing(
        for_date=today,
        markdown=render_full(ctx, now),
        html=render_html(ctx, now),
        push_text=render_push(ctx, now),
        cost_usd=ctx.footer.cost_usd,
        generated_at=now,
    )
    session.add(row)
    session.flush()
    return row


def get_briefing_by_date(session: Session, for_date: date) -> Briefing | None:
    return session.exec(select(Briefing).where(Briefing.for_date == for_date)).first()


def mark_briefing_pushed(session: Session, briefing: Briefing, now: datetime | None = None) -> None:
    briefing.pushed_at = now or utcnow()
    session.add(briefing)
    session.flush()
