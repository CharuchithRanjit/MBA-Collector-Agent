# STATE

Updated: 2026-08-05
Milestone: hour 10 slice 4 — render.py done (fixture-tested only, no
real data yet), no chief brief/scheduler yet

## Done
- models.py, db.py, config.py, cli.py
- services/applications.py (add/list/move, null-last ordering, injectable
  clock; add_application now also takes location/jd_url/jd_raw_text, and
  builds Application(role=role) not role_id= — see bugfix note below)
- add_application no longer accepts `tier` — it was silently discarded
  whenever the company already existed. Company keeps its default
  tier of 2; cli.py's `add` command no longer exposes --tier either.
- llm/base.py (LLMProvider protocol, hand-written) + models.LLMCall
- llm/: ClaudeCLIProvider, AnthropicAPIProvider, FakeLLM, shared
  structured() retry helper, LoggingProvider (writes llm_call, retry
  = 2 rows), factory.get_llm_provider() (env-selected, CHIEF_LLM_PROVIDER)
- fetch.py (httpx + trafilatura), extract/jd.py (RoleExtraction — no
  skills fields, jd_to_role), services/jobs.py (ingest_jd), `chief jd
  add [URL] [--paste]` wired end to end
- llm/prompts/extract_jd.v1.md — hand-written, then I added an explicit
  "## Output" JSON-shape section (jd_to_role does raw model_validate_json
  on completion text, no tool-use schema enforcement, so the exact key
  names needed spelling out). Live-tested against real `claude -p`:
  correctly extracted company/title/kind/location, correctly used the
  actual stated deadline (Nov 15 2026) and did not hallucinate one from
  "Summer 2027" appearing in the text.
- Bugfix: `Application(role_id=role.id)` let `.role` get GC'd and
  silently re-queried, hitting the SQLite-naive-datetime landmine on
  deadline_at. Fixed to `Application(role=role)`.
- fetch.py hardened against bot-blocking: sends a real browser
  User-Agent + Accept-Language (default python-httpx UA gets 403'd by
  a lot of corporate career sites), raises FetchError (not raw httpx
  exceptions) on bad status or empty extraction. cli.py's jd_add
  catches FetchError, prints a one-line "copy the page text and run
  --paste" hint (highlight=False — Rich's auto-highlighting was
  injecting ANSI codes into a message meant to be exact/greppable),
  exits 1, no traceback. Live-smoke-tested against a real 404.
- Role.requirements (JSON list, hand-written) now flows through:
  RoleExtraction.requirements, add_application(requirements=...),
  ingest_jd forwards extraction.requirements, jd_to_role defaults to
  prompt_version="v2". New `chief jd show <id>` command + new
  applications.get_application() service function (not LLM-related,
  no FakeLLM test needed). Live-tested with a real posting containing
  deliberate filler ("Strong communication skills") — v2 prompt
  correctly excluded it from requirements, exactly as instructed.
- Two of the three named tests for this slice (persists_requirements,
  handles_empty_requirements) already passed once the plumbing was
  written — same "trivial additive param" pattern as location/jd_url/
  jd_raw_text earlier, nothing to meaningfully stub there. Only
  get_application + chief jd show were genuinely new logic and went
  through a real red state first.
- Note: local data/chief.db still has the old Role schema (no
  requirements column) — create_all doesn't migrate existing tables.
  Not fixed here; you're recreating the DB by hand.
- ClaudeCLIProvider fixes from real-world use against the BNP posting
  (15KB): prompt now goes via stdin, not argv (the earlier unexplained
  nonzero exit is gone — ran clean on the exact file that triggered
  it). `--output-format json` parsed for real total_cost_usd and the
  modelUsage entry with the highest cost (Claude Code sometimes uses a
  cheap model internally alongside the main one, e.g. for conversation
  titling — picking max-cost avoids attributing the response to the
  wrong model). Bonus: input_tokens/output_tokens now populated too,
  same payload, previously always 0. LLMError now includes stderr and
  returncode and truncates the echoed command to 200 chars instead of
  dumping the whole prompt. Live-verified: model="claude-sonnet-5",
  cost_usd=0.1074 on the real BNP ingest, not "claude-cli"/0.0.
