"""Provider protocol. The only place the rest of the app talks to a model."""

from typing import Protocol

from pydantic import BaseModel


class LLMResponse(BaseModel):
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0


class LLMError(Exception):
    """Provider failed. Callers decide whether to degrade or raise."""


class LLMProvider(Protocol):
    name: str

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
        self,
        *,
        prompt: str,
        schema: type[T],
        system: str | None = None,
        purpose: str,
        prompt_version: str,
    ) -> T: ...