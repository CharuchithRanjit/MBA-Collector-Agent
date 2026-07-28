# Chief — Personal MBA Career Agent
## Technical Design Document

**Status:** Proposal, pre-implementation
**Author:** Staff Eng review
**Audience:** You, before you write line one
**Decision required:** Approve scope cuts in §3 before starting

---

## 0. Verdict up front

Build **one Python service, one SQLite file, one CLI, one scheduled job**. No agent framework. No vector DB. No microservices. No LangChain.

The one-day MVP is **three features**, not sixty:

1. **Application + deadline tracker** (zero AI)
2. **Job description ingest → structured extraction** (AI, extraction)
3. **Daily briefing** delivered to your phone at 6am (mostly deterministic, AI only at the last step)

Everything else in your list is a plug-in against the same schema. If those three don't run for 14 consecutive days, the rest is wasted work.

**First action (do this before reading the rest):** open a terminal and run `uv init chief && cd chief && git init`. Two minutes. It makes §15 real instead of theoretical.

---

## 1. Challenging your assumptions

I'm going to push on six things. Four are scope, two are technical and one of them is a hard blocker you haven't accounted for.

### 1.1 Your feature list has ~60 items and a one-day budget

A one-day budget with Claude Code buys roughly **1,200 lines of code you actually understand**, plus tests, plus Docker, plus one deployment. That's three features done well or fifteen done badly. Fifteen done badly is a repo you abandon in week three of your MBA.

I've triaged all 60 in §3. About 40 get cut permanently, not deferred.

### 1.2 The failure mode is data entry, not engineering

Every personal productivity system dies at the same place: **the human stops typing into it.** Not at the architecture. Not at the model quality.

This is the single most important design constraint in the document, and it produces a hard rule:

> **Every write path must be (a) automatic, (b) a single command, or (c) a single paste. If a feature needs a form, it dies.**

Two corollaries:
- **Read-only features are structurally more durable than write features.** The news digest survives your worst week because it requires nothing from you. The "reading tracker" does not.
- **Input must pay back inside 60 seconds.** `chief jd add <url>` pays back immediately (you get a match score). "Log your class notes" pays back in three months, i.e. never.

### 1.3 You will have zero free hours during recruiting season

Full-time MBA + recruiting is a 70-hour week. October to January you will not open the editor. This inverts the usual prioritization: **build the thing that saves you time in the window when you can't build anything.** That's the briefing, the deadline tracker, and the JD gap analysis. Interview simulators and learning journals are hobby features you'll build in September and never open in November.

### 1.4 Claude Pro does not include API access — and the workaround is unstable

This is the blocker. Your constraints say "$0/month" and "I have Claude Pro." Those are in tension.

The facts, as of today:

- <cite index="5-1">The Pro plan does not include API usage through the Claude Console. If you want both the Claude app and the Claude API, you need to set up Console access and pay for API usage separately.</cite>
- Anthropic announced in May 2026 that programmatic usage (Agent SDK, `claude -p`, GitHub Actions, third-party apps) would move to a separate monthly credit pool billed at API rates, then <cite index="20-1">paused the change on June 15 — for now, Agent SDK, `claude -p`, and third-party app usage still draw from your subscription's usage limits, the previously announced monthly credit isn't available, and Anthropic said it will give notice before anything takes effect.</cite>
- Separately, <cite index="27-1">Anthropic does not permit third-party developers to offer claude.ai Pro/Max login or subscription rate limits for products built on the Agent SDK — API-key authentication is required for anything you ship.</cite>

**What this means for you:**

| Path | Cost today | Risk |
|---|---|---|
| Shell out to `claude -p` from your cron job | $0 marginal (draws on Pro limits) | Anthropic tried to change this once and said they'd revisit. Also breaks your future SaaS ambition. |
| Anthropic API key, Haiku-class model | ~$0.50–2/mo at your volume | None. Predictable. |
| Google Gemini free tier | $0 | Free tiers change; rate limits are real |
| Local model on EC2 (Ollama) | $0 | Needs ≥8GB RAM. Your t3.micro cannot. Kills the cost constraint. |

**Recommendation:** Write an `LLMProvider` protocol in hour two with **two implementations from day one** — a `ClaudeCLIProvider` that shells out to `claude -p` (your $0 path) and an `AnthropicAPIProvider` (your reliable path). Swapping is an env var. This costs you 40 extra minutes and buys you immunity to a pricing change and a genuinely valuable engineering habit. Verify current pricing at https://claude.com/pricing before you budget.

Do not build against a single provider's SDK surface. That is the mistake to avoid here, and it's a real one, not a theoretical one.

### 1.5 Semantic search / RAG is premature and you should be able to prove it

You listed RAG and semantic search. For a personal corpus of a few hundred documents, **SQLite FTS5 with BM25 will beat a mediocre embedding pipeline**, costs nothing, adds zero dependencies, is deterministic, and is debuggable at 2am.

The right sequencing is: ship FTS5, build a 30-query eval set from your real searches, and add embeddings **only when you can point at the queries FTS5 loses on.** You will then have (a) justification, (b) a benchmark, and (c) the experience of having measured before adding infrastructure — which is worth more than the RAG implementation itself.

### 1.6 "Interview simulation" is a trap

It's the flashiest feature in your list and you will use it twice. Your MBA program will have mock interview infrastructure with actual humans who actually recruited at the firms you want. Competing with that is a losing bet.

**Downgrade to:** "given this JD and my resume, generate 12 likely behavioral questions and flag which of my stories map to each." That's a 30-line feature, 80% of the value, and it's actually useful the night before an interview.

---