- fetch_url_text's empty-extraction path (trafilatura.extract returns
  None) now has a direct test — was only covered indirectly before
- Stray tracked .pyc files (predating the ignore-bytecode commit)
  untracked with `git rm --cached`; .gitignore already covered them
- JD extraction eval harness (tests/eval/test_jd_extraction_quality.py,
  `-m eval`, excluded from default addopts) + 11 real golden postings
  in evals/jd/ (raw text + hand-labeled expected extraction). Ran for
  real against all 11, found and fixed two genuine prompt gaps:
  company name didn't say to strip a corporate suffix the posting
  itself displays ("Amazon, Inc." → should be "Amazon"), and the
  "several offices, use the first" location rule didn't distinguish a
  single combined location value ("Pittsburgh, PA or Dallas, TX
  (Hybrid)") from an actual office list. Also fixed oliver_wyman:
  university career-portal postings often repeat the same office list
  twice (unlabeled summary card vs. labeled "Location" field, slightly
  different formatting) — now prefers the labeled copy.
- 37 tests passing (unit suite; eval suite is 11 more, gated behind
  `-m eval`, not part of this count)
- Eval-noise backlog item resolved: chose option (c) from below — each
  golden case now runs 3x (`REPEATS`), requires 2/3 to match
  (`REPEAT_PASS_THRESHOLD`) before the parametrized test fails. Also
  normalizes smart punctuation (curly quotes/dashes → straight) before
  the requirements substring-coverage check, since that was a likely
  source of false-negative "misses" independent of real sampling
  variance. Smoke-tested against oliver_wyman_actuarial (3 real
  `claude -p` runs, passed, 58s, $0). claude_cli.py's LLMError now
  also includes stdout (previously stderr only) on nonzero exit.
- **RSS feed ingest slice 1: schema + fetch + parse + dedupe + persist.**
  `Feed`/`FeedItem` added to models.py (hand-written) — `guid` globally
  unique (matches design doc's stated idempotency key), `last_modified`
  kept as `str` not `datetime` (opaque HTTP header, echoed verbatim in
  `If-Modified-Since`, never reparsed). Deliberately left `summary`/
  `importance`/`model`/`prompt_version` off the table for now — those
  belong to the not-yet-designed summarization slice; "tables are created
  when a feature needs them, not upfront."
  New `src/chief/rss.py`: `fetch_feed(url, etag=, last_modified=)` —
  conditional GET via `httpx`, parses with `feedparser` (new dependency,
  approved). 304 returns `not_modified=True` (not an error, not raised).
  `parsed.bozo` alone doesn't raise — only `bozo and not entries`. guid
  fallback: `entry.id or entry.link`; entries with neither are skipped
  (no stable dedup key, one bad entry shouldn't fail the whole poll).
  New `services/feeds.py`: `add_feed`/`list_feeds`/`get_feed`/`poll_feed`/
  `poll_all_feeds`. Dedup is a Python set-membership check against
  `FeedItem.guid` — never a model, per the design doc's explicit
  anti-pattern. `poll_all_feeds` catches `FetchError` per-feed so one
  dead feed doesn't kill the batch.
  `chief feed add/list/poll <id>|--all` wired end to end.
  Live-tested against `https://hnrss.org/frontpage`: first poll pulled
  20 real items; second poll and `poll --all` both correctly returned 0
  new items (that feed sends `Last-Modified` but no `ETag` — conditional
  GET and/or guid dedup both cover the no-duplicate-rows case either way).
  68 unit tests passing (35 new: 15 rss, 15 feeds, 5 cli), eval suite
  still 11 more gated behind `-m eval`.
- **Feed item summarization slice 2 (Shape C): schema + LLM call +
  batch + persist.** `FeedItem` gained `summary`/`importance`/`model`/
  `prompt_version` (hand-written) — `summary` indexed since `WHERE
  summary IS NULL` is the idempotency key for the whole batch job (design
  doc §10). New `llm/prompts/summarize.v1.md` (hand-written) — one to two
  plain sentences plus a 0.0–1.0 importance score judged against "does
  this matter to someone actively recruiting for PM/AI-product/tech
  roles this week," explicit that the number is advisory input to a
  later deterministic ranking step, not the ranking decision itself.
  New `src/chief/analyze/summarize.py` (first module in a new `analyze/`
  package — Shape C, distinct from `extract/`'s Shape A): `summarize_item
  (text, llm) -> ItemSummary(summary, importance)`, identical shape to
  `jd_to_role` (same prompt-file loading seam, same `purpose=
  "summarize_feed_item"` hardcoded literal). New `services/summarize.py`:
  `summarize_pending_items(session, llm, limit=25)` — queries `summary IS
  NULL AND raw_text IS NOT NULL`, undated-last ordering, persists
  `model=llm.name` (coarser than `llm_call.model`, deliberately — exact
  model is already logged for free via `LoggingProvider`). Dropped a
  planned `now: datetime | None` param before implementing — computed
  and immediately discarded, nothing in the function is actually
  time-dependent, would have been dead code. `chief feed summarize
  [--limit N]` wired end to end, no per-feed scoping (mirrors
  `poll_all_feeds`'s globality).
  Live-tested against the same `hnrss.org` items from slice 1: real
  `claude -p` calls produced sensible summaries and importance scores
  (a DeepMind leadership-shakeup story scored 0.6, an Aristotle-quotes
  post scored 0.0). Idempotency confirmed across three real calls: 5
  summarized → 15 more (all 20 done) → 0 on a third call with nothing
  left pending.
  Deliberately deferred, by explicit choice, not oversight: the LLM-
  as-judge eval harness (design doc's Shape-C "no eval, no ship" gate is
  real, but rubric calibration against 20 hand-labeled examples is a
  bigger lift than the JD-extraction eval and needs real summary data to
  calibrate against — same "ship first, add golden eval as its own slice
  after" precedent JD extraction followed); `MODEL_FOR_PURPOSE` cheap-
  model routing (cross-cutting, would touch JD extraction too, cleaner
  as its own slice). Both noted below.
  80 unit tests passing (12 new: 4 analyze, 6 services, 2 cli), eval
  suite still 11 more gated behind `-m eval`.
- **rank.py slice 3: deterministic focus-item scoring.** Scoped to
  Application/Role ranking only (not news top-N-by-importance —
  briefing-spec.md treats those as two different mechanisms; news
  selection is a simple sort+threshold, deferred to whichever slice
  builds the news section). Exception to the usual division of labour:
  the user asked me to write rank.py itself this time (normally
  reserved to them per CLAUDE.md) since they were busy — flagged once,
  then proceeded. `score(application, now)`: urgency from whichever of
  `next_action_due_at` / `role.deadline_at` is sooner (an overdue next
  action and a close deadline are both maximally urgent; taking the min
  means neither signal gets silently ignored when both are set — this
  was an explicit call, not the strawman's original "next action always
  wins"), `STAGE_WEIGHTS` per `AppStatus`, `tier_weight = 4 - company.tier`,
  a 3x overdue multiplier. `as_utc()` on both candidate dates before
  subtraction — this is the exact landmine CLAUDE.md flags rank.py as
  the landing spot for. `rank_applications()` sorts descending; callers
  are expected to have already excluded terminal statuses.
  `services/applications.list_applications_ranked()` does that exclusion
  (REJECTED/WITHDRAWN filtered before rank.py ever sees them) — added to
  the existing file rather than a new `services/briefing.py`, since one
  ranking helper doesn't yet earn its own module.
  `chief app list --ranked` wired in as a standalone toggle (doesn't
  compose with `--status`/`--due-within-days` this slice). Live-tested:
  a near-term application without any next action beats a far-off one
  under plain deadline order; adding a next-action due tomorrow to the
  far-off one correctly pulls it ahead under `--ranked` while the
  unranked view stays deadline-ordered — confirms the "sooner of the two
  dates" logic is actually doing something, not just present in the code.
  `test_list_applications_ranked_respects_injected_now` is worth noting
  as a test-design pattern: proving `now` is actually threaded through
  needed a scenario where the *order itself* flips between two `now`
  values (tier-3-near vs tier-1-far; the far one wins once both are
  overdue and urgency saturates identically) — an early draft of this
  test only checked "still returns 1 row," which would have passed even
  if the function silently ignored `now` and always used `utcnow()`.
  91 unit tests passing (7 new for rank.py, 3 for
  list_applications_ranked, 1 CLI), eval suite still 11 more gated
  behind `-m eval`.
- **render.py slice 4: briefing markdown/push renderer, fixture-only.**
  Not hand-write-reserved (unlike rank.py) — design doc's own
  division-of-labour table lists Jinja templates under Claude-writes,
  distinct from prompts. Scoped deliberately to just the renderer: no
  `services/briefing.py` orchestrator, no `chief brief` command, nothing
  rendering real data yet — `render.py` can't build a real
  `BriefingContext` by itself (needs a focus-sentence LLM call and news
  selection, neither built), so that's next slice.
  New `BriefingContext`/`DeadlineRow`/`NextActionRow`/`PipelineCounts`/
  `NewsItem`/`BriefingFooter` dataclasses live in `render.py` itself (no
  `schemas.py` — same local-definition precedent as `extract/jd.py`'s
  `RoleExtraction`). `follow_ups`/`matches`/`calendar` present-but-empty
  per briefing-spec.md's explicit instruction, so those slices are a
  service change with zero renderer change later.
  New `src/chief/templates/` (external `.j2` files, mirroring
  `llm/prompts/`'s file-not-string-literal convention but for a
  different concern — Claude's to write, not hand-reserved).
  `render_full`/`render_push` do zero date math inside the templates —
  `_format_day`/`_when_label`/`_capped` (5-item hard cap + overflow
  count) all run in Python first, matching the "convert at the edges"
  rule. `Environment(keep_trailing_newline=True)` — Jinja's default
  strips the final newline, which would have silently mismatched every
  golden fixture's trailing `\n`.
  Two golden-markdown snapshot tests built on briefing-spec.md's peak-
  season and sparse-day-one samples (not literal copies — that file's
  own header says its data is fabricated for layout purposes — but
  structurally faithful), plus 8 single-rule tests (cap/overflow at
  exactly 5, the "None."/"Nothing due today." empty-section branches,
  the today-vs-weekday label boundary). 9 of 10 tests passed against the
  first implementation attempt; the one failure was the test's own bug
  (`"| Co"` incidentally substring-matches `"| Company |"` in the table
  header row), not a rendering bug — fixed to a more specific substring.
  101 unit tests passing (10 new), eval suite still 11 more gated
  behind `-m eval`. No live smoke test this slice, by design — first
  real data flows through render.py in the chief-brief slice.

## Next
- AnthropicAPIProvider's cost_usd is still hardcoded 0.0 (no
  MODEL_FOR_PURPOSE/pricing table) — unaffected by recent slices,
  which only touched ClaudeCLIProvider; that path gets cost directly
  from claude -p's own JSON, no pricing table needed there
- LLM-as-judge eval harness for summarization, deliberately deferred
  from slice 2 — now that real summary data exists (from the live
  smoke test), hand-label ~20 examples, write a judge prompt, calibrate
  judge-vs-human agreement (design doc target: ~80%) before trusting any
  number it produces
- `MODEL_FOR_PURPOSE` cheap-model routing (config.py/factory.py),
  deliberately deferred from slice 2 — summarization is the
  paradigmatic cheap-model workload per the design doc but currently
  runs on whatever `get_llm_provider()` returns, same as JD extraction
- Rest of the "hours 6–10" milestone, now that ingest/summarize/rank/
  render (slices 1–4) are done: `services/briefing.py` (the
  orchestrator — queries `list_applications_ranked()`, a new
  Shape-B focus-line prompt [hand-written, same as every other prompt],
  news top-N-by-importance selection, assembles a real
  `BriefingContext`), `chief brief` [--send], APScheduler +
  RUN_SCHEDULER flag, ntfy.sh push, Dockerfile/compose, EC2 deploy. Each
  still worth its own slice rather than scoping inline.

## Decided, do not reopen
- No agent framework. Pipelines of typed functions.
- Ranking is deterministic; the LLM writes the sentence only.
- FTS5 before embeddings. No user_id column.
- LLM default is ClaudeCLIProvider (`claude -p`, $0).
  AnthropicAPIProvider selected by CHIEF_LLM_PROVIDER=api.
