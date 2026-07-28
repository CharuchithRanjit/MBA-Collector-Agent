"""Fetches a URL and reduces it to clean, boilerplate-free text."""

import httpx
import trafilatura


class FetchError(Exception):
    """fetch_url_text failed — bad HTTP status or no extractable text."""


# A lot of corporate career sites 403 the default python-httpx UA.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
ACCEPT_LANGUAGE = "en-US,en;q=0.9"


def fetch_url_text(url: str) -> str:
    """GET the URL, strip nav/ads/boilerplate down to article text.

    Raises FetchError on a non-2xx response or if trafilatura can't
    find extractable text.
    """
    headers = {"User-Agent": USER_AGENT, "Accept-Language": ACCEPT_LANGUAGE}
    response = httpx.get(url, headers=headers, follow_redirects=True, timeout=10.0)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise FetchError(f"Could not fetch {url} ({response.status_code})") from e

    text = trafilatura.extract(response.text)
    if not text:
        raise FetchError(f"Could not extract readable text from {url}")
    return text
