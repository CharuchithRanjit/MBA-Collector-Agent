from datetime import UTC, datetime, timedelta

from chief import render as render_module
from chief.render import (
    BriefingContext,
    BriefingFooter,
    DeadlineRow,
    NewsItem,
    NextActionRow,
    PipelineCounts,
    render_full,
    render_html,
    render_push,
)

NOW = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)


def _populated_ctx() -> BriefingContext:
    return BriefingContext(
        for_date=NOW,
        focus="**Submit the Stripe APM application.** It closes in 47 hours.",
        deadlines=[
            DeadlineRow(
                deadline_at=datetime(2026, 10, 17, tzinfo=UTC),
                company="Stripe",
                role="APM Intern",
                status_label="not started",
            ),
            DeadlineRow(
                deadline_at=datetime(2026, 10, 20, tzinfo=UTC),
                company="Databricks",
                role="PM Intern (Data & AI)",
                status_label="draft saved",
            ),
            DeadlineRow(
                deadline_at=datetime(2026, 10, 21, tzinfo=UTC),
                company="Notion",
                role="APM Intern",
                status_label="not started",
            ),
        ],
        next_actions=[
            NextActionRow(due_at=NOW, company="Ramp", text="send onsite thank-you"),
            NextActionRow(due_at=NOW, company="Scale AI", text="reply to recruiter re: availability"),
            NextActionRow(
                due_at=datetime(2026, 10, 17, tzinfo=UTC), company="Nvidia", text="decide apply / skip"
            ),
        ],
        pipeline=PipelineCounts(
            tracked=12, applied=5, in_process=2, offer_stage=1, not_started=4, stale=["Figma"]
        ),
        news=[
            NewsItem(
                category="Model releases",
                headline="Vendor shipped a smaller reasoning model at a third the cost.",
                source="TechCrunch",
                read_time="2 min",
            ),
            NewsItem(
                category="Funding",
                headline="Startup raised a Series B for enterprise eval tooling.",
                source="The Information",
                read_time="3 min",
            ),
        ],
        footer=BriefingFooter(
            generated_at=NOW,
            items_scanned=21,
            items_kept=2,
            cost_usd=0.011,
            prompt_versions=["extract_jd.v2", "summarize.v1"],
        ),
    )


def _sparse_ctx() -> BriefingContext:
    return BriefingContext(
        for_date=NOW,
        focus="Nothing is due. Add a role: chief jd add <url>",
        deadlines=[],
        next_actions=[],
        pipeline=PipelineCounts(
            tracked=2, applied=0, in_process=0, offer_stage=0, not_started=2, stale=[]
        ),
        news=[],
        footer=BriefingFooter(
            generated_at=NOW, items_scanned=0, items_kept=0, cost_usd=0.0, prompt_versions=[]
        ),
    )


def test_render_full_matches_golden_markdown_for_populated_briefing():
    result = render_full(_populated_ctx(), NOW)

    expected = """# Good morning — Thu Oct 15

## Focus
**Submit the Stripe APM application.** It closes in 47 hours.

---

## Deadlines · next 7 days
| When | Company | Role | Status |
|---|---|---|---|
| Sat Oct 17 | Stripe | APM Intern | not started |
| Tue Oct 20 | Databricks | PM Intern (Data & AI) | draft saved |
| Wed Oct 21 | Notion | APM Intern | not started |

## Next actions · due
- **Today** — Ramp: send onsite thank-you
- **Today** — Scale AI: reply to recruiter re: availability
- **Sat Oct 17** — Nvidia: decide apply / skip

## Pipeline
12 tracked · 5 applied · 2 in process · 1 offer-stage · 4 not started
⚠ Stale: **Figma**

## AI news · 2 items
- [Model releases] Vendor shipped a smaller reasoning model at a third the cost. — *TechCrunch, 2 min*
- [Funding] Startup raised a Series B for enterprise eval tooling. — *The Information, 3 min*

---
*Generated 2026-10-15 09:00 · 21 items scanned, 2 kept · $0.011 · extract_jd.v2, summarize.v1*
"""

    assert result == expected


def test_render_full_matches_golden_markdown_for_sparse_briefing():
    result = render_full(_sparse_ctx(), NOW)

    expected = """# Good morning — Thu Oct 15

## Focus
Nothing is due. Add a role: chief jd add <url>

---

## Deadlines · next 7 days
None.

## Next actions · due
Nothing due today.

## Pipeline
2 tracked · 0 applied · 0 in process · 0 offer-stage · 2 not started

## AI news · 0 items
None.

---
*Generated 2026-10-15 09:00 · 0 items scanned, 0 kept · $0.000 · none*
"""

    assert result == expected


