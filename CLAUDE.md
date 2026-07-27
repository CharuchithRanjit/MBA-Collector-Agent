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