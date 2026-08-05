"""Feed item summarization. Calls the LLM through llm.base.LLMProvider only."""

from sqlmodel import Session, select

from chief.analyze.summarize import summarize_item
from chief.llm.base import LLMProvider
from chief.models import FeedItem

DEFAULT_BATCH_LIMIT = 25  # design doc §10: "cap at 25/day for cost"


def summarize_pending_items(
    session: Session,
    llm: LLMProvider,
    *,
    limit: int = DEFAULT_BATCH_LIMIT,
) -> list[FeedItem]:
    """Summarize up to `limit` FeedItems with no summary yet.

    Idempotency key is `summary IS NULL` (design doc §10) — once set, an
    item is never reprocessed by this function. Items with no raw_text
    are excluded from the query entirely (nothing to summarize; without
    this exclusion they'd occupy batch slots on every call forever).
    """
    pending = session.exec(
        select(FeedItem)
        .where(FeedItem.summary.is_(None))
        .where(FeedItem.raw_text.is_not(None))
        .order_by(FeedItem.published_at.is_(None), FeedItem.published_at)
        .limit(limit)
    ).all()

    updated = []
    for item in pending:
        result = summarize_item(item.raw_text, llm)
        item.summary = result.summary
        item.importance = result.importance
        item.model = llm.name
        item.prompt_version = "v1"
        session.add(item)
        updated.append(item)

    session.flush()
    return updated
