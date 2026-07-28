from datetime import date

from chief.extract import jd as jd_module
from chief.extract.jd import RoleExtraction, jd_to_role
from chief.llm.base import LLMResponse
from chief.models import RoleKind


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


def test_jd_to_role_returns_role_extraction_from_llm_structured(monkeypatch):
    monkeypatch.setattr(jd_module, "_read_prompt_template", lambda prompt_version: "TEMPLATE")
    expected = RoleExtraction(
        company="Acme", title="SWE Intern", kind=RoleKind.INTERN, deadline=date(2026, 9, 1)
    )
    provider = ScriptedProvider(expected)

    result = jd_to_role("some raw JD text", provider)

    assert result == expected
    assert provider.calls[0]["purpose"] == "extract_jd"
    assert provider.calls[0]["schema"] is RoleExtraction
    assert "some raw JD text" in provider.calls[0]["prompt"]
    assert "TEMPLATE" in provider.calls[0]["prompt"]
