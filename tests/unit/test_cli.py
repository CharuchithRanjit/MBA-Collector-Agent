from datetime import UTC, datetime, timedelta

from typer.testing import CliRunner

import chief.cli as cli_module
from chief.analyze.summarize import ItemSummary
from chief.fetch import FetchError
from chief.models import Feed, FeedItem, RoleKind
from chief.rss import FeedEntry, FetchFeedResult
from chief.services import applications
from chief.services import feeds as feeds_module
from chief.services import summarize as summarize_module

runner = CliRunner()


def test_jd_add_prints_paste_hint_on_fetch_error(session, monkeypatch):
    def fake_ingest_jd(*args, **kwargs):
        raise FetchError("Could not fetch https://example.com/job (403)")

    monkeypatch.setattr(cli_module.jobs, "ingest_jd", fake_ingest_jd)

    result = runner.invoke(cli_module.app, ["jd", "add", "https://example.com/job"])

    assert result.exit_code == 1
    assert "Could not fetch https://example.com/job (403)" in result.output
    assert "chief jd add --paste" in result.output
    assert "Traceback" not in result.output


def test_app_list_ranked_flag_uses_ranked_ordering(session):
    now = datetime.now(UTC)
    applications.add_application(
        session, "Later Co", "SWE", RoleKind.FULLTIME, deadline_at=now + timedelta(days=180)
    )
    applications.add_application(
        session, "Soon Co", "SWE", RoleKind.FULLTIME, deadline_at=now + timedelta(days=2)
    )
    session.commit()

    result = runner.invoke(cli_module.app, ["app", "list", "--ranked"])

    assert result.exit_code == 0
    assert result.output.index("Soon Co") < result.output.index("Later Co")


def test_jd_show_renders_requirements(session):
    applications.add_application(
        session,
        "Acme",
        "SWE Intern",
        RoleKind.INTERN,
        location="Remote",
        requirements=["Python", "SQL"],
    )
    session.commit()

    result = runner.invoke(cli_module.app, ["jd", "show", "1"])

    assert result.exit_code == 0
    assert "Acme" in result.output
    assert "SWE Intern" in result.output
    assert "Python" in result.output
    assert "SQL" in result.output


def _entry(guid: str) -> FeedEntry:
    return FeedEntry(
        guid=guid,
        url=f"https://example.com/{guid}",
        title="A Post",
        published_at=datetime(2025, 9, 1, tzinfo=UTC),
        raw_text="summary text",
    )


def test_feed_add_creates_feed(session):
    result = runner.invoke(cli_module.app, ["feed", "add", "https://example.com/feed.xml", "--name", "Example"])

    assert result.exit_code == 0
    assert "Example" in result.output


def test_feed_poll_prints_new_item_count(session, monkeypatch):
    feed = feeds_module.add_feed(session, "https://example.com/feed.xml", "Example")
    session.commit()

    fake_result = FetchFeedResult(entries=[_entry("g1"), _entry("g2")], etag="e1", last_modified="lm1", not_modified=False)
    monkeypatch.setattr(feeds_module, "fetch_feed", lambda url, **kwargs: fake_result)

    result = runner.invoke(cli_module.app, ["feed", "poll", str(feed.id)])

    assert result.exit_code == 0
    assert "2 new items" in result.output


def test_feed_poll_all_prints_aggregate_count(session, monkeypatch):
    feed_a = feeds_module.add_feed(session, "https://example.com/a.xml", "Feed A")
    feeds_module.add_feed(session, "https://example.com/b.xml", "Feed B")
    session.commit()

    def fake_fetch_feed(url, **kwargs):
        guid = "ga" if url == feed_a.url else "gb"
        return FetchFeedResult(entries=[_entry(guid)], etag="e1", last_modified="lm1", not_modified=False)

    monkeypatch.setattr(feeds_module, "fetch_feed", fake_fetch_feed)

    result = runner.invoke(cli_module.app, ["feed", "poll", "--all"])

    assert result.exit_code == 0
    assert "2 feeds" in result.output
    assert "2 new items" in result.output


def test_feed_poll_prints_fetch_error_and_exits_1(session, monkeypatch):
    feed = feeds_module.add_feed(session, "https://example.com/feed.xml", "Example")
    session.commit()

    def raise_fetch_error(url, **kwargs):
        raise FetchError(f"Could not fetch feed {url} (500)")

    monkeypatch.setattr(feeds_module, "fetch_feed", raise_fetch_error)

    result = runner.invoke(cli_module.app, ["feed", "poll", str(feed.id)])

    assert result.exit_code == 1
    assert "Could not fetch feed" in result.output
    assert "Traceback" not in result.output


def test_feed_poll_without_id_or_all_exits_1_with_message(session):
    result = runner.invoke(cli_module.app, ["feed", "poll"])

    assert result.exit_code == 1
    assert "Specify a feed id or --all" in result.output


def _make_pending_item(session, feed: Feed, guid: str) -> FeedItem:
    item = FeedItem(feed=feed, guid=guid, title="A Post", raw_text="raw text")
    session.add(item)
    return item


def test_feed_summarize_prints_count(session, monkeypatch):
    feed = feeds_module.add_feed(session, "https://example.com/feed.xml", "Example")
    _make_pending_item(session, feed, "g1")
    _make_pending_item(session, feed, "g2")
    session.commit()
    monkeypatch.setattr(
        summarize_module,
        "summarize_item",
        lambda text, llm, **kwargs: ItemSummary(summary="s", importance=0.5),
    )

    result = runner.invoke(cli_module.app, ["feed", "summarize"])

    assert result.exit_code == 0
    assert "Summarized 2 items" in result.output


def test_feed_summarize_respects_limit_option(session, monkeypatch):
    feed = feeds_module.add_feed(session, "https://example.com/feed.xml", "Example")
    _make_pending_item(session, feed, "g1")
    _make_pending_item(session, feed, "g2")
    _make_pending_item(session, feed, "g3")
    session.commit()
    monkeypatch.setattr(
        summarize_module,
        "summarize_item",
        lambda text, llm, **kwargs: ItemSummary(summary="s", importance=0.5),
    )

    result = runner.invoke(cli_module.app, ["feed", "summarize", "--limit", "2"])

    assert result.exit_code == 0
    assert "Summarized 2 items" in result.output
