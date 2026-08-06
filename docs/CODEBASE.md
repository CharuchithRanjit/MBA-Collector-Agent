# Codebase reference

What exists, file by file, and what capability each piece drives. This
is the "how it actually works" companion to `docs/STATE.md` (the
running changelog of *when* things were built and *why*) and
`docs/career-agent-design-doc.md` (the original architectural vision —
not everything here matches it exactly; deviations are noted).

## How the pieces fit together

```
CLI (cli.py) ──┐
               ├──> services/*.py  ──>  models.py (SQLite)
API (api.py) ──┘         │
                          ├──> llm/*  (Claude, via a Protocol)
                          ├──> rank.py       (pure, deterministic)
                          ├──> render.py     (pure, Jinja2 templates)
                          └──> notify.py     (ntfy.sh)

ops/  (systemd timer + service)  ──runs──>  the CLI, on a schedule
```

Two entrypoints (CLI, API) are thin wrappers — they parse input, call
exactly one service function, and format the result. All real logic
lives in `services/`. Everything that touches an LLM goes through the
`LLMProvider` protocol; nothing calls `claude -p` or the Anthropic SDK
directly outside `llm/`.

---

## Data model — `src/chief/models.py`

Hand-written (schema changes are the expensive kind). Two helpers
underpin every datetime in the system:

- `utcnow() -> datetime` — the only clock the app is allowed to call.
- `as_utc(dt) -> datetime | None` — SQLite reads timezone-aware
  datetimes back **naive**; this re-attaches UTC before any Python-side
  date arithmetic. Skipping this on a read path is the single most
  common bug across every slice of this project.

Tables, in the order they were built:

| Table | Key fields | What it's for |
|---|---|---|
| `Company` | `name` (unique), `tier` (1=dream, 3=safety) | The employer behind a role |
| `Role` | `company_id`, `title`, `kind`, `deadline_at`, `jd_raw_text`, `requirements` (JSON) | A specific posting. `jd_raw_text` is kept forever so extraction can be re-run later without re-fetching |
| `Application` | `role_id` (unique — one application per role), `status`, `next_action`, `next_action_due_at` | Your tracking state for a role |
| `LLMCall` | `purpose`, `provider`, `model`, `cost_usd`, `success`, `error` | One row per LLM call, success or failure — the entire cost/observability story |
| `Feed` | `url` (unique), `etag`, `last_modified`, `last_fetched_at` | An RSS/Atom source, with conditional-GET caching state |
| `FeedItem` | `guid` (unique), `raw_text`, `summary`, `importance`, `model` | One polled article; `summary`/`importance` are null until summarized |
| `Briefing` | `for_date` (date, unique), `markdown`/`html`/`push_text`, `cost_usd`, `pushed_at` | One row per calendar day — the cache that makes the web view and `--send` idempotent |

## LLM provider layer — `src/chief/llm/`

The architectural keystone. Nothing outside this package is allowed to
call a model directly.

- **`base.py`** — `LLMProvider` (a `Protocol`, not a base class): every
  provider implements `complete(prompt, ...) -> LLMResponse` and
  `structured(prompt, schema, ...) -> T`. `LLMResponse` carries text,
  token counts, cost, and latency on every call, success or not.
- **`claude_cli.py`** — `ClaudeCLIProvider`, the default, $0 path. Shells
  out to `claude -p --output-format json` via `subprocess.run`, parses
  the JSON for cost/tokens/the actual model used (picking the
  highest-cost entry in `modelUsage`, since Claude Code sometimes uses a
  cheap model internally for things like conversation titling).
- **`anthropic_api.py`** — `AnthropicAPIProvider`, the paid fallback
  (`CHIEF_LLM_PROVIDER=api`). Calls the Anthropic Messages API directly.
  `cost_usd` is not wired up here yet (`LLMResponse.cost_usd` stays
  `0.0` on this path) — a known, tracked gap.
- **`structured.py`** — the shared `structured()` function: call
  `complete()`, validate the response against a Pydantic schema, retry
  **exactly once** on `ValidationError` (feeding the error back into the
  prompt), let a second failure raise. Every provider gets this for
  free by delegating to it rather than reimplementing retry logic.
- **`call_log.py`** — `LoggingProvider`, a wrapper every provider is
  wrapped in before use. Writes one `LLMCall` row per `complete()` call
  (a retry via `structured()` produces two rows, not one — both
  attempts are billable and both get logged). Logs in its own DB
  session, deliberately, so a cost row survives if the caller's own
  transaction later rolls back.
