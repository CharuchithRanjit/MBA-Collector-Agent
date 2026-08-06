# Briefing Spec — v1 (§3.1 scope only)

> **All data below is fabricated for layout purposes.** Company names, deadlines, and news items are illustrative. This file is the spec for `render.py` and the Jinja template, not a real brief.

**Scope assumption:** application tracker, JD extraction, resume storage, RSS ingest, briefing. No contacts table, no gap analysis, no calendar, no search.

---

## Change from your original mockup

You had the ordering as: Calendar → Deadlines → Tasks → Companies → Networking → News → Reading → **Focus (last)**.

**Move focus to the top.** You read this on a lock screen at 6am. The one thing you must not miss goes in the first 40 characters, not after six sections you'll scroll past. Everything below focus is reference material for when you have a coffee in hand.

---

## Sample 1 — peak recruiting season

Thursday, October 15, 2026. This is the brief working as intended.

```markdown
# Good morning — Thursday, Oct 15

## Focus
**Submit the Stripe APM application.** It closes in 47 hours, it's your
only tier-1 deadline this week, and the JD is 80% overlap with the
Databricks one you already tailored for.

---

## Deadlines · next 7 days

| When | Company | Role | Status |
|---|---|---|---|
| **Fri Oct 17** | Stripe | APM Intern | not started |
| Mon Oct 20 | Databricks | PM Intern (Data & AI) | draft saved |
| Tue Oct 21 | Notion | APM Intern | not started |

## Next actions · due

- **Today** — Ramp: send onsite thank-you (onsite was Oct 13)
- **Today** — Scale AI: reply to recruiter re: availability
- Sat Oct 17 — Nvidia: decide apply / skip

## Pipeline

12 tracked · 5 applied · 2 in process · 1 offer-stage · 4 not started

⚠ Stale: **Figma** (applied Sep 28, 17 days, no response)

---

## AI news · 4 items

**Model releases**
- [Vendor] shipped a smaller reasoning model at roughly a third the
  cost of the previous tier; benchmarks are within noise of the
  larger one on coding. — *TechCrunch, 2 min*

**Product / PM angle**
- [Company] published a postmortem on their agent rollout: the
  failure mode was tool-call latency, not model quality. Worth
  reading before your Databricks interview. — *Eng blog, 6 min*

**Funding**
- [Startup] raised a Series B for enterprise eval tooling. Third
  eval-focused round this quarter — the category is consolidating.
  — *The Information, 3 min*

**Research**
- New paper on long-context retrieval degradation past 200k tokens.
  — *arXiv, skim*

---
*Generated 06:00 · 21 items scanned, 4 kept · $0.011 · extract_jd.v3, summarize.v2*
```

### Phone push (ntfy) — same data, 3-line summary + one headline per news item

```
Chief · Thu Oct 15
Focus: Submit Stripe APM — closes in 47h
2 actions due today · 3 deadlines this week · 4 AI items
• OpenAI ships GPT-6
• EvalCo raises $40M Series B
• ...
```

The headline lines use each item's raw feed title, not the LLM-generated
summary the markdown/HTML views show — the web view (`/briefing/today`)
is localhost-only, so the push is the only place these ever reach the
phone; a bare count wasn't enough to actually read them there.

**The push is a separate render of the same context object**, not a truncation of the markdown. Build `render_push(ctx)` and `render_full(ctx)` side by side.

---

## Sample 2 — day one, sparse data

Tuesday, July 28, 2026. This is what you'll actually see first, and it's the case that breaks naive renderers.

```markdown
# Good morning — Tuesday, Jul 28

## Focus
**Apply to the Databricks PM Intern role.** It's the only saved role
with a deadline inside 30 days, and you haven't started it.

---

## Deadlines · next 7 days
None.

## Next actions · due
Nothing due today.

## Pipeline
2 tracked · 0 applied · 2 not started

---

## AI news · 3 items

- [Vendor] released an updated model family; pricing dropped on the
  mid-tier. — *Vendor blog, 4 min*
- [Company] open-sourced their internal eval harness. — *GitHub, skim*
- Long read on how PM hiring is shifting at AI-native companies.
  — *Substack, 11 min*

---
*Generated 06:00 · 9 items scanned, 3 kept · $0.004 · summarize.v2*
```

