# Spec: Multi-Signal Evaluation Framework (Compression Scorecards)

**Status:** Draft for implementation
**Priority:** P0 (Phase 2 — after hooks)
**Date:** 2026-07-19
**Origin:** `docs/specs/features-from-youtube-research.md` §3
**Depends on:** Stream Processor Hooks (`spec-stream-processor-hooks.md`) — the EvalHook is the collection mechanism.
**Feeds:** Compression Eval Dashboard (`spec-eval-dashboard.md`), `cutctx learn` v2, canary release gates.

---

## 1. Problem

Compression today is measured almost entirely by **how much it saved** (tokens/bytes/ratio metrics in `crates/cutctx-proxy/src/observability/`), not **whether it was safe and worth it**. Quality evidence exists only offline: the Python eval suite (`cutctx/evals/` — `verbatim_fidelity`, F1/ROUGE/BLEU, `compression_only.py` with `fidelity_threshold=0.90`) runs as benchmarks, disconnected from production decisions. `cutctx/product_evidence.py` itself warns that "compression fidelity is not a substitute" for downstream task quality. Enterprises evaluating Cutctx ask one question we can't answer per-request: *did compression change the answer?*

The goal: every production compression decision produces a **scorecard** across five signals, cheap ones computed inline, expensive ones sampled and computed async. Scorecards accumulate per strategy/content-type/agent and gate future decisions.

## 2. Goals

- A `Scorecard` record per compression decision with five signals: **quality** (faithfulness), **cost** (tokens saved), **latency** (compression overhead vs estimated savings), **error rate** (structural integrity), **waste** (were compressed tokens even used?).
- Tiered computation: Tier A inline (<1ms, every request), Tier B async sampled (local heuristics), Tier C offline (LLM-judged, batch).
- Persistence in a local SQLite scorecard store + Prometheus aggregates.
- A feedback path: aggregated scorecards adjust strategy confidence (consumed by the strategies selector and `cutctx learn`).
- Rust/Python parity on signal definitions — Python evals remain the reference oracle; Rust production signals must be defined so Python can recompute them bit-for-bit from stored inputs.

## 3. Non-goals (v1)

- Online LLM-as-judge in the request path (never; Tier C only, offline).
- Automatic strategy *switching* from scorecards (v1 surfaces recommendations + confidence numbers; the strategies spec keeps its deterministic rules; auto-tuning is v2 after we trust the signals).
- Downstream task-success evaluation (needs agent-outcome labels; `cutctx learn` session mining is the eventual source — see §9).

## 4. Current state (ground truth)

Reusable machinery, by signal:

- **Cost:** `Outcome::Compressed { tokens_before, tokens_after, per_strategy_tokens }` (`compression/live_zone_anthropic.rs:79`); `tokens_saved` computed at proxy.rs:925; per-block `compression_ratio.rs::observe_ratio`.
- **Latency:** compression wall time measurable at the hooks `after_compress` payload (`elapsed`); TTFB via `first_byte_at: OnceLock<Instant>` (proxy.rs SSE path).
- **Error rate / structural integrity:** the passthrough-bytes-modified alarm (`proxy_metrics.rs::record_passthrough_bytes_modified`); `LiveZoneError` variants; live-zone byte-range surgery guarantees untouched blocks are byte-identical — what's missing is *post-compression structural validation* of touched blocks.
- **Quality:** Python `cutctx/evals/metrics.py` (`compute_f1`, `compute_rouge_l`, `compute_semantic_similarity`, `compute_information_recall`); `verbatim_fidelity = critical_item_hits / critical_item_total` (`evals/benchmark_runner.py`, `runners/compression_only.py`); Rust `relevance/` scorers (BM25/embedding/hybrid) and `signals/line_importance.rs` (`ImportanceCategory {Error, Warning, Importance, Security, Markdown}`, `Tiered` composition, `ESCALATE_THRESHOLD=0.7`).
- **Waste / usage:** CCR retrieval events — Python `cutctx/cache/compression_store.py` records retrieval feedback; proxy `/v1/retrieve/stats` (Python server.py:4189). Retrieval of an elided item = signal the compression dropped something needed.
- **Persistence precedents:** SQLite with WAL (`SqliteCcrStore`), append-only hash-chained ledger (`cutctx/assurance.py::evidence_ledger`), bounded-mpsc batch emitter (`spend_emitter.rs`).
- **Identity/labels:** tenancy headers, auth mode, model, strategy + rationale (from strategies spec), flag arm (from flags spec).

