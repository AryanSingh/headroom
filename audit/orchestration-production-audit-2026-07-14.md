# Orchestration production audit — 2026-07-14

Status: code-led + live verification. Supersedes the 2026-07-11 audit for anything touched by commit `e49ff7b6` ("harden model routing control plane"); items outside that diff are unchanged and not re-verified here.

## Method

1. Static read of `cutctx/orchestration/{engine,registry,service,models}.py`, `cutctx/proxy/model_router.py`, `cutctx/proxy/model_routing_evals.py`, `cutctx/proxy/routes/orchestration.py`, and the dashboard orchestrator pages, plus the diff introduced by `e49ff7b6`.
2. Live test: started the proxy from source on an isolated port (8799) with a scratch `CUTCTX_ORCHESTRATION_CONFIG`/`CUTCTX_ORCHESTRATION_DIR`, distinct from the two production proxy instances already running on 8787/8790 (untouched throughout, verified before and after).
3. In-process exercise of `classify_task_complexity` with representative prompts.
4. Competitive research against LiteLLM Router/Proxy, Portkey Gateway, Bifrost, Envoy AI Gateway, OpenRouter, and Not Diamond/Martian/Requesty.

## What's implemented (verified, not just documented)

- **Deterministic role→model binding, fail-closed strict mode.** Live: routing a configured role to a model that was never discovered by the registry returns `409 model_not_registered`; routing an undefined role returns `409 unassigned_role`. No silent substitution in either case.
- **Reliability-scored equivalent deployments.** `e49ff7b6` added a weighted rollout path: `_cohort_fraction` derives a stable per-request cohort from SHA-256(request_id)/2^256, then does cumulative-weight selection over eligible equivalents. Selection is bounded by health, rate-limit headroom, budget headroom, and latency — it never changes model identity or relaxes required capabilities.
- **Deployment cooldowns.** `registry.py` gained `cool_down` / `cooldown_remaining_seconds` / `clear_provider_cooldowns`, persisted in `metadata["cooldown_until_epoch"]`, lock-protected and self-expiring; wired into `service.py`'s `_cool_down_after_failure` on a real trigger set (timeout, rate limit, outage, auth failure, quota exhaustion). Config validation bounds `deployment_cooldown_seconds` to 1–3600s and rejects weight maps referencing anything other than the primary or declared equivalents.
- **Non-blocking shadow evaluation.** Shadow-eval calls in the Anthropic/OpenAI chat/responses handlers were converted from inline `await` to fire-and-forget `asyncio.Task`s with a draining done-callback (`schedule_model_routing_shadow`) — routing evaluation no longer adds latency to the primary response.
- **Routing evidence endpoint.** `GET /v1/orchestration/routing/evidence` is real and read-auth gated; live response returns a structured `no_evidence` state with sample thresholds (min 20 samples, 0.9 mean quality, 0.01 max unsafe rate) and per-dimension segmentation (client, task_type, model_pair, workspace_hash, repository_hash) — not a stub.
- **Direct-execution gating is structural, not decorative.** `/v1/orchestration/execute` and `POST /workflows/{id}/run` are only registered on the router inside `if direct_execution_enabled:` — confirmed live: 404 with the env var unset. When enabled they still carry the same admin auth + RBAC (`providers.write`) as every other write route.
- **Auth.** Confirmed live: unauthenticated request to `/v1/orchestration/providers` → 401.
- **Complexity classifier.** `classify_task_complexity` is an `IntEnum`-returning heuristic (regex/keyword), unchanged by this commit. Live test: "fix typo in README" → LOW, "add a docstring" → LOW, a multi-part distributed-consensus design request → HIGH, a traceback-bearing follow-up → HIGH. Conservative by design — defaults HIGH under ambiguity, holds out code/tool context and reference-dependent requests.
- **Durable local DAG workflows.** Dependency-ordered multi-task jobs with file-locked, lease-based at-least-once claiming; unchanged by this commit, not re-verified live this pass (static-only, matches 2026-07-11 audit description).
- No `TODO`/`FIXME`/`NotImplementedError`/stub markers found in any file touched by `e49ff7b6`.

## Gaps (confirmed, not fixed by this commit)

