"""Fetches and parses RSS/Atom feeds with conditional-GET (etag/last-modified) caching."""

from dataclasses import dataclass
from datetime import UTC, datetime

import feedparser
import httpx

from chief.fetch import ACCEPT_LANGUAGE, USER_AGENT, FetchError


@dataclass
class FeedEntry:
    guid: str
    url: str | None
    title: str
    published_at: datetime | None
    raw_text: str | None


@dataclass
class FetchFeedResult:
    entries: list[FeedEntry]
    etag: str | None
    last_modified: str | None
    not_modified: bool  # True on a 304 — entries is always [] then


def _entry_published_at(entry) -> datetime | None:
    struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if struct is None:
        return None
    return datetime(*struct[:6], tzinfo=UTC)


def _entry_raw_text(entry) -> str | None:
    content = entry.get("content")
    if content:
        return content[0].get("value")
    return entry.get("summary")


def _parse_entries(parsed: feedparser.FeedParserDict) -> list[FeedEntry]:
    entries = []
    for entry in parsed.entries:
        guid = entry.get("id") or entry.get("link")
        if not guid:
            continue
        entries.append(
            FeedEntry(
                guid=guid,
                url=entry.get("link"),
                title=entry.get("title") or "(untitled)",
                published_at=_entry_published_at(entry),
                raw_text=_entry_raw_text(entry),
            )
        )
    return entries


def fetch_feed(
    url: str,
    *,
    etag: str | None = None,
    last_modified: str | None = None,
) -> FetchFeedResult:
    """GET the feed with conditional-GET headers, parse entries via feedparser.

    Returns FetchFeedResult(not_modified=True, entries=[]) on a 304 — this is
    NOT an error. Raises FetchError on any other non-2xx status.
    """
    headers = {"User-Agent": USER_AGENT, "Accept-Language": ACCEPT_LANGUAGE}
    if etag is not None:
        headers["If-None-Match"] = etag
    if last_modified is not None:
        headers["If-Modified-Since"] = last_modified

    response = httpx.get(url, headers=headers, follow_redirects=True, timeout=10.0)

    if response.status_code == 304:
        return FetchFeedResult(entries=[], etag=etag, last_modified=last_modified, not_modified=True)
    if response.status_code // 100 != 2:
        raise FetchError(f"Could not fetch feed {url} ({response.status_code})")

    parsed = feedparser.parse(response.content)
    if not parsed.entries and parsed.bozo:
        raise FetchError(f"Could not parse feed {url}: {parsed.get('bozo_exception')}")

    return FetchFeedResult(
        entries=_parse_entries(parsed),
        etag=response.headers.get("ETag"),
        last_modified=response.headers.get("Last-Modified"),
        not_modified=False,
    )
