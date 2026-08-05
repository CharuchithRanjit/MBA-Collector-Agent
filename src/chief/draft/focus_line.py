"""Writes the one-sentence focus line for the daily briefing.

Shape B (draft) — a human reads this, never auto-sent anywhere. Uses
llm.complete(), not structured(): there's no schema here, just prose.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from chief.llm.base import LLMProvider
from chief.models import Application, AppStatus, as_utc

PROMPTS_DIR = Path(__file__).parent.parent / "llm" / "prompts"


@dataclass
class FocusLine:
    text: str
    cost_usd: float


def _signal_for(application: Application, now: datetime) -> str:
    """Deterministic classification of *why* this application is urgent —
    grounds the LLM in real numbers so it can't hallucinate a time figure.
    """
    next_action_due = as_utc(application.next_action_due_at)
    deadline = as_utc(application.role.deadline_at)

    if next_action_due and next_action_due < now:
        days_late = (now - next_action_due).days
        return f'next action "{application.next_action}" is {days_late} day(s) overdue'
    if next_action_due:
        hours = int((next_action_due - now).total_seconds() // 3600)
        return f'next action "{application.next_action}" is due in {hours} hours'
    if deadline and deadline < now + timedelta(days=7):
        hours = int((deadline - now).total_seconds() // 3600)
        return f"application deadline closes in {hours} hours"
    if (
        application.status == AppStatus.APPLIED
        and application.applied_at
        and (now - as_utc(application.applied_at)).days > 14
    ):
        days = (now - as_utc(application.applied_at)).days
        return f"applied {days} days ago with no response yet"
    return "saved but no action taken yet"


def _describe(application: Application, now: datetime) -> str:
    return (
        f"{application.role.company.name} (tier {application.role.company.tier}) — "
        f"{application.role.title} — {_signal_for(application, now)}"
    )


def write_focus_line(
    top: Application,
    runners_up: list[Application],
    now: datetime,
    llm: LLMProvider,
    *,
    prompt_version: str = "v1",
) -> FocusLine:
    template = (PROMPTS_DIR / f"focus_line.{prompt_version}.md").read_text()
    prompt = (
        f"{template}\n\n---\nTOP APPLICATION:\n{_describe(top, now)}\n\n"
        "RUNNER-UP APPLICATIONS (context only):\n"
        + "\n".join(f"{i + 1}. {_describe(a, now)}" for i, a in enumerate(runners_up))
    )
    response = llm.complete(prompt=prompt, purpose="focus_line", prompt_version=prompt_version)
    return FocusLine(text=response.text.strip(), cost_usd=response.cost_usd)