- **Single-host durability.** Both the workflow store and the routing-evidence/eval store are local JSON/JSONL files. No shared multi-host backend. This is a known, low-risk gap — LiteLLM already solved the equivalent problem for its own state via Redis, so the fix path is well-trodden.
- **Calibrated scorer rollout, not scorer implementation.** The audited runtime used the default heuristic, but the repository already provides an opt-in `LinearCalibratedTaskComplexityScorer`: it trains a privacy-safe logistic confidence artifact from shadow evidence, validates a deterministic holdout against quality, unsafe-rate, and heuristic-savings gates, and fails closed when an artifact is missing or invalid. The remaining gap versus learned-router competitors is operational adoption and richer model classes, not an absence of a learned path. See `cutctx/proxy/model_routing_training.py`, `benchmarks/model_routing_train.py`, and `tests/test_model_routing_training.py`.
- Process-local metrics/state noted in the 2026-07-11 audit (multi-worker horizontal scaling needs sticky sessions or shared stores) — out of scope for this diff, not re-verified.

## Competitive position (2026)

| Capability | cutctx | Field |
|---|---|---|
| Fail-closed strict-mode role binding | Yes | No competitor found with this — LiteLLM, Portkey, Bifrost, Envoy, OpenRouter, Not Diamond/Martian all degrade gracefully by design rather than refuse |
| Durable multi-step workflows (DAG, leases) | Yes | None of the above have this; all are single-request routing |
| Equivalent-deployment scoring (health+budget+latency, hashed cohort) | Composite, principled | LiteLLM: RPM/TPM-weighted random shuffle, re-rolled per call. Bifrost: closest analog (adaptive load balancer scoring error rate/latency/utilization) but Enterprise-only and lacks a budget-headroom dimension |
| Complexity classifier | Deterministic safety tier plus opt-in calibrated logistic confidence artifact | The default runtime remains heuristic until a promoted artifact is configured; richer learned intent/tier models remain a future differentiation area |
| Durability scope | Single-host JSON/JSONL | LiteLLM uses Redis for equivalent cross-instance state |

Sources consulted: LiteLLM routing/reliability/load-balancing docs, Portkey Gateway docs and GitHub, Bifrost GitHub and adaptive-load-balancing docs, Envoy AI Gateway capabilities docs, OpenRouter model-routing blog and pricing, Not Diamond's model-routing guide, and a 2026 comparative survey of LLM router/gateway products.

## Recommendation

Prioritize operationalizing the existing calibrated scorer before adding another model class: collect representative shadow evidence, train with `benchmarks.model_routing_train`, require the holdout gates to promote, configure `CUTCTX_MODEL_ROUTING_SCORER_ARTIFACT`, and monitor the authenticated routing-evidence endpoint. The durability gap remains real but low-risk and has an established Redis/Postgres migration path. A richer distilled intent/tier model should be evaluated only after calibrated-artifact rollout data shows the current bounded feature model is insufficient.

## Verification pass — 2026-07-14 (manual, real payloads)

Every item above was re-checked by constructing and executing real request/response payloads against the actual production classes (`DeterministicRoutingEngine`, `DynamicModelRegistry`, `WorkflowStateStore`, `ModelRoutingEvalStore`, `ModelRouter`, `train_linear_routing_artifact`), not by re-reading code or re-running the existing test suite. This also surfaced one code change that landed after this report was first drafted, which is reflected below.

**Confirmed correct, with concrete evidence:**

