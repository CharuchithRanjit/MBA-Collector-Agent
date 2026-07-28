import httpx
import pytest

from chief.fetch import fetch_url_text

FAKE_HTML = """
<html>
<head><title>SWE Intern at Acme</title></head>
<body>
<nav>Home | Jobs | About</nav>
<article>
<h1>Software Engineering Intern</h1>
<p>Acme is looking for a Software Engineering Intern to join our platform
team for summer 2026. You'll work on distributed systems, ship real
features, and pair with senior engineers every week. We're looking for
someone finishing a CS degree with experience in Python or Go.</p>
<p>Location: Remote. Apply by September 1st, 2026.</p>
</article>
<footer>&copy; 2026 Acme Corp</footer>
</body>
</html>
"""


def test_fetch_url_text_extracts_clean_text_from_html(monkeypatch):
    def fake_get(url, **kwargs):
        return httpx.Response(200, text=FAKE_HTML, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)

    text = fetch_url_text("https://example.com/job/123")

    assert "Software Engineering Intern" in text
    assert "Home | Jobs | About" not in text


def test_fetch_url_text_raises_on_http_error(monkeypatch):
    def fake_get(url, **kwargs):
        return httpx.Response(404, text="not found", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)

    with pytest.raises(httpx.HTTPStatusError):
        fetch_url_text("https://example.com/job/missing")
