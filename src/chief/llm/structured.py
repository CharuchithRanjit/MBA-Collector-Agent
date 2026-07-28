"""Shared complete() -> validate -> one retry helper for structured output.

Concrete providers implement complete() only, not structured() — this is
the single place that owns the retry. Call it with anything that has a
complete() method, including LoggingProvider, so a retry's second
completion gets logged too.
"""

from typing import Protocol

from pydantic import BaseModel, ValidationError

from chief.llm.base import LLMResponse


class CompletingProvider(Protocol):
    def complete(
        self,
        *,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 1024,
        purpose: str,
        prompt_version: str,
    ) -> LLMResponse: ...


def structured[T: BaseModel](
    provider: CompletingProvider,
    *,
    prompt: str,
    schema: type[T],
    system: str | None = None,
    purpose: str,
    prompt_version: str,
) -> T:
    """Complete, validate against schema, retry exactly once on failure."""
    response = provider.complete(
        prompt=prompt, system=system, purpose=purpose, prompt_version=prompt_version
    )
    try:
        return schema.model_validate_json(response.text)
    except ValidationError as e:
        retry_prompt = f"{prompt}\n\nYour output failed validation:\n{e}\nReturn only valid JSON."
        response = provider.complete(
            prompt=retry_prompt, system=system, purpose=purpose, prompt_version=prompt_version
        )
        return schema.model_validate_json(response.text)  # second failure raises
