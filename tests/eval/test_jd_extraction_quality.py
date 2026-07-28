"""Golden-file quality eval for JD extraction. Hits a real LLM — run with `-m eval`.

Each case is a pair of files in evals/jd/: `<name>.txt` (raw posting text)
and `<name>.golden.json` (hand-written expected RoleExtraction). Structured
fields must match exactly; requirements are scored on substring coverage,
since transcribed phrasing can vary slightly between runs.
"""

import json
from pathlib import Path

import pytest

from chief.extract.jd import jd_to_role
from chief.llm.factory import get_llm_provider

EVALS_DIR = Path(__file__).parent.parent.parent / "evals" / "jd"
REQUIREMENTS_COVERAGE_THRESHOLD = 0.7


def _golden_cases() -> list[Path]:
    return sorted(EVALS_DIR.glob("*.golden.json"))


def _requirements_coverage(golden: list[str], extracted: list[str]) -> tuple[float, list[str]]:
    extracted_text = " ".join(extracted).lower()
    missing = [item for item in golden if item.lower() not in extracted_text]
    coverage = 1.0 if not golden else 1 - len(missing) / len(golden)
    return coverage, missing


@pytest.mark.eval
@pytest.mark.parametrize(
    "golden_path", _golden_cases(), ids=lambda p: p.name.removesuffix(".golden.json")
)
def test_jd_extraction_matches_golden(golden_path: Path) -> None:
    golden = json.loads(golden_path.read_text())
    jd_text = (golden_path.parent / f"{golden_path.name.removesuffix('.golden.json')}.txt").read_text()

    extraction = jd_to_role(jd_text, get_llm_provider())

    assert extraction.company == golden["company"]
    assert extraction.title == golden["title"]
    assert extraction.kind == golden["kind"]
    assert extraction.location == golden["location"]
    deadline = extraction.deadline.isoformat() if extraction.deadline else None
    assert deadline == golden["deadline"]

    coverage, missing = _requirements_coverage(golden["requirements"], extraction.requirements)
    assert coverage >= REQUIREMENTS_COVERAGE_THRESHOLD, (
        f"requirements coverage {coverage:.0%} below {REQUIREMENTS_COVERAGE_THRESHOLD:.0%}, "
        f"missing: {missing}"
    )
