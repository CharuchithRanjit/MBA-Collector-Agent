"""Turns raw job-posting text into a RoleExtraction via the LLM.

The prompt itself is hand-written (see llm/prompts/extract_jd.*.md) —
this module just loads the template, appends the JD text, and calls
llm.structured(). _read_prompt_template is its own function so tests
can monkeypatch it without needing a real prompt file on disk.
"""

from datetime import date
from pathlib import Path

from pydantic import BaseModel

from chief.llm.base import LLMProvider
from chief.models import RoleKind

PROMPTS_DIR = Path(__file__).parent.parent / "llm" / "prompts"


class RoleExtraction(BaseModel):
    company: str
    title: str
    kind: RoleKind
    location: str | None = None
    deadline: date | None = None
    requirements: list[str] = []


def _read_prompt_template(prompt_version: str) -> str:
    return (PROMPTS_DIR / f"extract_jd.{prompt_version}.md").read_text()


def jd_to_role(text: str, llm: LLMProvider, *, prompt_version: str = "v2") -> RoleExtraction:
    """Extract company/title/kind/location/deadline from JD text."""
    template = _read_prompt_template(prompt_version)
    prompt = f"{template}\n\n---\nJOB POSTING TEXT:\n{text}"
    return llm.structured(
        prompt=prompt,
        schema=RoleExtraction,
        purpose="extract_jd",
        prompt_version=prompt_version,
    )
