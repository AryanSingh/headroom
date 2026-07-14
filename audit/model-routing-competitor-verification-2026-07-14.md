# Model-routing competitor verification — 2026-07-14

This note distinguishes verifiable product capabilities from vendor positioning.
It is intentionally not a throughput ranking: no common hardware, workload,
upstream, or deployment topology was available for a fair cross-product claim.

## Reported claim: default learned ModernBERT routing

**Verdict: not verified.** The public [vLLM Semantic Router
README](https://github.com/vllm-project/semantic-router) describes
signal-driven, stateful routing and research into router models, but does not
substantiate the specific claim that it ships a default ModernBERT classifier.
The Envoy claim likewise needs a versioned primary-source configuration example
before it can be treated as a product gap.

Cutctx's now-safe position is explicit: the heuristic is the default; a
calibrated scorer is opt-in and is reported as heuristic, promoted, or invalid
by the authenticated routing-evidence API and dashboard. Promotion requires a
substantial deterministic holdout rather than a small lucky split.

## Reported claim: mature routing, state and durability

**Verdict: capability gap closed; operational-maturity claim cannot be closed
by code alone.** Cutctx shares orchestration state and routing evidence through
Redis, with cross-worker claim, lease-expiry/reclaim, and stale-worker safety
tests. LiteLLM's documentation describes its router and Redis deployment
options, but an install base or years of traffic is not a measurable feature
claim that can be proven from documentation.

The remaining action is an operational soak test with production-like traffic,
failure injection, and SLOs. It must report p50/p95/p99, error rate, worker
restarts, Redis outages, and routing-quality safety metrics. No product should
claim equivalent production maturity until that evidence exists.

## Reported claim: managed-dashboard / enterprise breadth

**Verdict: only partially comparable.** Bifrost's public
[README](https://github.com/maximhq/bifrost) advertises multi-provider access,
failover/load balancing, caching, access control, and budget controls. Those
are valid features to compare, not evidence that a managed-dashboard UX is
automatically better. Cutctx has the corresponding self-hosted routing
governance, model-routing evidence, RBAC/SSO configuration, budget/rate-limit
surfaces, and tested dashboard controls.

Managed hosting, commercial support, and enterprise sales are business
offerings, not missing proxy-routing code. Add them only with explicit product
scope and an operations/support commitment.

## Reported claim: Go implementation means higher performance

**Verdict: unproven.** Bifrost calls itself a high-performance AI gateway, but
language choice alone is not a meaningful request-path comparison. Cutctx now
has `benchmarks/proxy_request_benchmark.py`, which sends traffic through its
real OpenAI-compatible handler with a fixed local upstream. It records p50,
p95, p99, success/failure counts, requests/sec, and environment metadata. It
does not present in-process results as an external end-to-end comparison.

The next fair comparison must run each product as a network service, on the
same machine and provider mock, at fixed concurrency and payload sizes, with
the raw artifacts retained. Until then, no throughput advantage is accepted as
fact.

## Completed engineering actions

1. Require robust deterministic holdout evidence before scorer promotion.
2. Expose scorer readiness without leaking model artifacts or customer data.
3. Make orchestration and evidence state Redis-shareable, with worker-lease
   fault coverage.
4. Add a reproducible request-path benchmark and document its limitations.
5. Exercise routing controls in browser tests and verify the production build.

## Required operational follow-through

1. Run the benchmark as a network-service suite on pinned hardware and publish
   raw JSON artifacts for every release candidate.
2. Run a staged production canary with automatic rollback on unsafe-routing,
   error-rate, or p99 regression thresholds.
3. Revisit the learned default only after representative labeled evidence meets
   the promotion gate across customers and task distributions.
