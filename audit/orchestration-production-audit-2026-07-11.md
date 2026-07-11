# Orchestration production audit — 2026-07-11

Status: active remediation. This review is code-led; product claims were not treated as proof.

## Execution architecture observed

The production path is a request-time proxy pipeline:

`OpenAI/Anthropic compatibility handler → model_router.prepare_model_routing → optional role binding → provider transport → request outcome telemetry`.

`cutctx/orchestration/` provides deterministic role/selector assignment, encrypted credentials, a model registry, LiteLLM-backed provider adapters, retries, execution telemetry, and a durable local DAG runner. `memory/subagent.py` remains context handoff only; durable workflow scheduling is implemented in `orchestration/workflow.py`.

## Findings

| Severity | Finding | Evidence | Status |
|---|---|---|---|
| Critical | Batch opt-in could return HTTP 202 for an in-memory queue with no worker, provider submission, poll route, persistence, or restart recovery. | `proxy/batch_router.py` had only `route()` and manual `mark_completed()`; handlers short-circuited requests. | Fixed: eligible traffic now fails-safe to synchronous passthrough and cannot claim batch savings. |
| High | Generic cheap-model routing did not prove that the target was supported by the current subscription transport. | `model_router.py` routes by requested model and prompt heuristic; `responses.py` resolves ChatGPT subscription transport only afterward. | Fixed: subscription traffic retains its requested model; only an explicit account-scoped orchestration binding may select a target. |
| Medium | Multi-host workflow execution needs a shared transactional backend. | `workflow.py` uses file-locked JSON state and renewable fencing leases, which are correct for one host or a shared POSIX volume. | The original High missing-DAG finding is fixed: durable DAG execution, checkpoints, retry/backoff, timeouts, cancellation, resumability, and local multi-process ownership now exist. Adopt a shared workflow store before claiming cross-host worker scheduling. |
| Medium | Request-time direct execution has append-only telemetry rather than durable job state. | `ExecutionTelemetryStore` persists JSONL after synchronous execution. | The original High job-state gap is fixed for workflows through authenticated durable submit/status/cancel/run APIs. The synchronous diagnostic endpoint remains explicitly opt-in and is not represented as a resumable job. |
| High | User-visible dashboard enablement previously activated a legacy router with no Terra-to-Mini route. | Runtime config flags constructed `ModelRouter()` when no preset was configured. | Fixed: dashboard activation loads `codex-gpt54mini-high`; covered by `test_dashboard_orchestrator_toggle_loads_codex_mini_preset`. |
| Medium | Complexity routing is a small heuristic rather than a learned classifier, with no outcome feedback loop. | `classify_task_complexity` in `proxy/model_router.py`. | Partially remediated: it now holds out multimodal content, code/tool context, multi-turn state, ambiguous references, and architecture/review/planning work; uncertain tasks retain the requested model. Add outcome-calibrated routing before making routing more aggressive. |
| Medium | Multi-worker state is process-local for several context and metrics subsystems. | Explicit warnings in `proxy/server.py` around lines 7186–7215. | Open: require sticky sessions or durable shared stores before horizontal orchestration. |
| Medium | Provider fallback is deterministic and bounded, but streaming cannot recover after bytes are emitted. | `OrchestrationService.stream`. | Fixed within protocol limits: provider/account setup, iterator construction, first-byte failures, and total-attempt timeouts now retry/fallback and record telemetry. After a byte is emitted, the stream intentionally fails rather than splice output from another provider. Cancellation closes the iterator and records the termination. |

## Verified work in this remediation

- Dashboard routing activation loads the canonical `gpt-5.6-terra → gpt-5.4-mini` preset.
- Exact account-scoped routing no longer records a false fallback.
- OpenCode Go is registered as a first-class OpenAI-compatible provider.
- OpenAI internal Codex Lite headers are stripped before forwarding.
- Batch opt-in is safe until a durable executor exists.
- Workflow submissions retain their immutable task definition and payload, recover interrupted tasks at-least-once, and expose bounded retry/cancellation semantics through `/v1/orchestration/workflows`.

