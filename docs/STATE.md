# STATE

Updated: 2026-07-28
Milestone: hour 3 of 10

## Done
- models.py, db.py, config.py, cli.py
- services/applications.py (add/list/move)
- list_applications: NULLs-last ordering, injected `now` param
- add_application: dropped silently-discarded `tier` param
- 8 tests passing

## In progress
- (none)

## Next
- LLM layer: llm/base.py (I hand-write), two providers, FakeLLM,
  llm_call logging, `chief jd add <url>`, 10 golden files in evals/

## Decided, do not reopen
- No agent framework. Pipelines of typed functions.
- Ranking is deterministic; the LLM writes the sentence only.
- FTS5 before embeddings.
- No user_id column.
- LLM default is ClaudeCLIProvider (`claude -p`, $0).
  AnthropicAPIProvider exists from day one, selected by
  CHIEF_LLM_PROVIDER=api. Switching is env-only, no code change.