import pytest
from pydantic import BaseModel, ValidationError

from chief.llm.base import LLMResponse
from chief.llm.structured import structured


class Extracted(BaseModel):
    title: str


class ScriptedProvider:
    """Returns each entry in `outputs` in order, one per complete() call."""

    name = "scripted"

    def __init__(self, outputs: list[str]) -> None:
        self._outputs = list(outputs)
        self.calls = 0

    def complete(self, *, prompt, system=None, max_tokens=1024, purpose, prompt_version) -> LLMResponse:
        text = self._outputs[self.calls]
        self.calls += 1
        return LLMResponse(text=text, model="scripted-model")


def test_structured_retries_once_on_validation_error():
    provider = ScriptedProvider(["not json", '{"title": "SWE Intern"}'])

    result = structured(
        provider,
        prompt="extract this",
        schema=Extracted,
        purpose="extract_jd",
        prompt_version="v1",
    )

    assert result == Extracted(title="SWE Intern")
    assert provider.calls == 2


def test_structured_raises_after_second_validation_failure():
    provider = ScriptedProvider(["not json", "still not json"])

    with pytest.raises(ValidationError):
        structured(
            provider,
            prompt="extract this",
            schema=Extracted,
            purpose="extract_jd",
            prompt_version="v1",
        )

    assert provider.calls == 2
