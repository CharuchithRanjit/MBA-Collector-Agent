"""Turns a feed item's raw text into a summary + importance score via the LLM.

Shape C (compression/judgment), not Shape A — there's no "correct"
extractable answer here, only a calibrated opinion. The prompt itself is
hand-written (see llm/prompts/summarize.*.md); this module just loads
the template, appends the item text, and calls llm.structured().
"""

from pathlib import Path

from pydantic import BaseModel

from chief.llm.base import LLMProvider

PROMPTS_DIR = Path(__file__).parent.parent / "llm" / "prompts"


class ItemSummary(BaseModel):
    summary: str
    importance: float


def _read_prompt_template(prompt_version: str) -> str:
    return (PROMPTS_DIR / f"summarize.{prompt_version}.md").read_text()


def summarize_item(text: str, llm: LLMProvider, *, prompt_version: str = "v1") -> ItemSummary:
    """Summarize a feed item's raw text and score its importance."""
    template = _read_prompt_template(prompt_version)
    prompt = f"{template}\n\n---\nITEM TEXT:\n{text}"
    return llm.structured(
        prompt=prompt,
        schema=ItemSummary,
        purpose="summarize_feed_item",
        prompt_version=prompt_version,
    )
