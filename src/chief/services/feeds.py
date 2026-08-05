"""Feed ingest. No LLM calls — summarization is a separate slice."""

from datetime import datetime

from sqlmodel import Session, func, select

from chief.fetch import FetchError
from chief.models import Feed, FeedItem, as_utc, utcnow
from chief.rss import fetch_feed


def add_feed(session: Session, url: str, name: str, category: str | None = None) -> Feed:
    """Create a feed row. Raises ValueError if url already registered."""
    existing = session.exec(select(Feed).where(Feed.url == url)).first()
    if existing is not None:
        raise ValueError(f"Feed already registered: {url}")

    feed = Feed(url=url, name=name, category=category)
    session.add(feed)
    session.flush()
    return feed


def list_feeds(session: Session) -> list[Feed]:
    """All feeds, ordered by name."""
    return list(session.exec(select(Feed).order_by(Feed.name)).all())


def get_feed(session: Session, feed_id: int) -> Feed:
    """Fetch a single feed by id. Raises ValueError if it doesn't exist."""
    feed = session.get(Feed, feed_id)
    if feed is None:
        raise ValueError(f"No feed with id {feed_id}")
    return feed


def poll_feed(session: Session, feed: Feed, now: datetime | None = None) -> list[FeedItem]:
    """Fetch via conditional GET, persist new items, update the feed's
    cache fields. Returns only newly-created items. Empty list on a 304
    or when every fetched entry is already known.

    Dedup is by guid, done in Python against a set query — never a model.
    """
    now = now or utcnow()
    result = fetch_feed(feed.url, etag=feed.etag, last_modified=feed.last_modified)

    if result.not_modified:
        feed.last_fetched_at = now
        session.add(feed)
        session.flush()
        return []

    guids = [entry.guid for entry in result.entries if entry.guid]
    existing = set(session.exec(select(FeedItem.guid).where(FeedItem.guid.in_(guids))).all())

    new_items = []
    for entry in result.entries:
        if not entry.guid or entry.guid in existing:
            continue
        item = FeedItem(
            feed=feed,
            guid=entry.guid,
            url=entry.url,
            title=entry.title,
            published_at=as_utc(entry.published_at),
            raw_text=entry.raw_text,
        )
        session.add(item)
        new_items.append(item)

    feed.etag = result.etag
    feed.last_modified = result.last_modified
    feed.last_fetched_at = now
    session.add(feed)
    session.flush()
    return new_items


def poll_all_feeds(session: Session, now: datetime | None = None) -> dict[int, list[FeedItem]]:
    """Poll every feed. One feed's FetchError doesn't abort the batch."""
    results: dict[int, list[FeedItem]] = {}
    for feed in list_feeds(session):
        try:
            results[feed.id] = poll_feed(session, feed, now=now)
        except FetchError:
            results[feed.id] = []
    return results


def get_top_news_items(
    session: Session, limit: int = 4, min_importance: float = 0.3
) -> list[FeedItem]:
    """Summarized items, importance-sorted, above the threshold, capped.

    Deterministic sort+threshold — never a model — per briefing-spec.md's
    field-source table ("News item selection: importance score, top N:
    deterministic threshold").
    """
    query = (
        select(FeedItem)
        .where(FeedItem.summary.is_not(None))
        .where(FeedItem.importance >= min_importance)
        .order_by(FeedItem.importance.desc())
        .limit(limit)
    )
    return list(session.exec(query).all())


def count_summarized_items(session: Session) -> int:
    """How many FeedItems have been summarized, ever — the briefing footer's 'scanned' count."""
    return session.exec(
        select(func.count()).select_from(FeedItem).where(FeedItem.summary.is_not(None))
    ).one()
