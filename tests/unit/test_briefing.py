from datetime import UTC, datetime, timedelta

from chief.draft.focus_line import FocusLine
from chief.models import Feed, FeedItem, RoleKind
from chief.services import applications, briefing


class DummyLLM:
    name = "dummy"


def test_build_briefing_context_falls_back_to_nothing_due_when_no_applications(session):
    ctx = briefing.build_briefing_context(session, DummyLLM())

    assert ctx.focus == "Nothing is due. Add a role: chief jd add <url>"


def test_build_briefing_context_calls_write_focus_line_with_top_and_two_runners_up(session, monkeypatch):
    now = datetime.now(UTC)
    top = applications.add_application(
        session, "Top Co", "SWE", RoleKind.FULLTIME, deadline_at=now - timedelta(days=1)
    )
    r1 = applications.add_application(
        session, "R1 Co", "SWE", RoleKind.FULLTIME, deadline_at=now + timedelta(days=3)
    )
    r2 = applications.add_application(
        session, "R2 Co", "SWE", RoleKind.FULLTIME, deadline_at=now + timedelta(days=4)
    )
    applications.add_application(
        session, "R3 Co", "SWE", RoleKind.FULLTIME, deadline_at=now + timedelta(days=5)
    )
    calls = []

    def fake_write_focus_line(top_arg, runners_up_arg, now_arg, llm_arg, **kwargs):
        calls.append((top_arg.id, [a.id for a in runners_up_arg]))
        return FocusLine(text="focus text", cost_usd=0.01)

    monkeypatch.setattr(briefing, "write_focus_line", fake_write_focus_line)

    ctx = briefing.build_briefing_context(session, DummyLLM(), now=now)

    assert calls[0] == (top.id, [r1.id, r2.id])
    assert ctx.focus == "focus text"


def test_build_briefing_context_zero_cost_on_fallback_path(session):
    ctx = briefing.build_briefing_context(session, DummyLLM())

    assert ctx.footer.cost_usd == 0.0
    assert ctx.footer.prompt_versions == []


def test_build_briefing_context_populates_deadlines_within_7_days(session, monkeypatch):
    now = datetime.now(UTC)
    applications.add_application(
        session, "Near Co", "SWE", RoleKind.FULLTIME, deadline_at=now + timedelta(days=3)
    )
    applications.add_application(
        session, "Far Co", "SWE", RoleKind.FULLTIME, deadline_at=now + timedelta(days=30)
    )
    monkeypatch.setattr(
        briefing, "write_focus_line", lambda *a, **k: FocusLine(text="focus", cost_usd=0.0)
    )

    ctx = briefing.build_briefing_context(session, DummyLLM(), now=now)

    assert [d.company for d in ctx.deadlines] == ["Near Co"]


def test_build_briefing_context_populates_pipeline_and_news(session, monkeypatch):
    now = datetime.now(UTC)
    applications.add_application(session, "Solo Co", "SWE", RoleKind.FULLTIME)
    feed = Feed(url="https://example.com/feed.xml", name="Example Feed")
    session.add(feed)
    session.flush()
    item = FeedItem(
        feed=feed, guid="g1", title="A Post", raw_text="raw text", summary="a summary", importance=0.9
    )
    session.add(item)
    session.flush()
    monkeypatch.setattr(
        briefing, "write_focus_line", lambda *a, **k: FocusLine(text="focus", cost_usd=0.0)
    )

    ctx = briefing.build_briefing_context(session, DummyLLM(), now=now)

    assert ctx.pipeline.tracked == 1
    assert len(ctx.news) == 1
    assert ctx.news[0].headline == "a summary"