- **`factory.py`** — `get_llm_provider()`: the one function the rest of
  the app calls. Returns `LoggingProvider(ClaudeCLIProvider())` by
  default, or `LoggingProvider(AnthropicAPIProvider())` if
  `CHIEF_LLM_PROVIDER=api`.
- **`fake.py`** — `FakeLLM`, for tests. Returns canned responses keyed
  by `purpose`, from a plain dict — no network, no subprocess, no DB.

**Capability this drives:** every other AI feature in the app is a thin
module that calls `llm.complete()` or `llm.structured()` and gets
retries, cost tracking, and observability for free, without
reimplementing any of it.

---

## Capability: application tracking

**Files:** `services/applications.py`, `cli.py` (`app` commands)

Pure CRUD, no AI. `add_application()` finds-or-creates the `Company`,
creates the `Role` and `Application` in one call (deliberately builds
`Application(role=role)`, not `role_id=role.id` — passing the live
object avoids a later reload that would hit the naive-datetime landmine
on `deadline_at`). `list_applications()` supports status/deadline
filtering; `move_application()` sets `applied_at` automatically on the
first transition into `APPLIED`.

`list_applications_ranked()`, `list_next_actions_due()`, and
`get_pipeline_summary()` were added later, once ranking and the
briefing needed them — they query the same table, just shaped for those
consumers instead of the terminal `app list` table.

**Capability this drives:** `chief app add/list/move` — the tracker
that every other feature reads from.

---

## Capability: JD ingest → structured extraction (Shape A)

**Files:** `fetch.py`, `extract/jd.py`, `services/jobs.py`, `cli.py`
(`jd` commands), `llm/prompts/extract_jd.v2.md`

