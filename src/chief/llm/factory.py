"""Selects and wires up the configured LLMProvider. Callers use this, never a provider class directly."""

from chief.config import settings
from chief.llm.anthropic_api import AnthropicAPIProvider
from chief.llm.base import LLMProvider
from chief.llm.call_log import LoggingProvider
from chief.llm.claude_cli import ClaudeCLIProvider


def get_llm_provider() -> LLMProvider:
    """ClaudeCLIProvider by default; AnthropicAPIProvider if settings.chief_llm_provider == "api"."""
    inner = AnthropicAPIProvider() if settings.chief_llm_provider == "api" else ClaudeCLIProvider()
    return LoggingProvider(inner)
