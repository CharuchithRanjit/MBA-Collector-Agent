from datetime import UTC, datetime, timedelta

from chief.draft.focus_line import write_focus_line
from chief.llm.base import LLMResponse
from chief.models import Application, AppStatus, Company, Role, RoleKind

NOW = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)


class ScriptedProvider:
    name = "scripted"

    def __init__(self, response_text: str, cost_usd: float = 0.0):
        self._response_text = response_text
        self._cost_usd = cost_usd
        self.calls = []

    def complete(self, *, prompt, system=None, max_tokens=1024, purpose, prompt_version) -> LLMResponse:
        self.calls.append({"prompt": prompt, "purpose": purpose, "prompt_version": prompt_version})
        return LLMResponse(text=self._response_text, model=self.name, cost_usd=self._cost_usd)

    def structured(self, *, prompt, schema, system=None, purpose, prompt_version):
        raise NotImplementedError


def _make_application(
    session,
    *,
    company_name: str = "Acme",
    tier: int = 2,
    status: AppStatus = AppStatus.INTERESTED,
    deadline_at: datetime | None = None,
    next_action: str | None = None,
    next_action_due_at: datetime | None = None,
    applied_at: datetime | None = None,
) -> Application:
    company = Company(name=company_name, tier=tier)
    session.add(company)
    session.flush()
    role = Role(company_id=company.id, title="Some Role", kind=RoleKind.INTERN, deadline_at=deadline_at)
    session.add(role)
    session.flush()
    application = Application(
        role=role,
        status=status,
        next_action=next_action,
        next_action_due_at=next_action_due_at,
        applied_at=applied_at,
    )
    session.add(application)
    session.flush()
    return application


def test_write_focus_line_returns_text_and_cost_from_llm_complete(session):
    top = _make_application(session, next_action_due_at=NOW + timedelta(hours=5))
    provider = ScriptedProvider("**Submit** the Acme app.", cost_usd=0.004)

    result = write_focus_line(top, [], NOW, provider)

    assert result.text == "**Submit** the Acme app."
    assert result.cost_usd == 0.004


def test_write_focus_line_describes_overdue_next_action_signal(session):
    top = _make_application(
        session, next_action="Follow up", next_action_due_at=NOW - timedelta(days=1)
    )
    provider = ScriptedProvider("text")

    write_focus_line(top, [], NOW, provider)

    assert 'next action "Follow up" is 1 day(s) overdue' in provider.calls[0]["prompt"]


def test_write_focus_line_describes_upcoming_deadline_signal(session):
    top = _make_application(session, deadline_at=NOW + timedelta(hours=48))
    provider = ScriptedProvider("text")

    write_focus_line(top, [], NOW, provider)

    assert "application deadline closes in 48 hours" in provider.calls[0]["prompt"]


def test_write_focus_line_describes_stale_application_signal(session):
    top = _make_application(
        session,
        status=AppStatus.APPLIED,
        applied_at=NOW - timedelta(days=20),
        deadline_at=NOW + timedelta(days=90),
    )
    provider = ScriptedProvider("text")

    write_focus_line(top, [], NOW, provider)

    assert "applied 20 days ago with no response yet" in provider.calls[0]["prompt"]


def test_write_focus_line_includes_up_to_two_runners_up_in_prompt(session):
    top = _make_application(session, company_name="Top Co", next_action_due_at=NOW + timedelta(hours=5))
    runner_1 = _make_application(session, company_name="Runner One", deadline_at=NOW + timedelta(days=5))
    runner_2 = _make_application(session, company_name="Runner Two", deadline_at=NOW + timedelta(days=6))
    provider = ScriptedProvider("text")

    write_focus_line(top, [runner_1, runner_2], NOW, provider)

    prompt = provider.calls[0]["prompt"]
    assert "Runner One" in prompt
    assert "Runner Two" in prompt


def test_write_focus_line_calls_complete_with_focus_line_purpose(session):
    top = _make_application(session, next_action_due_at=NOW + timedelta(hours=5))
    provider = ScriptedProvider("text")

    write_focus_line(top, [], NOW, provider)

    assert provider.calls[0]["purpose"] == "focus_line"
    assert provider.calls[0]["prompt_version"] == "v1"