## 5. Signal definitions

All signals normalized to `[0.0, 1.0]`, higher = better, `None` = not computed (never coerced — no-silent-fallbacks rule; confidence carried separately).

### S1 — Quality (faithfulness)

- **Tier A (inline, every request):** `critical_preservation` — extract critical items from the *original* block (lines matching `LineImportanceDetector` with category `Error|Security|Warning`, plus ccr markers, plus tool-call ids); score = fraction still present (exact substring) in compressed output. This is the Rust port of Python `verbatim_fidelity`; definitions must match `runners/compression_only.py` (`fidelity = len(preserved)/len(critical_items)`; empty critical set ⇒ score 1.0 with `confidence=0.3`).
- **Tier B (async, sampled at `sample_rate`, default 5%):** `term_recall` — BM25 top-k salient terms of original (reuse `BM25Scorer` tokenizer regex) recall in compressed; plus embedding cosine similarity original↔compressed via `EmbeddingScorer` **only if available** (`is_available()`; never load fastembed in-proxy — Tier B runs in the sidecar, §6.3).
- **Tier C (offline batch):** LLM judge answer-equivalence using existing `compute_answer_equivalence` / `compute_semantic_similarity` in `cutctx/evals/metrics.py`, over sampled (original, compressed) pairs pulled from the scorecard store + CCR.

### S2 — Cost

`tokens_saved_ratio = tokens_saved / tokens_before` from `Outcome`. Tier A, exact, confidence 1.0. Also raw `tokens_saved` for dollar math downstream (dashboard owns USD conversion via `savings_tracker.py` rates).

### S3 — Latency

`latency_score = clamp01(1 - compress_elapsed / latency_budget)` where `latency_budget = cfg.latency_budget_ms` (default 150ms). Raw `compress_elapsed_ms` stored alongside. Tier A.

### S4 — Structural integrity (error rate)

Tier A, per touched block:
1. compressed block parses as JSON when original was JSON (`serde_json::from_str` round-trip);
2. tool-call arrays: every `tool_use.id`/`tool_call_id` present in original is present in compressed (compression must never orphan a tool result);
3. role sequence of the messages array unchanged in relative order;
4. all inserted ccr markers match `[a-f0-9]{16}` and resolve in the store (`CcrStore::get` — check sampled, not every request: `marker_check_rate` default 10%).

Score = fraction of checks passed; any failure of check 2 or 3 additionally fires `proxy_eval_integrity_violation_total{check}` at ERROR severity — these should be release-blocking in CI.

### S5 — Waste (post-hoc usage)

Tier B/C, computed by joining later events onto the scorecard:
- `retrieval_penalty`: a `cutctx_retrieve` call resolving a marker this request created ⇒ the elision was wrong for this content. Score contribution `1 - retrieved_fraction`.
- `output_reference`: (Tier C) does the LLM response reference content that was compressed away? Approximated by BM25 match of response text against the *removed* spans (removed spans reconstructable via CCR).

## 6. Design

### 6.1 Scorecard record

