# Cutctx Best-in-Class Evidence Packet

Generated: 2026-07-09

This packet records current verified evidence for the best-in-class roadmap. It does not make a public market-leadership claim; it separates proven behavior from remaining gaps.

## Verification Summary

### Compression Verification

Source artifacts: `verify-report.md` / `verify-report.json`

- Command: `cutctx verify --ci --format json -o verify-report.json`
- Status: PASS
- Dataset: `tool_outputs`
- Compressors: `content_router`, `smart_crusher`
- Summary: 2 passed, 0 failed, 0 skipped, 670 total tokens saved
- Verifier now warms one untimed case per compressor before enforcing the latency gate, removing first-run cold-start flakes from CI. Latest local rerun: 2026-07-10.

| Compressor | Tokens Saved | Ratio | F1 | Information Recall | Critical Recall | Latency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| content_router | 335 | 0.7912 | 1.0 | 1.0 | 1.0 | 45.71 ms |
| smart_crusher | 335 | 0.7912 | 1.0 | 1.0 | 1.0 | 0.06 ms |

### Product Benchmark Smoke

- Command: `uv run python benchmarks/run_all.py --dry-run`
- Status: PASS
- Synthetic corpora loaded: `json`, `code`, `prose`, `mixed`
- Mixed corpus latency improved from a prior observed ~7879 ms to 13.7 ms after making opportunistic Kompress fallback opt-in.
- Mixed corpus still saved 27.0% tokens at 13.7 ms.
- JSON corpus saved 59.0% tokens.

### Breadth Benchmark

- Command: `rtk .venv/bin/python -m cutctx.cli.main evals benchmark -d code_samples -d rag_samples -d mixed_agent_traces -c content_router -c smart_crusher --metrics ratio --metrics tokens_saved --metrics tokens_per_second --metrics f1 --metrics information_recall --metrics critical_item_recall --metrics verbatim_fidelity --parallel 1 --output artifacts/benchmark-breadth.json --markdown`
- Status: PASS
- Datasets loaded locally: `CodeSamples`, `RAGSamples`, `MixedAgentTraces`
- `CodeSamples`: `content_router` now saves `111` tokens at `74.8%` ratio, runs at `3,225.8` tokens/sec, and preserves `1.000` information recall / `1.000` critical-item recall / `1.000` verbatim fidelity with `0.823` F1; `smart_crusher` stayed unchanged with `1.000` F1 / recall.
- `RAGSamples`: both compressors stayed unchanged with `1.000` F1, `1.000` information recall, and `1.000` critical-item recall.
- `MixedAgentTraces`: both compressors saved `92` tokens at `82.6%` ratio with `1.000` F1, `1.000` information recall, and `1.000` critical-item recall.
- Honest takeaway: local breadth proof is now stronger and deterministic, and the code-heavy path now recovers meaningful savings while still preserving declared must-keep anchors. The main remaining tradeoff is stylistic overlap: exact-anchor preservation and information recall now stay perfect on the local code fixtures, but `F1` still drops because safe fallback compaction removes low-value comments/whitespace while preserving executable code. Throughput is now first-class too, but raw tokens/sec still needs context because unchanged paths can look artificially fast.

### Dedicated Verbatim Benchmark

- Command: `rtk ./.venv/bin/python -m cutctx.cli.main evals benchmark -d verbatim_compaction -c verbatim_compactor -c content_router -c smart_crusher --metrics ratio --metrics tokens_saved --metrics tokens_per_second --metrics f1 --metrics information_recall --metrics critical_item_recall --metrics verbatim_fidelity --parallel 1 --output artifacts/verbatim-compaction-benchmark.json --markdown --html`
- Status: PASS
- Dataset loaded locally: `VerbatimCompactionSamples`
- `VerbatimCompactor`: `151` tokens saved at `71.4%` ratio, `3,969,719.5` tokens/sec, `0.741` F1, `0.750` information recall, `1.000` critical-item recall, `1.000` verbatim fidelity.
- `ContentRouter`: `180` tokens saved at `69.5%` ratio, `1,688.2` tokens/sec, but only `0.538` critical-item recall / `0.538` verbatim fidelity on exact-preservation fixtures.
- `SmartCrusher`: `43` tokens saved at `91.2%` ratio, `13,575,260.4` tokens/sec, `1.000` F1 / information recall, but only `0.769` critical-item recall / `0.769` verbatim fidelity.
- Honest takeaway: the dedicated compaction mode now gives us a real narrow benchmark story. For exact-preservation workloads, `verbatim_compactor` is currently the strongest local option for keeping file paths, line anchors, and error strings verbatim.

