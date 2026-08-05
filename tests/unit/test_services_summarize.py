from datetime import UTC, datetime

from chief.analyze.summarize import ItemSummary
from chief.models import Feed, FeedItem
from chief.services import summarize


class DummyLLM:
    name = "dummy"


def _make_feed(session) -> Feed:
    feed = Feed(url="https://example.com/feed.xml", name="Example Feed")
    session.add(feed)
    session.flush()
    return feed


def _make_item(session, feed: Feed, guid: str, **kwargs) -> FeedItem:
    kwargs.setdefault("raw_text", "raw text")
    item = FeedItem(feed=feed, guid=guid, title="A Post", **kwargs)
    session.add(item)
    session.flush()
    return item


def test_summarize_pending_items_summarizes_items_with_null_summary(session, monkeypatch):
    feed = _make_feed(session)
    item_a = _make_item(session, feed, "g1")
    item_b = _make_item(session, feed, "g2")
    monkeypatch.setattr(
        summarize, "summarize_item", lambda text, llm, **kwargs: ItemSummary(summary="s", importance=0.5)
    )

    updated = summarize.summarize_pending_items(session, DummyLLM())

    assert {i.id for i in updated} == {item_a.id, item_b.id}
    assert item_a.summary == "s"
    assert item_a.importance == 0.5
    assert item_b.summary == "s"


def test_summarize_pending_items_skips_items_already_summarized(session, monkeypatch):
    feed = _make_feed(session)
    _make_item(session, feed, "g1", summary="already done", importance=0.9)
    pending = _make_item(session, feed, "g2")
    monkeypatch.setattr(
        summarize, "summarize_item", lambda text, llm, **kwargs: ItemSummary(summary="s", importance=0.5)
    )

    updated = summarize.summarize_pending_items(session, DummyLLM())

    assert [i.id for i in updated] == [pending.id]


def test_summarize_pending_items_skips_items_with_no_raw_text(session, monkeypatch):
    feed = _make_feed(session)
    _make_item(session, feed, "g1", raw_text=None)
    monkeypatch.setattr(
        summarize, "summarize_item", lambda text, llm, **kwargs: ItemSummary(summary="s", importance=0.5)
    )

    updated = summarize.summarize_pending_items(session, DummyLLM())

    assert updated == []


def test_summarize_pending_items_respects_limit(session, monkeypatch):
    feed = _make_feed(session)
    _make_item(session, feed, "g1")
    _make_item(session, feed, "g2")
    _make_item(session, feed, "g3")
    monkeypatch.setattr(
        summarize, "summarize_item", lambda text, llm, **kwargs: ItemSummary(summary="s", importance=0.5)
    )

    updated = summarize.summarize_pending_items(session, DummyLLM(), limit=2)

    assert len(updated) == 2


def test_summarize_pending_items_persists_model_and_prompt_version(session, monkeypatch):
    feed = _make_feed(session)
    item = _make_item(session, feed, "g1")
    monkeypatch.setattr(
        summarize, "summarize_item", lambda text, llm, **kwargs: ItemSummary(summary="s", importance=0.5)
    )

    summarize.summarize_pending_items(session, DummyLLM())

    assert item.model == "dummy"
    assert item.prompt_version == "v1"


def test_summarize_pending_items_orders_undated_items_last(session, monkeypatch):
    feed = _make_feed(session)
    undated = _make_item(session, feed, "g1", published_at=None)
    dated = _make_item(session, feed, "g2", published_at=datetime(2025, 9, 1, tzinfo=UTC))
    monkeypatch.setattr(
        summarize, "summarize_item", lambda text, llm, **kwargs: ItemSummary(summary="s", importance=0.5)
    )

    updated = summarize.summarize_pending_items(session, DummyLLM(), limit=1)

    assert [i.id for i in updated] == [dated.id]
    assert undated.summary is None
