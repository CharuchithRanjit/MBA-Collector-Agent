# Chief — Continuity Document

**Purpose:** hand this to a fresh Claude session so it can resume with no loss of shared understanding. Written for a reader with zero context.

**Snapshot taken:** mid-review of the first real feature (the application tracker service layer). Roughly hour 3 of a 10-hour build.

**Supersedes:** an earlier, shorter "handover" document produced in this same conversation for use in *parallel* chats. If both exist, this one is authoritative and more complete.

---

# 1. WHAT WE'RE DOING

## The project

**Chief** — a personal AI "chief of staff" for the user's MBA and job-recruiting journey. Single user. Runs on one small AWS EC2 instance. Target cost as close to $0/month as possible.

The user is about to start an MBA and will be recruiting for Product Management / AI Product / tech roles. They want a system they genuinely use every day, not a demo.

## The product thesis (settled, and it does real work)

> **Chief is a read-mostly system that answers one question every morning: what is the single most important thing I should do today for my career, and why?**

Everything else exists to make that answer correct. The tracker exists so the briefing knows deadlines. The job-description extractor exists so the tracker gets populated without typing. If a proposed feature doesn't improve the morning answer or reduce the friction of feeding it, it gets cut.

## The user's role and background

- Software engineer. Strong Python, SQL, data engineering, enterprise generative AI. Comfortable with Docker, APIs, backend systems.
- **Stated goal, in their words: they want to get back into writing code instead of relying entirely on AI.** This is not incidental — it shapes the whole working method (see §4).
- They are using Claude Code inside VS Code, remoted into EC2, and asked to be taught how experienced engineers actually use it.

## The assistant's role

Technical lead and architect. The user explicitly asked to be *challenged*: to have assumptions questioned, features removed, and the highest-value MVP identified. They asked for a Staff-Engineer-grade design document before any code was written, and got one.

The secondary role — arguably the primary one — is **teacher**. The user wants to come out of this a better engineer, not just with a working repo.

---

# 2. WHERE WE ARE

## Environment

| | |
|---|---|
| Host | AWS EC2, Amazon Linux, user `ec2-user` |
| Repo path | `~/projects/MBA_Agent/chief` |
| Editor | VS Code, remote to EC2 |
| Agent | Claude Code v2.1.220, running Sonnet 5, on a Claude Pro subscription |
| Python | **3.12.13**, installed via `uv python install`. The system Python is 3.9 — never use it. |
| Package manager | `uv`, package mode, `src/` layout |
| Git | initialised, committing as we go |

## Three prior artifacts exist

The user has these as separate files. A fresh session won't have their contents unless the user re-attaches them.

1. **`career-agent-design-doc.md`** — the full technical design document. ~18 sections. Architecture, data model, AI-usage framework, roadmap, Claude Code workflow, cost model.
2. **`briefing-spec.md`** — two sample daily briefings (a peak-recruiting-season one and a sparse day-one one), plus a field-source table mapping every line of the briefing to its data source and whether it's deterministic or AI-generated.
3. **`chief-handover.md`** — the earlier, shorter parallel-chat handover. Now superseded by this document.

## Files that exist and are done

```
chief/
├── CLAUDE.md                      ✅ repo root; confirmed loaded via /memory
├── pyproject.toml                 ✅ requires-python >=3.12; [tool.pytest.ini_options] testpaths=["tests"]
├── .python-version                ✅ 3.12
├── .gitignore                     ✅ (should include data/, .env — verify)
├── src/chief/
│   ├── __init__.py                ✅
│   ├── models.py                  ✅ HAND-WRITTEN BY THE USER
│   ├── config.py                  ✅ pydantic-settings, db_path="data/chief.db"
│   ├── db.py                      ✅ reviewed and hardened together
│   ├── cli.py                     ⚠️  exists and works — NEVER REVIEWED (see §7)
│   └── services/
│       ├── __init__.py            ✅
│       └── applications.py        🔨 written, reviewed, 3 fixes pending
├── tests/
│   ├── conftest.py                ✅
│   └── unit/
│       ├── test_models.py         ✅ 2 tests passing
│       └── test_applications.py   ⚠️  written by Claude Code, never inspected
└── data/chief.db                  ✅ exists, contains 1 real application (Stripe APM Intern)
```

**Installed:** fastapi, uvicorn, typer, rich, sqlmodel, httpx, pydantic-settings, structlog, jinja2. Dev: pytest, pytest-cov, ruff, freezegun.

