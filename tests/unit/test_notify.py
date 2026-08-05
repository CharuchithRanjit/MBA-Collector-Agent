import httpx
import pytest

from chief.notify import NotifyError, send_push


def test_send_push_posts_text_to_the_given_topic_url(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    send_push("hello", "my-topic")

    assert captured["url"] == "https://ntfy.sh/my-topic"


def test_send_push_sends_text_as_the_request_body(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured["content"] = kwargs.get("content")
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    send_push("hello world", "my-topic")

    assert captured["content"] == b"hello world"


def test_send_push_raises_notify_error_on_bad_status(monkeypatch):
    def fake_post(url, **kwargs):
        return httpx.Response(500, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(NotifyError):
        send_push("hello", "my-topic")
