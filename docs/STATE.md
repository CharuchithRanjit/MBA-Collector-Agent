# STATE

Updated: 2026-07-28
Milestone: hour 8 of 10 complete — ClaudeCLIProvider real cost/model, stdin prompt

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
- 36 tests passing

## Next
- 10 real job descriptions as golden files in evals/ + an eval harness
  (`-m eval` marker, real API calls) — a quality-measurement slice,
  distinct from "does the pipeline wire together"
- fetch_url_text's empty-extraction path raises FetchError but has no
  direct test yet (only the 403/HTTP-error path and the UA header are
  tested) — flagged, not added since it wasn't a named test this slice
- AnthropicAPIProvider's cost_usd is still hardcoded 0.0 (no
  MODEL_FOR_PURPOSE/pricing table) — unaffected by this slice, which
  only touched ClaudeCLIProvider; that path gets cost directly from
  claude -p's own JSON, no pricing table needed there

## Decided, do not reopen
- No agent framework. Pipelines of typed functions.
- Ranking is deterministic; the LLM writes the sentence only.
- FTS5 before embeddings. No user_id column.
- LLM default is ClaudeCLIProvider (`claude -p`, $0).
  AnthropicAPIProvider selected by CHIEF_LLM_PROVIDER=api.
