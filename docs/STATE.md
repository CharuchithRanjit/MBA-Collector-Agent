# STATE

Updated: 2026-07-28
Milestone: hour 5 of 10 complete

## Done
- models.py, db.py, config.py, cli.py
- services/applications.py (add/list/move, null-last ordering, injectable clock)
- llm/base.py (LLMProvider protocol, hand-written) + models.LLMCall
- llm/: ClaudeCLIProvider, AnthropicAPIProvider, FakeLLM, shared
  structured() retry helper, LoggingProvider (writes llm_call, retry
  = 2 rows), factory.get_llm_provider() (env-selected, CHIEF_LLM_PROVIDER)
- 21 tests passing

## Next
- `chief jd add <url>`: fetch + extract/jd.py + extract_jd.v1.md prompt
- 10 real job descriptions as golden files in evals/
- MODEL_FOR_PURPOSE routing table + real cost_usd calc (both deferred
  when the provider layer shipped — no purpose needs cheap/expensive
  routing yet)

## Decided, do not reopen
- No agent framework. Pipelines of typed functions.
- Ranking is deterministic; the LLM writes the sentence only.
- FTS5 before embeddings. No user_id column.
- LLM default is ClaudeCLIProvider (`claude -p`, $0).
  AnthropicAPIProvider selected by CHIEF_LLM_PROVIDER=api.