**Two rules this case forces:**

1. **Empty sections say "None." in one line.** They do not disappear (you'd wonder if the job broke) and they do not get padded with encouragement.
2. **Focus has a fallback ladder.** When no task is due, drop down the ladder deterministically:

```
1. Overdue next_action        →  "Do X, it's N days late"
2. Deadline within 7 days     →  "Submit X, closes in Nh"
3. Stale application >14d     →  "Follow up on X, N days quiet"
4. Saved role, not started    →  "Apply to X"
5. Nothing at all             →  "Nothing is due. Add a role: chief jd add <url>"
```

Rung 5 is important. **A brief with nothing to say should say nothing and suggest the input that fixes it.** Do not let the model invent a motivational task — that's how you learn to ignore the brief.

---

## Field sources — build this table before the template

Every line above, and where it comes from. If a row says *deterministic*, the model must never touch it.

| Brief element | Source | How |
|---|---|---|
| Date header | `now` | deterministic |
| Focus — **which** item | `rank.score()` over `task` + `application` | **deterministic** |
| Focus — **the sentence** | top item + 2 runners-up as context | **AI, Shape B** |
| Deadlines table | `role.deadline_at` ≤ now+7d | deterministic |
| "closes in 47 hours" | date math | **deterministic** — never a model |
| Next actions | `application.next_action_due_at` ≤ today | deterministic |
| Pipeline counts | `GROUP BY application.status` | deterministic |
| Stale flag | `applied_at < now-14d AND status='APPLIED'` | deterministic |
| News item summary | `feed_item.raw_text` | **AI, Shape C** (one call per item) |
| News item selection | importance score, top N | deterministic threshold |
| News grouping | `feed.category` | deterministic |
| "Worth reading before your Databricks interview" | top-2 upcoming roles passed into the summarize prompt | **AI, Shape C** |
| Footer metrics | `SUM(llm_call.cost_cents)` for this run | deterministic |

**Exactly two AI calls per brief** at steady state: one focus sentence, N item summaries (already done at 05:15, so cached). The 06:00 job should make **one** live call.

---

## Renderer rules

1. **`render.py` takes a `BriefingContext` dataclass and `now`. No DB access, no LLM.** The focus sentence is already a string on the context by the time the renderer sees it. This is what makes the snapshot test in §12.2 possible.
2. **Markdown is the source of truth.** HTML and the push are derived. Store the markdown in `briefing.markdown`.
3. **Hard cap: 5 news items, 5 deadlines, 5 next actions.** Overflow becomes "+3 more" with a link. A brief you scroll is a brief you skip.
4. **Never emit a section header with no content and no "None."** Pick one; be consistent.
5. **Every relative time is computed once, at render, from the passed `now`.** No `datetime.now()` inside the template.

---

## What v1 must *not* include

Leave these out even though the mockup temptation is real. Each one needs a table you don't have yet:

| Absent | Needs | Arrives |
|---|---|---|
| Networking follow-ups | `contact`, `interaction` | §3.2 weekend |
| "Your resume matches this JD at 72%" | `gap_analysis` | §3.2 weekend |
| Today's calendar | Google Calendar ingest | §3.3 month one |
| Reading suggestions | `document` + FTS5 | §3.3 month one |

**Design the context object with those fields present and empty now.** `BriefingContext(focus, deadlines, next_actions, pipeline, news, follow_ups=[], matches=[], calendar=[])`. The template renders empty lists as nothing. Then §3.2 is a service change with **zero renderer change** — which is the whole point of the split.

---

## Your 15-minute exercise

Sample 1 is my guess at your priorities. It's probably wrong in at least two places.

Copy this file to `docs/briefing-spec.md`, then edit Sample 1 until it's the brief *you* want at 6am in October. Specifically decide:

1. Does pipeline count earn its space, or is it vanity metrics?
2. Is 4 news items right, or is 2?
3. What's missing that you'd actually check your phone for?

The edited file is your acceptance test for hour 6–10.
