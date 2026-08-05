from datetime import UTC, datetime

import httpx
import pytest

from chief.fetch import FetchError
from chief.rss import fetch_feed

FAKE_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Example Feed</title>
<link>https://example.com</link>
<item>
<title>First Post</title>
<link>https://example.com/first</link>
<guid>https://example.com/first</guid>
<pubDate>Mon, 01 Sep 2025 12:00:00 GMT</pubDate>
<description>First post summary</description>
</item>
<item>
<title>Second Post</title>
<link>https://example.com/second</link>
<guid>https://example.com/second</guid>
<pubDate>Tue, 02 Sep 2025 12:00:00 GMT</pubDate>
<description>Second post summary</description>
</item>
</channel>
</rss>
"""

FAKE_RSS_XML_MISSING_GUID = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Example Feed</title>
<item>
<title>No Guid Post</title>
<link>https://example.com/no-guid</link>
<pubDate>Mon, 01 Sep 2025 12:00:00 GMT</pubDate>
<description>Falls back to link</description>
</item>
</channel>
</rss>
"""

FAKE_RSS_XML_MISSING_GUID_AND_LINK = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Example Feed</title>
<item>
<title>Unidentifiable Post</title>
<description>No guid, no link — should be skipped</description>
</item>
<item>
<title>Good Post</title>
<link>https://example.com/good</link>
<guid>https://example.com/good</guid>
<pubDate>Mon, 01 Sep 2025 12:00:00 GMT</pubDate>
<description>Should still be parsed</description>
</item>
</channel>
</rss>
"""

FAKE_RSS_XML_NO_PUBDATE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Example Feed</title>
<item>
<title>Undated Post</title>
<link>https://example.com/undated</link>
<guid>https://example.com/undated</guid>
<description>No pubDate element</description>
</item>
</channel>
</rss>
"""

FAKE_ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>Example Atom Feed</title>
<entry>
<title>Atom Post One</title>
<link href="https://example.com/atom/1"/>
<id>urn:uuid:1234</id>
<published>2025-09-01T12:00:00Z</published>
<summary>Atom summary one</summary>
</entry>
<entry>
<title>Atom Post Two</title>
<link href="https://example.com/atom/2"/>
<id>urn:uuid:5678</id>
<updated>2025-09-02T12:00:00Z</updated>
<content>Full atom content two</content>
</entry>
</feed>
"""


def _fake_get(status: int, content: str = "", headers: dict[str, str] | None = None):
    def fake_get(url, **kwargs):
        return httpx.Response(
            status, content=content.encode(), headers=headers or {}, request=httpx.Request("GET", url)
        )

    return fake_get


def test_fetch_feed_parses_rss_entries_into_feed_entry_list(monkeypatch):
    monkeypatch.setattr(httpx, "get", _fake_get(200, FAKE_RSS_XML))

    result = fetch_feed("https://example.com/feed.xml")

    assert result.not_modified is False
    assert len(result.entries) == 2
    first = result.entries[0]
    assert first.guid == "https://example.com/first"
    assert first.url == "https://example.com/first"
    assert first.title == "First Post"
    assert first.raw_text == "First post summary"


def test_fetch_feed_sends_conditional_get_headers_when_etag_given(monkeypatch):
    captured = {}

    def fake_get(url, **kwargs):
        captured["headers"] = kwargs.get("headers", {})
        return httpx.Response(200, content=FAKE_RSS_XML.encode(), request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)

    fetch_feed("https://example.com/feed.xml", etag='"abc123"')

    assert captured["headers"].get("If-None-Match") == '"abc123"'


def test_fetch_feed_sends_if_modified_since_when_last_modified_given(monkeypatch):
    captured = {}

    def fake_get(url, **kwargs):
        captured["headers"] = kwargs.get("headers", {})
        return httpx.Response(200, content=FAKE_RSS_XML.encode(), request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)

    fetch_feed("https://example.com/feed.xml", last_modified="Wed, 03 Sep 2025 00:00:00 GMT")

    assert captured["headers"].get("If-Modified-Since") == "Wed, 03 Sep 2025 00:00:00 GMT"


def test_fetch_feed_returns_not_modified_on_304_without_raising(monkeypatch):
    monkeypatch.setattr(httpx, "get", _fake_get(304))

    result = fetch_feed("https://example.com/feed.xml", etag='"abc123"', last_modified="lm")

    assert result.not_modified is True
    assert result.entries == []
    assert result.etag == '"abc123"'
    assert result.last_modified == "lm"


def test_fetch_feed_raises_fetch_error_on_non_304_non_2xx_status(monkeypatch):
    monkeypatch.setattr(httpx, "get", _fake_get(500))

    with pytest.raises(FetchError):
        fetch_feed("https://example.com/feed.xml")


def test_fetch_feed_returns_new_etag_and_last_modified_from_response_headers(monkeypatch):
    headers = {"ETag": '"newetag"', "Last-Modified": "Wed, 03 Sep 2025 00:00:00 GMT"}
    monkeypatch.setattr(httpx, "get", _fake_get(200, FAKE_RSS_XML, headers))

    result = fetch_feed("https://example.com/feed.xml")

    assert result.etag == '"newetag"'
    assert result.last_modified == "Wed, 03 Sep 2025 00:00:00 GMT"
    assert result.not_modified is False


def test_fetch_feed_falls_back_to_link_when_entry_has_no_id(monkeypatch):
    monkeypatch.setattr(httpx, "get", _fake_get(200, FAKE_RSS_XML_MISSING_GUID))

    result = fetch_feed("https://example.com/feed.xml")

    assert len(result.entries) == 1
    assert result.entries[0].guid == "https://example.com/no-guid"


def test_fetch_feed_skips_entry_missing_both_id_and_link(monkeypatch):
    monkeypatch.setattr(httpx, "get", _fake_get(200, FAKE_RSS_XML_MISSING_GUID_AND_LINK))

    result = fetch_feed("https://example.com/feed.xml")

    assert len(result.entries) == 1
    assert result.entries[0].title == "Good Post"


def test_fetch_feed_parses_atom_entries_as_well_as_rss(monkeypatch):
    monkeypatch.setattr(httpx, "get", _fake_get(200, FAKE_ATOM_XML))

    result = fetch_feed("https://example.com/atom.xml")

    assert len(result.entries) == 2
    guids = {e.guid for e in result.entries}
    assert guids == {"urn:uuid:1234", "urn:uuid:5678"}


def test_fetch_feed_converts_published_parsed_to_aware_utc_datetime(monkeypatch):
    monkeypatch.setattr(httpx, "get", _fake_get(200, FAKE_RSS_XML))

    result = fetch_feed("https://example.com/feed.xml")

    published_at = result.entries[0].published_at
    assert published_at == datetime(2025, 9, 1, 12, 0, 0, tzinfo=UTC)


def test_fetch_feed_handles_entry_with_no_published_date(monkeypatch):
    monkeypatch.setattr(httpx, "get", _fake_get(200, FAKE_RSS_XML_NO_PUBDATE))

    result = fetch_feed("https://example.com/feed.xml")

    assert len(result.entries) == 1
    assert result.entries[0].published_at is None
