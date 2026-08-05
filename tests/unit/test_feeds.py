from datetime import UTC, datetime

import pytest
from sqlmodel import select

from chief.fetch import FetchError
from chief.models import Feed, FeedItem
from chief.rss import FeedEntry, FetchFeedResult
from chief.services import feeds


def _entry(guid: str, title: str = "A Post") -> FeedEntry:
    return FeedEntry(
        guid=guid,
        url=f"https://example.com/{guid}",
        title=title,
        published_at=datetime(2025, 9, 1, tzinfo=UTC),
        raw_text="summary text",
    )


def test_add_feed_creates_row(session):
    feed = feeds.add_feed(session, "https://example.com/feed.xml", "Example Feed", category="tech")

    assert feed.id is not None
    assert feed.url == "https://example.com/feed.xml"
    assert feed.name == "Example Feed"
    assert feed.category == "tech"


def test_add_feed_rejects_duplicate_url(session):
    feeds.add_feed(session, "https://example.com/feed.xml", "Example Feed")

    with pytest.raises(ValueError):
        feeds.add_feed(session, "https://example.com/feed.xml", "Duplicate")


def test_poll_feed_first_poll_creates_items(session, monkeypatch):
    feed = feeds.add_feed(session, "https://example.com/feed.xml", "Example Feed")
    result = FetchFeedResult(
        entries=[_entry("g1"), _entry("g2")], etag="e1", last_modified="lm1", not_modified=False
    )
    monkeypatch.setattr(feeds, "fetch_feed", lambda url, **kwargs: result)

    new_items = feeds.poll_feed(session, feed)

    assert len(new_items) == 2
    assert {i.guid for i in new_items} == {"g1", "g2"}


def test_poll_feed_persists_etag_and_last_modified_after_poll(session, monkeypatch):
    feed = feeds.add_feed(session, "https://example.com/feed.xml", "Example Feed")
    result = FetchFeedResult(entries=[_entry("g1")], etag="e1", last_modified="lm1", not_modified=False)
    monkeypatch.setattr(feeds, "fetch_feed", lambda url, **kwargs: result)

    feeds.poll_feed(session, feed)

    assert feed.etag == "e1"
    assert feed.last_modified == "lm1"
    assert feed.last_fetched_at is not None


def test_poll_feed_second_poll_with_matching_etag_creates_zero_new_items(session, monkeypatch):
    feed = feeds.add_feed(session, "https://example.com/feed.xml", "Example Feed")
    first_result = FetchFeedResult(entries=[_entry("g1")], etag="e1", last_modified="lm1", not_modified=False)
    monkeypatch.setattr(feeds, "fetch_feed", lambda url, **kwargs: first_result)
    feeds.poll_feed(session, feed)

    not_modified_result = FetchFeedResult(entries=[], etag="e1", last_modified="lm1", not_modified=True)
    monkeypatch.setattr(feeds, "fetch_feed", lambda url, **kwargs: not_modified_result)

    new_items = feeds.poll_feed(session, feed)

    assert new_items == []


def test_poll_feed_sends_stored_etag_as_conditional_get_header(session, monkeypatch):
    feed = feeds.add_feed(session, "https://example.com/feed.xml", "Example Feed")
    feed.etag = "stored-etag"
    feed.last_modified = "stored-lm"
    session.add(feed)
    session.flush()
    captured = {}

    def fake_fetch_feed(url, **kwargs):
        captured["etag"] = kwargs.get("etag")
        captured["last_modified"] = kwargs.get("last_modified")
        return FetchFeedResult(entries=[], etag="stored-etag", last_modified="stored-lm", not_modified=True)

    monkeypatch.setattr(feeds, "fetch_feed", fake_fetch_feed)

    feeds.poll_feed(session, feed)

    assert captured["etag"] == "stored-etag"
    assert captured["last_modified"] == "stored-lm"


def test_poll_feed_dedupes_by_guid_within_same_feed_across_two_polls(session, monkeypatch):
    feed = feeds.add_feed(session, "https://example.com/feed.xml", "Example Feed")
    result = FetchFeedResult(entries=[_entry("g1")], etag="e1", last_modified="lm1", not_modified=False)
    monkeypatch.setattr(feeds, "fetch_feed", lambda url, **kwargs: result)

    feeds.poll_feed(session, feed)
    second_new_items = feeds.poll_feed(session, feed)

    assert second_new_items == []
    items = session.exec(select(FeedItem).where(FeedItem.guid == "g1")).all()
    assert len(items) == 1


def test_poll_feed_dedupes_overlapping_guid_across_two_different_feeds(session, monkeypatch):
    feed_a = feeds.add_feed(session, "https://example.com/a.xml", "Feed A")
    feed_b = feeds.add_feed(session, "https://example.com/b.xml", "Feed B")
    result = FetchFeedResult(entries=[_entry("shared")], etag="e1", last_modified="lm1", not_modified=False)
    monkeypatch.setattr(feeds, "fetch_feed", lambda url, **kwargs: result)

    feeds.poll_feed(session, feed_a)
    new_items_b = feeds.poll_feed(session, feed_b)

    assert new_items_b == []
    items = session.exec(select(FeedItem).where(FeedItem.guid == "shared")).all()
    assert len(items) == 1


