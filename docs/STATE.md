# STATE

Updated: 2026-07-28
Milestone: hour 6 of 10 complete — chief jd add works end to end for real

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
- 31 tests passing

## Next
- 10 real job descriptions as golden files in evals/ + an eval harness
  (`-m eval` marker, real API calls) — a quality-measurement slice,
  distinct from "does the pipeline wire together"
- MODEL_FOR_PURPOSE routing table + real cost_usd calc (still deferred
  — no purpose needs cheap/expensive routing yet)
- ClaudeCLIProvider's LLMResponse.model is just "claude-cli" (the
  provider name), not a real model identifier — `claude -p` plain
  output doesn't expose which model ran. Fine for now; would need
  --output-format json to fix, not worth it yet.

## Decided, do not reopen
- No agent framework. Pipelines of typed functions.
- Ranking is deterministic; the LLM writes the sentence only.
- FTS5 before embeddings. No user_id column.
- LLM default is ClaudeCLIProvider (`claude -p`, $0).
  AnthropicAPIProvider selected by CHIEF_LLM_PROVIDER=api.
