from chief.config import settings
from chief.llm.factory import get_llm_provider


def test_get_llm_provider_defaults_to_claude_cli(monkeypatch):
    monkeypatch.setattr(settings, "chief_llm_provider", "cli")

    provider = get_llm_provider()

    assert provider.name == "claude-cli"


def test_get_llm_provider_selects_anthropic_api_when_env_set(monkeypatch):
    monkeypatch.setattr(settings, "chief_llm_provider", "api")

    provider = get_llm_provider()

    assert provider.name == "anthropic-api"
