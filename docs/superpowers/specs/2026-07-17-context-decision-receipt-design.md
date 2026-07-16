# Context Decision Receipt Design

## Goal

Turn the existing request-trace inspector into an auditable context-decision receipt. For any completed proxy request, an operator must be able to determine what Cutctx changed, why it changed or abstained, what evidence constrained the decision, which savings source received credit, and which facts were unavailable.

The receipt is a provider-neutral observation contract. It records decisions already made by compression, caching, CCR, routing, fallback, and policy components; it does not make or recompute those decisions.

## Current state

Cutctx already has the core product surface:

- `ModelRoutingDecisionTrace` emits a versioned routing decision with candidates, rejected candidates, capability requirements, confidence, transport proof, and selection evidence.
- `RequestOutcome` unifies completed-request observations and the request logger persists a bounded JSONL history.
- `/transformations/traces` and `/transformations/traces/{request_id}` expose structured traces behind local-admin authentication.
- the Overview page opens a request-trace inspector with routing summary, attributed savings, timings, fallback state, and optional before/after payloads.

The missing link is persistence and presentation. The outcome funnel currently reduces `model_routing_trace` to a small `routing_metadata` summary, cache observations are partly collapsed into booleans, CCR references are not part of the request record, and the API reconstructs a trace from fields with ambiguous zero/false defaults. The dashboard therefore cannot explain outcomes such as `workload_not_downgradeable` with the evidence that produced them.

## Chosen design

Build one end-to-end, additive receipt contract and render it inside the existing inspector. Do not introduce a second trace store, dashboard route, policy engine, or payload logging requirement.

### 1. Stable receipt contract

Every newly persisted `RequestLog` will carry an optional `decision_receipt` object with `schema_version: 1`. The trace API returns that object verbatim under `trace.decision_receipt`. Older JSONL rows without a receipt remain readable; the trace builder creates a clearly marked legacy summary for them but never pretends missing evidence was observed.

The version 1 shape is:

```json
{
  "schema_version": 1,
  "request_id": "req_123",
  "observation": {
    "completeness": "complete|partial|legacy",
    "missing": ["ccr.retrieval_outcome"],
    "payload_capture": "disabled|redacted|captured"
  },
  "routing": {
    "status": "applied|retained|not_evaluated|unobserved",
    "reason": "workload_not_downgradeable",
    "explanation": "Recent tool context is classified as high-risk, so Cutctx retained the requested model.",
    "requested_model": "gpt-5.4",
    "effective_model": "gpt-5.4",
    "mechanism": "optimization_preset",
    "confidence": 0.93,
    "scorer": "heuristic_v1",
    "required_capabilities": ["tool_calling"],
    "candidates": ["gpt-5.4-mini"],
    "rejected_candidates": [{"candidate": "gpt-5.4-mini", "reason": "workload_not_downgradeable"}],
    "transport": {},
    "selection_evidence": {},
    "request_overrides": null
  },
  "compression": {
    "status": "applied|abstained|not_evaluated|unobserved",
    "reason": null,
    "input_tokens_original": 1500,
    "input_tokens_forwarded": 1000,
    "direct_tokens_saved": 500,
    "transforms": ["smart_crusher"],
    "protected_content": {
      "cache_protected_tokens": 200,
      "signals": ["recent_tool_context"]
    }
  },
  "cache": {
    "provider_prompt_cache": {"status": "hit|miss|unobserved", "read_tokens": 200, "write_tokens": 0, "inferred": false},
    "semantic_response_cache": {"status": "hit|miss|unobserved", "saved_tokens": 0},
    "self_hosted_prefix_cache": {"status": "hit|miss|unobserved", "saved_tokens": 0},
    "cache_safe_prefix": {"status": "protected|not_protected|unobserved", "protected_tokens": 200}
  },
  "ccr": {
    "status": "available|expired|missing|not_used|unobserved",
    "references": [{"hash": "abc123", "availability": "available|expired|missing|unobserved", "expires_at": null}],
    "retrieval_outcome": "retrieved|not_requested|failed|unobserved"
  },
  "attribution": {
    "total_saved_tokens": 700,
    "created_savings_tokens": 500,
    "observed_provider_savings_tokens": 200,
    "by_source_tokens": {"cutctx_compression": 500, "provider_prompt_cache": 200},
    "by_source_usd": {},
    "savings_basis": "estimated",
    "pricing_basis": "model_input_list_price"
  },
  "policy": {
    "routing_policy": null,
    "routing_mode": null,
    "config_fingerprint": "sha256:...",
    "cutctx_version": "0.31.0"
  }
}
```

Optional values remain JSON `null`; observation status fields distinguish `unobserved` from an observed zero, miss, or no-op. Receipt consumers must use the status rather than infer truth from numeric defaults.

### 2. Receipt creation and persistence

Add a focused `cutctx.proxy.decision_receipt` module that owns:

