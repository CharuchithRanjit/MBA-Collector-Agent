"""Pushes text to a phone via ntfy.sh. Free, no account, no API key."""

import httpx

NTFY_URL = "https://ntfy.sh"


class NotifyError(Exception):
    """send_push failed — bad HTTP status from ntfy.sh."""


def send_push(text: str, topic: str) -> None:
    """POST text to the given ntfy.sh topic. Raises NotifyError on a bad status."""
    response = httpx.post(f"{NTFY_URL}/{topic}", content=text.encode(), timeout=10.0)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise NotifyError(f"Could not send push notification ({response.status_code})") from e