## Contents of the key files

### `models.py` — hand-written by the user, deliberately

- `utcnow()` returns `datetime.now(UTC)`; `as_utc(dt)` re-attaches UTC to a naive datetime. **Rule: all datetimes are timezone-aware UTC in the database.**
- `RoleKind` StrEnum: `intern`, `fulltime`
- `AppStatus` StrEnum: `interested`, `applied`, `oa`, `phone`, `onsite`, `offer`, `rejected`, `withdrawn`
- `Company` — `name` (unique, indexed), `domain`, `tier` (1 = dream, 3 = safety, default 2), `notes`, `created_at`
- `Role` — `company_id` FK, `title`, `kind`, `location`, `jd_url`, **`jd_raw_text`**, `deadline_at` (indexed), `created_at`
- `Application` — `role_id` FK with `unique=True` (one application per role), `status` (indexed), `applied_at`, `next_action`, `next_action_due_at` (indexed), `created_at`
- Relationships: `Company.roles` ↔ `Role.company`; `Role.application` ↔ `Application.role`

### `db.py`

- `make_engine(url, **kwargs)` — a factory, **used by both the application and the tests** so they can't drift apart
- A per-connection `@event.listens_for(engine, "connect")` handler running `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=5000`, `PRAGMA foreign_keys=ON`
- `get_session()` contextmanager: commits on clean exit, rolls back and **re-raises** on exception, uses `expire_on_commit=False`
- `init_db()` — creates the parent directory, then `SQLModel.metadata.create_all`

### `conftest.py`

A `session` fixture giving each test a **fresh in-memory SQLite database**, built through `make_engine` with `poolclass=StaticPool`, then `create_all`, then `yield`, then `engine.dispose()`.

### `services/applications.py` — three functions

`add_application(session, company_name, title, kind, deadline_at=None, tier=2) -> Application`
Looks up the company by name, creates it if absent, `flush()`es to get the primary key, then creates the Role, then the Application. Applies `as_utc()` to the deadline on write.

`list_applications(session, status=None, due_within_days=None) -> list[Application]`
Selects Applications joined to Role, optionally filters by status and by deadline within N days, orders by `Role.deadline_at`.

`move_application(session, application_id, status=None, next_action=None, next_action_due_at=None) -> Application`
Raises `ValueError` on unknown id. Sets `applied_at` on the first transition into `APPLIED`. Updates whichever fields were passed.

## What works end to end right now

```bash
uv run chief app add "Stripe" "APM Intern" intern --deadline 2026-09-15
# → "Added application 1"
```

Note `kind` is a **positional** argument in the current CLI, not an option.

## Not started at all

`llm/` (the provider protocol and both implementations) · `ingest/` (HTTP and RSS) · `rank.py` · `render.py` · `notify.py` · `jobs.py` (scheduler) · `api.py` (FastAPI) · `evals/` · Dockerfile · docker-compose · GitHub Actions.

Tables not yet implemented (deliberately — tables are created when a feature needs them, not upfront): `contact`, `interaction`, `resume`, `gap_analysis`, `feed`, `feed_item`, `document` + `document_fts`, `task`, `briefing`, `llm_call`.

---

# 3. DECISIONS & REASONING

Each of these is closed. Reopening one needs a new argument, not a restatement of the alternative.

### 3.1 Scope was cut from ~60 features to 3

The user's original brief listed roughly sixty features across recruiting, resume, networking, MBA admin, knowledge management, AI research, news, and daily briefing.

**Decision — the one-day MVP is:** (1) application and deadline tracker, (2) job-description ingest with structured extraction, (3) daily briefing pushed to the phone. Plus resume storage and RSS ingest as supporting pieces.

**Rejected:** building broadly and shallowly. A one-day budget with an AI coding agent buys roughly 1,200 lines the user actually understands. Fifteen half-built features is a repo abandoned in week three of an MBA.

