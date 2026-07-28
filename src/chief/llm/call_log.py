"""Wraps a provider and logs every complete() call to models.LLMCall.

structured() is not implemented directly — it delegates to
llm.structured.structured(self, ...), which calls self.complete() for
both the first attempt and the retry, so a retry produces two LLMCall
rows, not one.
"""

import time

from pydantic import BaseModel

from chief.db import get_session
from chief.llm.base import LLMError, LLMResponse
from chief.llm.structured import CompletingProvider
from chief.llm.structured import structured as _structured
from chief.models import LLMCall


class LoggingProvider:
    def __init__(self, inner: CompletingProvider) -> None:
        self._inner = inner
        self.name = inner.name

    def complete(
        self,
        *,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 1024,
        purpose: str,
        prompt_version: str,
    ) -> LLMResponse:
        """Call inner.complete(), write one LLMCall row, re-raise on failure."""
        start = time.monotonic()
        try:
            response = self._inner.complete(
                prompt=prompt,
                system=system,
                max_tokens=max_tokens,
                purpose=purpose,
                prompt_version=prompt_version,
            )
        except LLMError as e:
            self._log(
                purpose=purpose,
                provider=self.name,
                model=self.name,
                prompt_version=prompt_version,
                latency_ms=int((time.monotonic() - start) * 1000),
                success=False,
                error=str(e),
            )
            raise

        self._log(
            purpose=purpose,
            provider=self.name,
            model=response.model,
            prompt_version=prompt_version,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=response.cost_usd,
            latency_ms=response.latency_ms,
            success=True,
        )
        return response

    def structured[T: BaseModel](
        self,
        *,
        prompt: str,
        schema: type[T],
        system: str | None = None,
        purpose: str,
        prompt_version: str,
    ) -> T:
        return _structured(
            self,
            prompt=prompt,
            schema=schema,
            system=system,
            purpose=purpose,
            prompt_version=prompt_version,
        )

    def _log(self, **kwargs) -> None:
        """Own session via get_session(), not the caller's.

        A cost row must survive the caller's transaction rolling back —
        e.g. extraction fails after a real, billable LLM call already
        happened. Logging that call must not be undone by an unrelated
        rollback later in the same request.
        """
        with get_session() as session:
            session.add(LLMCall(**kwargs))