### Focused Test Evidence

- Eval benchmark / verify slice: `24 passed`
- Agent Context Report / buyer report slice: `43 passed`
- Hosted compression endpoint/client: `14 passed`
- Request trace inspector/logger/feed slice: `20 passed`
- Rate limiter stats + route auth slice: `27 passed`
- LLMLingua adapter + benchmark truthfulness slice: `67 passed`
- Enterprise procurement packet + trust-doc split slice: `2 passed`
- Benchmark relative-delta report + task-class docs slice: `31 passed`
- Agent Context local smoke artifact slice: `4 passed`
- Buyer report local smoke artifact slice: `24 passed`
- Savings reconciliation local smoke artifact slice: `43 passed`
- Code fallback + benchmark refresh slice: `94 passed`
- Dashboard request trace inspector + dashboard/proxy regression slice: `13 passed`
- Governance rate-limit + budget visibility slice: `20 passed`
- Orchestrator provider-policy + failover controls slice: `23 passed`
- Anthropic configurable fallback execution slice: `4 passed`
- OpenAI chat configurable fallback slice: `2 passed`
- OpenAI Responses configurable fallback slice: `1 passed`
- OpenAI Responses WebSocket configurable fallback slice: `28 passed`
- Gemini configurable fallback slice: `2 passed`
- Streaming request logger regression slice: `8 passed`
- Pipeline/ContentRouter/agent profile matrix: `71 passed`
- Backup verification script: `4 passed`
- Prior integrated matrix sprint: `125 passed`
- Dashboard build/lint Playwright slices passed during dashboard savings UX workstream; fresh 2026-07-10 `npm run lint` and `npm run build` also pass after eliminating synchronous effect state updates in the request-inspector and orchestrator views.
- Dedicated verbatim verify run passed with thresholds: `F1 >= 0.70`, `information recall >= 0.70`, `critical-item recall >= 0.90`, `verbatim fidelity >= 0.90`, `tokens/sec >= 500`, `compression ratio <= 0.80`.
- Suite-runner zero-cost smoke for `Verbatim Compaction` returned `accuracy_rate = 1.0`, `tokens_saved = 151`, `passed = true`.
- Dedicated verbatim verify run now passes in CI mode with explicit compaction thresholds: `F1 >= 0.70`, `information recall >= 0.70`, `critical-item recall >= 0.90`, `verbatim fidelity >= 0.90`, `tokens/sec >= 500`, `compression ratio <= 0.80`.
- Aggregate zero-cost suite artifact under `artifacts/eval-suite-compression-only/` records `Verbatim Compaction` at `100.0%` verbatim fidelity, `critical_item_recall = 1.0`, and `151` tokens saved.
- Suite-runner zero-cost smoke for `Tool Schema Compaction` returned `accuracy_rate = 1.0`, `tokens_saved = 119`, `tokens_per_second = 1,324,042.99`, and `passed = true`.
- Hosted localhost smoke script coverage: `1 passed`.
- Hosted client/endpoint plus live localhost smoke slice: `16 passed`.
- Hosted smoke now launches its localhost `uvicorn` process with the active/project virtualenv, preventing interpreter-dependent readiness failures in mixed test runners.

## Implemented Roadmap Evidence

### Hosted Compression Entrypoint

