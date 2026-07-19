# Event-Journal Release & Production Audit — 2026-07-19

**Scope:** `codex/event-journal-foundation` (event-sourced replay journal —
the durable-execution capability from the AI-Engineer relevance doc: Temporal
/ Trigger.dev / LangGraph-checkpointing territory). Merged to `main` (clean
fast-forward) after this audit. Method: 4 **haiku subagents** across
release-gates / security-privacy / production-reliability / competitor-parity,
with every high-stakes finding independently re-verified in code.

## Verdict: **merge-ready, alpha-scoped** — merged.

The feature is flag-gated `CUTCTX_REPLAY=1`, **default-off** (verified
belt-and-suspenders: `get_replay_store()` returns None, extension not
registered, `record_replay_event` no-ops), so the normal production path is
unaffected. 9,000 tests pass, 0 failures; versions aligned; all commits
conventional; ruff clean.

## What it delivers (competitor-gap closure)
Append-only SQLite event journal + deterministic reducer (`reduce_replay_events`)
+ admin-gated recovery endpoints (`/v1/sessions`, `/recover`, `/{id}/replay`,
`/{id}/state`), covering LLM-request lifecycle, tool calls, streaming
completion/truncation, compression, and error/failure state. This is the
event-log + reducer + recovery layer from `event-sourced-agent-harness.md` —
the doc's #1/#2/#4/#7/#10 cluster (Templestein, ZenML save-button, Microsoft
"good luck reproducing it," Pydantic durable, Trigger.dev replay).

## Findings

### Release gates — PASS (independently verified)
Flag default-off honored; schema has both indexes + bounded retention
(`DEFAULT_REPLAY_RETENTION_DAYS=7`, per-session/global caps); ruff clean; no
debug code / TODO / hardcoded paths beyond `~/.cutctx`.

### Security & privacy — PASS (independently verified)
- **No content/secrets persisted.** `_sanitize_detail` is a strict allowlist:
  only counts, token numbers, model/provider names, tool names, error codes,
  ≤200-char bounded strings. Verified in code + the branch's own test
  asserting `api_key`/`messages` are dropped.
- **Recovery endpoints admin-gated** — all four call
  `await _require_local_admin_auth`.
- **SQL fully parameterized** — zero string-built queries.

### Production reliability — PASS with one documented alpha limitation
- Writes are **fail-open** (try/except → warn, never raise) and **thread-safe**
  (`threading.Lock` + per-op connection); reducer replay bounded.
- **Known alpha limitation (documented in the module):** journal writes are
  synchronous SQLite executed inline on the request path when replay is ON.
  Writes are tiny (single INSERT, WAL, 100ms busy-timeout) and default-off, so
  the normal path is unaffected — but under high concurrency with replay ON
  they add event-loop latency. Remediation before promoting out of alpha:
  drain writes through a bounded background queue (or `asyncio.to_thread` at
  the extension boundary). Not fixed now: a proper fix touches the broadly-used
  synchronous `emit` and would risk the clean merge; captured as explicit
  pre-promotion work.

### Fixes applied this audit
1. **Test sync** (`test: sync session-recovery expected payload…`): a later
   branch commit added `stream_completion_count`/`stream_truncation_count` to
   the reducer output; an earlier integration test's expected dict predated
   them. Fixed the test to match the correct richer output.
2. **Replay DB path** (`fix: honor operator-supplied replay DB path`): the
   haiku security agent flagged `CUTCTX_REPLAY_DB_PATH` as an unvalidated
   path-traversal primitive. I initially confined it to `~/.cutctx` — but that
   **broke the legitimate operator use case** of relocating the journal to
   another volume (and its tests). Corrected: the env var is operator-trusted
   config (same boundary as the admin key), not untrusted request input, so it
   is honored as given. The haiku agent applied a web-app threat model to
   operator config — a good catch to investigate, wrong conclusion to ship.

### Competitor parity — the roadmap (net-new, NOT defects)
These are the honest gaps vs Temporal/Trigger.dev/LangGraph. None block the
alpha (which correctly scopes itself as trace/state recovery, not
re-execution):
| Gap | Impact | Note |
|---|---|---|
| No resume-execution / event-injection API | high (commercial) | biggest differentiator to build next; needs the sandboxing story from the harness spec resolved first |
| No incremental snapshotting (O(1) recovery) | high | the replay-vs-snapshot fork (talk #4); CCR store is the natural home |
| Single-process SQLite; no distributed store | high | pluggable `EventStore` interface → Postgres for multi-proxy (Phase 3 in the harness spec) |
| No deterministic re-execution guarantees | high | record input hashes/seeds; prerequisite for true replay |
| No event schema versioning | medium | tag events `schema_version`; add before journals go long-lived |

## Recommendation
Merge (done). Keep replay flag-gated alpha. Before promoting it to a
default/paid capability, land: (1) off-loop async writes, (2) snapshotting,
(3) schema versioning — in that order. The resume-execution/injection API is
the real durable-agent differentiator but must not ship until its trust model
is a prerequisite, not an open question.
