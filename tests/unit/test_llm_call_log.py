import pytest
from pydantic import BaseModel
from sqlmodel import select

from chief.llm.base import LLMError, LLMResponse
from chief.llm.call_log import LoggingProvider
from chief.models import LLMCall


class StubProvider:
    name = "stub"

    def __init__(self, response: LLMResponse | None = None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error

    def complete(self, *, prompt, system=None, max_tokens=1024, purpose, prompt_version):
        if self._error is not None:
            raise self._error
        return self._response


class ScriptedProvider:
    """Returns each entry in `outputs` in order, one per complete() call."""

    name = "scripted"

    def __init__(self, outputs: list[str]) -> None:
        self._outputs = list(outputs)
        self.calls = 0

    def complete(self, *, prompt, system=None, max_tokens=1024, purpose, prompt_version):
        text = self._outputs[self.calls]
        self.calls += 1
        return LLMResponse(text=text, model="scripted-model")


def test_logging_provider_writes_llm_call_row_on_success(session):
    inner = StubProvider(
        response=LLMResponse(
            text="hi", model="stub-model", input_tokens=3, output_tokens=5, cost_usd=0.01, latency_ms=42
        )
    )
    provider = LoggingProvider(inner)

    result = provider.complete(prompt="p", purpose="test", prompt_version="v1")

    assert result.text == "hi"
    rows = session.exec(select(LLMCall)).all()
    assert len(rows) == 1
    assert rows[0].success is True
    assert rows[0].purpose == "test"
    assert rows[0].provider == "stub"
    assert rows[0].model == "stub-model"
    assert rows[0].input_tokens == 3
    assert rows[0].output_tokens == 5


def test_logging_provider_writes_llm_call_row_on_failure_and_reraises(session):
    inner = StubProvider(error=LLMError("boom"))
    provider = LoggingProvider(inner)

    with pytest.raises(LLMError):
        provider.complete(prompt="p", purpose="test", prompt_version="v1")

    rows = session.exec(select(LLMCall)).all()
    assert len(rows) == 1
    assert rows[0].success is False
    assert rows[0].error == "boom"


def test_logging_provider_structured_retry_writes_two_llm_call_rows(session):
    """Extra, beyond the approved list: verifies change #1 directly — a
    retry must produce two LLMCall rows, one per completion, so retry
    cost is visible."""

    class Extracted(BaseModel):
        title: str

    inner = ScriptedProvider(["not json", '{"title": "SWE Intern"}'])
    provider = LoggingProvider(inner)

    result = provider.structured(
        prompt="extract", schema=Extracted, purpose="extract_jd", prompt_version="v1"
    )

    assert result == Extracted(title="SWE Intern")
    rows = session.exec(select(LLMCall)).all()
    assert len(rows) == 2
    assert all(r.success for r in rows)
