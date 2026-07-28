"""Job description ingestion. No LLM calls except through llm.base.LLMProvider."""

from datetime import UTC, datetime, time

from sqlmodel import Session

from chief.extract.jd import jd_to_role
from chief.fetch import fetch_url_text
from chief.llm.base import LLMProvider
from chief.models import Application
from chief.services import applications


def ingest_jd(
    session: Session,
    llm: LLMProvider,
    *,
    url: str | None = None,
    pasted_text: str | None = None,
) -> Application:
    """Fetch or use pasted JD text, extract a role, create the application.

    Raises ValueError if neither url nor pasted_text is given.
    """
    if pasted_text is None and url is None:
        raise ValueError("ingest_jd requires either url or pasted_text")

    text = pasted_text if pasted_text is not None else fetch_url_text(url)
    extraction = jd_to_role(text, llm)

    deadline_at = None
    if extraction.deadline is not None:
        deadline_at = datetime.combine(extraction.deadline, time.min, tzinfo=UTC)

    return applications.add_application(
        session,
        extraction.company,
        extraction.title,
        extraction.kind,
        deadline_at=deadline_at,
        location=extraction.location,
        jd_url=url,
        jd_raw_text=text,
    )
