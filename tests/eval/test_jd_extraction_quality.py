"""Golden-file quality eval for JD extraction. Hits a real LLM — run with `-m eval`.

Each case is a pair of files in evals/jd/: `<name>.txt` (raw posting text)
and `<name>.golden.json` (hand-written expected RoleExtraction). Structured
fields must match exactly; requirements are scored on substring coverage,
since transcribed phrasing can vary slightly between runs.
"""

import json
from pathlib import Path

import pytest

from chief.extract.jd import RoleExtraction, jd_to_role
from chief.llm.base import LLMProvider
from chief.llm.factory import get_llm_provider

EVALS_DIR = Path(__file__).parent.parent.parent / "evals" / "jd"
REQUIREMENTS_COVERAGE_THRESHOLD = 0.7
REPEATS = 3
REPEAT_PASS_THRESHOLD = 2  # majority of REPEATS must match golden

_SMART_PUNCTUATION = str.maketrans({
    "‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-",
})


def _normalize(text: str) -> str:
    return text.translate(_SMART_PUNCTUATION)


def _golden_cases() -> list[Path]:
    return sorted(EVALS_DIR.glob("*.golden.json"))


def _requirements_coverage(golden: list[str], extracted: list[str]) -> tuple[float, list[str]]:
    extracted_text = _normalize(" ".join(extracted)).lower()
    missing = [item for item in golden if _normalize(item).lower() not in extracted_text]
    coverage = 1.0 if not golden else 1 - len(missing) / len(golden)
    return coverage, missing


def _check_extraction(extraction: RoleExtraction, golden: dict) -> tuple[bool, str]:
    mismatches = []
    for field in ("company", "title", "kind", "location"):
        actual = getattr(extraction, field)
        expected = golden[field]
        if actual != expected:
            mismatches.append(f"{field}: expected {expected!r}, got {actual!r}")

    deadline = extraction.deadline.isoformat() if extraction.deadline else None
    if deadline != golden["deadline"]:
        mismatches.append(f"deadline: expected {golden['deadline']!r}, got {deadline!r}")

    coverage, missing = _requirements_coverage(golden["requirements"], extraction.requirements)
    if coverage < REQUIREMENTS_COVERAGE_THRESHOLD:
        mismatches.append(
            f"requirements coverage {coverage:.0%} below {REQUIREMENTS_COVERAGE_THRESHOLD:.0%}, "
            f"missing: {missing}"
        )

    return (not mismatches, "; ".join(mismatches))


@pytest.mark.eval
@pytest.mark.parametrize(
    "golden_path", _golden_cases(), ids=lambda p: p.name.removesuffix(".golden.json")
)
def test_jd_extraction_matches_golden(golden_path: Path) -> None:
    golden = json.loads(golden_path.read_text())
    jd_text = (golden_path.parent / f"{golden_path.name.removesuffix('.golden.json')}.txt").read_text()
    provider: LLMProvider = get_llm_provider()

    run_failures = []
    for run in range(1, REPEATS + 1):
        extraction = jd_to_role(jd_text, provider)
        ok, reason = _check_extraction(extraction, golden)
        if not ok:
            run_failures.append(f"run {run}: {reason}")

    passes = REPEATS - len(run_failures)
    assert passes >= REPEAT_PASS_THRESHOLD, (
        f"only {passes}/{REPEATS} runs matched golden\n" + "\n".join(run_failures)
    )
