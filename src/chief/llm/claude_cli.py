"""Shells out to `claude -p` — the $0 provider path.

No structured() here — that lives in llm/structured.py so a retry's
second completion can be logged by whatever wraps this provider.
"""

import json
import shutil
import subprocess
import tempfile
import time

from chief.llm.base import LLMError, LLMResponse


def _echo(cmd: list[str]) -> str:
    """Command as a string, truncated — never dump a 15KB prompt into a log line."""
    return " ".join(cmd)[:200]


def _main_model(payload: dict) -> str | None:
    """The modelUsage entry with the highest cost — the one that generated
    `result`, as opposed to an incidental cheap background call (e.g. Claude
    Code sometimes uses a small model for conversation-title generation)."""
    model_usage = payload.get("modelUsage") or {}
    if not model_usage:
        return None
    return max(model_usage, key=lambda name: model_usage[name].get("costUSD", 0))


class ClaudeCLIProvider:
    name = "claude-cli"

    def complete(
        self,
        *,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 1024,
        purpose: str,
        prompt_version: str,
    ) -> LLMResponse:
        """Run `claude -p` in a scratch cwd so this repo's CLAUDE.md never
        leaks into the prompt, and raise LLMError on nonzero exit."""
        cmd = ["claude", "-p", "--output-format", "json"]
        if system is not None:
            cmd = ["claude", "--append-system-prompt", system, "-p", "--output-format", "json"]

        scratch_dir = tempfile.mkdtemp(prefix="chief-llm-")
        start = time.monotonic()
        try:
            result = subprocess.run(
                cmd, cwd=scratch_dir, input=prompt, capture_output=True, text=True, check=True
            )
        except subprocess.CalledProcessError as e:
            raise LLMError(
                f"claude -p failed (exit {e.returncode}): {_echo(cmd)}\n"
                f"stderr: {e.stderr}\nstdout: {e.stdout}"
            ) from e
        except OSError as e:
            raise LLMError(f"claude -p failed to start: {_echo(cmd)}: {e}") from e
        finally:
            shutil.rmtree(scratch_dir, ignore_errors=True)

        latency_ms = int((time.monotonic() - start) * 1000)
        payload = json.loads(result.stdout)
        usage = payload.get("usage", {})
        return LLMResponse(
            text=payload["result"],
            model=_main_model(payload) or self.name,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cost_usd=payload.get("total_cost_usd", 0.0),
            latency_ms=latency_ms,
        )
