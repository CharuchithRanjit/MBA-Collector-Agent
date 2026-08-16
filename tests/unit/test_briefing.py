from datetime import UTC, date, datetime, timedelta

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


def test_get_or_create_briefing_generates_on_first_call_of_day(session, monkeypatch):
    now = datetime.now(UTC)
    monkeypatch.setattr(
        briefing, "write_focus_line", lambda *a, **k: FocusLine(text="focus", cost_usd=0.0)
    )

    row = briefing.get_or_create_briefing(session, DummyLLM(), now=now)

    assert row.for_date == now.date()
    assert "Nothing is due" in row.markdown
    assert row.pushed_at is None


def test_get_or_create_briefing_returns_cached_row_on_second_call_same_day(session, monkeypatch):
    now = datetime.now(UTC)
    monkeypatch.setattr(
        briefing, "write_focus_line", lambda *a, **k: FocusLine(text="focus", cost_usd=0.0)
    )

    first = briefing.get_or_create_briefing(session, DummyLLM(), now=now)
    second = briefing.get_or_create_briefing(session, DummyLLM(), now=now + timedelta(hours=2))

    assert first.id == second.id


def test_get_or_create_briefing_does_not_call_write_focus_line_on_cache_hit(session, monkeypatch):
    now = datetime.now(UTC)
    applications.add_application(
        session, "Some Co", "SWE", RoleKind.FULLTIME, deadline_at=now + timedelta(days=3)
    )
    calls = []
    monkeypatch.setattr(
        briefing,
        "write_focus_line",
        lambda *a, **k: (calls.append(1) or FocusLine(text="focus", cost_usd=0.01)),
    )

    briefing.get_or_create_briefing(session, DummyLLM(), now=now)
    briefing.get_or_create_briefing(session, DummyLLM(), now=now + timedelta(hours=2))

    assert len(calls) == 1


def test_get_or_create_briefing_generates_fresh_row_for_a_different_day(session, monkeypatch):
    day1 = datetime(2026, 1, 1, tzinfo=UTC)
    day2 = datetime(2026, 1, 2, tzinfo=UTC)
    monkeypatch.setattr(
        briefing, "write_focus_line", lambda *a, **k: FocusLine(text="focus", cost_usd=0.0)
    )

    row1 = briefing.get_or_create_briefing(session, DummyLLM(), now=day1)
    row2 = briefing.get_or_create_briefing(session, DummyLLM(), now=day2)

    assert row1.id != row2.id
    assert row1.for_date == date(2026, 1, 1)
    assert row2.for_date == date(2026, 1, 2)


def test_build_briefing_context_marks_selected_news_items_shown(session, monkeypatch):
    now = datetime.now(UTC)
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

    briefing.build_briefing_context(session, DummyLLM(), now=now)

    assert item.shown_at == now


def test_get_or_create_briefing_cache_hit_does_not_remark_shown_items(session, monkeypatch):
    now = datetime.now(UTC)
    monkeypatch.setattr(
        briefing, "write_focus_line", lambda *a, **k: FocusLine(text="focus", cost_usd=0.0)
    )
    calls = []
    original = briefing.feeds.mark_items_shown

    def fake_mark(session_arg, item_ids, now=None):
        calls.append(item_ids)
        return original(session_arg, item_ids, now=now)

    monkeypatch.setattr(briefing.feeds, "mark_items_shown", fake_mark)

    briefing.get_or_create_briefing(session, DummyLLM(), now=now)
    briefing.get_or_create_briefing(session, DummyLLM(), now=now + timedelta(hours=2))

    assert len(calls) == 1


def test_send_news_detail_pushes_sends_one_push_per_shown_item(session, monkeypatch):
    feed = Feed(url="https://example.com/feed.xml", name="Example Feed")
    session.add(feed)
    session.flush()
    item1 = FeedItem(
        feed=feed, guid="g1", title="T1", raw_text="raw text", summary="s1", importance=0.9
    )
    item2 = FeedItem(
        feed=feed, guid="g2", title="T2", raw_text="raw text", summary="s2", importance=0.8
    )
    session.add(item1)
    session.add(item2)
    session.flush()
    now = datetime(2026, 1, 1, tzinfo=UTC)
    briefing.feeds.mark_items_shown(session, [item1.id, item2.id], now=now)
    calls = []
    monkeypatch.setattr(briefing.notify, "send_push", lambda text, topic: calls.append((text, topic)))

    count = briefing.send_news_detail_pushes(session, "my-topic", now.date())

    assert count == 2
    assert len(calls) == 2
    assert all(topic == "my-topic" for _, topic in calls)
    assert any("T1" in text for text, _ in calls)
    assert any("T2" in text for text, _ in calls)


def test_send_news_detail_pushes_sends_nothing_for_a_date_with_no_shown_items(session):
    count = briefing.send_news_detail_pushes(session, "my-topic", date(2020, 1, 1))

    assert count == 0


def test_get_briefing_by_date_returns_none_when_not_found(session):
    result = briefing.get_briefing_by_date(session, date(2020, 1, 1))

    assert result is None


def test_mark_briefing_pushed_sets_pushed_at(session, monkeypatch):
    now = datetime.now(UTC)
    monkeypatch.setattr(
        briefing, "write_focus_line", lambda *a, **k: FocusLine(text="focus", cost_usd=0.0)
    )
    row = briefing.get_or_create_briefing(session, DummyLLM(), now=now)
    assert row.pushed_at is None

    briefing.mark_briefing_pushed(session, row, now=now)

    assert row.pushed_at == now
