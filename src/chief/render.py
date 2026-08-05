"""Turns a BriefingContext into markdown or a 3-line push summary.

No I/O, no DB, no LLM — the focus sentence and every other string are
already computed by the time this module sees them. All date math
happens here in Python, once, from the passed `now` — never inside a
template, never a fresh datetime.now() call.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)

CAP = 5


@dataclass
class DeadlineRow:
    deadline_at: datetime
    company: str
    role: str
    status_label: str  # "not started", "draft saved" -- free text, not AppStatus


@dataclass
class NextActionRow:
    due_at: datetime
    company: str
    text: str


@dataclass
class PipelineCounts:
    tracked: int
    applied: int
    in_process: int
    offer_stage: int
    not_started: int
    stale: list[str]  # company names ("applied 17d ago, no response")


@dataclass
class NewsItem:
    category: str
    headline: str
    source: str
    read_time: str  # "2 min", "skim"


@dataclass
class BriefingFooter:
    generated_at: datetime
    items_scanned: int
    items_kept: int
    cost_usd: float
    prompt_versions: list[str]


@dataclass
class BriefingContext:
    for_date: datetime
    focus: str  # already-generated sentence or fallback-ladder text; render.py never picks it
    deadlines: list[DeadlineRow]
    next_actions: list[NextActionRow]
    pipeline: PipelineCounts
    news: list[NewsItem]
    footer: BriefingFooter
    follow_ups: list = field(default_factory=list)  # empty until contacts slice
    matches: list = field(default_factory=list)  # empty until gap-analysis slice
    calendar: list = field(default_factory=list)  # empty until calendar slice


def _format_day(dt: datetime) -> str:
    return dt.strftime("%a %b %-d")  # "Fri Oct 17"


def _when_label(due_at: datetime, now: datetime) -> str:
    return "Today" if due_at.date() == now.date() else _format_day(due_at)


def _capped(items: list, cap: int = CAP) -> tuple[list, int]:
    """Returns (visible items, overflow count) per the hard-cap renderer rule."""
    return items[:cap], max(0, len(items) - cap)


def render_full(ctx: BriefingContext, now: datetime) -> str:
    deadlines, deadlines_overflow = _capped(ctx.deadlines)
    next_actions, next_actions_overflow = _capped(ctx.next_actions)
    news, news_overflow = _capped(ctx.news)
    template = _env.get_template("briefing.md.j2")
    return template.render(
        header_date=_format_day(ctx.for_date),
        focus=ctx.focus,
        deadlines=[
            {
                "when": _format_day(d.deadline_at),
                "company": d.company,
                "role": d.role,
                "status_label": d.status_label,
            }
            for d in deadlines
        ],
        deadlines_overflow=deadlines_overflow,
        next_actions=[
            {"when": _when_label(a.due_at, now), "company": a.company, "text": a.text}
            for a in next_actions
        ],
        next_actions_overflow=next_actions_overflow,
        pipeline=ctx.pipeline,
        news=news,
        news_total=len(ctx.news),
        news_overflow=news_overflow,
        generated_label=ctx.footer.generated_at.strftime("%Y-%m-%d %H:%M"),
        items_scanned=ctx.footer.items_scanned,
        items_kept=ctx.footer.items_kept,
        cost_label=f"${ctx.footer.cost_usd:.3f}",
        prompt_versions_label=(
            ", ".join(ctx.footer.prompt_versions) if ctx.footer.prompt_versions else "none"
        ),
    )


def render_push(ctx: BriefingContext, now: datetime) -> str:
    template = _env.get_template("briefing_push.txt.j2")
    return template.render(
        header_date=_format_day(ctx.for_date),
        focus=ctx.focus,
        next_actions_due_today=sum(1 for a in ctx.next_actions if a.due_at.date() == now.date()),
        deadlines_this_week=len(ctx.deadlines),
        news_count=len(ctx.news),
    )