- Feature-flagged `POST /v1/hosted/compress` surface added for simple hosted compression use cases.
- Python SDK wrapper added via `HostedCompressionClient` with lazy package exports from `cutctx`.
- Disabled by default via `CUTCTX_HOSTED_COMPRESSION_ENABLED=0`, preserving local-first proxy behavior.
- Optional `CUTCTX_HOSTED_COMPRESSION_API_KEY` gates hosted compression bearer or `X-Cutctx-Api-Key` credentials.
- Accepts either raw `text` or chat `messages`; text mode returns both plain `text` and compressed `messages`.
- Raw text mode now exposes explicit compatibility wrappers for `tool_output`, `rag_text`, and `agentic_text` while keeping the default text path backward-compatible as `tool_output`.
- Contract tests verify text mode matches local `cutctx.compress()` pipeline on fixed fixtures, including the explicit `rag_text` and `agentic_text` compatibility modes, and the hosted response schema key set across text and message paths.
- TypeScript SDK wrapper added via `HostedCompressionClient` exports from `cutctx-ai`, matching the Python thin hosted client contract.
- Python hosted client coverage: `pytest tests/test_hosted_compression_client.py tests/test_hosted_compression_endpoint.py -q` -> `14 passed`.
- TypeScript hosted client coverage: `rtk npm run test -- hosted.test.ts` -> `7 passed`.
- TypeScript parity test proves the same hosted client call shape works with a simple `baseUrl` swap between `http://localhost:8787` and a hosted URL while preserving the returned compression payload.
- TypeScript package verification: `rtk npm run test -- client.test.ts hosted.test.ts` -> `21 passed`; `rtk npm run typecheck` -> pass; `rtk npm run build` -> pass.
- Hosted localhost smoke now passes through the real HTTP client path: `rtk pytest tests/test_generate_hosted_compression_smoke.py tests/test_hosted_compression_client.py tests/test_hosted_compression_endpoint.py -q` -> `15 passed`.
- Live localhost hosted artifact now exists at `artifacts/hosted-compression-smoke.{json,md}` with `2,999` tokens saved (`4,942 -> 1,943`, `60.68%` compression) via `HostedCompressionClient` against a live `uvicorn` runtime app.
- Remaining caveat: hosted proof is now real local HTTP smoke plus fixture parity, but not yet a smoke against a remote hosted environment.
- Client tests verify request shape, auth header, response parsing, and structured hosted-error handling.

- Aggregate zero-cost suite run under the real CLI passed `4/4` benchmarks and wrote a combined artifact under `artifacts/eval-suite-compression-only/`.
- Aggregate zero-cost suite metrics on `2026-07-09`: `CCR Round-trip` saved `12,100` tokens at `53%` compression with `145,640.2` tokens/sec, `Info Retention` saved `11,490` at `66%` with `42,240.3` tokens/sec, `Verbatim Compaction` saved `151` at `29%` with `critical_item_recall = 1.0`, `verbatim_fidelity = 1.0`, and `4,048,760.3` tokens/sec, and `Tool Schema Compaction` saved `119` at `19%` with `2,638,642.0` tokens/sec.
- Markdown report-card cells now escape secondary-metric separators correctly, so the saved suite artifact renders as a valid table in markdown instead of splitting `Secondary Metrics` across extra columns.

- Named `llmlingua_research` benchmark preset now exists on the main eval CLI and is regression-covered at both the CLI and adapter levels.
- Completed canonical live preset run on `2026-07-10` wrote `artifacts/llmlingua-research-preset.{json,md}` over repo-local fixed fixtures: `metadata.llmlingua_model = microsoft/llmlingua-2-xlm-roberta-large-meetingbank`, 8/8 cells, zero errors, seed 42. LLMLingua saved `202/145/216/299` tokens on code/RAG/mixed/verbatim suites versus Cutctx `111/0/92/180`; Cutctx was faster and retained more information recall on every suite (`1.000/1.000/1.000/0.867` versus `0.600/0.750/0.450/0.606`).
- The `llmlingua` optional extra is now installed in the repo `uv` environment, and direct runtime fetch reached the upstream Hugging Face model download path on `2026-07-09`.
- A completed live run on `2026-07-10` now exists at `artifacts/llmlingua-bert-base-research-preset.{json,md}` using the explicitly recorded official `microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank` checkpoint: 8/8 cells, zero errors, and seed 42. LLMLingua saved more tokens on all four local suites (`150/140/164/244` versus Cutctx `111/0/92/180`), but Cutctx retained more declared critical items (`1.000/1.000/1.000/0.538` versus `0.833/0.333/0.333/0.154`).
- Benchmark truthfulness is hardened: if LLMLingua falls back to passthrough because the dependency is unavailable or runtime compression fails, the benchmark now records that cell as an error instead of silently reporting a valid zero-savings result.
- Both canonical XLM-R-large and separately labeled BERT-base official LLMLingua-2 artifacts now exist. They prove the comparison surface and task-class tradeoffs on pinned local fixtures; they do not justify a universal market-performance claim without broader external corpora and production/design-partner telemetry.

### Savings Attribution