- the schema version and stable status vocabulary;
- normalization of an existing `model_routing_trace` into receipt routing evidence;
- plain-language explanations for stable reason codes;
- cache observation classification;
- CCR reference normalization;
- receipt completeness and missing-evidence calculation;
- a deterministic fingerprint of decision-relevant, non-secret configuration.

`emit_request_outcome` is the single construction point because it already has the normalized outcome, final savings attribution, request logger, and proxy handler/config. It must extract the full `model_routing_trace` from `outcome.savings_metadata`, combine it with typed outcome observations, build the receipt, and persist it on `RequestLog`.

Two existing paths write `RequestLog` directly: rate-limit denials and the OpenAI Responses WebSocket session summary. They must call the same receipt builder with their limited typed observations. Their receipts are intentionally partial, but no new request-log row may bypass receipt construction. Warm-loading old JSONL rows remains the only source of receipt-less legacy entries.

The configuration fingerprint includes only normalized controls that materially affect compression, routing, cache protection, CCR, and policy mode. It excludes credentials, URLs containing credentials, paths, payloads, arbitrary headers, tenant secrets, and raw environment values. Keys are sorted before hashing so equivalent configuration produces the same fingerprint.

### 3. Routing evidence

The receipt persists the complete existing `model_routing_trace`; it does not reproduce the router's logic. If only legacy `model_routing` summary metadata exists, the receipt records the summary and marks routing evidence partial.

Plain-language explanations are deterministic copy mapped from reason codes. The first set covers the reason codes already documented for routing presets, including:

- `workload_not_downgradeable`: the request contained high-complexity or high-risk work, including recent tool context, so the requested model was retained;
- `confidence_below_threshold`: routing evidence was insufficient to justify a downgrade;
- `target_missing_capabilities`: the candidate lacked proof for required request capabilities;
- `downgrade_blocked_unproven_transport`: the candidate transport or account could not be proven safe;
- `low_complexity` or `downgrade_applied`: the compatible lower-cost target passed the configured gates;
- `no_route_for_model`: the active policy had no eligible target for the requested model.

Unknown reason codes render a neutral fallback and retain the raw code.

### 4. Cache evidence

Do not use the existing combined `cache_hit` boolean as the receipt's source of truth. Persist typed observations already present on `RequestOutcome`: provider read/write counters and inferred-write flag, semantic-response-cache hit and avoided tokens, self-hosted prefix-cache tokens, and cache-protected tokens.

An observed provider usage response with zero read tokens is a `miss`; absence of provider cache usage evidence is `unobserved`. A semantic cache decision explicitly evaluated with no hit is a `miss`; handlers that never evaluate semantic cache remain `unobserved`. This requires an explicit evaluated flag where the current outcome cannot distinguish those states.

Provider cache savings remain observed provider savings and must never be added to Cutctx-created savings.

### 5. CCR evidence

Add provider-neutral CCR observation fields to `RequestOutcome` with neutral defaults: references, availability when checked, and retrieval outcome. Handler/compression paths populate references from actual inserted CCR markers or compressor results, even when full message logging is disabled. The receipt stores hashes and status only, never retrieved content.

CCR insertion and retrieval paths thread the status they actually observed into the outcome, including expiry when the store exposes it. Receipt construction does not perform a new store lookup on the response-finalization path. The persisted field is availability at request completion, not a promise that the entry remains available when the trace is viewed later. Retrieval outcomes already known during CCR continuation are threaded into the outcome. When no CCR transform or reference occurred, status is `not_used` rather than `missing`.

This milestone does not promise historical retrieval outcomes for requests completed before the receipt existed.

### 6. Payload privacy and redaction

The receipt is useful with `log_full_messages=False`, which remains the default. It stores decision metadata, counts, hashes, reason codes, and safe configuration identity—not prompts, responses, protected text, tool output, or retrieved CCR content.

`payload_capture` means:

- `disabled`: full message logging was disabled;
- `redacted`: payload capture was enabled and one or more payload values were replaced by the request logger's redactor;
- `captured`: payload capture was enabled and no supported redaction was applied.

The request logger's redaction helper will return or expose per-entry redaction evidence so this state is based on the current entry rather than the process-wide counter. Because redaction happens inside `RequestLogger.log`, that method may update only `decision_receipt.observation.payload_capture` before the row is appended or serialized; it must not alter any other receipt evidence. The existing payload cards remain governed by local-admin authentication and `log_full_messages`.

### 7. Trace API compatibility

The existing endpoints and response fields remain intact. `trace.decision_receipt` is additive.

- New rows return the persisted version 1 receipt.
- Legacy rows return a derived `legacy` receipt containing only directly supported fields and a `missing` list.
- Unknown future schema versions are returned without destructive normalization so clients can display raw data or an unsupported-version state.
- The endpoint remains protected by `_require_local_admin_auth`.
- Trace list limits and bounded request-log retention remain unchanged.