```rust
// crates/cutctx-core/src/evals/scorecard.rs   (new module: crates/cutctx-core/src/evals/)
pub struct Scorecard {
    pub id: String,                 // = request_id + block ordinal
    pub ts_unix_ms: i64,
    pub request_id: String,
    pub session_key: Option<String>,
    pub tenancy: TenancyLabels,     // org/workspace/project/agent (strings, may be empty)
    pub model: String,
    pub auth_mode: &'static str,
    pub strategy: String,           // live-zone strategy or context strategy name
    pub strategy_rationale: String,
    pub flag_arm: Option<String>,
    pub content_type: String,       // ContentType as_str
    pub tokens_before: u64,
    pub tokens_after: u64,
    pub compress_elapsed_ms: f64,
    pub signals: SignalSet,         // s1..s5: Option<SignalValue { score: f32, confidence: f32, tier: Tier }>
    pub ccr_keys: Vec<String>,      // markers created (for S5 joins + Tier C reconstruction)
    pub schema_version: u32,        // = 1
}
```

### 6.2 Collection — `EvalHook` (built on hooks API)

- Registers `after_compress` (build scorecard, compute Tier A signals S1a/S2/S3/S4) and `after_llm_recv` (attach usage + TTFB context).
- Tier A budget: hard 1ms; S1a and S4 operate on the touched blocks only (available from `BlockOutcome` list in the manifest), not the whole body. If a request's touched-content exceeds `cfg.inline_eval_max_bytes` (default 256 KiB), Tier A runs on a prefix + marks `confidence *= 0.5`.
- Emission: bounded mpsc → writer task (the `SpendEmitter` pattern: channel 10k, batch 100, flush 500ms, drop-with-warn + `proxy_eval_scorecards_dropped_total`).

### 6.3 Storage + Tier B sidecar

- **Store:** SQLite `~/.cutctx/scorecards.db` (WAL, like `SqliteCcrStore::open`), table `scorecards` mirroring §6.1 (signals as columns `s1_score, s1_conf, s1_tier, ...`), indexes on `(ts_unix_ms)`, `(strategy, content_type)`, `(tenancy_agent)`. Retention: `cfg.retention_days` default 30, lazy purge on write (CCR TTL-purge pattern).
- Config: `--eval-scorecards` / `CUTCTX_PROXY_EVAL_SCORECARDS` (default `off` first release), `--eval-db-path`, `--eval-sample-rate` (Tier B, default 0.05), `--eval-latency-budget-ms`.
- **Tier B sidecar:** a tokio task inside the proxy (not a separate process, v1) that drains a `tier_b` queue (sampled scorecard ids + original/compressed text captured at sample time), computes S1b term-recall (+ embedding if the `eval-embeddings` cargo feature is on) and S5 retrieval joins, and UPDATEs rows. Strictly lower priority: `tokio::task::yield_now` between items; queue bound 1000, sampled-out overflow dropped loudly.
- **S5 retrieval join:** the retrieve path (Rust `/v1/retrieve` if/when present; today Python `server.py:4142`) must log `(marker_hash, ts)` retrieval events. v1: Rust proxy writes a `retrievals` table in the same DB when its own CCR store serves a get for a marker-formatted key; Python-proxy deployments join offline via the Tier C tool.

### 6.4 Tier C offline runner (Python)

New `cutctx/evals/runners/scorecard_judge.py`:
- reads `scorecards.db` (+ CCR store for originals), samples N per (strategy, content_type) cell,
- computes `compute_answer_equivalence` / semantic similarity / output_reference,
- writes `s1c/s5c` columns back and emits a report via the existing `evals/reports/report_card.py` ("Verbatim Fidelity" label map already there),
- CLI: `cutctx evals scorecards --db ... --sample 50 --model ...` added to `cutctx/cli/evals.py`.

### 6.5 Aggregation + feedback

- New module `crates/cutctx-core/src/evals/aggregate.rs`: `StrategyReport { strategy, content_type, n, mean(sX), p10(s1), violation_rate }` computed over a sliding window (default 7 days) by SQL.
- **Confidence surface:** `fn strategy_confidence(strategy, content_type) -> Option<f32>` = `p10(s1_score)` gated on `n >= 200`. Exposed to:
  - the strategies selector (strategies spec §10.1 open question — v2 auto-tuning input),
  - `cutctx learn`: a new learn source that turns cells with `p10(s1) < 0.85` into `Recommendation` entries ("strategy X degrades content-type Y — consider denylisting via flags") written through the existing `cutctx/learn/writer.py` marker blocks,
  - the release gate: CI canary compares arms on mean(s2) and p10(s1) with the same CI≥95% discipline as `LIVE_SAVINGS_CANARY_RUNBOOK.md`.