`fetch.py`'s `fetch_url_text()` does the only non-LLM part: `httpx.get`
with a real browser User-Agent (the default `python-httpx` UA gets
403'd by a lot of corporate career sites), then `trafilatura.extract()`
strips nav/ads down to article text.

`extract/jd.py`'s `jd_to_role(text, llm)` loads the hand-written prompt
file, appends the JD text, and calls `llm.structured()` against
`RoleExtraction` (company, title, kind, location, deadline,
requirements). The prompt is explicit that a deadline must be `None`
unless stated outright — models reliably hallucinate a plausible one
otherwise.

`services/jobs.py`'s `ingest_jd()` is the glue: fetch-or-use-pasted-text
→ extract → hand off to `applications.add_application()`.

**Capability this drives:** `chief jd add <url>` / `chief jd add
--paste` — the thing that removes the only real typing burden from the
tracker.

---

## Capability: RSS feed ingest

**Files:** `rss.py`, `services/feeds.py`, `cli.py` (`feed add/list/poll`)

`rss.py`'s `fetch_feed(url, etag=, last_modified=)` sends conditional
GET headers, returns `not_modified=True` on a real 304 (not an error),
and parses the body with `feedparser`. A malformed-feed flag
(`bozo`) alone doesn't raise — only `bozo` with zero parseable entries
does, since many real-world feeds set it for cosmetic reasons. Guid
falls back to the entry's link when no id is present; entries with
neither are skipped rather than failing the whole poll.

`services/feeds.py`'s `poll_feed()` dedupes new entries against
existing `FeedItem.guid` values in Python (a hash comparison, never a
model — see the design doc's explicit anti-pattern about letting an LLM
decide deduplication) and updates the feed's cached `etag`/
`last_modified` for next time. `poll_all_feeds()` polls every
registered feed, catching `FetchError` per-feed so one dead feed
doesn't block the rest.

**Capability this drives:** `chief feed add/poll` — cheap, repeatable
news ingestion (a daily poll of an unchanged feed costs one HTTP round
trip and a 304, nothing else).

---

## Capability: feed summarization (Shape C)

**Files:** `analyze/summarize.py`, `services/summarize.py`, `cli.py`
(`feed summarize`), `llm/prompts/summarize.v1.md`

`analyze/summarize.py`'s `summarize_item(text, llm)` is the same shape
as `jd_to_role` — load prompt, call `llm.structured()` — but against
`ItemSummary(summary, importance)`. The prompt asks for a 0.0–1.0
importance score judged against relevance to someone actively
recruiting for PM/AI-product/tech roles, and is explicit that this
number is *advisory input* to a later ranking step, not the ranking
decision itself.

`services/summarize.py`'s `summarize_pending_items(session, llm,
limit=25)` selects `FeedItem` rows where `summary IS NULL AND raw_text
IS NOT NULL`, oldest-undated-last, capped at `limit` — the idempotency
key is simply "already has a summary," so re-running never reprocesses
anything.

**Capability this drives:** turns raw polled articles into short,
scored blurbs — the input the briefing's news section and the ranking
layer actually consume.

---

## Capability: deterministic ranking

**File:** `rank.py` (hand-written — the one scoring function this
project treats as pure architecture, not implementation)

`score(application, now) -> float` combines four factors, multiplied:
urgency (`1 / days-until-due`, from whichever of `next_action_due_at` /
`role.deadline_at` is sooner), a stage weight (`STAGE_WEIGHTS`, higher
for later pipeline stages), a tier weight (`4 - company.tier`), and a
3x multiplier if the driving date is already overdue.
`rank_applications()` sorts by that score, descending.

This is the one piece of the whole system where "the model decides
what's important" is explicitly forbidden — the model only ever writes
a sentence about whatever `rank.py` already decided.

**Capability this drives:** `chief app list --ranked`, and — the
important one — which application becomes the briefing's Focus line.

---

## Capability: rendering

**Files:** `render.py`, `templates/*.j2`

`BriefingContext` and its nested dataclasses (`DeadlineRow`,
`NextActionRow`, `PipelineCounts`, `NewsItem`, `BriefingFooter`) are the
one shape three independent renderers consume:

- `render_full()` → `briefing.md.j2` — the markdown shown in the
  terminal and cached as `Briefing.markdown`.
- `render_html()` → `briefing.html.j2` — the web view, cached as
  `Briefing.html`. Uses a **separate, `autoescape=True`** Jinja
  environment from the other two — company names and feed headlines
  trace back to external, untrusted sources (RSS, scraped JD text), so
  HTML output needs real escaping. (This was a real bug, found and
  fixed during the `api.py` slice: an un-escaped `<url>` in a fallback
  message rendered as a literal, browser-interpreted tag.)
- `render_push()` → `briefing_push.txt.j2` — the 3-line ntfy summary.

All date math and the 5-item hard-cap-with-overflow logic happen in
Python (`_format_day`, `_when_label`, `_capped`) before any template is
touched — none of the three templates do arithmetic or call `now()`
themselves, which is what makes them independently, deterministically
testable.

**Capability this drives:** one context object, three outputs, zero
duplicated formatting logic.

---

## Capability: the focus line (Shape B)

**File:** `draft/focus_line.py`, `llm/prompts/focus_line.v1.md`

The one Shape-B (draft) call in the app — a human reads it, it's never
auto-sent anywhere else. `_signal_for(application, now)` is a
deterministic classifier that turns "why is this application urgent"
into an exact sentence fragment (an overdue next action, an upcoming
deadline in hours, a stale application, or "no action taken yet") —
this grounds the LLM in a real number so it can't invent or round a
time figure. `write_focus_line(top, runners_up, now, llm)` builds the
prompt from that signal plus up to two runner-up applications for
comparison context, calls `llm.complete()` (plain text — there's no
schema here, unlike extraction/summarization), and returns
`FocusLine(text, cost_usd)`.

**Capability this drives:** the one sentence at the top of every
briefing that tells you what to actually do today.

---

## Capability: briefing orchestration & caching

**File:** `services/briefing.py` — the orchestrator the design doc
described as "not really an orchestrator, just 40 lines you can read on
one screen."

`build_briefing_context(session, llm, now)` is the "always compute
fresh" primitive: rank applications, write the focus line (or fall back
to a hardcoded "nothing is due" string with zero LLM cost if there are
no active applications), pull the 7-day deadlines table, next actions
due, pipeline counts, and top news items, and assemble one
`BriefingContext`.

`get_or_create_briefing(session, llm, now)` is the caching layer on top
— one `Briefing` row per calendar day. A cache hit skips the LLM call
entirely, which is why `chief brief` (terminal), `chief brief --send`
(push), and `GET /briefing/today` (web) all cost exactly one real LLM
call *combined*, per day, no matter how many times any of them run —
whichever runs first pays for it, the rest reuse the row.

`mark_briefing_pushed()` sets `Briefing.pushed_at`, which is what makes
`--send` idempotent (running it twice sends one push, not two).

**Capability this drives:** the actual daily briefing, and the fact
that refreshing the web page or re-running the CLI doesn't quietly
re-bill a `claude -p` call every time.

---

## Capability: notifications

**File:** `notify.py`

`send_push(text, topic)` — one function, POSTs to `https://ntfy.sh/{topic}`.
No account, no API key, no dependency beyond `httpx` (already present).
Deliberately not wrapped in a `Notifier` protocol/class — one
implementation doesn't earn an abstraction yet (the design doc's own
stated threshold: "two is the minimum, one is speculation").

**Capability this drives:** `chief brief --send`'s actual phone push.

---

## Entrypoints

### CLI — `cli.py`

Every command is ≤5 lines: parse arguments, call one service function,
render the result. Rich tables for list views; plain `print()` (not
`console.print()`) for the briefing markdown specifically, since Rich
would otherwise interpret the markdown's own `**bold**`/`[Category]`
syntax as its own markup and corrupt the output.

| Command | Calls | Capability |
|---|---|---|
| `chief app add/list/move` | `services/applications.py` | tracker |
| `chief jd add/show` | `services/jobs.py` | JD extraction |
| `chief feed add/list/poll/summarize` | `services/feeds.py`, `services/summarize.py` | news ingest |
| `chief brief [--send]` | `services/briefing.py`, `notify.py` | the daily briefing |

### Web — `api.py`

A deliberately small FastAPI app — three routes, all synchronous
(`def`, not `async def` — every service call underneath is blocking I/O
already, so FastAPI's own threadpool dispatch is used instead of
introducing `httpx.AsyncClient` anywhere):

```
GET /healthz            -- {"status": "ok"}, no DB access
GET /briefing/today      -- today's cached (or freshly generated) HTML
GET /briefing/{date}     -- a past date's cached HTML, 404 if none exists
```

Bound to `127.0.0.1` only (reached over an SSH tunnel) — public
exposure and TLS are explicitly not done here; see `docs/STATE.md`'s
"Next" section.

---

## Scheduler & ops — `ops/`

- **`run_daily.sh`** — the actual daily pipeline: `chief feed poll
  --all` → `chief feed summarize --limit 25` → `chief brief --send`,
  in sequence. The first two steps are allowed to fail without stopping
  the script (`|| echo ... continuing`) — a summarization hiccup
  shouldn't silently skip the actually-important deadline/focus content
  that `chief brief --send` produces.
- **`chief-brief.service` + `.timer`** — a systemd **user** timer (no
  `sudo` to manage), `OnCalendar` set to 6am in the user's local time
  as a fixed UTC offset (not DST-aware — see `ops/README.md` for the
  twice-yearly manual bump), `Persistent=true` so a missed run fires as
  soon as the box is back rather than waiting a full day.
- **`chief-api.service`** — the long-running counterpart, keeps
  `uvicorn chief.api:app` alive, `Restart=on-failure`.
- Both service files set `Environment="PATH=..."` explicitly, including
  `~/.local/bin` — systemd's default user-session `PATH` doesn't
  include it, and that's where the `claude` binary lives. Without this,
  every real LLM call triggered via systemd fails with "claude not
  found," silently, while cache-hit runs (nothing new to generate)
  succeed and mask the problem. This was a real, live bug found only by
  checking `journalctl` output rather than trusting a green exit code.

**Note on Docker:** a `Dockerfile`/`docker-compose.yml` exist at the
repo root but are intentionally **not** part of the running deployment
and are untracked in git. The `$0` `ClaudeCLIProvider` path depends on
a host-authenticated `claude` CLI session (a real binary plus a live
OAuth token), which a container can't have without either mounting
live credentials into it or switching to the paid API — see
`docs/STATE.md` for the full account.

---

## Testing

`tests/unit/` — no network, no real LLM calls, no filesystem beyond an
in-memory SQLite DB (`tests/conftest.py`'s `session` fixture). Two
conventions repeat throughout:

- **A function that itself calls an LLM** (`jd_to_role`,
  `summarize_item`, `write_focus_line`) is tested directly, against a
  small scripted stub implementing the `LLMProvider` shape, asserting
  on the exact `purpose`/prompt contents passed to `complete()`/
  `structured()`.
- **A service that calls one of those functions** (`ingest_jd`,
  `summarize_pending_items`, `build_briefing_context`) is tested by
  monkeypatching the inner function away entirely with a canned return
  value, plus a `DummyLLM` that's never actually invoked.

`tests/eval/` — the one place real `claude -p` calls happen in tests,
gated behind `-m eval` (excluded from the default `pytest` run). Golden
JD postings with hand-labeled expected extractions, each case run 3
times with a majority-vote pass threshold to smooth real LLM sampling
variance.

---

## What's deliberately not built

Documented here so it doesn't read as an oversight: `POST
/applications`, `POST /jobs/ingest`, `POST /notes`, `GET /costs`
(write-path API endpoints — this project only built the read-only web
view), public exposure + TLS for the web view, an LLM-as-judge eval
harness for summarization quality, `MODEL_FOR_PURPOSE` cheap-model
routing, and `AnthropicAPIProvider`'s cost tracking. Each is a real,
scoped-out decision — see `docs/STATE.md`'s "Next" section for the
reasoning behind each one.