## 2. Product thesis

**Chief is a read-mostly system that answers one question every morning: *what is the single most important thing I should do today for my career, and why?***

Everything else exists to make that answer correct.

That framing does real work:
- The tracker exists so the briefing knows your deadlines.
- The JD extractor exists so the tracker gets populated without typing.
- The contact log exists so "follow up with X" can appear.
- The news digest exists so the briefing is worth opening on a slow day. (Honestly: it's the hook. Read §3.4.)

If a proposed feature doesn't improve the morning answer or reduce the friction of feeding it, cut it.

---

## 3. Scope triage

### 3.1 Build now (the MVP)

| Feature | Why it survives |
|---|---|
| Application tracker (company, role, stage, deadline, next action) | The spine. Everything reads from it. |
| JD ingest → structured extract | Removes the only real data-entry burden |
| Daily briefing → phone push | The habit loop. Zero input required. |
| Resume store (plain markdown, one table) | Prerequisite for gap analysis. Trivial. |
| RSS feed ingest + summarize | Zero-input content for the briefing |

### 3.2 Build on the weekend

| Feature | Why |
|---|---|
| Resume ↔ JD gap analysis + match score | Highest-value AI feature in the whole list |
| `chief note "..."` → structured contact interaction | Networking is where MBA ROI actually lives; this is the only low-friction way to capture it |
| Follow-up reminders | Falls out of the above for free |
| CI + TLS deploy | Engineering practice you asked to learn |

### 3.3 Build in month one

Single agent over your own data (§5.3) · FTS5 search · eval harness · cost dashboard · Gmail/Calendar read-only ingest · Alembic migrations.

### 3.4 Keep but demote: AI research / news tracking

Honest assessment: **this will not change your behavior.** You already read this stuff. Two newsletters cover it better.

Keep it anyway, for two reasons that are worth being explicit about:
1. It is the best *teaching* vehicle in the project — fetch → dedupe → cache → summarize → rank → render is the canonical AI pipeline shape and you'll reuse every piece.
2. It gives the briefing something to say on days when you have no tasks, which is what keeps you opening it.

Just don't confuse it with the product.

### 3.5 Cut permanently

Interview simulation (→ downgrade per §1.6) · cover letter generation (they're dying; and you should write these yourself) · salary research (Levels.fyi exists) · company research agent (you have Claude in a browser) · reading tracker · learning journal · class notes · assignment tracking (your school has an LMS) · podcast/YouTube saving · club events · resume ATS scoring (mostly folklore; the keyword analysis in gap analysis covers the real signal) · multi-user · public SaaS.

That's ~35 features removed. Each one you keep is a table, a CLI verb, tests, and a lifetime maintenance cost.

---

## 4. Where AI belongs — the three shapes

You asked for a per-feature justification. Rather than 60 ad-hoc answers, here's the rule I'd actually apply, then the table.

**AI earns its place in exactly three shapes:**

| Shape | Definition | Why deterministic code loses | Guardrail |
|---|---|---|---|
| **A — Extraction** | Unstructured text → typed object | Parsing JDs/emails/free-text with regex is an infinite swamp; the input space is adversarial | Pydantic schema validates every output; golden-file eval set |
| **B — Draft** | Produce something a human edits before use | Blank page cost is real; correctness is human-verified downstream | **Never auto-send.** Output goes to a file or a screen, never to a person |
| **C — Compression / judgment** | Summarize, rank against a rubric, compare | 30 articles → 5 sentences has no deterministic equivalent | Requires an eval harness. No eval, no ship. |

**Everything else is deterministic. The test is simple:**

> **If you can write the assertion, write the code.**

`days_until_deadline < 7` is an assertion. Don't ask a model.

### 4.1 Anti-patterns — where AI actively hurts here

1. **Date and duration math.** Models get "third Tuesday after the 15th" wrong silently. Pure Python, always.
2. **Choosing what to show you.** Rank deterministically on known fields. Let the model *phrase* the recommendation, not *pick* it. (§7.2 — this is the important one.)
3. **As a query layer.** Do not let a model write SQL against your DB in v1. Named queries, typed params.
4. **Deduplication.** GUID + normalized-title hash. A model will merge two genuinely different articles and you'll never notice.
5. **Anywhere failure is silent.** If a wrong answer looks exactly like a right answer, you need deterministic code or an eval, not vibes.

### 4.2 Feature-by-feature

| Feature | AI? | Shape | Reasoning |
|---|---|---|---|
| Store application / status / dates | **No** | — | CRUD. A model here is pure downside. |
| Deadline reminders | **No** | — | Date math + scheduler. |
| Parse JD from pasted text/URL | **Yes** | A | Every job board has a different DOM and prose style. |
| Fetch JD HTML | No | — | httpx + trafilatura. |
| Dedupe feed items | **No** | — | Hash. See anti-pattern 4. |
| Summarize an article | **Yes** | C | No deterministic equivalent. |
| Rank the briefing items | **No** | — | Weighted function of due date, stage, tier. Unit-testable. |
| Write the "recommended focus" line | **Yes** | B | One sentence, human reads it, low stakes, high polish value. |
| Resume storage / versioning | **No** | — | Text in a table. |
| Resume ↔ JD gap analysis | **Yes** | A + C | Genuine judgment: which of my bullets addresses which requirement. |
| Match score (the number) | **Partly** | C | Model extracts covered/missing requirements; **Python computes the score.** Never let the model output the number directly — it's uncalibrated and you can't test it. |
| Bullet rewrite suggestions | **Yes** | B | Draft you edit. |
| Free-text note → structured interaction | **Yes** | A | The whole point is that you type one sentence. |
| Follow-up due date from that note | **No** | — | Rule: default +14 days, override if the model extracted an explicit date. |
| Search my saved docs | **No** (v1) | — | FTS5. §1.5. |
| Chat over my career data | **Yes** | Agent | §5.3. The one legitimate agent. |

---

## 5. Agent architecture

### 5.1 You do not need multiple agents

You listed seven candidate agents. Let's be precise about what each one actually is:

| Proposed "agent" | What it actually is |
|---|---|
| News Agent | A cron job, an HTTP client, and a summarize prompt |
| Research Agent | Same cron job with different feed URLs |
| Resume Agent | One function: `(resume, jd) -> GapAnalysis` |
| Recruiting Agent | A CRUD table |
| Networking Agent | The same CRUD table with a different noun |
| Daily Briefing Agent | A SQL query, a ranking function, and a template |
| Knowledge Agent | An FTS5 index |

**Zero of these need an agent loop.** An agent loop — model decides which tool to call, observes the result, decides again — is justified when the sequence of steps is *not known in advance*. In all seven cases you know the sequence. You wrote it down.

Multi-agent architectures buy you: parallelism across independent contexts, and isolation of failure. You have neither problem. What they cost you: nondeterminism, 3–10× token spend, debugging by reading transcripts, and an entire framework dependency.

**Verdict: pipelines, not agents.** Named Python functions in a DAG you can read. This is not a lesser architecture; it is the correct one, and being able to argue this in a PM interview is worth more than having built the multi-agent version.

### 5.2 What to build instead

```
ingest/     pure I/O          fetch_feeds(), fetch_jd(url)
extract/    Shape A           jd_to_role(text) -> Role
                              note_to_interaction(text) -> Interaction
analyze/    Shape C           summarize(text) -> str
                              gap_analysis(resume, role) -> GapAnalysis
rank/       deterministic     score_task(task, now) -> float
render/     deterministic     briefing_markdown(ctx) -> str
                              + one Shape B call for the focus line
```

Every arrow is a typed function. Every function is independently testable. There is no orchestrator because `briefing.py` **is** the orchestrator, and it's 40 lines you can read in one screen.

### 5.3 The one agent that is justified

`chief ask "which of my applications have I gone quiet on?"`

Here the step sequence genuinely isn't known ahead of time — the model must decide whether to query applications, interactions, or both, and how to filter. That's a real agent loop with ~8 read-only tools over your own database.

Two recommendations:
1. **Build it by hand first** — a while-loop, a tool registry, `tool_use` blocks, ~150 lines. Do this over one afternoon in month one. You will learn more from that afternoon than from six months of framework usage, and you'll understand exactly what the Agent SDK is doing for you.
2. **Then** swap in the Agent SDK behind the same interface and compare. That comparison is the actual learning artifact.
3. **All tools read-only in v1.** No write tools until you have a confirmation layer. An agent that can modify your application deadlines is a liability.

---

## 6. System architecture

### 6.1 Diagram

```
                    ┌─────────────────────────────┐
   phone (ntfy) ◄───┤                             │
   browser      ◄───┤   FastAPI  (uvicorn)        │
   terminal     ◄───┤   Typer CLI  (`chief`)      │
                    │   APScheduler                │
                    └──────────┬──────────────────┘
                               │  imports
                    ┌──────────▼──────────────────┐
                    │   chief/services/           │  ← all business logic
                    │   pure functions, no I/O     │     lives here
                    └──────────┬──────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
     ┌────────────────┐ ┌────────────┐ ┌──────────────┐
     │ SQLite (WAL)   │ │ llm/       │ │ ingest/      │
     │ ./data/chief.db│ │ Provider   │ │ httpx +      │
     │ + FTS5         │ │ protocol   │ │ feedparser   │
     └────────────────┘ └─────┬──────┘ └──────────────┘
                              │
                   ┌──────────┴──────────┐
                   ▼                     ▼
            ClaudeCLIProvider    AnthropicAPIProvider
            (`claude -p`, $0)    (API key, reliable)
```

**Three entrypoints, one codebase, one database.** The CLI and the API are thin shells over `services/`. This matters: it means every feature is usable from the terminal on day one without building UI, and gets an HTTP endpoint for free when you want a phone-friendly view.

### 6.2 Why one container (for now)

MVP runs FastAPI + APScheduler in **one process**, scheduler started in the FastAPI lifespan behind a `RUN_SCHEDULER=true` env flag.

Why not split immediately: on a 1GB box a second Python process is ~90MB you don't need to spend yet, and it's a one-day MVP.

Why the flag: splitting later becomes a `docker-compose.yml` change with **zero code change** — same image, second service, `RUN_SCHEDULER=true` on one and `false` on the other. This is the pattern worth internalizing: *design for the split, don't pay for it until you need it.*

**SQLite with two processes is fine** — but you must set both, or you'll get intermittent `database is locked` at 6am and lose an hour:
```python
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;
```

### 6.3 Folder structure

```
chief/
├── pyproject.toml            # uv, ruff, pytest config — one file
├── docker-compose.yml
├── Dockerfile
├── CLAUDE.md                 # ← §16.1. Most important file in the repo.
├── .env.example
├── src/chief/
│   ├── config.py             # pydantic-settings, one Settings object
│   ├── db.py                 # engine, session, pragmas
│   ├── models.py             # ALL SQLModel tables. You write this by hand.
│   ├── schemas.py            # Pydantic I/O models (≠ tables)
│   ├── llm/
│   │   ├── base.py           # Protocol. You write this by hand.
│   │   ├── claude_cli.py
│   │   ├── anthropic_api.py
│   │   ├── fake.py           # ← for tests. Non-negotiable.
│   │   └── prompts/
│   │       ├── extract_jd.v1.md
│   │       ├── summarize.v1.md
│   │       └── focus_line.v1.md
│   ├── services/
│   │   ├── applications.py
│   │   ├── jobs.py           # JD ingest + extraction
│   │   ├── resume.py
│   │   ├── contacts.py
│   │   ├── feeds.py
│   │   └── briefing.py       # the orchestrator
│   ├── ingest/
│   │   ├── http.py
│   │   └── rss.py
│   ├── rank.py               # pure. heavily unit-tested.
│   ├── render.py             # jinja2 templates → markdown/html
│   ├── notify.py             # ntfy.sh
│   ├── jobs.py               # APScheduler registrations
│   ├── cli.py                # Typer
│   └── api.py                # FastAPI
├── tests/
│   ├── conftest.py           # in-memory DB fixture, FakeLLM fixture, frozen clock
│   ├── unit/
│   └── integration/
├── evals/
│   ├── golden/jd/*.json      # 15 real JDs + expected extractions
│   ├── golden/notes/*.json
│   └── test_evals.py         # pytest -m eval
└── .github/workflows/ci.yml
```

**Rules that keep this from rotting:**
- `services/` never imports `cli.py` or `api.py`. Enforce with a ruff import-linter rule.
- `rank.py` and `render.py` do no I/O and take `now` as a parameter. This is why they're testable.
- Prompts are **files, not string literals**, and the filename carries the version.

---

## 7. Data model

### 7.1 Tables

```python
# Identity / opportunity
company(id, name, domain, tier: int, notes)
role(id, company_id, title, kind: Enum[INTERN, FULLTIME],
     location, jd_url, jd_raw_text, deadline_at, source, created_at)
application(id, role_id, status: Enum[INTERESTED, APPLIED, OA, PHONE,
            ONSITE, OFFER, REJECTED, WITHDRAWN],
            applied_at, next_action, next_action_due_at, priority_override)

# Networking
contact(id, name, company_id, title, linkedin_url, how_met, created_at)
interaction(id, contact_id, occurred_at, channel, notes_raw,
            notes_summary, follow_up_due_at, created_at)

# Resume
resume(id, label, content_md, is_default, created_at)
gap_analysis(id, resume_id, role_id, match_score, covered json,
             missing json, suggestions json,
             model, prompt_version, created_at)

# Knowledge / news
feed(id, url, name, category, etag, last_modified, last_fetched_at)
feed_item(id, feed_id, guid UNIQUE, url, title, published_at,
          raw_text, summary, importance, model, prompt_version)
document(id, kind, url, title, raw_text, summary, created_at)
document_fts   -- FTS5 virtual table over document(title, raw_text, summary)

# Cross-cutting
task(id, title, due_at, source_type, source_id, done_at, created_at)
briefing(id, for_date UNIQUE, markdown, generated_at, cost_cents)
llm_call(id, ts, purpose, model, prompt_version, input_tokens,
         output_tokens, cost_cents, latency_ms, ok, error)
```

### 7.2 The five decisions that matter

**1. Always store `raw_text` next to derived fields.**
Derived data is disposable. Source text is not. When you improve the extraction prompt in month two, you re-run over stored raw text instead of re-crawling job boards that have since deleted the posting. This single decision saves the project.

**2. Every AI-derived row carries `model` + `prompt_version`.**
Non-negotiable. Without it you cannot answer "did quality regress when I changed the prompt?" — and answering that question is the entire skill of evaluation.

**3. `llm_call` is your whole observability story in one table.**
Cost, latency, error rate, per-purpose token spend. `SELECT purpose, SUM(cost_cents) FROM llm_call WHERE ts > date('now','-30 day') GROUP BY 1` is your cost dashboard. Write to it from inside the provider wrapper so it's impossible to forget.

**4. Unified `task` table with a polymorphic source.**
Deadlines, follow-ups, and manual todos all become tasks. The briefing then reads *one* table instead of UNION-ing four. Denormalized on purpose — the write path is a trigger-equivalent in `services/`, not a DB trigger.

**5. Ranking is a pure function, and the model never sees the ranking decision.**

```python
def score(task: Task, now: datetime) -> float:
    urgency = 1 / max(days_until(task.due_at, now), 0.5)
    stage   = STAGE_WEIGHTS[task.stage]      # ONSITE=5, APPLIED=2, ...
    tier    = task.company_tier              # 1..3
    overdue = 3.0 if task.due_at < now else 1.0
    return urgency * stage * tier * overdue
```

Twelve lines. Fully unit-testable with a frozen clock. The model's only job is turning `top_task` into a nice sentence. **If the briefing ever recommends something wrong, you can debug it** — which you cannot do if a model picked it.

**No `user_id` anywhere.** Adding multi-tenancy later is one Alembic migration and a query-filter helper. Adding it now is a tax you pay on every query for a user base of one. Premature multi-tenancy is a classic mistake; don't make it.

---

## 8. Interfaces

### 8.1 CLI (primary — build this first)

```bash
chief app add "Stripe" "APM Intern" --deadline 2026-09-15
chief app list --status applied --due-within 7
chief app move 12 --status onsite --next "send thank-you" --due tomorrow

chief jd add https://boards.greenhouse.io/...   # fetch → extract → create role
chief jd add --paste                            # stdin, for LinkedIn etc.

chief resume add ~/resume.md --label pm-v3 --default
chief gap 12                                    # resume ↔ role 12

chief note "coffee w/ Priya Nair, PM at Figma, met at AI club, \
            wants me to ping her after their Q3 launch"

chief brief                    # print today's briefing
chief brief --send             # + push to phone
chief ask "who have I not followed up with?"     # month one

chief costs --days 30
```

Typer + Rich. The CLI is not a stepping stone to a "real" UI — for a single user on a laptop it *is* the right interface, and it's the reason you can ship in a day.

### 8.2 HTTP (thin)

```
GET  /healthz
GET  /briefing/today          # HTML, phone-readable
GET  /briefing/{date}
GET  /applications?status=&due_within=
POST /applications
POST /jobs/ingest             # {url} or {text}
POST /notes                   # {text} → structured interaction
GET  /costs
```

Everything under a single API-key header from `.env`. No user auth in v1 — that's what a bearer token and a security group are for.

**Design rule:** route handlers are ≤5 lines. Parse, call service, return. All logic in `services/`. Claude Code will try to put business logic in handlers; reject it every time.

---

## 9. The LLM layer

### 9.1 The protocol (write this yourself — it's the architectural keystone)

```python
class LLMProvider(Protocol):
    def complete(self, *, prompt: str, system: str | None = None,
                 max_tokens: int = 1024) -> LLMResponse: ...

    def structured[T: BaseModel](self, *, prompt: str, schema: type[T],
                                 system: str | None = None) -> T: ...
```

`LLMResponse` carries text plus token counts plus latency. The wrapper that implements this writes an `llm_call` row on every invocation, success or failure. That's how observability becomes free instead of aspirational.

### 9.2 Structured output

Don't parse prose. Two viable approaches:

1. **Tool-use / JSON schema** — pass the Pydantic schema as a tool definition, model returns validated JSON. Preferred where supported.
2. **Prompt + fenced JSON + `model_validate_json`** — works everywhere, needs a retry.

Either way: **one retry on `ValidationError`, feeding the validation error back into the prompt.** Second failure raises. Do not retry three times; if it fails twice your schema is wrong, not the model.

```python
try:
    return schema.model_validate_json(raw)
except ValidationError as e:
    raw = self.complete(prompt=f"{prompt}\n\nYour output failed validation:\n{e}\nReturn only valid JSON.")
    return schema.model_validate_json(raw)   # let this one raise
```

### 9.3 Model routing

Cheap model (Haiku-class) for: summarization, note extraction, focus-line generation. This is 95% of your calls.
Expensive model (Sonnet-class) for: gap analysis, the agent loop. Maybe 5 calls a week.

Put the mapping in `config.py` as `MODEL_FOR_PURPOSE: dict[str, str]`, not scattered through the code. Check current model names and prices at https://claude.com/pricing — don't hardcode from memory.

### 9.4 FakeLLM

`llm/fake.py` returns canned Pydantic objects keyed by purpose. **95% of your test suite must never touch the network.** This is *the* testing lesson for AI systems and the thing most tutorials skip. Tests that call real models are slow, flaky, expensive, and give you no signal about your own code.

---

## 10. Background jobs

| Job | Schedule | Idempotency key | Notes |
|---|---|---|---|
| `fetch_feeds` | 05:00 daily | `feed_item.guid` UNIQUE | Send `If-None-Match` from stored etag |
| `summarize_new_items` | 05:15 | `feed_item.summary IS NULL` | Batch, cap at 25/day for cost |
| `generate_briefing` | 06:00 | `briefing.for_date` UNIQUE | Regenerating is safe |
| `push_briefing` | 06:05 | — | ntfy.sh |
| `prune` | Sunday 03:00 | — | Null out `feed_item.raw_text` older than 90d, keep summaries |

**Every job must be safely re-runnable.** Your EC2 box will restart, your job will crash mid-way, and you will run things manually to debug. `chief jobs run generate_briefing` should always be safe. Design for that from the start — retrofitting idempotency is miserable.

APScheduler with `misfire_grace_time=3600` so a reboot at 05:55 doesn't silently skip your briefing.

### Notifications: ntfy.sh

Free, no account, no SMTP, no API key. `curl -d "text" ntfy.sh/your-random-topic` and it hits your phone. Pick an unguessable topic name. Self-hostable later if you care. This is strictly better than fighting with SES or Gmail SMTP for v1.

Telegram bot is the good alternative if you want interactivity (reply to the briefing to mark a task done — nice month-two feature).

---

## 11. Docker, deployment, ops

### 11.1 Dockerfile

Multi-stage, `uv` for install, non-root user, `python:3.12-slim` base. Target: **under 250MB.**

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src/ ./src/
RUN uv sync --frozen --no-dev

FROM python:3.12-slim
RUN useradd -m app
COPY --from=builder --chown=app:app /app /app
USER app
ENV PATH="/app/.venv/bin:$PATH"
HEALTHCHECK CMD ["python","-c","import httpx;httpx.get('http://localhost:8000/healthz').raise_for_status()"]
CMD ["uvicorn","chief.api:app","--host","0.0.0.0","--port","8000"]
```

### 11.2 compose

```yaml
services:
  app:
    image: ghcr.io/you/chief:latest
    env_file: .env
    environment: { RUN_SCHEDULER: "true" }
    volumes: [ "./data:/data" ]
    ports: [ "127.0.0.1:8000:8000" ]
    restart: unless-stopped
```

Bind to `127.0.0.1` and reach it over an SSH tunnel. Add Caddy for TLS on the weekend when you want the briefing on your phone browser; Caddy does Let's Encrypt with two lines of config and zero cost.

### 11.3 Build where you have RAM

**Do not `docker build` on a t3.micro.** You'll OOM on the first package with a compiled wheel. Build in GitHub Actions, push to GHCR (free for public repos, and free for private within the Actions storage allowance), then `docker compose pull && up -d` on EC2. This is also how you learn a real CD pipeline, so the "shortcut" is actually the correct practice.

Add **2GB of swap** on the instance regardless. Five minutes, saves you an evening.

### 11.4 Backups

Your SQLite file is your entire product.

```bash
sqlite3 /data/chief.db ".backup /data/backup-$(date +%F).db"
```

Nightly, keep 7, and rclone one weekly copy off-box (or just `scp` to your laptop). `.backup` is the correct command — copying the file while WAL is active can give you a corrupt snapshot. Test the restore once, now, not after you need it.

### 11.5 Logging & config

- **structlog**, JSON to stdout, `docker compose logs`. Do not build a log aggregation stack for one user.
- Every LLM call logs `purpose`, `model`, `prompt_version`, `tokens`, `cost`, `latency`.
- Bind a `request_id` / `job_run_id` into the context so one briefing's whole trace is greppable.
- **pydantic-settings**, one `Settings` object, `.env` for local + `.env` on the box (chmod 600). Never commit it; commit `.env.example`.
- Secrets: `.env` file + git-secrets pre-commit hook. AWS Secrets Manager for a single-user app is cost and complexity theatre.

---

## 12. Testing & evaluation

This is the part most people skip, and it's the part that separates "I built an AI app" from "I can build AI systems."

### 12.1 The test pyramid for AI systems

| Layer | Count | Speed | Touches a model? |
|---|---|---|---|
| Unit (rank, render, date logic, services w/ FakeLLM) | ~80 | <2s total | No |
| Integration (CLI → in-memory DB → FakeLLM) | ~15 | <10s | No |
| Contract (provider returns parseable shape) | ~3 | ~5s | Yes, `-m live` |
| Eval (golden files, quality) | ~30 cases | ~60s | Yes, `-m eval` |

CI runs the first two. Evals run locally, on demand, gated by a marker. That keeps CI free and fast.

### 12.2 Eval harness — concretely

**Extraction (Shape A) — objective, so measure it objectively.**
15 real JDs you've saved, each with a hand-written expected JSON. Score field-by-field exact match; strings normalized. Report per-field accuracy, not a single number — you want to see that `deadline_at` is at 60% while `title` is at 100%, because that tells you what to fix.

```
$ pytest -m eval -k jd
extract_jd.v3  n=15
  company     15/15   100%
  title       15/15   100%
  kind        14/15    93%
  deadline_at  9/15    60%   ← fix this
  skills      avg F1 0.81
```

**Summarization (Shape C) — subjective, so calibrate your judge.**
LLM-as-judge with a fixed 3-criterion rubric (faithful / complete / concise, 1–5 each). But: **hand-label 20 examples yourself first**, then check your judge agrees with you. An uncalibrated judge is a random number generator with good grammar. If judge-human agreement is below ~80%, fix the rubric before trusting any number it produces.

**Ranking — snapshot test with a frozen clock.**
Fixture DB, `freezegun` to a fixed instant, assert the top-3 task IDs. Deterministic, instant, catches every regression in the logic that actually drives the product.

### 12.3 Prompt versioning as a workflow

1. Prompts are files: `prompts/extract_jd.v3.md`.
2. `prompt_version` written to every derived row.
3. Changing a prompt = new file + rerun evals + record the numbers in the PR description.
4. A prompt change with no eval numbers doesn't get merged — including when you're the only reviewer. **Especially** then.

This four-step loop is, in practice, the entire discipline of production prompt engineering.

---

## 13. Roadmap

### Hours 0–2: skeleton and spine (zero AI)

**Ship:** `uv` project, `models.py`, SQLite with pragmas, `chief app add/list/move`, 10 passing tests, first commit.

**Learn:** uv workflow, SQLModel, Typer, session management, pytest fixtures with in-memory SQLite, the service/interface boundary.

**Why first:** the schema is the most expensive thing to change later, and you need a working spine before AI has anything to attach to. Also — starting with the boring part is how you verify your tooling works before adding nondeterminism.

**Done when:** `chief app list` shows a real application you actually care about.

---

### Hours 2–6: the LLM layer and your first AI feature

**Ship:** `LLMProvider` protocol, both providers, `FakeLLM`, `llm_call` logging, `chief jd add <url>` end to end, 10 golden JDs in `evals/`.

**Learn:** structured outputs, Pydantic validation as a guardrail, retry-on-validation-error, prompt files + versioning, provider abstraction, mocking LLMs in tests.

**Why now:** this is the highest-leverage two hours in the project. Once extraction works, populating the tracker stops being work, which is what makes the whole system survivable.

**Done when:** you paste a real job URL and a correctly-populated row appears.

---

### Hours 6–10: the one-day MVP — the briefing

**Ship:** RSS ingest with etag caching, summarization job, `rank.py`, `render.py`, `chief brief`, `GET /briefing/today`, APScheduler, ntfy push, Dockerfile, compose, deployed on EC2.

**Learn:** scheduling, idempotency, HTTP conditional requests, templating, containerization, deploying a real service.

**Ship criterion — and this is the only one that matters:**
> **Tomorrow at 6:05am your phone buzzes and you read the briefing before getting out of bed.**

If that doesn't happen, the code quality is irrelevant. Everything after this milestone is optional; everything before it is not.

---

### Weekend (8–12 more hours)

**Ship:** resume storage, `chief gap <role_id>` with match score, `chief note` → structured interaction, follow-up reminders wired into the briefing, GitHub Actions CI (ruff + pytest), Caddy + TLS, structlog.

**Learn:** multi-step AI pipelines, extraction on messy human input, CI/CD, reverse proxies, structured logging.

**Why now:** you've proven the habit sticks. Now make it good. The gap analysis is the feature you'll use most during actual recruiting.

---

### Month one (weekends, 4–6h each)

| Weekend | Ship | Learn |
|---|---|---|
| 1 | Hand-rolled agent loop + 8 read-only tools + `chief ask` | Tool calling from first principles, agent loop mechanics, context management |
| 2 | Swap in Agent SDK behind the same interface; compare cost, latency, quality | What frameworks buy you and what they cost |
| 3 | Eval harness proper: judge calibration, per-prompt reports, cost dashboard | Evaluation as an engineering discipline |
| 4 | FTS5 search + Gmail/Calendar read-only ingest + Alembic | Search, OAuth, schema migrations |

---

## 14. Claude Code workflow

You said this is the most important part. Here's how I'd actually run it.

### 14.1 CLAUDE.md is the highest-leverage file in the repo

Keep it under 200 lines. It should contain:

```markdown
# Chief
Personal career agent. Single user. Runs on one small EC2 box.

## Stack
Python 3.12, uv, FastAPI, Typer, SQLModel, SQLite, pytest, ruff, Docker.

## Rules
- Business logic lives in src/chief/services/. Route handlers and CLI
  commands are ≤5 lines: parse, call service, return.
- rank.py and render.py do no I/O and take `now: datetime` as a parameter.
- All datetimes are timezone-aware UTC in the DB. Convert at the edges only.
- Never call an LLM provider directly. Go through llm.base.LLMProvider.
- Prompts are files in llm/prompts/, versioned in the filename.
- No new dependencies without asking. Especially no LangChain,
  no LlamaIndex, no Celery, no Redis.
- Never write `except Exception: pass`.
- Every new service function gets a unit test using FakeLLM.

## Commands
uv run pytest            # tests
uv run ruff check --fix  # lint
uv run chief --help      # CLI
```

That "no new dependencies" line will save you more grief than anything else in the file.

### 14.2 The division of labour

| You write by hand | Claude writes |
|---|---|
| `models.py` (the schema) | Service implementations |
| `llm/base.py` (the protocol) | CLI command wiring |
| `rank.py` scoring function | Test bodies (after you name them) |
| Test **names** | Dockerfile, compose, CI yaml |
| Prompts | Jinja templates |
| Every architectural boundary | Everything inside the boundaries |

The rule behind it: **you own the interfaces, Claude owns the implementations.** You said you want to get back into writing code rather than relying entirely on AI. This is how. The interfaces are where the thinking lives and they're only ~200 lines total; implementations are 80% of the volume and 20% of the thinking.

### 14.3 The loop for every milestone

```
1. PLAN     "Read CLAUDE.md and src/chief/models.py. I want to add
             JD ingestion. Don't write code. Propose module boundaries
             and function signatures. List what you'd put in services/
             vs ingest/ vs extract/."

2. REVIEW    You read the plan. Push back on anything that puts logic
             in the wrong layer. This is the step people skip and it's
             where 90% of the value is.

3. TEST      "Write the failing tests for jobs.ingest_jd. Use FakeLLM.
             Don't implement the function yet."

4. VERIFY    Run them. Confirm they fail for the RIGHT reason.
             (A test that fails on ImportError is not a red test.)

5. IMPLEMENT "Now implement jobs.ingest_jd to pass these tests."

6. READ      Read every line. If you can't explain a function after
             one pass, delete it and re-ask with tighter constraints.

7. COMMIT    One commit per vertical slice. Never per file.
```

Step 4 is the one to be disciplined about. Claude will happily write a test that passes against a mock while the real code is broken.

### 14.4 Prompts that work, by milestone

**Hour 0:**
> "Set up a uv project named `chief`. Python 3.12. Dependencies: fastapi, uvicorn, typer, rich, sqlmodel, httpx, pydantic-settings, structlog, jinja2. Dev: pytest, pytest-cov, ruff, freezegun. Configure ruff and pytest in pyproject.toml. Create the folder structure I'm pasting below. No code in the modules yet, just `__init__.py` files and docstrings."

**Hour 1:**
> "Here's my `models.py` [paste]. Write `db.py`: engine with WAL and busy_timeout=5000, a `get_session` context manager, and `init_db()`. Then `conftest.py` with an in-memory SQLite fixture that creates all tables per test."

**Hour 2:**
> "Here's `llm/base.py` [paste the protocol]. Implement `AnthropicAPIProvider`. Requirements: uses the Anthropic Python SDK, `structured()` uses tool-use to get schema-validated JSON, retries exactly once on ValidationError by feeding the error back, and writes an `llm_call` row on every call including failures. Do not add caching or streaming."

**Hour 3 (extraction):**
> "Write `extract/jd.py`. One function: `jd_to_role(text: str, llm: LLMProvider) -> RoleExtraction`. `RoleExtraction` is a Pydantic model with company, title, kind, location, deadline (date|None), required_skills (list[str]), preferred_skills. The prompt lives in `llm/prompts/extract_jd.v1.md` — write that file too. Deadline must be None unless explicitly stated in the text; never infer it."

That last sentence is important. Models love to hallucinate plausible deadlines.

**Hour 6 (ranking — do this one yourself, then):**
> "Here's `rank.py` [paste]. Write exhaustive unit tests using freezegun. Cover: overdue tasks outrank due-today, tier-1 company outranks tier-3 at equal urgency, a task due in 6 months has near-zero score, and division-by-zero when due_at == now."

**Refactoring:**
> "`services/briefing.py` is 180 lines and does four things. Don't change behaviour. Propose a split into smaller functions, tell me which existing tests protect each one, and identify anything currently untested. Then wait for my approval."

### 14.5 Mistakes Claude Code will make on this specific project

Watch for these in review — they're the ones I'd expect:

1. **Naive datetimes.** `datetime.now()` instead of `datetime.now(UTC)`. This will silently corrupt every deadline calculation. Catch it in review; a linter rule helps.
2. **Business logic in route handlers.** It'll write a 40-line FastAPI endpoint. Reject, move to `services/`.
3. **Tests that assert on the mock.** `assert fake_llm.called` is not a test. Assert on the database state or the returned object.
4. **`except Exception: pass` around the LLM call.** You'll have a briefing that silently omits news for three weeks before you notice.
5. **Uninvited dependencies.** LangChain will appear if you let it. So will Celery and Redis, for a cron job with one user.
6. **Over-abstraction.** An abstract base class with exactly one subclass. Two is the threshold; one is speculation.
7. **Blocking I/O in async routes.** `httpx.get()` (sync) inside `async def`. Either go all-sync or use `httpx.AsyncClient`.
8. **SQLAlchemy relationship config that doesn't exist.** SQLModel's relationship API is a common hallucination target. Verify against the docs, not against confidence.

### 14.6 Git

Branch per milestone (`feat/jd-ingest`), conventional commits, squash merge to `main`. PR to yourself with a real description — writing "what changed and why" for an audience of one is still the exercise that catches your own bad decisions.

CI on PR: `ruff check`, `ruff format --check`, `pytest -m "not eval and not live"`. Free tier Actions minutes are ample. No LLM calls in CI, ever.

---

## 15. Cost and resource budget

**On a t3.micro (2 vCPU burstable, 1GB RAM):**

| Component | RAM | CPU | Storage |
|---|---|---|---|
| uvicorn + FastAPI + APScheduler | 120–180MB | idle ~0%, briefing job ~30s of one core/day | — |
| SQLite | ~10MB page cache | negligible | 50MB yr 1, ~300MB yr 2 with pruning |
| Docker daemon | ~80MB | — | ~500MB images |
| **Total** | **~280MB** | **well within burst credits** | **~2GB** |

Comfortable. Add 2GB swap anyway. Do **not** build images on this box (§11.3).

**Monthly cost:**

| Item | Cost |
|---|---|
| EC2 t3.micro | $0 if in free tier; ~$8/mo after. Verify your account's free-tier status — AWS changed the free tier structure for newer accounts. |
| Storage (8GB gp3) | ~$0.64/mo |
| ntfy.sh | $0 |
| RSS feeds | $0 |
| GitHub Actions + GHCR | $0 |
| LLM: via `claude -p` on Pro | $0 marginal today — see §1.4 for the risk |
| LLM: via API, Haiku-class | ~$0.50–2.00/mo at 25 summaries + 1 briefing/day |

**Realistic: $1–3/mo on top of whatever EC2 costs you.** Set a spend limit in the Anthropic Console on day one regardless of which path you take.

---

## 16. Extension points

Each future feature and the seam it plugs into. If any of these would require restructuring, the design is wrong.

| Future feature | Where it plugs in | Refactor needed |
|---|---|---|
| Gmail ingest | New `ingest/gmail.py` → existing `extract/` → `interaction` table | None |
| Google Calendar | New `ingest/gcal.py` → `task` table | None |
| Slack/Discord notify | New impl behind `notify.Notifier` protocol | Extract the protocol (~20 min) |
| Voice | New entrypoint calling `services/` | None — this is why the CLI/API/service split matters |
| Mobile | It's already an HTTP API. Add a PWA manifest to the briefing page. | None |
| Local LLM | New `llm/ollama.py` implementing `LLMProvider` | None — this is the payoff from §1.4 |
| RAG | New `search/vector.py` behind the same `search()` signature as FTS5 | None if you define `search()` as an interface now |
| PostgreSQL | Swap the SQLModel engine URL | Only FTS5 — isolated in one repository class, so ~1 hour |
| Auth | FastAPI dependency | None |
| Multi-user | Add `user_id`, one Alembic migration, a query-filter helper | ~1 day. Correctly deferred. |
| SaaS | Requires API-key auth (§1.4), background worker, Postgres | This is a different product. Don't design for it. |

The two decisions that make all of this cheap: **services never import entrypoints**, and **every external dependency sits behind a Protocol.** That's the whole extensibility story. Everything else is discipline.

---

## 17. If you only get four hours

Cut the news pipeline and the API. Ship:

1. `models.py` + SQLite + `chief app add/list` (60 min)
2. `LLMProvider` + `chief jd add` (90 min)
3. `chief brief` printing to terminal, tasks only, no news (60 min)
4. Cron on the box, output piped to ntfy (30 min)

That is a genuinely useful product and a real foundation. The news pipeline is a Saturday.

---

## 18. Open questions for you

1. **Which LLM path** — `claude -p` at $0 with the stability risk, or API key at ~$2/mo? (I'd say: build both, default to `claude -p`, and you'll never think about it again.)
2. **Is your EC2 account still in the 12-month free tier?** Changes the cost story from ~$2 to ~$10.
3. **What actually goes in the briefing on day one?** Write the ideal briefing by hand, in a text file, right now, before writing code. That artifact is your spec — and it will be shorter than you expect.

---

**Next action:** write that hand-crafted briefing (question 3). Fifteen minutes, no code. Then run `uv init chief`.
