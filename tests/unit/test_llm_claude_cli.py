import subprocess
import tempfile

import pytest

from chief.llm.base import LLMError
from chief.llm.claude_cli import ClaudeCLIProvider


def test_claude_cli_provider_parses_stdout_into_response(monkeypatch):
    captured = {}

    def fake_run(*args, **kwargs):
        captured["cwd"] = kwargs.get("cwd")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="hello from claude", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    provider = ClaudeCLIProvider()
    response = provider.complete(prompt="say hi", purpose="test", prompt_version="v1")

    assert response.text == "hello from claude"
    # Must not run in the repo's own cwd — that would leak CLAUDE.md into the prompt.
    assert captured["cwd"] is not None
    assert captured["cwd"] != str(tempfile.gettempdir())  # a real scratch dir, not just the temp root
    assert captured["cwd"].startswith(tempfile.gettempdir())


def test_claude_cli_provider_raises_llm_error_on_nonzero_exit(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(returncode=1, cmd=args, output="", stderr="boom")

    monkeypatch.setattr(subprocess, "run", fake_run)

    provider = ClaudeCLIProvider()
    with pytest.raises(LLMError):
        provider.complete(prompt="say hi", purpose="test", prompt_version="v1")