### 8. Dashboard presentation

Extend `RequestTraceInspector` in the Overview page. Do not add a new route in this slice.

The top of the inspector becomes a concise decision summary:

- a status badge: routed, retained, compressed, abstained, cached, or partial evidence;
- the plain-language explanation, with the raw reason code adjacent;
- requested and effective model;
- direct Cutctx savings and observed provider-cache savings shown separately;
- an evidence-completeness indicator.

Below the summary, render collapsible evidence groups:

1. Routing evidence: mechanism, confidence, scorer, capabilities, candidates, rejected candidates, transport proof, selection evidence, and request overrides.
2. Context and compression: before/forwarded tokens, transforms, decline reason, protected-token count, and protection signals.
3. Cache and attribution: per-cache status, cache-safe-prefix state, created versus observed savings, and source totals.
4. CCR: references, availability/expiry, and retrieval outcome.
5. Policy and privacy: routing policy/mode, safe config fingerprint, Cutctx version, payload-capture state, and missing evidence.

Sensitive payloads remain in the existing separate payload section and are not automatically expanded.

### 9. Error handling

- Receipt construction is observation-only and must never fail or delay the customer request. Unexpected builder failures log a sanitized warning and persist a minimal partial receipt when possible.
- CCR status lookup is bounded, local, best-effort, and skipped when there are no references.
- Malformed legacy routing or cache metadata is treated as missing evidence.
- The dashboard renders unknown status/reason values as neutral text and offers the raw JSON evidence; it must not crash on additive fields.
- Trace endpoint errors retain the current inspector error state.

## Boundaries and non-goals

- Do not change compression, routing, cache, fallback, CCR retrieval, or policy decisions.
- Do not introduce a separate analytics database or distributed trace store.
- Do not enable full message logging or persist new payload content.
- Do not add automatic policy promotion, threshold tuning, benchmark execution, or quality claims.
- Do not build a new dashboard page, graph memory system, or generic observability platform.
- Do not claim every evidence field is available for every provider; unavailable evidence must be explicit.

## Verification path

Implementation follows red-green-refactor at three boundaries.

### Schema and builder tests

- A complete routed outcome produces schema version 1 with full routing evidence, separated created/observed attribution, cache observations, policy identity, and no payload content.
- A retained recent-tool request produces `workload_not_downgradeable` with the expected explanation and rejected candidate evidence.
- Missing provider usage becomes `unobserved`, while an explicitly observed zero becomes `miss`.
- CCR references remain available when message logging is disabled and never include retrieved content.
- Config fingerprints are stable across key ordering and change when a decision-relevant control changes; secrets do not affect or appear in the receipt.
- Malformed or partial metadata yields a parseable partial receipt rather than an exception.

### Proxy and persistence tests

- A real proxy request writes a receipt to `RequestLogger`, survives JSONL serialization and warm restart, and is returned unchanged by the detail endpoint.
- A legacy `RequestLog` without a receipt returns a `legacy` receipt with an accurate missing-evidence list.
- Admin authentication remains required.
- Full-message logging disabled still returns the complete non-payload receipt and `payload_capture: disabled`.
- Savings source totals reconcile exactly and provider cache is not counted as Cutctx-created savings.

### Dashboard tests

- Playwright opens a retained request and sees the plain-language explanation for `workload_not_downgradeable`, raw reason code, rejected candidate, capability/transport evidence, cache states, CCR state, policy fingerprint, and privacy state.
- A partial/legacy receipt renders its missing-evidence warning without fabricating misses or zeroes.
- Payload cards remain absent or show the existing no-capture state when full logging is disabled.
- Unknown additive fields and reason codes do not break rendering.

### Regression checks

- focused decision-receipt, request-logger, request-trace API, model-router, and Overview Playwright tests;
- Python formatting, Ruff, and MyPy for changed modules;
- dashboard lint and production build;
- existing request-outcome, routing-trace, cache-attribution, CCR, and dashboard trace tests.

## Acceptance criteria

1. Every newly logged completed request has a parseable version 1 receipt or a sanitized partial receipt if observation construction fails.
2. The receipt explains `workload_not_downgradeable` from persisted routing evidence rather than dashboard inference.
3. Observed misses, observed hits, no-ops, and unobserved evidence are distinct.
4. Cutctx-created savings and provider-observed savings reconcile without double counting.
5. CCR references and status can be inspected without enabling full payload logging.
6. No secrets or new prompt/response content enter the receipt or configuration fingerprint.
7. Existing trace API consumers remain compatible.
8. The existing Overview inspector renders the receipt end to end and remains usable for legacy rows.

## Follow-on work

Once version 1 receipts are operating, later milestones may add receipt export, trace-to-evaluation linking, replay verdicts, workload-contract simulation, fleet aggregation, retention controls, and a dedicated Decision Explorer page. Those features must consume the stable receipt rather than introduce parallel evidence formats.