def test_render_full_shows_none_for_empty_deadlines_section():
    result = render_full(_sparse_ctx(), NOW)

    assert "## Deadlines · next 7 days\nNone." in result


def test_render_full_shows_nothing_due_today_for_empty_next_actions():
    result = render_full(_sparse_ctx(), NOW)

    assert "## Next actions · due\nNothing due today." in result


def test_render_full_caps_deadlines_at_five_with_overflow_note():
    ctx = _populated_ctx()
    ctx.deadlines = [
        DeadlineRow(
            deadline_at=NOW + timedelta(days=i), company=f"Co{i}", role="Role", status_label="not started"
        )
        for i in range(7)
    ]

    result = render_full(ctx, NOW)

    assert result.count("not started |") == 5
    assert "+2 more" in result


def test_render_full_caps_news_at_five_with_overflow_note():
    ctx = _populated_ctx()
    ctx.news = [
        NewsItem(category="Cat", headline=f"Headline {i}", source="Src", read_time="1 min")
        for i in range(6)
    ]

    result = render_full(ctx, NOW)

    assert result.count("Headline") == 5
    assert "+1 more" in result


def test_render_full_uses_today_label_for_next_action_due_on_now():
    ctx = _populated_ctx()
    ctx.next_actions = [NextActionRow(due_at=NOW, company="Ramp", text="follow up")]

    result = render_full(ctx, NOW)

    assert "**Today** — Ramp: follow up" in result


def test_render_full_uses_weekday_label_for_next_action_due_later():
    ctx = _populated_ctx()
    ctx.next_actions = [
        NextActionRow(due_at=NOW + timedelta(days=2), company="Ramp", text="follow up")
    ]

    result = render_full(ctx, NOW)

    assert "**Sat Oct 17** — Ramp: follow up" in result


def test_render_push_includes_news_headlines():
    ctx = _populated_ctx()
    ctx.news = [
        NewsItem(
            category="Model releases",
            headline="Vendor shipped a smaller reasoning model at a third the cost.",
            source="TechCrunch",
            read_time="2 min",
            title="OpenAI ships GPT-6",
        ),
        NewsItem(
            category="Funding",
            headline="Startup raised a Series B for enterprise eval tooling.",
            source="The Information",
            read_time="3 min",
            title="EvalCo raises $40M Series B",
        ),
    ]

    result = render_push(ctx, NOW)

    assert "Chief · Thu Oct 15" in result
    assert "Focus: **Submit the Stripe APM application.** It closes in 47 hours." in result
    assert "2 actions due today · 3 deadlines this week · 2 AI items" in result
    assert "OpenAI ships GPT-6" in result
    assert "EvalCo raises $40M Series B" in result


def test_render_push_counts_only_actions_due_today():
    ctx = _populated_ctx()
    ctx.next_actions = [
        NextActionRow(due_at=NOW, company="Ramp", text="a"),
        NextActionRow(due_at=NOW + timedelta(days=3), company="Nvidia", text="b"),
    ]

    result = render_push(ctx, NOW)

    assert "1 actions due today" in result


def test_render_html_includes_focus_text():
    result = render_html(_populated_ctx(), NOW)

    assert "Submit the Stripe APM application" in result
    assert "<html" in result


def test_render_html_escapes_untrusted_content():
    # Feed headlines/company names trace back to external sources (RSS,
    # scraped JD text) -- a literal `<tag>` in that data must render as
    # escaped text, not be interpreted as real markup by the browser.
    ctx = _sparse_ctx()
    ctx.focus = "Nothing is due. Add a role: chief jd add <url>"

    result = render_html(ctx, NOW)

    assert "&lt;url&gt;" in result
    assert "<url>" not in result


def test_render_html_shows_none_for_empty_deadlines_section():
    result = render_html(_sparse_ctx(), NOW)

    assert "None." in result


def test_render_news_detail_includes_title_summary_and_source():
    item = NewsItem(
        category="Model releases",
        headline="A summary sentence.",
        source="TechCrunch",
        read_time="2 min",
        title="OpenAI ships GPT-6",
    )

    result = render_module.render_news_detail(item)

    assert "OpenAI ships GPT-6" in result
    assert "A summary sentence." in result
    assert "TechCrunch" in result
    assert "2 min" in result


def test_render_html_caps_news_at_five():
    ctx = _populated_ctx()
    ctx.news = [
        NewsItem(category="Cat", headline=f"Headline {i}", source="Src", read_time="1 min")
        for i in range(7)
    ]

    result = render_html(ctx, NOW)

    assert result.count("Headline") == 5
    assert "+2 more" in result