**Cut permanently, with reasons:** interview simulation (the user's business school will have mock interviews with humans who actually recruited at these firms; downgraded to "generate 12 likely behavioral questions from this job description") · cover letter generation · salary research (Levels.fyi exists) · company research agent (a browser and a chat model already do this) · reading tracker · learning journal · class notes · assignment tracking (the school has a learning management system) · podcast and video saving · applicant-tracking-system resume scoring (largely folklore) · multi-user · public SaaS version.

**Deferred to a weekend:** resume↔job-description gap analysis with a match score, `chief note` for free-text networking capture, follow-up reminders, continuous integration, TLS deployment.

**Deferred to month one:** the single agent (`chief ask`), full-text search, the evaluation harness, a cost dashboard, Gmail and Calendar read-only ingest, Alembic migrations.

### 3.2 The failure mode is data entry, not engineering

The most load-bearing insight in the whole design.

Personal productivity systems die when the human stops typing into them — never because of the architecture. From this: **every write path must be automatic, a single command, or a single paste. If a feature needs a form, it dies.** Read-only features are structurally more durable than write features. Input must pay back within about sixty seconds.

This is why the job-description extractor is in the MVP at all: it removes the only real typing burden from the tracker.

### 3.3 No multi-agent architecture

The user proposed seven agents: Resume, Recruiting, Research, News, Knowledge, Daily Briefing, Networking.

**Decision:** pipelines of named, typed Python functions. No agent framework.

**Reasoning:** six of the seven are a cron job, a CRUD table, or a pure function wearing a costume. An agent loop is justified when the *sequence of steps is not known in advance*. In all these cases the sequence is known — you can write it down. Multi-agent buys parallelism across independent contexts and failure isolation; neither is a problem here. It costs nondeterminism, 3–10× the tokens, debugging by reading transcripts, and a framework dependency.

**One exception, planned for month one:** `chief ask "which applications have I gone quiet on?"` — here the step sequence genuinely isn't known ahead of time. Roughly eight read-only tools over the user's own database. **To be hand-rolled first (~150 lines: a while-loop and a tool registry), then swapped for the Agent SDK, and compared.** The comparison is the learning artifact; skipping straight to the framework loses the lesson.

### 3.4 AI is permitted in exactly three shapes

- **Shape A — Extraction:** unstructured text → validated Pydantic object. Guardrail: schema validation plus a golden-file eval set.
- **Shape B — Draft:** produce something a human edits before use. Guardrail: **never auto-send.**
- **Shape C — Compression / judgment:** summarize, rank against a rubric. Guardrail: requires an eval harness; no eval, no ship.

Everything else is deterministic. **The test: if you can write the assertion, write the code.**

**Explicit anti-patterns — never use a model for:** date and duration math · deduplication (use a hash) · choosing what to display · generating SQL · anywhere a wrong answer looks identical to a right one.

### 3.5 Ranking is deterministic; the model only writes the sentence

The briefing's "today's focus" is picked by a ~12-line pure scoring function over days-until-due × stage weight × company tier, with an overdue multiplier. The language model's only job is turning the winning item into a nice sentence.

**Rejected:** letting a model choose the priority. If the briefing ever recommends the wrong thing, you can debug a scoring function. You cannot debug a vibe. This is the single most important architectural decision in the product.

There is also a five-rung deterministic fallback ladder for the focus line when nothing is due, ending in: *say nothing and suggest the input that fixes it*. Never let the model invent a motivational task — that is how users learn to ignore a briefing.

### 3.6 Full-text search before vector embeddings

**Decision:** SQLite FTS5 with BM25 first. Add embeddings only when a real evaluation set shows FTS5 losing on specific queries.

**Rejected:** RAG in the MVP. For a personal corpus of a few hundred documents, FTS5 beats a mediocre embedding pipeline, costs nothing, adds no dependencies, and is debuggable at 2am. The sequencing also teaches the more valuable lesson: measure before adding infrastructure.

### 3.7 One service, one SQLite file, three entrypoints

Typer CLI, FastAPI, and APScheduler are all thin shells over `services/`. Not microservices.

For the MVP the scheduler runs **in the same process** as FastAPI, started in the lifespan hook, behind a `RUN_SCHEDULER` environment flag. Splitting later is a docker-compose change with **zero code change**. The principle: *design for the split, don't pay for it until you need it.*

**Banned dependencies, by name, in CLAUDE.md:** LangChain, LlamaIndex, Celery, Redis. Celery and Redis for a daily cron job with one user is complexity theatre.

### 3.8 No `user_id` column anywhere

**Rejected:** designing for multi-tenancy now. It's one Alembic migration plus a query-filter helper later. Paying that tax on every query for a user base of one is a classic premature-generalisation mistake.

### 3.9 Claude Pro does not include API access — the unresolved cost problem

This was the hard constraint the user hadn't accounted for. Their brief said "$0/month" and "I have Claude Pro."

**Facts established by search during the conversation:** the Pro plan does not include API usage through the Console — that is billed separately. Anthropic announced in May 2026 that programmatic usage (Agent SDK, `claude -p`, GitHub Actions, third-party apps) would move to a separate monthly credit pool at API rates, then **paused that change on 15 June 2026**; for now such usage still draws on subscription limits, and Anthropic said it would give notice before anything took effect. Separately, subscription-based authentication is **not permitted** for products built on the Agent SDK and shipped to others — that requires an API key.

**Decision:** write an `LLMProvider` protocol with **two implementations from day one** — a `ClaudeCLIProvider` that shells out to `claude -p` (the $0 path) and an `AnthropicAPIProvider` (the reliable path). Switching is an environment variable. Costs about 40 extra minutes; buys immunity to a pricing change and teaches provider abstraction.

**Not yet built.** This is the next milestone.

### 3.10 Observability is one database table

Every language model call writes a row to `llm_call`: timestamp, purpose, model, prompt version, input and output tokens, cost, latency, success, error. Written from inside the provider wrapper so it is impossible to forget. That single table gives cost tracking, latency tracking, error rates, and per-purpose spend without any monitoring stack.

**Rejected:** any log aggregation or metrics infrastructure. structlog writing JSON to stdout, read via `docker compose logs`, is correct for one user.

### 3.11 Prompts are versioned files, not string literals

`llm/prompts/extract_jd.v1.md`. Every AI-derived database row stores `model` and `prompt_version`. Changing a prompt means a new file, re-running evals, and recording the numbers. **A prompt change with no eval numbers doesn't get merged — including when you're the only reviewer.**

### 3.12 Notifications via ntfy.sh

Free, no account, no SMTP, no API key: `curl -d "text" ntfy.sh/some-unguessable-topic` reaches the phone. Self-hostable later. Telegram is the alternative if interactivity is wanted (replying to the briefing to mark a task done).

**Rejected:** email. Fighting SES or Gmail SMTP for a v1 notification channel is wasted hours.

### 3.13 Don't build Docker images on the EC2 box

A t3.micro will run out of memory on the first package with a compiled wheel. Build in GitHub Actions, push to GitHub Container Registry, `docker compose pull` on the box. The shortcut is also the correct practice — it's a real continuous-deployment pipeline. Add 2GB of swap regardless.

### 3.14 Focus goes at the top of the briefing

The user's original mockup put "Recommended Focus / one high-impact task" **last**, after six other sections. Moved to first. It's read on a phone lock screen at 6am; the thing you must not miss goes in the first forty characters.

---

# 4. THE USER'S PREFERENCES & CONSTRAINTS

## How they work — observed, not stated

**They stop to understand rather than cargo-culting.** Mid-build, before proceeding, they asked "can I know how pytest works before we proceed further." They got an explanation of collection by naming convention, fixtures as dependency injection, `conftest.py` being magic by filename, `yield` as setup/teardown, and why `StaticPool` is needed for in-memory SQLite. **Honour this instinct. When something new appears, offering to explain the mechanism is welcome, not a delay.**

**They push back on vague instructions, twice, and they were right both times.**
- "In step 3 it's not clear at what level CLAUDE.md should be, can you make the steps more clear."
- "Can you explain which files have to change for each and where more clearly."

**Consequence: always give the explicit file path and whether the change is a replacement, an append, or an edit.** Never say "add these imports" without saying which file and whether they may already exist — they caught that ambiguity too ("in file 3, should Company be an import as well").

**They parallelise.** They asked mid-build for a handover document so they could run a second chat for questions while Claude Code worked. Producing portable context artifacts on request is expected.

**They verify.** They ran commands and pasted real output, including screenshots of the terminal, rather than reporting success abstractly.

## Format and tone that has been working

- Numbered steps with time estimates ("5 min", "40 min")
- State restated at the top of a reply ("Step 4 of 5", "hours 0–2 complete")
- Exactly one concrete next action at the end of every message
- Short lists, capped at about five items
- Tables for comparisons and file-change maps
- Explicit "watch for these four things in the diff" before they review Claude Code's output
- Explaining **why**, not just handing over code — this is the whole point of the project for them

## Hard constraints

| | |
|---|---|
| Budget | As close to $0/month as possible. EC2 is the only accepted recurring cost. Realistic estimate: $1–3/month of language model spend on top of EC2. |
| Hardware | Must run comfortably on a small EC2 instance. Estimated footprint ~280MB RAM total. |
| Preference | Docker Compose over managed cloud services. Free APIs. Open source. |
| Stack (their choice, honoured) | Python, uv, FastAPI, Typer, Pydantic, SQLModel, SQLite, Rich, httpx, pytest, Ruff, Docker, Docker Compose, GitHub Actions |
| Timeline | MVP buildable in one day |

## The division of labour — the most important working agreement

Because the user said they want to get back to writing code themselves:

| The user hand-writes | Claude Code writes |
|---|---|
| `models.py` (the schema) | Service implementations |
| `llm/base.py` (the protocol) | CLI and API wiring |
| `rank.py` (the scoring function) | Test bodies, after the user names them |
| Test **names** | Dockerfile, compose, CI configuration |
| Prompts | Templates |
| Every architectural boundary | Everything inside the boundaries |

**The user owns the interfaces; the agent owns the implementations.** Interfaces are about 200 lines total and are where the thinking lives; implementations are 80% of the volume and 20% of the thinking.

**They have honoured this.** They hand-typed `models.py` when told to, and were told explicitly not to delegate it. When a small change was proposed to the CLI signature, they were told to make it themselves rather than delegate. Keep enforcing this.

## The review loop being taught

1. Ask Claude Code to **plan** with no code
2. The user reviews the plan and pushes back on layer violations
3. Ask for **failing tests first**
4. Verify they fail for the *right* reason (an ImportError is not a red test)
5. Implement
6. Read every line — if a function can't be explained after one pass, delete and re-ask with tighter constraints
7. One commit per vertical slice, never per file

The user was also advised to **turn off Claude Code's "accept edits" auto-approve mode** — they had drifted into it. Reasoning: auto-accept is right for a repo you know cold and wrong for one you're building to learn from. *Unconfirmed whether they switched back.*

---

# 5. THINGS LEARNED ABOUT THIS PROBLEM

## Traps already hit — do not re-suggest these

| Trap | Resolution |
|---|---|
| Plain `uv init` produces *application* mode — no `src/`, no `[build-system]`, no console script | Repaired by deleting the generated files and running `uv init --package . --name chief` |
| `uv` selected the system Python 3.9 → `ImportError: cannot import name 'UTC' from 'datetime'` (both `datetime.UTC` and `StrEnum` need 3.11+) | `uv python install 3.12 && uv python pin 3.12`, plus bumping `requires-python` |
| A bare string `"Application \| None"` in a SQLModel `Relationship` | SQLModel can't resolve a union inside a string; use `Optional["Application"]`. **This was the assistant's error, caught by Claude Code.** |
| In-memory SQLite silently losing fixture data between connections | `poolclass=StaticPool` plus `check_same_thread=False`. Without it, each connection gets a different empty database and the failure looks like a bug in the model code. |
| Foreign keys silently unenforced | SQLite defaults foreign-key enforcement **off**, per connection. `PRAGMA foreign_keys=ON` in the connect handler, with a test that proves it. |
| Tests running a different engine configuration from production | A single `make_engine` factory used by both |
| `Session.__exit__` does not commit — silent data loss for any caller who forgets | Explicit commit-on-success / rollback-and-re-raise in `get_session()` |
| `DetachedInstanceError` after commit | `expire_on_commit=False` |
| `OperationalError: unable to open database file` | The `data/` directory didn't exist and nothing ever called `init_db()`. Fixed with `mkdir -p data` plus a Typer `@app.callback()` that calls `init_db()` before every command (idempotent). |
| Typer dumping 200 lines of traceback for a missing directory | `typer.Typer(pretty_exceptions_show_locals=False)` |

## Non-obvious insights that emerged

**In-memory tests have a permanent blind spot.** The missing-`data/`-directory bug could never have been caught by the test suite, because `sqlite://` never touches the filesystem. In-memory tests buy speed and isolation and in exchange cannot see filesystem, permission, or write-ahead-log problems. The mitigation — one integration test using pytest's `tmp_path` fixture — was identified and **deferred to the weekend, not yet written.**

**The assistant makes command-line errors the user then hits.** At least three: a redundant `cd chief` when they were already in the directory, `--kind intern` when Typer had made `kind` positional, and the `Optional` union bug above. **Verify command syntax against what the code actually generates rather than against what was specified.** The user has been gracious about this but it costs them time.

**The user's original feature list contained its own answer.** "Daily Briefing" was presented last, as the culmination. It is actually the correct MVP: it's the only zero-input feature, which makes it the habit loop, which is what keeps the rest alive.

**The AI news digest is the lowest-value and highest-fun feature, and is kept anyway — honestly labelled.** It won't change the user's behaviour; they already read this material and two newsletters cover it better. It's kept for two reasons: it is the best *teaching* vehicle in the project (fetch → dedupe → cache → summarize → rank → render is the canonical pipeline shape and every piece gets reused), and it gives the briefing something to say on days with no tasks, which is what keeps the user opening it. **Don't let it be confused with the product.**

**The recruiting-season time budget inverts normal prioritisation.** October to January the user will have zero free hours. So: build the thing that saves time in the window when you can't build anything. Interview simulators and learning journals are September hobbies that never get opened in November.

---

# 6. WHAT'S NEXT

## Immediate — resume exactly here

We are **mid-review of `services/applications.py`**. The user pasted the file; four issues were identified. Three need fixing, one is a warning about a future landmine. **It is unconfirmed whether any have been applied.** Ask.

**Fix 1 — NULL ordering bug (the real bug).**
`query.order_by(Role.deadline_at)` puts roles with no deadline at the **top**, because SQLite sorts NULL before any value. The most urgent items sink below undated ones — exactly backwards for a tracker.

```python
query = query.order_by(Role.deadline_at.is_(None), Role.deadline_at)
```

`False` sorts before `True`, so real deadlines come first. Portable, unlike `NULLS LAST`. Should be covered by a test that adds a deadline-less role and asserts it lands last.

**Fix 2 — `list_applications` should take `now` as a parameter.**
It currently calls `utcnow()` internally, violating the CLAUDE.md rule that time-dependent functions accept the clock. Add `now: datetime | None = None` and `now = now or utcnow()` so the "due within N days" path is testable without freezegun.

**Fix 3 — `tier` is silently discarded for an existing company.**
`chief app add "Stripe" ... --tier 1` on a company that already exists does nothing, with no error. Recommendation given: **drop `tier` from `add_application` entirely** and add a separate `chief company set-tier` later, because mixing create-if-missing with update-if-present in one function makes services muddy. The user has not yet chosen.

**Warning 4 — the datetime landmine (nothing to fix yet).**
Aware UTC datetimes are written; SQLite stores a string with no timezone; **they read back naive**. Comparisons inside SQL are fine, so nothing breaks today. But the first Python-side arithmetic will raise `TypeError: can't subtract offset-naive and offset-aware datetimes`. `as_utc` exists for exactly this — nothing calls it on the read path yet. **This will bite when `rank.py` is written, around hour 7.** Coerce on read at that point.

## Then

**Review `src/chief/cli.py`.** It has been requested three times and never pasted — not resistance, just conversational flow. Three specific things to check:
1. Does the `--deadline` parser produce a **timezone-aware** UTC datetime, or a naive one?
2. Does business logic sit in the command bodies? CLAUDE.md says commands are ≤5 lines: parse, call service, render.
3. Is the `init_db()` callback in place?

Also never inspected: `tests/unit/test_applications.py`, written by Claude Code. It was supposed to cover: duplicate company reuse, `due_within_days` excluding far-future deadlines, moving to APPLIED setting `applied_at`, and a bad id raising `ValueError`. **Worth checking the tests assert on behaviour rather than on mocks or row counts.**

Then commit the tracker: `git commit -am "feat: application tracker (add/list/move)"`.

## Then — hours 2–6 of the roadmap: the LLM layer

Described as the highest-leverage two hours in the project, because once extraction works, populating the tracker stops being manual work, which is what makes the whole system survivable.

**Ship:** the `LLMProvider` protocol (**hand-written by the user** — it's the architectural keystone), both provider implementations, a `FakeLLM` for tests, `llm_call` logging inside the wrapper, `chief jd add <url>` working end to end, and ten real job descriptions saved as golden files in `evals/`.

The protocol shape already agreed:

```python
class LLMProvider(Protocol):
    def complete(self, *, prompt: str, system: str | None = None,
                 max_tokens: int = 1024) -> LLMResponse: ...
    def structured[T: BaseModel](self, *, prompt: str, schema: type[T],
                                 system: str | None = None) -> T: ...
```

Structured output: prefer tool-use / JSON-schema where supported, otherwise fenced JSON plus `model_validate_json`. **Exactly one retry** on `ValidationError`, feeding the validation error back into the prompt; the second failure raises. Rationale: if it fails twice, the schema is wrong, not the model.

Model routing lives in `config.py` as a `MODEL_FOR_PURPOSE` dictionary — a cheap model for summarization, note extraction, and the focus line (95% of calls); a stronger one for gap analysis and the agent loop. **Do not hardcode model names or prices from memory; check the current pricing page.**

Extraction prompt note already agreed: the deadline field **must be `None` unless explicitly stated in the text** — models love to hallucinate plausible deadlines.

**Then hours 6–10** — RSS ingest with etag caching, `rank.py`, `render.py`, `chief brief`, APScheduler, ntfy push, Dockerfile, compose, deploy.

**The ship criterion for the one-day MVP, and the only one that matters:**
> Tomorrow at 6:05am the user's phone buzzes and they read the briefing before getting out of bed. If that doesn't happen, code quality is irrelevant.

---

# 7. OPEN QUESTIONS

## For the user to decide

1. **Which LLM path?** `claude -p` shelling out at $0 with the stability risk, or an API key at roughly $2/month? Recommendation given: build both, default to `claude -p`, then never think about it again. **Undecided.**
2. **Is the EC2 account still inside the 12-month free tier?** Changes the monthly cost story from about $2 to about $10. **Unanswered.**
3. **Hand-write the ideal briefing.** They were asked twice to spend fifteen minutes writing, by hand in a text file, the briefing they actually want at 6am in October — that artifact is the acceptance test for hours 6–10. **No evidence they've done it.** The `briefing-spec.md` file gives them a starting point to edit. Specific sub-questions posed: does the pipeline-count line earn its space or is it vanity metrics; is four news items right or is two; what's missing that they'd actually check their phone for.
4. **The `tier` decision** in `add_application` (Fix 3 above).
5. **Should `kind` become an option defaulting to `intern`** rather than a third positional argument? Raised on friction grounds — three positionals is a lot at 11pm, and friction on write paths is what kills these systems. They were told to make the change themselves if they want it. **No answer given.**

## For the assistant to resolve

6. **Review `cli.py`.** Never seen. Highest-priority unknown in the codebase.
7. **Review `tests/unit/test_applications.py`.** Never seen.
8. **Confirm whether fixes 1–3 to `applications.py` were applied.**
9. **Confirm whether the user turned auto-accept off in Claude Code.**
10. **Verify `.gitignore` contains `data/` and `.env`.** Advised, never confirmed. The database now contains real application data.
11. **Write the `tmp_path` integration test** covering the filesystem gap that in-memory tests cannot see. Deferred to the weekend.

---

# 8. THINGS I'M UNSURE I'VE CAPTURED CORRECTLY

Flagged honestly, per the request:

- **`cli.py` contents are entirely unknown.** Everything said about it in this document is inferred from a traceback line, a usage string, and Claude Code's own summary. It may contain layer violations or a naive datetime parser. Treat all claims about it as unverified.
- **`config.py` was never read.** It is described from Claude Code's summary only. Assumed to be a trivial pydantic-settings class.
- **Whether the `init_db()` Typer callback and `pretty_exceptions_show_locals=False` were actually added** — both were recommended after the `mkdir -p data` workaround unblocked things, and the user may have simply moved on.
- **The exact contents of `CLAUDE.md` as it now stands.** A specific version was supplied as a shell heredoc and confirmed loaded via `/memory`, but the user may have edited it. Worth a `cat CLAUDE.md` at the start of the next session.
- **Which of the three prior artifacts the user still has to hand.** They were produced as downloadable files in the previous conversation; a fresh session cannot see them.
- **Test count.** Two tests were confirmed passing in `test_models.py`. `test_applications.py` was written by Claude Code and reported as passing, but the output was never shown. Actual current test count is unverified.
- **Whether the earlier `handover.md` was saved into project knowledge**, which would mean two overlapping context documents exist. This one is the more complete of the two.

---

## Suggested first move for the new session

```bash
cat CLAUDE.md
cat src/chief/cli.py
cat tests/unit/test_applications.py
uv run pytest -v
git log --oneline
```

That closes items 6, 7, 8, and most of §8 in one paste.
