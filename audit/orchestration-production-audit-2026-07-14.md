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
