import json
import subprocess
import tempfile

import pytest

from chief.llm.base import LLMError
from chief.llm.claude_cli import ClaudeCLIProvider


def test_claude_cli_parses_cost_and_model(monkeypatch):
    payload = json.dumps(
        {
            "result": "hello from claude",
            "total_cost_usd": 0.0042,
            "usage": {"input_tokens": 12, "output_tokens": 34},
            "modelUsage": {
                "claude-haiku-4-5-20251001": {"costUSD": 0.0001},
                "claude-sonnet-5": {"costUSD": 0.0041},
            },
        }
    )
    captured = {}

    def fake_run(*args, **kwargs):
        captured["cwd"] = kwargs.get("cwd")
        captured["input"] = kwargs.get("input")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=payload, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    provider = ClaudeCLIProvider()
    response = provider.complete(prompt="say hi", purpose="test", prompt_version="v1")

    assert response.text == "hello from claude"
    assert response.cost_usd == 0.0042
    # highest-cost model in modelUsage — the one that actually generated
    # the response, not an incidental cheap background call
    assert response.model == "claude-sonnet-5"
    assert response.input_tokens == 12
    assert response.output_tokens == 34
    # prompt goes via stdin now, not argv (15KB in argv caused an
    # unexplained nonzero exit)
    assert captured["input"] == "say hi"
    # still a scratch cwd, not the repo — CLAUDE.md must never leak in
    assert captured["cwd"] is not None
    assert captured["cwd"].startswith(tempfile.gettempdir())
    assert captured["cwd"] != str(tempfile.gettempdir())


def test_claude_cli_error_includes_stderr(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(returncode=2, cmd=args, output="", stderr="rate limited")

    monkeypatch.setattr(subprocess, "run", fake_run)

    provider = ClaudeCLIProvider()
    with pytest.raises(LLMError) as exc_info:
        provider.complete(prompt="say hi", system="x" * 500, purpose="test", prompt_version="v1")

    message = str(exc_info.value)
    assert "rate limited" in message
    assert "2" in message
    # command echo truncated to 200 chars, not the full 500-char system prompt
    assert len(message) < 500
