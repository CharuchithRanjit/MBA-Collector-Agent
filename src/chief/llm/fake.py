"""Fake provider for tests. No network, no subprocess, no DB."""

from pydantic import BaseModel

from chief.llm.base import LLMResponse


class FakeLLM:
    name = "fake"

    def __init__(
        self,
        complete_responses: dict[str, str] | None = None,
        structured_responses: dict[str, BaseModel] | None = None,
    ) -> None:
        self._complete_responses = complete_responses or {}
        self._structured_responses = structured_responses or {}

    def complete(
        self,
        *,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 1024,
        purpose: str,
        prompt_version: str,
    ) -> LLMResponse:
        """Return the canned response registered for `purpose`."""
        return LLMResponse(text=self._complete_responses[purpose], model=self.name)

    def structured[T: BaseModel](
        self,
        *,
        prompt: str,
        schema: type[T],
        system: str | None = None,
        purpose: str,
        prompt_version: str,
    ) -> T:
        """Return the canned Pydantic object registered for `purpose`."""
        return self._structured_responses[purpose]
