# STATE

Updated: 2026-08-06
Milestone: hour 10 slice 8 — `api.py` + web view live (localhost only,
native, no Docker). Hours 6–10 roadmap is functionally complete; what's
left (Docker, TLS, public exposure) is optional hardening, not core
product.

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
- **`chief brief` slice 5: the orchestrator + first Shape-B LLM call.**
  Plain `chief brief` only (confirmed scope) — `--send`/ntfy is its own
  slice, `notify.py` doesn't exist yet.
  New `llm/prompts/focus_line.v1.md` (hand-written) — explicit "don't
  invent facts" guardrails, since Shape B is where a model is most
  tempted to fabricate a plausible-sounding comparison between
  applications. New `src/chief/draft/focus_line.py` (third Shape
  package, joining `extract/`=A and `analyze/`=C): `write_focus_line()`
  uses `llm.complete()`, not `structured()` — Shape B is prose, no
  schema — and returns `FocusLine(text, cost_usd)` so the briefing
  footer's cost figure comes straight from `LLMResponse.cost_usd`, no
  separate `llm_call` query needed. A deterministic `_signal_for()`
  classifies *why* the top application is urgent (overdue next action /
  deadline soon / stale >14d / not started) and hands the model an exact
  hours/days figure — the prompt explicitly forbids the model from
  computing or estimating its own time figure, only restating the given
  one in its own words.
  `services/applications.py` gained `list_next_actions_due` and
  `get_pipeline_summary` (bucket math confirmed against the design doc's
  own sample: 5 applied + 2 in-process + 1 offer + 4 not-started = 12
  tracked). `services/feeds.py` gained `get_top_news_items` (importance
  sort + threshold, deterministic — never a model, per the design doc's
  explicit anti-pattern) and `count_summarized_items`.
  New `services/briefing.py` — the actual orchestrator design doc §5.2
  promised ("there is no orchestrator because briefing.py *is* the
  orchestrator"). Composes rank + the one LLM call + news selection +
  render, no SQL of its own. Falls back to a hardcoded "Nothing is due"
  string with zero cost when there are no active applications — no LLM
  call at all on that path.
  `chief brief` prints via plain `print()`, not `console.print()` —
  Rich's `Console` interprets `[Category]`-style text as its own markup
  syntax by default, which would have corrupted the real briefing output
  (news bullets use exactly that bracket format).
  All 26 new tests passed against the first implementation attempt — the
  strongest signal yet that the plan-before-code discipline is paying
  off, though it's also a small sample of one slice.
  **Live-tested end to end for the first time** — every piece in the
  project running together against real data: 2 real applications, a
  real Hacker News poll (20 items), 10 real summarizations, then a real
  `claude -p` focus-line call. Deadline math was exact (deadline minus
  the actual run timestamp, not a rounded guess) and the model correctly
  declined to invent a reason beyond what `_signal_for()` gave it.
  Re-running `chief brief` immediately after showed the identical news
  items (same top-N by importance) with only the footer timestamp
  changing — matches "regenerating is safe," not a bug, per design doc.
  Known simplifications, flagged not hidden: `items_scanned` counts all
  summarized items ever, not "today's poll" (no run-marker exists yet);
  running `chief brief` twice shows the same news both times (no
  "already shown" tracking — needs the deferred `Briefing` table);
  `read_time` is a real word-count estimate over stored `raw_text`, not
  the full original article.
  122 unit tests passing (21 new: 6 focus_line, 5 briefing, 5
  applications, 4 feeds, 1 cli), eval suite still 11 more gated behind
  `-m eval`.
- **`notify.py` + `chief brief --send` slice 6.** No blocking
  prerequisite — first slice with no LLM call and nothing touching
  models.py/rank.py/a prompt file, so nothing was reserved to the user
  per CLAUDE.md. `notify.py` is a bare function (`send_push(text,
  topic)`), not a `Notifier` protocol/class — design doc §16 lists that
  abstraction as future work "once a second implementation is needed"
  (Slack/Discord); one notifier doesn't earn it yet, same "two is the
  threshold" rule followed elsewhere. Mirrors `fetch.py`'s exact shape:
  one exception (`NotifyError`), `raise_for_status()` in a narrow
  `try/except`, only `HTTPStatusError` caught (not connection-level
  errors — same scope `fetch_url_text` already accepts).
  New `config.py` setting `ntfy_topic: str | None`, and the first
  `.env.example` in the repo (committed; `.env` already gitignored) —
  worth one since this is the first genuinely private setting (an
  unguessable topic name is load-bearing for ntfy.sh's public-server
  privacy tradeoff, which the design doc explicitly accepts rather than
  hides).
  `chief brief --send` prints the full markdown always, then
  additionally pushes via `render_push()` (already existed, unused until
  now) when `--send` is passed — not an either/or, matches
  briefing-spec.md's "the push is a separate render of the same context
  object, not a truncation" framing. Missing `NTFY_TOPIC` or a push
  failure both exit 1 with a clean message, no traceback, same pattern
  as `FetchError` handling elsewhere.
  9 new tests, all passed on the first implementation attempt.
  Live-tested against the real ntfy.sh public server with a disposable
  throwaway topic (not the user's real one) — POST succeeded, and
  delivery was independently confirmed by polling ntfy's own JSON API
  (`GET /{topic}/json?poll=1`), not just trusting a 200 status. The
  user's real `.env`/`NTFY_TOPIC` and phone subscription are theirs to
  set up and verify — not done as part of this session.
  129 unit tests passing (7 new: 3 notify, 4 cli), eval suite still 11
  more gated behind `-m eval`. User has since configured a real
  `NTFY_TOPIC` in `.env` (confirmed by real pushes during the next
  slice's verification, below) — `.env.example` was subsequently
  deleted from disk as a side effect of editing `.env` directly (not
  something this session did), user confirmed leaving it deleted.
- **Scheduler slice 7: systemd user timer, not APScheduler.** No
  Python code, no new tests — entirely operational artifacts. `api.py`
  was never built (every slice stayed CLI-only, `GET /briefing/today`
  deferred every time), and `fastapi`/`uvicorn`/`structlog` have sat
  unused in `pyproject.toml` since day one — standing up a web server
  just to host a scheduler for a once-a-day job was more machinery than
  the job needed. **This retires "APScheduler + RUN_SCHEDULER flag"
  from the roadmap** — there's no app process for that flag to toggle
  anymore; the equivalent control is enabling/disabling the systemd
  timer.
  New `ops/run_daily.sh`: `chief feed poll --all` → `chief feed
  summarize --limit 25` → `chief brief --send`, in sequence. The first
  two steps are allowed to fail without stopping the script (`||
  echo ... continuing`, not bare `set -e`) — a single malformed
  summarization response shouldn't silently skip the actually-important
  deadline/focus content. Script exit code is `chief brief --send`'s
  (the last command), so a real failure there still fails the run
  visibly. Absolute path to `uv`, not `$PATH` — systemd's minimal
  environment doesn't source shell rc files.
  New `ops/chief-brief.service` + `ops/chief-brief.timer`, user-level
  (no sudo to install/manage) with `Persistent=true` (systemd's
  equivalent of the design doc's `misfire_grace_time` concern — a
  missed 06:00 fires as soon as the box is back, not silently skipped
  until tomorrow). One combined run, not the design doc's four
  separately-timed jobs — deliberate simplification, nothing here takes
  long enough to need staggered scheduling at this scale.
  **Live-verified through the real systemd unit**, not just the script
  by hand: `sudo loginctl enable-linger ec2-user` (needed root — this
  box has passwordless sudo, confirmed with the user before running),
  `systemctl --user enable --now chief-brief.timer`, then `systemctl
  --user start chief-brief.service` to trigger the exact unit the timer
  will fire, confirmed via `journalctl` — real feed poll, real
  summarize, real `chief brief --send`, exit 0, real push landed on the
  user's actual phone (their real `NTFY_TOPIC` is now configured).
  **Caught during verification, not anticipated in the plan**: the
  box's system clock is UTC (`timedatectl`), so the original
  `OnCalendar=06:00:00` would have fired at 6am UTC, not 6am the user's
  local time. User is UTC-4 (US Eastern/EDT) — corrected to
  `OnCalendar=10:00:00`. This is a fixed offset, not a named timezone,
  so it will **not** auto-adjust for DST — `ops/README.md` documents
  the twice-yearly manual update (10:00 UTC for EDT, 11:00 UTC for EST)
  and the alternative (`timedatectl set-timezone America/New_York` on
  the whole box, not done here since it affects all system time, not
  just this timer).
- **Docker attempted, parked — `api.py` + web view built natively
  instead, slice 8.** Tried containerizing (`Dockerfile`,
  `docker-compose.yml` — both still on disk, uncommitted, untracked):
  image built and ran fine for non-LLM commands, but hit a real wall —
  the `$0` `ClaudeCLIProvider` path depends on a host-authenticated
  `claude` CLI session (a 277MB binary plus a live OAuth token in
  `~/.claude/.credentials.json`), which a container can't have without
  either mounting live credentials into it or switching to the paid
  API. Decided to stay native and build the long-deferred web view
  instead, which doesn't need Docker at all.
  New `Briefing` table (hand-written) finally built — `for_date`
  (`date`, not `datetime` — one row per calendar day, a timestamp would
  make `UNIQUE` meaningless), caches all three rendered variants
  (`markdown`/`html`/`push_text`) since this codebase's `render.py`
  produces each independently, not via markdown→HTML conversion.
  `pushed_at` fixes `chief brief --send`'s long-standing push
  non-idempotency for free — same table closes two deferred gaps at
  once. `services/briefing.get_or_create_briefing()` — one row per
  day, cache hit skips the LLM call entirely; `chief brief` and the new
  `api.py` share the same cache, so whichever runs first each day pays
  for it, the other reuses it.
  New `src/chief/api.py`: `GET /healthz`, `GET /briefing/today`, `GET
  /briefing/{date}`. Plain `def` handlers (not `async def`) — every
  service call underneath is synchronous, FastAPI dispatches sync
  handlers through its own threadpool, avoiding CLAUDE.md's landmine #7
  ("blocking I/O in async routes"). Bound to `127.0.0.1` only —
  reachable via SSH tunnel, not the network, not phone-tappable yet;
  public exposure + TLS is separate future work, not done here.
  **Two real bugs found and fixed during live verification, not
  anticipated in the plan:**
  1. `render_html` had no autoescaping — `chief jd add <url>` rendered
     as a literal (browser-interpreted) `<url>` tag, not escaped text.
     Since feed headlines/company names trace back to external sources
     (RSS, scraped JD text), this was a real HTML-injection risk, not
     just cosmetic. Fixed with a second, `autoescape=True` Jinja
     environment used only for HTML (markdown/push text must stay
     unescaped or `**bold**` would mangle). Caught by manually
     inspecting the cached row's stored HTML, not by a test — a
     regression test (`test_render_html_escapes_untrusted_content`) was
     added after the fact.
  2. systemd's user-session `PATH` (`/usr/local/bin:/usr/local/sbin:
     /usr/bin:/usr/sbin`) doesn't include `~/.local/bin`, where `claude`
     lives. `chief` shells out to `claude` by bare name (subprocess PATH
     lookup) — this silently broke any *real* LLM call triggered via
     systemd, including in the scheduler slice, undetected until now
     only because every prior systemd verification happened to hit the
     "nothing due" fallback (no LLM call needed). Fixed by adding
     `Environment="PATH=..."` to both `chief-brief.service` and the new
     `chief-api.service`. Confirmed fixed live: `chief feed summarize`
     went from "claude not found" to "Summarized 25 items" through the
     exact same systemd unit, no other changes.
  Live-verified end to end: real HTTP round trip to `/healthz` and
  `/briefing/today` (200, then a second identical 200 with no new LLM
  call), `/briefing/2020-01-01` correctly 404s, and — the real payoff —
  triggering `chief-brief.service` after `/briefing/today` had already
  generated today's row printed `"Already pushed today"` and reused the
  *exact* cached markdown (same `Generated` timestamp), proving the
  scheduler and the web view genuinely share one cache, not two
  independent code paths that happen to look similar.
  146 unit tests passing (17 new: 6 briefing-cache, 5 api, 4 render
  [including the escaping regression test found after the fact], 2
  cli), eval suite still 11 more gated behind `-m eval`.
- **Push notification now carries news headlines, not just a count.**
  Prompted by a real complaint: the user got "4 AI items" on their
  phone and had no way to read them, since `/briefing/today` is
  localhost-only (public exposure is parked, see Next). Interim fix
  instead of pulling that forward: `NewsItem` gained a `title: str = ""`
  field (the raw `FeedItem.title`, distinct from `headline`, which
  stays the LLM summary markdown/HTML use), threaded through from
  `services/briefing.py`. `render_push()` now emits one `• {title}`
  line per news item after the existing 3-line header — templates
  still do no I/O, still take `now`. This intentionally breaks the
  design doc's "3 lines" push spec (`docs/briefing-spec.md` updated to
  match); the hand-written test that encoded the old contract,
  `test_render_push_produces_three_line_summary`, was replaced with
  `test_render_push_includes_news_headlines` (user-supplied name).
  146 → still 146 (one test replaced, not added) + the new test passes
  the same run as everything else; `docs/CODEBASE.md`'s push
  description updated too.

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
- **DST reminder**: update `OnCalendar` in `ops/chief-brief.timer` (both
  the repo copy and `~/.config/systemd/user/chief-brief.timer`) to
  `11:00:00` when US clocks fall back to EST (~November), back to
  `10:00:00` when EDT resumes (~March) — see `ops/README.md`
- Docker: parked, not cancelled. `Dockerfile`/`docker-compose.yml` on
  disk, uncommitted, proven for non-LLM commands. Revisit if a paid
  `ANTHROPIC_API_KEY` ever makes the container fully viable (no
  host-credential mounting needed) — see slice 8's note above for the
  exact blocker.
- Public exposure + TLS (Caddy) — what actually makes tapping the phone
  push notification open `/briefing/today`. Also the point at which
  API-key auth on `api.py` starts to matter (not needed while
  localhost-only, since SSH access is already the access boundary).
  Design doc calls this "the weekend" — genuinely separate, deliberate
  future work, not an oversight.
- `POST /applications`, `POST /jobs/ingest`, `POST /notes`, `GET
  /costs` — design doc's full `api.py` endpoint list; this slice built
  only the read-only web view, deliberately.
- EC2 deploy / GitHub Actions + GHCR — not attempted; this box already
  *is* the running deployment (systemd + native `uv`), so "deploy"
  going forward means either standing up CI for this same host or
  revisiting Docker per the note above.

## Decided, do not reopen
- No agent framework. Pipelines of typed functions.
- Ranking is deterministic; the LLM writes the sentence only.
- FTS5 before embeddings. No user_id column.
- LLM default is ClaudeCLIProvider (`claude -p`, $0).
  AnthropicAPIProvider selected by CHIEF_LLM_PROVIDER=api.
