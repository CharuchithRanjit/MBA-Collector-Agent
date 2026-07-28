"""Anthropic API provider — the reliable, non-$0 path.

No structured() here — that lives in llm/structured.py so a retry's
second completion can be logged by whatever wraps this provider.
"""

import time

import anthropic

from chief.llm.base import LLMError, LLMResponse

# Verify against https://claude.com/pricing before relying on this for
# budgeting — cost tracking (cost_usd) isn't wired up in this slice.
DEFAULT_MODEL = "claude-haiku-4-5-20251001"


class AnthropicAPIProvider:
    name = "anthropic-api"

    def __init__(self, client: anthropic.Anthropic | None = None) -> None:
        self._client = client or anthropic.Anthropic()

    def complete(
        self,
        *,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 1024,
        purpose: str,
        prompt_version: str,
    ) -> LLMResponse:
        """Call the Messages API and raise LLMError on failure."""
        kwargs = {
            "model": DEFAULT_MODEL,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system is not None:
            kwargs["system"] = system

        start = time.monotonic()
        try:
            message = self._client.messages.create(**kwargs)
        except anthropic.AnthropicError as e:
            raise LLMError(f"Anthropic API call failed: {e}") from e
        latency_ms = int((time.monotonic() - start) * 1000)

        return LLMResponse(
            text=message.content[0].text,
            model=message.model,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            latency_ms=latency_ms,
        )