- **Weighted equivalent-deployment rollout.** Constructed a 3:1 weighted binding (`account-a` weight 3.0, `account-b` weight 1.0`) and routed 400 distinct `request_id`s: observed split was `account-a=308, account-b=92` (77.0%, target 75%). The same `request_id` routed 20 times landed on the same account every time. Matches the documented stable-cohort-hash design.
- **Cooldown exclusion.** Cooled down the primary deployment for 60s, then routed a fresh request: engine correctly selected the equivalent account and reported `selection_evidence.rejected = [{"model": "openai:account-a:shared-model", "reason": "cooling_down"}]`.
- **Strict mode never substitutes a different model.** Configured an "equivalent" pointing at a genuinely different model id; the engine ignored it and still assigned the original model to the original account — the differently-named model never entered the eligible set.
- **Strict mode fails closed rather than picking anything else.** An unavailable primary with no valid equivalent raised `RoutingUnavailableError` (`... cannot execute: unavailable`) instead of routing anywhere.
- **Calibrated-scorer fail-closed behavior.** Pointed `CUTCTX_MODEL_ROUTING_SCORER_ARTIFACT` at a nonexistent file: `ModelRouter` logged the load failure and fell back to `HeuristicTaskComplexityScorer` (confirmed by type). Pointed it at a freshly trained, valid artifact: `ModelRouter` loaded `LinearCalibratedTaskComplexityScorer` and produced a real calibrated confidence value distinct from the heuristic's binary signal.
- **Training pipeline runs and gates end-to-end.** Trained a real artifact from 200 synthetic-but-informative records (deterministic hash-based train/holdout split, gradient descent, holdout metrics); artifact round-tripped through `save()`/`load()` correctly.
- **HTTP-level auth, strict-mode error codes, and direct-execution gating**: re-confirmed live on a fresh isolated proxy instance (401 unauthenticated, 409 `model_not_registered`/`unassigned_role`, 404 on `/execute` without the dev-only env var).

**Correction to this report — multi-host durability gap is now closed.** Commit `a0bd945a` ("share orchestration state through redis", 2026-07-14 13:17, landed after this report's original draft) added an optional Redis backend to both `WorkflowStateStore` and `ModelRoutingEvalStore` (`CUTCTX_ORCHESTRATION_REDIS_URL`). This was verified live against a real Redis instance, not just read: two independently constructed `WorkflowStateStore` instances (simulating two hosts) shared a submitted workflow immediately, and a distributed Redis lock correctly prevented both hosts from claiming the same task (`host_b` claimed it, `host_a`'s subsequent claim attempt correctly returned `False`). Two independent `ModelRoutingEvalStore` instances shared a written evidence record across the same mechanism. **The "single-host durability" gap listed above should be considered resolved as an opt-in feature**, not merely a low-risk future fix — it still defaults to local JSON/JSONL when the env var isn't set, so single-host remains the out-of-the-box behavior, but the distributed path exists and works.

**New finding — the training holdout gate is weaker against small/noisy samples than its description implies.** Training `train_linear_routing_artifact` on 200 records with deliberately non-informative (pure noise) features — i.e., a case that should be rejected by the "must not underperform the heuristic baseline" check — did **not** raise `ValueError`. It promoted an artifact with `selected_samples: 8` out of a 52-record holdout, `selected_unsafe_rate: 0.0`, satisfying the configured quality bar. Root cause: the rejection gate compares against a heuristic baseline computed from the same synthetic records, which was already degenerate in this test (a uniform `confidence=1.0` produced `heuristic_holdout_unsafe_rate: 1.0`/`heuristic_holdout_savings_usd: 0.0`, the worst possible baseline), so almost any learned threshold "beats" it. More importantly, the promotion path performs a confidence-threshold search over a modest holdout set (52 records here; the code's own default `minimum_samples`/`minimum_segment_samples` is 20) and can find a small subset (8 of 52) that happens to satisfy the quality/unsafe-rate bar by chance even when the underlying features carry zero real signal. This is a plausible overfitting/multiple-comparisons risk for real deployments with small live shadow-evidence volumes, not a fabricated defect — it did not trigger on a deliberately adversarial input in a live run. Recommend adding a statistical-significance or minimum-lift check (e.g., against a properly computed heuristic-only baseline, plus a confidence interval on the selected subset) before trusting small-sample promotions in production, and treating `minimum_samples: 20` as a floor to raise rather than a validated production threshold.

## Re-verification pass — 2026-07-14 (later, after fixes)

Commits `100f062a`, `90084a0f`, `d6ad1ee3`, `3b1c89ed` landed after the previous verification pass. Each is re-tested below with fresh, independently-constructed payloads (not the shipped test suite).

- **Training-gate fix confirmed.** Re-ran the exact pure-noise repro from the prior pass (same seed, same synthetic feature generator) against the patched `train_linear_routing_artifact`: it now raises `ValueError: At least 10 selected holdout records are required for scorer promotion; found 1`. The genuine-signal case still promotes (11 selected, above the new floor) — no regression. **Fixed, verified.**
- **Lease-expiry / stale-worker rejection confirmed**, independently of the shipped test: two `WorkflowStateStore`s sharing a live Redis instance, 1s lease — worker B reclaimed the task after expiry, and worker A's late `mark_task_completed` was correctly rejected (`task is not running`). **Verified.**
- **Scorer-readiness endpoint confirmed**, live over HTTP on a fresh isolated proxy instance, across all three states: no artifact configured → `{"status": "heuristic", "configured": false}`; a corrupt artifact file → `{"status": "invalid", "configured": true}` with no local file path leaked in the response; a freshly trained valid artifact → `{"status": "promoted", "configured": true, "training_samples": 200, "minimum_confidence": ..., "quality_floor": 0.8}`. **Verified.**
- **`audit/model-routing-competitor-verification-2026-07-14.md`** (added in `3b1c89ed`) is a fair self-critique of the earlier competitor comparison — it correctly declines to accept the "Envoy/vLLM ships a default ModernBERT classifier" and "Bifrost's Go implementation is faster" claims as verified, since neither was checked against a primary source or a controlled same-machine benchmark. That caution is warranted and is reflected in the updated competitive judgment below.

### Critical finding: the real request path is bottlenecked on synchronous disk fsync + full-state JSON re-serialization inside a process-wide lock

Running the new `benchmarks/proxy_request_benchmark.py` (added in `d6ad1ee3`) against the actual OpenAI-compatible handler, with cache/rate-limit/cost-tracking disabled and a fixed instant upstream, produced a flat throughput ceiling regardless of concurrency:

| Concurrency | Requests | p50 | Requests/sec |
|---|---|---|---|
| 1 | 20 | 138 ms | 7.25 |
| 5 | 50 | 656 ms | 7.66 |
| 20 | 200 | 2,676 ms | 7.30 |

Median latency scales almost exactly linearly with concurrency while throughput stays flat at ~7.3–7.7 req/s — the signature of full serialization, not natural per-request cost. Profiling the same in-process benchmark with `cProfile` (20 requests, concurrency 1) showed **96% of total wall time** (12.8s of 13.27s) inside `savings_tracker.py:_save_locked` → `json.dumps`, called from `record_request` on every single request via `emit_request_outcome` → `prometheus_metrics.record_request`.

Root cause, confirmed by reading the code: `SavingsTracker.record_request` is an `async def` that runs directly on the event loop (never dispatched via `asyncio.to_thread`/an executor), acquires a plain `threading.Lock()` (`savings_tracker.py:1122`), and inside that lock calls `_save_locked()`, which re-serializes the **entire** persisted state (`lifetime`, `history`, `projects`, `models`, `clients`, `shadow_checks`) with `json.dumps(indent=2)` and then calls `os.fsync()` — synchronous, blocking disk I/O — before releasing the lock. Because this runs in the coroutine body itself, it blocks the whole single-threaded event loop for its duration, not just the requests contending for the lock. `history` is bounded (`_max_history_points`), so this is not unbounded quadratic blowup, but it is still a full-state re-encode plus an fsync on every request, which is enough on its own to explain the measured ~130–150ms floor per request at low concurrency and the complete failure to scale with concurrency.

This is unrelated to Python vs. Go — it would serialize a Go proxy the same way if it held a mutex across a blocking fsync in the request path. It is an architecture bug: hot-path state should be durably persisted asynchronously/batched (e.g., off the event loop via a background writer, or an append-only log instead of full-state rewrite-and-fsync per request), not synchronously on every request under a single process-wide lock.

**This materially changes the earlier "best in market" performance judgment.** The prior competitive answer treated Bifrost's Go-implementation performance claim as an unverified, and possibly overstated, marketing claim — that skepticism was reasonable and is echoed in `audit/model-routing-competitor-verification-2026-07-14.md`. But this pass found a concrete, measured, reproducible cutctx-side bottleneck capping the real request path at roughly 7–8 requests/sec per process even with every optional subsystem (cache, rate limiting, cost tracking) disabled and an instant local upstream. Until this is fixed, any throughput comparison against LiteLLM/Bifrost/Portkey/Envoy should be assumed to favor them, not cutctx, on raw request-path throughput — the routing/durability/strict-mode advantages documented above are real, but they currently sit on top of a request path with a hard, verified low ceiling.

**Recommendation, added to the priority list above this section:** move savings/outcome persistence off the synchronous request path — batch writes, debounce fsync frequency, or hand the write to a background task/thread — before making any throughput claim, and before the benchmark harness above is used for a publishable comparison. This is now a higher-priority fix than either the multi-host durability work (already resolved via Redis) or the calibrated-classifier rollout, because it caps throughput for every request regardless of routing configuration.

## Re-verification pass — 2026-07-14 (savings persistence fix, commits `d41aec2d`/`e5b95d5f`)

**Fix confirmed to resolve the flat throughput ceiling.** `SavingsTracker` now takes a `persistence_mode` (`"sync"` retained as the direct-library default; `PrometheusMetrics` now constructs it with `persistence_mode="async"`). In async mode, `_save_locked` no longer does `json.dumps`+`fsync` on the caller's thread — it appends a small journal patch (dict of just the changed top-level fields, plus the newest history/shadow entry) to an in-memory list and notifies a dedicated background writer thread (`cutctx-savings-writer`), which append-only writes+fsyncs the journal on a debounced ~250ms interval (`DEFAULT_SAVINGS_FLUSH_INTERVAL_SECONDS`). Full-state snapshot rewrite only happens periodically via journal compaction, on `close()`, or when `history_response()` is called (an explicit durability boundary for read-your-writes on `/stats-history`).

Re-ran the identical `benchmarks/proxy_request_benchmark.py` methodology (100 req, warmup 10) at the same concurrency levels used in the prior pass:

| concurrency | before (req/s) | after (req/s) | before p50 | after p50 |
|---|---|---|---|---|
| 1  | 7.25 | 210.9 | 138ms  | 4.2ms |
| 5  | 7.66 | 486.2 | 656ms  | 9.5ms |
| 20 | 7.30 | 279.5 | 2676ms | 54.4ms |

Throughput now scales with concurrency instead of flatlining — a 29x–63x improvement, and the request-path is no longer capped regardless of load. Independently reproduced the same effect at the `SavingsTracker` unit level (bypassing HTTP entirely): 200 direct `record_request()` calls averaged 4.64ms/call in `persistence_mode="sync"` vs 0.125ms/call in `persistence_mode="async"` in the same script — a ~37x reduction in caller-thread cost, consistent with the HTTP-level numbers and confirming the win is the persistence change itself, not benchmark noise.

**Durability was checked, not assumed.** Constructed real `SavingsTracker(persistence_mode="async")` instances directly (not via the shipped `tests/test_savings_hot_path.py`) and verified:
- Journal replay on restart: wrote 50 records, waited past one debounce window (no explicit flush), then loaded a **second** independent tracker instance pointed at the same path — it correctly recovered all 50 requests via `_replay_journal`, matching the live instance's in-memory count.
- Graceful shutdown durability: calling `close()` (which `server.py` now invokes on proxy shutdown, per `d41aec2d`) flushes all pending writes, joins the writer thread, and compacts the journal into the main JSON snapshot (`0` bytes remaining) — recovered lifetime count on disk matched exactly.

**Residual finding (disclosed trade-off, not a regression):** a true hard-kill (SIGKILL/OOM/power loss) that does not run `close()` can lose up to one debounce window (~250ms) of the most recent writes — verified directly: fired 10 `record_request()` calls with no `close()`/`flush()`/sleep and dropped the reference immediately, and only 2 of 10 had reached the journal on reload. This is an explicit, bounded trade-off inherent to any debounced/batched persistence design, not a bug — the previous synchronous design had zero data-loss window but capped throughput at ~7 req/s for every request regardless of load. Graceful shutdown (`SIGTERM` → `close()`, already wired into `server.py`) is fully durable; only an ungraceful process kill is exposed to the bounded window. Worth stating explicitly in any customer-facing durability claim rather than leaving implicit.

**Net assessment:** this closes the critical performance finding from the prior pass. The request path no longer has an artificial ~7-8 req/s ceiling, and the durability mechanism (write-ahead journal + periodic compaction + explicit flush boundaries on shutdown/history-read) is sound and independently verified. The only remaining action is documenting the bounded ungraceful-crash data-loss window in operator-facing docs, and re-running the benchmark as a network-service comparison (per the competitor-verification doc's "Required operational follow-through") now that the in-process ceiling is gone.
