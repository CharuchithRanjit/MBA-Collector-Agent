# STATE

Updated: 2026-07-28
Milestone: hour 6 of 10 complete

## Done
- models.py, db.py, config.py, cli.py
- services/applications.py (add/list/move, null-last ordering, injectable
  clock; add_application now also takes location/jd_url/jd_raw_text, and
  builds Application(role=role) not role_id= — see bugfix note below)
- llm/base.py (LLMProvider protocol, hand-written) + models.LLMCall
- llm/: ClaudeCLIProvider, AnthropicAPIProvider, FakeLLM, shared
  structured() retry helper, LoggingProvider (writes llm_call, retry
  = 2 rows), factory.get_llm_provider() (env-selected, CHIEF_LLM_PROVIDER)
- fetch.py (httpx + trafilatura), extract/jd.py (RoleExtraction — no
  skills fields, jd_to_role), services/jobs.py (ingest_jd), `chief jd
  add [URL] [--paste]` wired end to end except the prompt file (below)
- Bugfix: `Application(role_id=role.id)` let `.role` get GC'd and
  silently re-queried, hitting the SQLite-naive-datetime landmine on
  deadline_at. Fixed to `Application(role=role)`.
- 31 tests passing

## Next
- `llm/prompts/extract_jd.v1.md` — blocking, yours to write (prompts
  are hand-written). Must state deadline is None unless explicit in
  the text, never inferred. Until it exists, `chief jd add` fails
  cleanly at the prompt-read step; everything else in the pipeline
  (fetch/paste, dedup, DB writes) is verified working.
- 10 real job descriptions as golden files in evals/ (needs the prompt
  above first)
- MODEL_FOR_PURPOSE routing table + real cost_usd calc (still deferred
  — no purpose needs cheap/expensive routing yet)

## Decided, do not reopen
- No agent framework. Pipelines of typed functions.
- Ranking is deterministic; the LLM writes the sentence only.
- FTS5 before embeddings. No user_id column.
- LLM default is ClaudeCLIProvider (`claude -p`, $0).
  AnthropicAPIProvider selected by CHIEF_LLM_PROVIDER=api.