- Persistent `created_savings_usd` vs `observed_provider_savings_usd` fields added across savings lifetime, display-session, and history rows.
- Schema migrated with v5 migration/backfill tests.
- Provider prompt-cache and semantic-cache savings are reported as observed provider savings, not product-created Cutctx savings.
- Source-level USD parity and reconciliation tests pass.
- Local reconciliation smoke now writes `artifacts/savings-reconciliation-smoke.{json,md}` from real durable savings history and proves lifetime, display-session, history, and buyer-report totals all agree at `4,150` tokens saved, `$0.34` created by Cutctx, `$0.14` observed at provider, and `$0.48` total.

### Dashboard Savings UX

- Savings overview pages show created vs observed savings.
- Local buyer-report smoke now writes `artifacts/buyer-report-smoke.{json,md}` from real durable savings history and proves source-level reconciliation: `4,150` total tokens saved and `$0.48` total USD saved, exactly matching the per-source sums in the generated artifact.
- Dead `$0.00` rows are hidden unless explicitly active.
- Compression decline reasons render only when telemetry exists.
- Dashboard build, lint, and Playwright slices passed during the UX workstream.

### Gateway Observability Depth

- Request logs now persist structured per-request trace fields, latency breakdowns, source-level savings, decline reasons, routing metadata, and request-cost estimates.
- `RequestLogger.get_recent_with_messages()` now tails the shared JSONL file, so multi-process dashboards can inspect traces handled by sibling proxy workers instead of only the current process.
- Shared-log trace readers now fail open: if the observability JSONL file becomes unreadable at runtime, trace and feed surfaces fall back to in-memory request logs instead of failing the proxy path.
- Direct `/v1/compress` requests now have explicit regression proof that they emit request-trace rows which are immediately queryable through `/transformations/traces` and `/transformations/traces/{request_id}`.
- `/v1/rate_limit/stats` now exposes recorded denial counters plus last-limited event metadata (`request_denied_total`, `token_denied_total`, `bucket_limit_denied_total`, `last_rate_limited`), so actual rate-limit events are queryable instead of only configured RPM/TPM.
- Admin inspector APIs exist at `/transformations/traces` and `/transformations/traces/{request_id}`.
- `/transformations/feed` preserves message-diff payloads while exposing the same trace metadata.
- Overview now ships a click-through request inspector under `Recent requests`, including requested vs actual model, total savings, request cost, latency, routing path, source-level attribution, raw/compressed payloads, tags, and pipeline timings.
- Shared upstream retry path now stamps request-trace telemetry with circuit-breaker state, active failover provider, retry-after timing, and fallback reason.
- Governance now exposes live proxy budget status alongside rate limiting.
- CostTracker stats publish a structured `budget` snapshot in `/stats`.
- Orchestrator consumes `/policy/status` and shows provider-aware routing/compression posture for Anthropic, OpenAI, and Gemini.
- Orchestrator also exposes live provider health plus manual `/v1/providers` enable/disable controls for incident steering.
- Anthropic, OpenAI chat, OpenAI Responses HTTP, OpenAI Responses WebSocket, Gemini HTTP, and Gemini SSE paths now have opt-in configurable fallback flows with verified fallback attribution.
- `cutctx report agent-context` now includes a telemetry snapshot derived from durable request history, surfacing observed request counts, provider mix, fallback counts, decline reasons, routing activity, latency percentiles, and request cost without adding new hot-path proxy work.
- Live report generation against the current machine's persisted request log produced `artifacts/agent-context-report.{json,md}` with 13,276 observed request-log rows over the last 7 days, confirming the report works on real local telemetry and not only monkeypatched tests.

### Benchmark Proof And Verification

- Repo-local breadth datasets now cover code, RAG, and mixed-agent traces.
- Benchmark results now include first-class `critical_item_recall` instead of relying only on overlap proxies.
- Benchmark results now also include first-class `tokens_per_second` and `verbatim_fidelity` metrics.
- Built-in fixtures declare explicit must-keep strings, and benchmark aggregation measures whether those survive compression.
- `cutctx verify` now reports `critical_item_recall_source="benchmark_metric"` when real benchmark-critical items are available.
- CI verification warms one untimed case per compressor before enforcing latency thresholds, stabilizing first-run verification without weakening the timed pass/fail gate.
- `scripts/generate_benchmark_release_manifest.py` now writes `artifacts/benchmark-release-manifest.json` with git SHA, runtime/package versions, platform, checkpoint ID, seed, fixture hashes, timestamp, and explicit raw/provider-native arm availability. Provider-native compaction remains labeled `unavailable` until a provider emits an observable native signal.

### ContentRouter Correctness And Latency