## Routing audit

- Selection is deterministic: selector bindings sort by specificity, documented selector precedence, then binding ID. Capability, availability, deprecation, and account enablement are checked before an assignment is returned.
- Strict mode is non-relaxable through data-plane input; role-locked policy refuses unconfigured fallbacks. Relaxed mode walks a deduplicated candidate chain and records each attempted deployment, preventing fallback loops.
- Compatibility endpoints fail closed when the configured provider or account cannot be proven. Subscription traffic does not receive an implicit cheap-model rewrite.
- Cost routing is deliberately conservative. The mini preset holds out multimodal, code/tool, multi-turn, ambiguous, planning, review, and architecture requests; only clear low-complexity turns are eligible.

## Orchestrator and failure analysis

- Workflows validate DAGs, persist immutable definitions and idempotency fingerprints, run ready work with bounded concurrency, and preserve dependency ordering.
- File-locked state transitions, renewable local leases, fencing epochs, and release-on-runner-cancellation prevent duplicate local-worker ownership. Expired leases recover at-least-once; downstream side effects must carry an idempotency key.
- Provider execution has bounded retries, typed fallback triggers, per-task timeouts, and provider/account failover before stream output. Streaming never mixes provider output after the first byte.
- Cancellation closes in-flight stream iterators and emits telemetry. Workflow cancellation cancels local child tasks and leaves work safely resumable.

## Context, UX, configuration, and performance analysis

- The canonical compatibility pipeline retains existing compression, cache, firewall, memory, rate-limit, audit, and outcome paths. The development-only direct executor is explicitly isolated so it cannot silently bypass production policy.
- Workflow status exposes task state and result through authenticated APIs. Operators can see routing reason, assigned/actual model, provider, fallback, latency, and errors in execution telemetry.
- Configuration precedence is global → user → workspace → project. Merged candidates are validated before atomic persistence; strict settings cannot be relaxed by untrusted request input.
- Routing is in-memory and deterministic. Workflow scheduling intentionally favors correctness over throughput: each transition is durable and file-locked. For high-rate or multi-host use, replace the JSON state store with a shared transactional backend.

## Competitive gap analysis and prioritized action items

The implemented layer now matches the core reliability expectations of developer agents—deterministic model-role enforcement, safe fallback, durable local workflow execution, cancellation, retries, timeout handling, and observable progress—without embedding another agent UI or model policy engine.

1. **Medium:** introduce a shared transactional `WorkflowStateStore` implementation for multi-host worker fleets.
2. **Medium:** calibrate routing eligibility from outcome data before expanding cheap-model coverage.
3. **Low:** add first-class planner/reviewer/merge task templates above the generic role workflow API; keep their model assignments declarative.
4. **Low:** add workflow queue-delay and lease-contention metrics for capacity planning.

## Risk assessment

- At-least-once recovery can repeat an external side effect after a crash; downstream task operations need idempotency keys.
- JSON state is intentionally limited to one host or a correctly shared POSIX volume. It is not a distributed database.
- Stream continuation after an emitted byte is impossible without corrupting protocol semantics; the system reports a terminal error instead of switching providers mid-response.
- Cheap-model routing prioritizes quality under uncertainty by retaining the requested model, which may reduce savings until outcome calibration is available.

## Verification report

- Full project Python suite: concise `rtk test uv run pytest -q` completed successfully.
- Focused orchestration verification: 65 API/platform/workflow tests passed, including DAG ordering, retries, timeout, cancellation, lease fencing, idempotency conflict, account setup fallback, first-byte fallback, stream deadline, and stream cancellation.
- Focused routing verification: 85 model-router, Codex header-isolation, and subscription-compatibility tests passed.
- Dashboard verification: API toggle tests and Playwright orchestrator toggle test passed; the live proxy served `/dashboard/orchestrator` and the rebuilt dashboard asset successfully.
- Static checks: Ruff and `git diff --check` passed.
