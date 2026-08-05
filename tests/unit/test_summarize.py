from chief.analyze import summarize as summarize_module
from chief.analyze.summarize import ItemSummary, summarize_item
from chief.llm.base import LLMResponse


class ScriptedProvider:
    name = "scripted"

    def __init__(self, structured_result):
        self._result = structured_result
        self.calls = []

    def complete(self, *, prompt, system=None, max_tokens=1024, purpose, prompt_version) -> LLMResponse:
        raise NotImplementedError

    def structured(self, *, prompt, schema, system=None, purpose, prompt_version):
        self.calls.append(
            {"prompt": prompt, "schema": schema, "purpose": purpose, "prompt_version": prompt_version}
        )
        return self._result


def test_summarize_item_returns_item_summary_from_llm_structured(monkeypatch):
    monkeypatch.setattr(summarize_module, "_read_prompt_template", lambda prompt_version: "TEMPLATE")
    expected = ItemSummary(summary="A thing happened.", importance=0.7)
    provider = ScriptedProvider(expected)

    result = summarize_item("some raw item text", provider)

    assert result == expected


def test_summarize_item_calls_structured_with_summarize_feed_item_purpose(monkeypatch):
    monkeypatch.setattr(summarize_module, "_read_prompt_template", lambda prompt_version: "TEMPLATE")
    provider = ScriptedProvider(ItemSummary(summary="x", importance=0.1))

    summarize_item("some raw item text", provider)

    assert provider.calls[0]["purpose"] == "summarize_feed_item"
    assert provider.calls[0]["schema"] is ItemSummary


def test_summarize_item_includes_raw_text_in_prompt(monkeypatch):
    monkeypatch.setattr(summarize_module, "_read_prompt_template", lambda prompt_version: "TEMPLATE")
    provider = ScriptedProvider(ItemSummary(summary="x", importance=0.1))

    summarize_item("some raw item text", provider)

    assert "some raw item text" in provider.calls[0]["prompt"]
    assert "TEMPLATE" in provider.calls[0]["prompt"]


def test_summarize_item_defaults_to_prompt_version_v1(monkeypatch):
    monkeypatch.setattr(summarize_module, "_read_prompt_template", lambda prompt_version: "TEMPLATE")
    provider = ScriptedProvider(ItemSummary(summary="x", importance=0.1))

    summarize_item("some raw item text", provider)

    assert provider.calls[0]["prompt_version"] == "v1"
