from datetime import UTC, date, datetime

import pytest

from chief.extract.jd import RoleExtraction
from chief.models import RoleKind
from chief.services import jobs


class DummyLLM:
    name = "dummy"


def test_ingest_jd_creates_application_from_pasted_text(session, monkeypatch):
    extraction = RoleExtraction(company="Acme", title="SWE Intern", kind=RoleKind.INTERN)
    monkeypatch.setattr(jobs, "jd_to_role", lambda text, llm, **kwargs: extraction)

    application = jobs.ingest_jd(session, DummyLLM(), pasted_text="raw jd text here")

    assert application.role.company.name == "Acme"
    assert application.role.title == "SWE Intern"


def test_ingest_jd_fetches_url_when_no_pasted_text_given(session, monkeypatch):
    extraction = RoleExtraction(company="Acme", title="SWE Intern", kind=RoleKind.INTERN)
    monkeypatch.setattr(jobs, "jd_to_role", lambda text, llm, **kwargs: extraction)
    fetch_calls = []

    def fake_fetch(url):
        fetch_calls.append(url)
        return "fetched jd text"

    monkeypatch.setattr(jobs, "fetch_url_text", fake_fetch)

    application = jobs.ingest_jd(session, DummyLLM(), url="https://example.com/job/1")

    assert fetch_calls == ["https://example.com/job/1"]
    assert application.role.company.name == "Acme"


def test_ingest_jd_converts_extraction_deadline_to_utc_datetime(session, monkeypatch):
    extraction = RoleExtraction(
        company="Acme", title="SWE Intern", kind=RoleKind.INTERN, deadline=date(2026, 9, 1)
    )
    monkeypatch.setattr(jobs, "jd_to_role", lambda text, llm, **kwargs: extraction)

    application = jobs.ingest_jd(session, DummyLLM(), pasted_text="raw jd text")

    assert application.role.deadline_at == datetime(2026, 9, 1, tzinfo=UTC)


def test_ingest_jd_leaves_deadline_at_none_when_extraction_has_no_deadline(session, monkeypatch):
    extraction = RoleExtraction(company="Acme", title="SWE Intern", kind=RoleKind.INTERN)
    monkeypatch.setattr(jobs, "jd_to_role", lambda text, llm, **kwargs: extraction)

    application = jobs.ingest_jd(session, DummyLLM(), pasted_text="raw jd text")

    assert application.role.deadline_at is None


def test_ingest_jd_persists_jd_raw_text(session, monkeypatch):
    extraction = RoleExtraction(company="Acme", title="SWE Intern", kind=RoleKind.INTERN)
    monkeypatch.setattr(jobs, "jd_to_role", lambda text, llm, **kwargs: extraction)

    application = jobs.ingest_jd(session, DummyLLM(), pasted_text="raw jd text here")

    assert application.role.jd_raw_text == "raw jd text here"


def test_ingest_jd_raises_value_error_when_neither_url_nor_pasted_text_given(session):
    with pytest.raises(ValueError):
        jobs.ingest_jd(session, DummyLLM())


def test_ingest_jd_persists_requirements(session, monkeypatch):
    extraction = RoleExtraction(
        company="Acme",
        title="SWE Intern",
        kind=RoleKind.INTERN,
        requirements=["Python", "3+ years experience", "BS in CS"],
    )
    monkeypatch.setattr(jobs, "jd_to_role", lambda text, llm, **kwargs: extraction)

    application = jobs.ingest_jd(session, DummyLLM(), pasted_text="raw jd text")

    assert application.role.requirements == ["Python", "3+ years experience", "BS in CS"]


def test_ingest_jd_handles_empty_requirements(session, monkeypatch):
    extraction = RoleExtraction(company="Acme", title="SWE Intern", kind=RoleKind.INTERN)
    monkeypatch.setattr(jobs, "jd_to_role", lambda text, llm, **kwargs: extraction)

    application = jobs.ingest_jd(session, DummyLLM(), pasted_text="raw jd text")

    assert application.role.requirements == []
