from types import SimpleNamespace

import anthropic
import pytest

from chief.llm.anthropic_api import AnthropicAPIProvider
from chief.llm.base import LLMError


class FakeMessages:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error

    def create(self, **kwargs):
        if self._error is not None:
            raise self._error
        return self._response


class FakeClient:
    def __init__(self, response=None, error=None):
        self.messages = FakeMessages(response=response, error=error)


def test_anthropic_api_provider_parses_response_into_llm_response():
    fake_response = SimpleNamespace(
        content=[SimpleNamespace(text="hello from claude")],
        model="claude-fake-model",
        usage=SimpleNamespace(input_tokens=10, output_tokens=20),
    )
    provider = AnthropicAPIProvider(client=FakeClient(response=fake_response))

    response = provider.complete(prompt="say hi", purpose="test", prompt_version="v1")

    assert response.text == "hello from claude"
    assert response.model == "claude-fake-model"
    assert response.input_tokens == 10
    assert response.output_tokens == 20


def test_anthropic_api_provider_raises_llm_error_on_api_failure():
    provider = AnthropicAPIProvider(client=FakeClient(error=anthropic.AnthropicError("boom")))

    with pytest.raises(LLMError):
        provider.complete(prompt="say hi", purpose="test", prompt_version="v1")
