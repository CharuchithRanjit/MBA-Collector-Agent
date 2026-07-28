"""Fetches a URL and reduces it to clean, boilerplate-free text."""

import httpx
import trafilatura


def fetch_url_text(url: str) -> str:
    """GET the URL, strip nav/ads/boilerplate down to article text.

    Raises httpx.HTTPStatusError on a non-2xx response, ValueError if
    trafilatura can't find extractable text.
    """
    response = httpx.get(url, follow_redirects=True, timeout=10.0)
    response.raise_for_status()

    text = trafilatura.extract(response.text)
    if not text:
        raise ValueError(f"Could not extract readable text from {url}")
    return text