## 7. Observability

Prometheus (metric_names.rs conventions, force-touch at boot):

- `proxy_eval_signal{signal, strategy, content_type}` — histogram of scores, buckets `[0.5, 0.7, 0.8, 0.85, 0.9, 0.95, 0.99, 1.0]`
- `proxy_eval_integrity_violation_total{check}` — counter (page-worthy)
- `proxy_eval_scorecards_total{tier}` / `proxy_eval_scorecards_dropped_total`
- `proxy_eval_tier_b_lag_seconds` — gauge, queue age

OTel: `cutctx.eval.quality`, `cutctx.eval.integrity_violations` (dotted, otel.rs pattern).

## 8. Testing

- **Parity (the critical suite):** golden corpus of (original, compressed, expected S1a) triples checked into `tests/fixtures/eval_parity/`; both Rust `evals/scorecard.rs` tests AND Python `tests/test_eval_parity.py` (recomputing with `compression_only.py` logic) must produce identical scores to 1e-6. Any drift fails CI.
- **Unit:** S4 checks against handcrafted corruptions (orphaned tool id, role swap, broken JSON, dangling marker) — each must score the specific check to 0 and fire the right violation counter.
- **Perf:** criterion — Tier A on p95-sized touched blocks < 1ms; end-to-end proxy overhead with eval on ≤ 2%.
- **Load:** 1k rps sustained, assert dropped-scorecards = 0 at defaults and DB size growth matches retention math.
- **Integration:** compress → retrieve the created marker → assert S5 retrieval_penalty reflected after Tier B pass.
- **Tier C:** smoke test on 10 fixture pairs with a stub LLM backend (LiteLLM fake), report renders via `report_card.py`.

## 9. Acceptance criteria

1. `--eval-scorecards on` at 1k rps: ≤2% latency overhead, zero dropped requests, zero integrity false-positives on the golden corpus.
2. Rust↔Python S1a parity suite green.
3. Scorecards queryable: `SELECT strategy, avg(s1_score), sum(tokens_before-tokens_after) FROM scorecards GROUP BY strategy` returns sane data after the e2e suite.
4. `cutctx evals scorecards` produces a report card with per-strategy fidelity, and a seeded low-fidelity cell produces a `cutctx learn` recommendation.
5. Dashboard spec's `/v1/evals/summary` contract (see `spec-eval-dashboard.md` §5.3) is servable from `aggregate.rs` output.

## 10. Implementation plan

1. `evals/scorecard.rs` types + S2/S3 + SQLite store + writer task. (~2 days)
2. S1a critical-preservation (port of verbatim_fidelity) + parity fixtures + Python parity test. (~2 days)
3. S4 structural checks + violation metrics. (~1.5 days)
4. EvalHook wiring + config + perf gate. (~1 day)
5. Tier B sidecar (term recall, retrieval join). (~2 days)
6. `aggregate.rs` + confidence surface + Prometheus. (~1 day)
7. Tier C Python runner + learn integration + report card. (~2 days)

## 11. Open questions

1. Capture of original/compressed text for Tier B sampling: store in scorecard DB (duplicates CCR) vs re-derive from CCR keys (misses reformat-only paths)? v1: sampled requests store both texts zstd-compressed in a `samples` table, capped 512 KiB/row, 7-day retention.
2. Should S4 tool-id check block the request (turn compression into passthrough) rather than just score? Strong candidate for v1.1 as a `GuardrailHook` mode once false-positive rate is measured at 0 for a full release cycle.
3. Multi-worker Python proxy parity — scorecard store is per-process; same caveat as the known `/stats` multi-worker instability (server.py:4675). Rust proxy is single-process so unaffected; document for Python follow-up.