def test_poll_feed_skips_entry_with_no_derivable_guid(session, monkeypatch):
    feed = feeds.add_feed(session, "https://example.com/feed.xml", "Example Feed")
    bad_entry = _entry("")
    result = FetchFeedResult(
        entries=[bad_entry, _entry("g1")], etag="e1", last_modified="lm1", not_modified=False
    )
    monkeypatch.setattr(feeds, "fetch_feed", lambda url, **kwargs: result)

    new_items = feeds.poll_feed(session, feed)

    assert len(new_items) == 1
    assert new_items[0].guid == "g1"


def test_poll_feed_updates_last_fetched_at_even_on_304(session, monkeypatch):
    feed = feeds.add_feed(session, "https://example.com/feed.xml", "Example Feed")
    result = FetchFeedResult(entries=[], etag=None, last_modified=None, not_modified=True)
    monkeypatch.setattr(feeds, "fetch_feed", lambda url, **kwargs: result)
    now = datetime(2026, 1, 1, tzinfo=UTC)

    feeds.poll_feed(session, feed, now=now)

    assert feed.last_fetched_at == now


def test_poll_feed_raises_fetch_error_on_bad_status_and_leaves_feed_unchanged(session, monkeypatch):
    feed = feeds.add_feed(session, "https://example.com/feed.xml", "Example Feed")

    def raise_fetch_error(url, **kwargs):
        raise FetchError("boom")

    monkeypatch.setattr(feeds, "fetch_feed", raise_fetch_error)

    with pytest.raises(FetchError):
        feeds.poll_feed(session, feed)

    assert feed.etag is None
    assert feed.last_fetched_at is None


def test_list_feeds_orders_by_name(session):
    feeds.add_feed(session, "https://example.com/z.xml", "Zebra Feed")
    feeds.add_feed(session, "https://example.com/a.xml", "Apple Feed")

    results = feeds.list_feeds(session)

    assert [f.name for f in results] == ["Apple Feed", "Zebra Feed"]


def test_get_feed_with_bad_id_raises_value_error(session):
    with pytest.raises(ValueError):
        feeds.get_feed(session, 9999)


def test_poll_all_feeds_continues_after_one_feed_fetch_error(session, monkeypatch):
    feed_a = feeds.add_feed(session, "https://example.com/a.xml", "Feed A")
    feed_b = feeds.add_feed(session, "https://example.com/b.xml", "Feed B")

    def fake_fetch_feed(url, **kwargs):
        if url == feed_a.url:
            raise FetchError("boom")
        return FetchFeedResult(entries=[_entry("g1")], etag="e1", last_modified="lm1", not_modified=False)

    monkeypatch.setattr(feeds, "fetch_feed", fake_fetch_feed)

    results = feeds.poll_all_feeds(session)

    assert results[feed_a.id] == []
    assert len(results[feed_b.id]) == 1


def test_poll_all_feeds_returns_new_items_keyed_by_feed_id(session, monkeypatch):
    feed_a = feeds.add_feed(session, "https://example.com/a.xml", "Feed A")
    feed_b = feeds.add_feed(session, "https://example.com/b.xml", "Feed B")

    def fake_fetch_feed(url, **kwargs):
        guid = "ga" if url == feed_a.url else "gb"
        return FetchFeedResult(entries=[_entry(guid)], etag="e1", last_modified="lm1", not_modified=False)

    monkeypatch.setattr(feeds, "fetch_feed", fake_fetch_feed)

    results = feeds.poll_all_feeds(session)

    assert results[feed_a.id][0].guid == "ga"
    assert results[feed_b.id][0].guid == "gb"


def _make_feed(session) -> Feed:
    feed = Feed(url="https://example.com/feed.xml", name="Example Feed")
    session.add(feed)
    session.flush()
    return feed


def _make_summarized_item(session, feed: Feed, guid: str, importance: float) -> FeedItem:
    item = FeedItem(
        feed=feed, guid=guid, title="A Post", raw_text="raw text", summary="a summary", importance=importance
    )
    session.add(item)
    session.flush()
    return item


def test_get_top_news_items_orders_by_importance_descending(session):
    feed = _make_feed(session)
    low = _make_summarized_item(session, feed, "g1", importance=0.4)
    high = _make_summarized_item(session, feed, "g2", importance=0.9)

    results = feeds.get_top_news_items(session)

    assert [i.id for i in results] == [high.id, low.id]


def test_get_top_news_items_excludes_below_threshold(session):
    feed = _make_feed(session)
    _make_summarized_item(session, feed, "g1", importance=0.1)
    kept = _make_summarized_item(session, feed, "g2", importance=0.9)

    results = feeds.get_top_news_items(session, min_importance=0.3)

    assert [i.id for i in results] == [kept.id]


def test_get_top_news_items_respects_limit(session):
    feed = _make_feed(session)
    for i in range(6):
        _make_summarized_item(session, feed, f"g{i}", importance=0.5 + i * 0.01)

    results = feeds.get_top_news_items(session, limit=3)

    assert len(results) == 3


def test_count_summarized_items_counts_only_items_with_summary(session):
    feed = _make_feed(session)
    _make_summarized_item(session, feed, "g1", importance=0.5)
    unsummarized = FeedItem(feed=feed, guid="g2", title="No summary yet", raw_text="raw text")
    session.add(unsummarized)
    session.flush()

    count = feeds.count_summarized_items(session)

    assert count == 1
