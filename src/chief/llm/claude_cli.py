"""Shells out to `claude -p` — the $0 provider path.

No structured() here — that lives in llm/structured.py so a retry's
second completion can be logged by whatever wraps this provider.
"""

import shutil
import subprocess
import tempfile
import time

from chief.llm.base import LLMError, LLMResponse


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
        cmd = ["claude", "-p", prompt]
        if system is not None:
            cmd = ["claude", "--append-system-prompt", system, "-p", prompt]

        scratch_dir = tempfile.mkdtemp(prefix="chief-llm-")
        start = time.monotonic()
        try:
            result = subprocess.run(cmd, cwd=scratch_dir, capture_output=True, text=True, check=True)
        except (subprocess.CalledProcessError, OSError) as e:
            raise LLMError(f"claude -p failed: {e}") from e
        finally:
            shutil.rmtree(scratch_dir, ignore_errors=True)

        latency_ms = int((time.monotonic() - start) * 1000)
        return LLMResponse(text=result.stdout.strip(), model=self.name, latency_ms=latency_ms)
