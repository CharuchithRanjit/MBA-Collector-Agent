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

## Context
Read docs/CODEBASE.md before any non-trivial task. docs/career-agent-design-doc.md
is the full architecture. docs/STATE.md is the live status — read it first,
update it last.

## Division of labour
I hand-write: models.py, llm/base.py, rank.py, prompts, test NAMES,
and every architectural boundary. You write: service bodies, CLI and
API wiring, test bodies, Dockerfile, compose, CI.
If a task requires changing an interface I own, STOP and tell me.
Do not write it for me.

## How to work
1. Plan first, no code. Wait for my approval.
2. Failing tests before implementation. Show me they fail for the
   right reason — an ImportError is not a red test.
3. Implement.
4. One commit per vertical slice. Never per file.

## Challenge me
If a request adds a feature that does not improve the morning briefing
or reduce input friction, say so before building it. If a simpler
deterministic solution exists, propose it. Do not agree by default.

## Known landmines
- SQLite reads datetimes back NAIVE. Call as_utc() on the read path
  before any Python-side arithmetic. This will bite in rank.py.
- Order by `Col.is_(None), Col` — SQLite sorts NULL first.
- Time-dependent functions take `now: datetime | None = None`.