- Router diagnostics expose selected strategy, chain, ratios, token savings, accepted routes, and rejected routes.
- Regex log/search/diff/html signals override Rust `source_code` misses.
- CI ContentRouter benchmark disables heavyweight ML fallback and uses passthrough for unknown text, keeping verification deterministic.
- Product pipeline disables opportunistic Kompress fallback by default via `CUTCTX_ENABLE_KOMPRESS=0`; explicit `force_kompress` / `kompress_model` remain opt-in.

### Decline Telemetry

- Compression decisions expose canonical `decline_reason`.
- Anthropic, Gemini, and OpenAI handlers use canonical decline tags in logs and metrics.
- Decline telemetry tests cover the updated paths.

### Semantic Cache

- Semantic cache keys normalize volatile metadata, trailing whitespace, timestamp-like blocks, and cache-control noise.
- Streaming cache entries preserve raw SSE bytes in byte-fidelity tests.

### Trust And Security

- CCR retrieve and feedback routes require admin authentication.
- `/v1/feedback/{tool_name}` now also requires CCR entitlement.
- Feedback route imports the actual compression feedback module.
- Backup verification script now supports strict mode and fails when required DBs are missing if zero databases were verified.
- The proprietary `cutctx-ee` package now declares `sqlalchemy>=2.0,<3.0`, matching its enterprise memory-service persistence imports; package regression and memory-route tests pass.

## Backup Verification Evidence

- Script: `scripts/verify-backup.sh`
- Verified behavior:
  - Valid SQLite file passes `PRAGMA integrity_check`.
  - Corrupt SQLite file fails.
  - `--strict` fails when the expected default durable DB is missing.
  - Non-strict default mode still fails if no databases are verified.
- Test command: `pytest tests/test_verify_backup_script.py -q` -> `4 passed`

## Remaining Caveats

- Public “best in market” claims are still not justified until public benchmarks and production/design-partner telemetry both pass.
- Hosted API simplicity is materially better, gateway request inspector depth is implemented across API and dashboard layers, and active failover controls are wired. Real localhost hosted-client smoke now exists at `artifacts/hosted-compression-smoke.{json,md}` and local persisted-telemetry snapshots now generate through Agent Context Report, but named design-partner, production, or remote hosted deployment snapshots still need collection before we can call the observability gap fully closed.
- A fresh local multi-request smoke run now generates `artifacts/agent-context-smoke-report.{json,md}` from real durable proxy telemetry: 24 observed `/v1/compress` requests, 57,456 tokens saved, and request-history-backed provider/cost snapshot output by the standard `cutctx report agent-context` path.
- Benchmark breadth is materially better: repo-local `code_samples`, `rag_samples`, and `mixed_agent_traces` now run through `cutctx evals benchmark` and are covered by focused tests. The previously broken local code-path proof is now fixed: `content_router` saves `111` tokens on the pinned code fixtures while preserving `1.000` information recall, `1.000` critical-item recall, and `1.000` verbatim fidelity. The remaining gap is no longer a broken local benchmark path; it is broader external proof and comparison coverage, plus the narrower stylistic-overlap tradeoff reflected in the local `0.823` F1 score.
- Benchmark reports now include both absolute per-metric tables and relative delta tables vs the baseline compressor, so LLMLingua comparison output exposes both raw scores and directional change in the same artifact.
- Benchmark docs now include an explicit compressor task-class table for `content_router`, `llmlingua`, and `verbatim_compactor`, clarifying where each arm is intended to win or lose.
- Enterprise procurement packet now exists at `artifacts/enterprise-procurement-packet.md` with a fixed checklist and evidence links for identity, audit, retention, and deployment posture.
- Public trust docs now explicitly separate `Available now in product` from `External or planned workstreams`, reducing compliance overclaim risk in reviewer-facing materials.
- Remaining caveat: legal/compliance sign-off itself is still external work. The packet is procurement-ready for review, not proof that DPA/MSA or certification programs are complete.
- Remote hosted and staged-gateway runners are implemented but intentionally return `not_configured` until `CUTCTX_HOSTED_BASE_URL`/`CUTCTX_HOSTED_API_KEY` and `CUTCTX_STAGED_PROXY_BASE_URL`/`CUTCTX_STAGED_PROXY_ADMIN_API_KEY` are supplied. Partner telemetry validation requires a consented report covering at least seven days; the local same-day smoke artifact is correctly rejected for that purpose.
