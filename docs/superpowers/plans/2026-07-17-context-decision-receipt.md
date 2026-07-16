# Context Decision Receipt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist and render a versioned, privacy-safe decision receipt that explains each Cutctx request's routing, compression, cache, CCR, attribution, policy, and evidence completeness.

**Architecture:** Add a pure provider-neutral receipt builder, feed it from the canonical `RequestOutcome` funnel, persist the resulting dictionary on `RequestLog`, and return it unchanged through the existing trace API. Existing request rows are adapted to an explicit legacy receipt, and the current Overview inspector renders the same contract without requiring full payload logging.

**Tech Stack:** Python 3.11+, dataclasses, FastAPI, JSONL request logging, React 19, Vite, pytest, Ruff, MyPy, and Playwright.

## Global Constraints

- Receipt schema version is exactly `1`; changes to version 1 are additive only.
- Observation states distinguish `hit`, `miss`, `not_used`, and `unobserved`; numeric zero is not evidence by itself.
- The receipt must not contain prompts, responses, tool outputs, retrieved CCR content, credentials, secret headers, secret configuration, or raw environment values.
- `log_full_messages=False` remains the default and must still produce useful receipts.
- Provider prompt-cache savings remain observed provider savings and must not be counted as Cutctx-created savings.
- Receipt creation is observation-only and must never change routing, compression, cache, CCR, fallback, or policy behavior.
- Existing `/transformations/traces` fields and authentication remain compatible.
- No new runtime dependency, database, dashboard route, or background service is introduced.
- All shell commands in this repository are prefixed with `rtk`.

---

## File structure

- Create `cutctx/proxy/decision_receipt.py`: schema vocabulary, reason explanations, safe configuration fingerprint, complete receipt builder, and legacy adapter.
- Create `tests/test_decision_receipt.py`: pure contract, privacy, observation-state, fingerprint, and malformed-input tests.
- Modify `cutctx/proxy/outcome.py`: carry typed observation flags and create the receipt at the canonical finalization boundary.
- Modify `cutctx/proxy/models.py`: persist `decision_receipt` and typed cache/CCR observations on `RequestLog`.
- Modify `cutctx/proxy/request_logger.py`: expose per-entry redaction evidence and preserve receipts across JSONL writes and warm restart.
- Modify `cutctx/ccr/markers.py`: recursively extract CCR references from provider-neutral payload structures.
- Modify `cutctx/proxy/handlers/openai/compress.py`: preserve `/v1/compress` CCR references without payload logging.
- Modify `cutctx/proxy/server.py`: emit partial receipts for direct denial rows and return persisted or legacy receipts through trace endpoints.
- Modify `cutctx/proxy/handlers/openai/responses.py`: emit a partial receipt for the direct WebSocket session-summary row.
- Modify `tests/test_request_outcome.py`, `tests/test_proxy/test_request_logger.py`, `tests/test_ccr_markers.py`, and `tests/test_proxy/test_request_trace_inspector.py`: integration and persistence coverage.
- Modify `dashboard/src/pages/Overview.jsx` and `dashboard/src/index.css`: receipt summary and evidence groups in the existing inspector.
- Modify `tests/test_dashboard_overview_request_trace_inspector.py`: browser coverage for complete and legacy receipts.
- Regenerate `cutctx/dashboard/index.html` and `cutctx/dashboard/assets/` using `scripts/sync_dashboard_assets.py`; do not edit generated bundles manually.
- Modify `docs/content/docs/proxy.mdx`: document the additive receipt field and privacy semantics.

---

### Task 1: Pure decision-receipt contract

**Files:**
- Create: `cutctx/proxy/decision_receipt.py`
- Create: `tests/test_decision_receipt.py`

**Interfaces:**
- Produces: `DECISION_RECEIPT_SCHEMA_VERSION: int = 1`
- Produces: `explain_routing_reason(reason: str | None, selection_evidence: Mapping[str, Any] | None = None) -> str`
- Produces: `fingerprint_decision_config(config: Any | None) -> str | None`
- Produces: `build_decision_receipt(evidence: Mapping[str, Any], *, config: Any | None = None, payload_capture: str = "disabled") -> dict[str, Any]`
- Produces: `build_legacy_decision_receipt(log: Mapping[str, Any], *, payload_capture: str) -> dict[str, Any]`
- Produces: `build_minimal_decision_receipt(request_id: str, *, payload_capture: str, failure: str) -> dict[str, Any]`

- [ ] **Step 1: Write failing reason and schema tests**

```python
from types import SimpleNamespace

from cutctx.proxy.decision_receipt import (
    DECISION_RECEIPT_SCHEMA_VERSION,
    build_decision_receipt,
    explain_routing_reason,
    fingerprint_decision_config,
)


def test_workload_not_downgradeable_explains_retention() -> None:
    explanation = explain_routing_reason(
        "workload_not_downgradeable",
        {"complexity": "high", "signals": ["recent_tool_context"]},
    )
    assert "recent tool context" in explanation.lower()
    assert "retained" in explanation.lower()


def test_complete_receipt_keeps_created_and_observed_savings_separate() -> None:
    receipt = build_decision_receipt(
        {
            "request_id": "req-1",
            "requested_model": "gpt-5.4",
            "effective_model": "gpt-5.4",
            "routing_trace": {
                "schema_version": 1,
                "mechanism": "optimization_preset",
                "reason": "workload_not_downgradeable",
                "applied": False,
                "required_capabilities": ["tool_calling"],
                "candidates": ["gpt-5.4-mini"],
                "rejected_candidates": [
                    {"candidate": "gpt-5.4-mini", "reason": "workload_not_downgradeable"}
                ],
                "selection_evidence": {
                    "complexity": "high",
                    "signals": ["recent_tool_context"],
                },
            },
            "input_tokens_original": 1500,
            "input_tokens_forwarded": 1000,
            "direct_tokens_saved": 300,
            "transforms": ["smart_crusher"],
            "cache_protected_tokens": 200,
            "cache_protection_evaluated": True,
            "provider_cache_observed": True,
            "provider_cache_read_tokens": 200,
            "provider_cache_write_tokens": 0,
            "provider_cache_inferred": False,
            "semantic_cache_evaluated": False,
            "semantic_cache_hit": False,
            "semantic_cache_saved_tokens": 0,
            "prefix_cache_evaluated": False,
            "prefix_cache_saved_tokens": 0,
            "ccr_references": [],
            "ccr_retrieval_outcome": None,
            "total_saved_tokens": 500,
            "created_savings_tokens": 300,
            "observed_provider_savings_tokens": 200,
            "by_source_tokens": {
                "cutctx_compression": 300,
                "provider_prompt_cache": 200,
            },
            "by_source_usd": {},
            "savings_basis": "estimated",
            "pricing_basis": "model_input_list_price",
        }
    )

    assert receipt["schema_version"] == DECISION_RECEIPT_SCHEMA_VERSION
    assert receipt["routing"]["status"] == "retained"
    assert receipt["routing"]["reason"] == "workload_not_downgradeable"
    assert receipt["cache"]["provider_prompt_cache"]["status"] == "hit"
    assert receipt["cache"]["semantic_response_cache"]["status"] == "unobserved"
    assert receipt["attribution"]["created_savings_tokens"] == 300
    assert receipt["attribution"]["observed_provider_savings_tokens"] == 200
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `rtk pytest tests/test_decision_receipt.py -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'cutctx.proxy.decision_receipt'`.

- [ ] **Step 3: Implement the schema vocabulary and receipt builder**

Create `cutctx/proxy/decision_receipt.py` with:

```python
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from cutctx import __version__

DECISION_RECEIPT_SCHEMA_VERSION = 1

_CONFIG_FINGERPRINT_FIELDS = (
    "min_tokens_to_crush",
    "ccr_inject_tool",
    "ccr_inject_marker",
    "ccr_handle_responses",
    "ccr_store_ttl_seconds",
    "cache_enabled",
    "cache_aligner_enabled",
    "prefix_freeze_enabled",
    "model_routing_preset",
    "workload_class",
    "context_budget_enabled",
    "context_budget_max_tokens",
    "context_budget_policy",
)

_REASON_EXPLANATIONS = {
    "confidence_below_threshold": "Routing evidence was insufficient to justify a model change, so Cutctx retained the requested model.",
    "target_missing_capabilities": "The candidate lacked proof for one or more required capabilities, so Cutctx retained the requested model.",
    "downgrade_blocked_unproven_transport": "The target transport or account could not be proven safe, so Cutctx retained the requested model.",
    "low_complexity": "The request passed the configured safety and compatibility gates for the selected lower-cost model.",
    "downgrade_applied": "The request passed the configured safety and compatibility gates for the selected lower-cost model.",
    "no_route_for_model": "The active routing policy had no eligible target for the requested model.",
}


def explain_routing_reason(
    reason: str | None,
    selection_evidence: Mapping[str, Any] | None = None,
) -> str:
    if reason == "workload_not_downgradeable":
        signals = set((selection_evidence or {}).get("signals") or [])
        if "recent_tool_context" in signals:
            return "Recent tool context was classified as high-risk, so Cutctx retained the requested model."
        return "The workload was classified as high-complexity or high-risk, so Cutctx retained the requested model."
    if reason in _REASON_EXPLANATIONS:
        return _REASON_EXPLANATIONS[reason]
    if reason:
        return f"Cutctx recorded routing outcome '{reason}'. Review the evidence below for details."
    return "No model-routing decision was observed for this request."


def fingerprint_decision_config(config: Any | None) -> str | None:
    if config is None:
        return None
    values = {name: getattr(config, name, None) for name in _CONFIG_FINGERPRINT_FIELDS}
    encoded = json.dumps(values, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
```

Implement the normalizers with the following concrete structure (small coercion helpers such as `_mapping`, `_integer`, and `_string_list` stay private to this module):

```python
def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _cache_status(*, observed: bool, hit: bool) -> str:
    if not observed:
        return "unobserved"
    return "hit" if hit else "miss"


def build_decision_receipt(
    evidence: Mapping[str, Any],
    *,
    config: Any | None = None,
    payload_capture: str = "disabled",
) -> dict[str, Any]:
    routing_trace = _mapping(evidence.get("routing_trace"))
    routing_summary = _mapping(evidence.get("routing_summary"))
    selection_evidence = _mapping(routing_trace.get("selection_evidence"))
    reason = routing_trace.get("reason") or routing_summary.get("reason")
    routing_observed = bool(routing_trace or routing_summary)
    applied = bool(routing_trace.get("applied", routing_summary.get("routed", False)))
    routing_status = "applied" if applied else "retained" if routing_observed else "unobserved"

    transforms = [str(value) for value in evidence.get("transforms") or []]
    decline_reason = evidence.get("decline_reason")
    direct_saved = _integer(evidence.get("direct_tokens_saved"))
    compression_observed = any(
        key in evidence
        for key in ("input_tokens_original", "input_tokens_forwarded", "direct_tokens_saved")
    )
    compression_status = (
        "applied"
        if direct_saved > 0 or transforms
        else "abstained"
        if compression_observed and decline_reason
        else "not_evaluated"
        if compression_observed
        else "unobserved"
    )

    provider_observed = bool(evidence.get("provider_cache_observed", False))
    provider_read = _integer(evidence.get("provider_cache_read_tokens"))
    semantic_evaluated = bool(evidence.get("semantic_cache_evaluated", False))
    semantic_hit = bool(evidence.get("semantic_cache_hit", False))
    prefix_evaluated = bool(evidence.get("prefix_cache_evaluated", False))
    prefix_saved = _integer(evidence.get("prefix_cache_saved_tokens"))
    protected_tokens = _integer(evidence.get("cache_protected_tokens"))
    cache_protection_evaluated = bool(evidence.get("cache_protection_evaluated", False))

    ccr_references = [
        {
            "hash": str(item.get("hash")),
            "availability": str(item.get("availability") or "unobserved"),
            "expires_at": item.get("expires_at"),
        }
        for item in evidence.get("ccr_references") or []
        if isinstance(item, Mapping) and item.get("hash")
    ]
    ccr_outcome = evidence.get("ccr_retrieval_outcome")
    ccr_status = (
        "available"
        if any(item["availability"] == "available" for item in ccr_references)
        else "expired"
        if ccr_references and all(item["availability"] == "expired" for item in ccr_references)
        else "missing"
        if ccr_references and all(item["availability"] == "missing" for item in ccr_references)
        else "unobserved"
        if ccr_references
        else "not_used"
    )

    missing: list[str] = []
    if not routing_trace:
        missing.extend(("routing.confidence", "routing.rejected_candidates", "routing.transport"))
    if not provider_observed:
        missing.append("cache.provider_prompt_cache")
    if ccr_references and ccr_outcome is None:
        missing.append("ccr.retrieval_outcome")

    receipt = {
        "schema_version": DECISION_RECEIPT_SCHEMA_VERSION,
        "request_id": evidence.get("request_id"),
        "observation": {
            "completeness": "complete" if not missing else "partial",
            "missing": sorted(set(missing)),
            "payload_capture": payload_capture,
        },
        "routing": {
            "status": routing_status,
            "reason": reason,
            "explanation": explain_routing_reason(reason, selection_evidence),
            "requested_model": routing_trace.get("requested_model")
            or routing_summary.get("requested_model")
            or evidence.get("requested_model"),
            "effective_model": routing_trace.get("effective_model")
            or routing_summary.get("actual_model")
            or evidence.get("effective_model"),
            "mechanism": routing_trace.get("mechanism"),
            "confidence": routing_trace.get("confidence"),
            "scorer": routing_trace.get("scorer"),
            "required_capabilities": list(routing_trace.get("required_capabilities") or []),
            "candidates": list(routing_trace.get("candidates") or []),
            "rejected_candidates": list(routing_trace.get("rejected_candidates") or []),
            "transport": _mapping(routing_trace.get("transport")),
            "selection_evidence": selection_evidence,
            "request_overrides": routing_summary.get("request_overrides"),
        },
        "compression": {
            "status": compression_status,
            "reason": decline_reason,
            "input_tokens_original": evidence.get("input_tokens_original"),
            "input_tokens_forwarded": evidence.get("input_tokens_forwarded"),
            "direct_tokens_saved": direct_saved,
            "transforms": transforms,
            "protected_content": {
                "cache_protected_tokens": protected_tokens,
                "signals": list(selection_evidence.get("signals") or []),
            },
        },
        "cache": {
            "provider_prompt_cache": {
                "status": _cache_status(observed=provider_observed, hit=provider_read > 0),
                "read_tokens": provider_read,
                "write_tokens": _integer(evidence.get("provider_cache_write_tokens")),
                "inferred": bool(evidence.get("provider_cache_inferred", False)),
            },
            "semantic_response_cache": {
                "status": _cache_status(observed=semantic_evaluated, hit=semantic_hit),
                "saved_tokens": _integer(evidence.get("semantic_cache_saved_tokens")),
            },
            "self_hosted_prefix_cache": {
                "status": _cache_status(observed=prefix_evaluated, hit=prefix_saved > 0),
                "saved_tokens": prefix_saved,
            },
            "cache_safe_prefix": {
                "status": (
                    "protected"
                    if protected_tokens > 0
                    else "not_protected"
                    if cache_protection_evaluated
                    else "unobserved"
                ),
                "protected_tokens": protected_tokens,
            },
        },
        "ccr": {
            "status": ccr_status,
            "references": ccr_references,
            "retrieval_outcome": ccr_outcome or ("not_requested" if not ccr_references else "unobserved"),
        },
        "attribution": {
            "total_saved_tokens": _integer(evidence.get("total_saved_tokens")),
            "created_savings_tokens": _integer(evidence.get("created_savings_tokens")),
            "observed_provider_savings_tokens": _integer(
                evidence.get("observed_provider_savings_tokens")
            ),
            "by_source_tokens": _mapping(evidence.get("by_source_tokens")),
            "by_source_usd": _mapping(evidence.get("by_source_usd")),
            "savings_basis": evidence.get("savings_basis") or "estimated",
            "pricing_basis": evidence.get("pricing_basis") or "model_input_list_price",
        },
        "policy": {
            "routing_policy": routing_trace.get("policy"),
            "routing_mode": routing_trace.get("mode"),
            "config_fingerprint": fingerprint_decision_config(config),
            "cutctx_version": __version__,
        },
    }
    return receipt


def build_legacy_decision_receipt(
    log: Mapping[str, Any],
    *,
    payload_capture: str,
) -> dict[str, Any]:
    receipt = build_decision_receipt(
        {
            "request_id": log.get("request_id"),
            "requested_model": _mapping(log.get("routing_metadata")).get("requested_model")
            or log.get("model"),
            "effective_model": log.get("model"),
            "routing_summary": _mapping(log.get("routing_metadata")),
            "input_tokens_original": log.get("input_tokens_original"),
            "input_tokens_forwarded": log.get("input_tokens_optimized"),
            "direct_tokens_saved": log.get("tokens_saved"),
            "transforms": log.get("transforms_applied") or [],
            "decline_reason": log.get("decline_reason"),
            "provider_cache_observed": _integer(log.get("cache_saved_tokens")) > 0,
            "provider_cache_read_tokens": log.get("cache_saved_tokens"),
            "semantic_cache_evaluated": _integer(log.get("semantic_cache_saved_tokens")) > 0,
            "semantic_cache_hit": _integer(log.get("semantic_cache_saved_tokens")) > 0,
            "semantic_cache_saved_tokens": log.get("semantic_cache_saved_tokens"),
            "prefix_cache_evaluated": _integer(log.get("self_hosted_prefix_cache_saved_tokens")) > 0,
            "prefix_cache_saved_tokens": log.get("self_hosted_prefix_cache_saved_tokens"),
            "total_saved_tokens": log.get("total_saved_tokens"),
            "created_savings_tokens": log.get("created_savings_tokens"),
            "observed_provider_savings_tokens": log.get("observed_provider_savings_tokens"),
            "by_source_tokens": log.get("savings_by_source_tokens") or {},
            "by_source_usd": log.get("savings_by_source_usd") or {},
            "savings_basis": log.get("savings_basis"),
            "pricing_basis": log.get("pricing_basis"),
        },
        payload_capture=payload_capture,
    )
    receipt["observation"]["completeness"] = "legacy"
    receipt["observation"]["missing"] = sorted(
        set(receipt["observation"]["missing"])
        | {"routing.rejected_candidates", "routing.transport", "ccr.availability"}
    )
    return receipt


def build_minimal_decision_receipt(
    request_id: str,
    *,
    payload_capture: str,
    failure: str,
) -> dict[str, Any]:
    receipt = build_decision_receipt(
        {"request_id": request_id},
        payload_capture=payload_capture,
    )
    receipt["observation"]["completeness"] = "partial"
    receipt["observation"]["missing"] = [failure]
    return receipt
```

- [ ] **Step 4: Add privacy, fingerprint, and malformed-input tests**

```python
def test_config_fingerprint_ignores_secrets_and_is_order_stable() -> None:
    left = SimpleNamespace(
        min_tokens_to_crush=500,
        cache_enabled=True,
        model_routing_preset="codex-gpt54mini-high",
        admin_api_key="secret-a",
    )
    right = SimpleNamespace(
        model_routing_preset="codex-gpt54mini-high",
        cache_enabled=True,
        min_tokens_to_crush=500,
        admin_api_key="secret-b",
    )
    assert fingerprint_decision_config(left) == fingerprint_decision_config(right)
    assert "secret" not in str(fingerprint_decision_config(left))


def test_explicit_zero_cache_read_is_miss_but_missing_observation_is_unobserved() -> None:
    observed = build_decision_receipt(
        {
            "request_id": "a",
            "provider_cache_observed": True,
            "provider_cache_read_tokens": 0,
            "cache_protection_evaluated": True,
            "cache_protected_tokens": 0,
        }
    )
    missing = build_decision_receipt(
        {"request_id": "b", "provider_cache_observed": False, "provider_cache_read_tokens": 0}
    )
    assert observed["cache"]["provider_prompt_cache"]["status"] == "miss"
    assert observed["cache"]["cache_safe_prefix"]["status"] == "not_protected"
    assert missing["cache"]["provider_prompt_cache"]["status"] == "unobserved"
    assert missing["cache"]["cache_safe_prefix"]["status"] == "unobserved"


def test_malformed_evidence_returns_partial_receipt_without_payload_content() -> None:
    receipt = build_decision_receipt(
        {
            "request_id": "bad",
            "routing_trace": "not-a-mapping",
            "request_messages": [{"role": "user", "content": "private"}],
        }
    )
    serialized = str(receipt)
    assert receipt["observation"]["completeness"] == "partial"
    assert "private" not in serialized
    assert "request_messages" not in serialized
```

- [ ] **Step 5: Run focused tests and verify GREEN**

Run: `rtk pytest tests/test_decision_receipt.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit the pure contract**

Run:

```bash
rtk git add cutctx/proxy/decision_receipt.py tests/test_decision_receipt.py
rtk git -c core.editor=true commit -m "feat: add decision receipt contract"
```

---

### Task 2: Persist receipts through the canonical outcome funnel

**Files:**
- Modify: `cutctx/proxy/outcome.py`
- Modify: `cutctx/proxy/models.py`
- Modify: `cutctx/proxy/request_logger.py`
- Modify: `tests/test_request_outcome.py`
- Modify: `tests/test_proxy/test_request_logger.py`

**Interfaces:**
- Consumes: `build_decision_receipt(...)` from Task 1.
- Produces: `RequestOutcome.provider_cache_observed: bool`
- Produces: `RequestOutcome.semantic_cache_evaluated: bool`
- Produces: `RequestOutcome.self_hosted_prefix_cache_evaluated: bool`
- Produces: `RequestOutcome.cache_protection_evaluated: bool`
- Produces: `RequestOutcome.ccr_references: tuple[dict[str, Any], ...]`
- Produces: `RequestOutcome.ccr_retrieval_outcome: str | None`
- Produces: `RequestLog.decision_receipt: dict[str, Any] | None`
- Produces: `redact_image_base64_with_count(payload: Any) -> tuple[Any, int]`

- [ ] **Step 1: Write the failing outcome-persistence test**

Add a test using the existing dummy handler and `emit_request_outcome` fixture in `tests/test_request_outcome.py`:

```python
@pytest.mark.asyncio
async def test_emit_request_outcome_persists_full_routing_receipt() -> None:
    from cutctx.proxy.models import ProxyConfig
    from cutctx.proxy.request_logger import RequestLogger

    handler = _FunnelHarness()
    handler.config = ProxyConfig()
    handler.logger = RequestLogger(log_file=None, log_full_messages=False)
    outcome = RequestOutcome(
        request_id="receipt-1",
        provider="openai",
        model="gpt-5.4",
        original_tokens=1000,
        optimized_tokens=800,
        output_tokens=100,
        tokens_saved=200,
        attempted_input_tokens=1000,
        provider_cache_observed=True,
        cache_read_tokens=100,
        cache_protected_tokens=100,
        savings_metadata={
            "model_routing": {
                "source_model": "gpt-5.4",
                "target_model": "gpt-5.4",
                "reason": "workload_not_downgradeable",
            },
            "model_routing_trace": {
                "schema_version": 1,
                "mechanism": "optimization_preset",
                "requested_model": "gpt-5.4",
                "effective_model": "gpt-5.4",
                "reason": "workload_not_downgradeable",
                "applied": False,
                "candidates": ["gpt-5.4-mini"],
                "rejected_candidates": [
                    {"candidate": "gpt-5.4-mini", "reason": "workload_not_downgradeable"}
                ],
                "required_capabilities": ["tool_calling"],
                "selection_evidence": {"signals": ["recent_tool_context"]},
            },
        },
    )

    await handler._record_request_outcome(outcome)

    row = handler.logger.get_recent_with_messages(1)[0]
    receipt = row["decision_receipt"]
    assert receipt["routing"]["reason"] == "workload_not_downgradeable"
    assert receipt["routing"]["rejected_candidates"][0]["candidate"] == "gpt-5.4-mini"
    assert receipt["cache"]["provider_prompt_cache"]["status"] == "hit"
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `rtk pytest tests/test_request_outcome.py -q -k persists_full_routing_receipt`

Expected: failure because `RequestOutcome` does not accept the observation fields and `RequestLog` has no `decision_receipt`.

- [ ] **Step 3: Add typed observation and persistence fields**

Add these neutral fields to `RequestOutcome`:

```python
provider_cache_observed: bool = False
semantic_cache_evaluated: bool = False
self_hosted_prefix_cache_evaluated: bool = False
cache_protection_evaluated: bool = False
ccr_references: tuple[dict[str, Any], ...] = ()
ccr_retrieval_outcome: str | None = None
```

Extend `RequestOutcome.from_stream` with `provider_cache_observed: bool | None = None`. Set the stored flag to the explicit value when supplied; otherwise infer observation only when at least one of `cache_read_tokens`, `cache_write_tokens`, or `uncached_input_tokens` is positive. This makes an upstream usage report with zero cache reads and positive uncached tokens an observed miss, while a provider that reports no cache split remains unobserved.

Add this focused derivation test:

```python
def test_from_stream_distinguishes_provider_cache_miss_from_unobserved() -> None:
    miss = RequestOutcome.from_stream(
        **_stream_kwargs(cache_read_tokens=0, cache_write_tokens=0, uncached_input_tokens=800)
    )
    unknown = RequestOutcome.from_stream(
        **_stream_kwargs(cache_read_tokens=0, cache_write_tokens=0, uncached_input_tokens=0)
    )
    assert miss.provider_cache_observed is True
    assert unknown.provider_cache_observed is False
```

Add these fields to `RequestLog`:

```python
provider_cache_observed: bool = False
provider_cache_write_tokens: int = 0
provider_cache_inferred: bool = False
semantic_cache_evaluated: bool = False
self_hosted_prefix_cache_evaluated: bool = False
cache_protection_evaluated: bool = False
ccr_references: list[dict[str, Any]] | None = None
ccr_retrieval_outcome: str | None = None
decision_receipt: dict[str, Any] | None = None
```

Immediately before `request_logger.log(RequestLog(...))`, build the exact evidence mapping and persist the returned dictionary:

```python
extra_metadata = outcome.savings_metadata or {}
routing_trace = extra_metadata.get("model_routing_trace")
cache_protection_evaluated = bool(
    outcome.cache_protection_evaluated or eligible_input_tokens > 0
)
receipt = build_decision_receipt(
    {
        "request_id": outcome.request_id,
        "requested_model": (routing_meta or {}).get("requested_model") or outcome.model,
        "effective_model": outcome.model,
        "routing_trace": routing_trace if isinstance(routing_trace, dict) else None,
        "routing_summary": routing_meta,
        "input_tokens_original": outcome.original_tokens,
        "input_tokens_forwarded": outcome.optimized_tokens,
        "direct_tokens_saved": _savings_by_source_tokens.get("cutctx_compression", 0),
        "transforms": list(outcome.transforms_applied),
        "decline_reason": decline_reason,
        "cache_protected_tokens": cache_protected_tokens,
        "cache_protection_evaluated": cache_protection_evaluated,
        "provider_cache_observed": outcome.provider_cache_observed,
        "provider_cache_read_tokens": outcome.cache_read_tokens,
        "provider_cache_write_tokens": outcome.cache_write_tokens,
        "provider_cache_inferred": outcome.cache_inferred,
        "semantic_cache_evaluated": bool(
            outcome.semantic_cache_evaluated
            or outcome.semantic_cache_hit
            or outcome.from_response_cache
        ),
        "semantic_cache_hit": outcome.semantic_cache_hit or outcome.from_response_cache,
        "semantic_cache_saved_tokens": semantic_cache_saved_tokens,
        "prefix_cache_evaluated": bool(
            outcome.self_hosted_prefix_cache_evaluated
            or self_hosted_prefix_cache_saved_tokens > 0
        ),
        "prefix_cache_saved_tokens": self_hosted_prefix_cache_saved_tokens,
        "ccr_references": list(outcome.ccr_references),
        "ccr_retrieval_outcome": outcome.ccr_retrieval_outcome,
        "total_saved_tokens": total_saved_tokens,
        "created_savings_tokens": created_savings_tokens,
        "observed_provider_savings_tokens": observed_provider_savings_tokens,
        "by_source_tokens": dict(_savings_by_source_tokens),
        "by_source_usd": dict(_savings_by_source_usd),
        "savings_basis": outcome.savings_basis,
        "pricing_basis": outcome.pricing_basis,
    },
    config=getattr(handler, "config", None),
    payload_capture="captured" if request_logger.log_full_messages else "disabled",
)
```

Pass the same typed cache and CCR fields, `cache_protection_evaluated=cache_protection_evaluated`, and `decision_receipt=receipt` into `RequestLog(...)`. A positive eligible-input denominator means the protection stage had a real request to assess; rate-limit and empty protocol rows remain unobserved. Do not derive created or observed savings a second time.

Wrap only receipt construction in `try/except Exception`. On failure, emit a sanitized warning containing the request ID and exception type but not the evidence mapping, then use:

```python
receipt = build_minimal_decision_receipt(
    outcome.request_id,
    payload_capture="captured" if request_logger.log_full_messages else "disabled",
    failure="receipt_builder_failed",
)
```

Add a test that monkeypatches `cutctx.proxy.outcome.build_decision_receipt` to raise `ValueError("private payload")`, then asserts request logging still succeeds, `observation.missing == ["receipt_builder_failed"]`, and neither the exception message nor evidence appears in the row.

- [ ] **Step 4: Write the failing per-entry redaction-state test**

Add to `tests/test_proxy/test_request_logger.py`:

```python
def test_request_logger_marks_only_the_current_receipt_as_redacted() -> None:
    logger = RequestLogger(log_file=None, log_full_messages=True)
    first = _entry(
        request_id="image",
        request_messages=[{"role": "user", "image_url": "data:image/png;base64," + "A" * 9000}],
        decision_receipt={"observation": {"payload_capture": "captured"}},
    )
    second = _entry(
        request_id="text",
        request_messages=[{"role": "user", "content": "hello"}],
        decision_receipt={"observation": {"payload_capture": "captured"}},
    )

    logger.log(first)
    logger.log(second)

    rows = logger.get_recent_with_messages(2)
    assert rows[0]["decision_receipt"]["observation"]["payload_capture"] == "redacted"
    assert rows[1]["decision_receipt"]["observation"]["payload_capture"] == "captured"
```

- [ ] **Step 5: Implement per-entry redaction evidence**

Refactor the redaction recursion to accept a mutable local counter, then expose:

```python
def redact_image_base64_with_count(payload: Any) -> tuple[Any, int]:
    counter = [0]
    redacted = _redact_value(payload, in_image_path=False, local_counter=counter)
    return redacted, counter[0]


def redact_image_base64(payload: Any) -> Any:
    redacted, _count = redact_image_base64_with_count(payload)
    return redacted
```

In `RequestLogger.log`, sum the counts from request messages, compressed messages, and response content. If the sum is positive and a receipt exists, copy the receipt and nested observation dictionaries before setting `payload_capture="redacted"`. This avoids mutating a dictionary shared by callers or another log entry.

- [ ] **Step 6: Verify persistence, redaction, JSONL, and restart behavior**

Run:

```bash
rtk pytest tests/test_request_outcome.py tests/test_proxy/test_request_logger.py -q
```

Expected: all tests pass, including existing `log_full_messages=False` stripping and JSONL warm-start tests.

- [ ] **Step 7: Commit canonical persistence**

Run:

```bash
rtk git add cutctx/proxy/outcome.py cutctx/proxy/models.py cutctx/proxy/request_logger.py tests/test_request_outcome.py tests/test_proxy/test_request_logger.py
rtk git -c core.editor=true commit -m "feat: persist request decision receipts"
```

---

### Task 3: Capture CCR references without payload logging

**Files:**
- Modify: `cutctx/ccr/markers.py`
- Modify: `cutctx/proxy/outcome.py`
- Modify: `cutctx/proxy/handlers/openai/compress.py`
- Modify: `tests/test_ccr_markers.py`
- Modify: `tests/test_request_outcome.py`
- Modify: `tests/test_proxy_compress_endpoint.py`

**Interfaces:**
- Produces: `extract_marker_hashes_from_payload(value: Any) -> list[str]`
- Consumes: `RequestOutcome.ccr_references` from Task 2.

- [ ] **Step 1: Write the failing recursive marker test**

Add to `tests/test_ccr_markers.py`:

```python
def test_extract_marker_hashes_from_nested_payload_preserves_order() -> None:
    payload = [
        {"role": "tool", "content": "<<ccr:1111222233334444>>"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "[20 rows compressed. hash=aaaabbbbccccdddd]"},
                {"type": "text", "text": "again <<ccr:1111222233334444>>"},
            ],
        },
    ]
    assert extract_marker_hashes_from_payload(payload) == [
        "1111222233334444",
        "aaaabbbbccccdddd",
    ]
```

- [ ] **Step 2: Run the marker test and verify RED**

Run: `rtk pytest tests/test_ccr_markers.py -q -k nested_payload`

Expected: import or attribute failure for `extract_marker_hashes_from_payload`.

- [ ] **Step 3: Implement provider-neutral recursive extraction**

Add to `cutctx/ccr/markers.py`:

```python
def extract_marker_hashes_from_payload(value: Any) -> list[str]:
    hashes: list[str] = []
    seen: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, str):
            for hash_key in extract_marker_hashes(item):
                if hash_key not in seen:
                    seen.add(hash_key)
                    hashes.append(hash_key)
            return
        if isinstance(item, Mapping):
            for child in item.values():
                visit(child)
            return
        if isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            for child in item:
                visit(child)

    visit(value)
    return hashes
```

Import `Mapping` and `Sequence` from `collections.abc`, and export the helper through `__all__`.

- [ ] **Step 4: Write the failing no-payload-logging outcome test**

Add to `tests/test_request_outcome.py`:

```python
def test_from_stream_preserves_ccr_hashes_when_message_logging_is_disabled() -> None:
    body = {
        "messages": [
            {"role": "tool", "content": "<<ccr:1111222233334444>>"},
        ]
    }
    outcome = RequestOutcome.from_stream(
        **_stream_kwargs(body=body, log_full_messages=False)
    )
    assert outcome.request_messages is None
    assert outcome.compressed_messages is None
    assert outcome.ccr_references == (
        {"hash": "1111222233334444", "availability": "unobserved", "expires_at": None},
    )
```

- [ ] **Step 5: Derive CCR references before payload snapshots are discarded**

In `RequestOutcome.from_stream`, call `extract_marker_hashes_from_payload(request_items)` before the `log_full_messages` branch. Convert hashes to immutable reference dictionaries and pass them to `RequestOutcome.ccr_references`. Set no retrieval outcome unless the caller supplies one.

In `/v1/compress`, normalize only hashes parsed from actual CCR marker strings in `result.markers_inserted` and pass reference dictionaries with `availability="available"` into the emitted `RequestOutcome`; the transform has just confirmed insertion into its configured CCR store. Do not treat `stable_prefix_hash:*` markers as CCR references. Add an endpoint assertion that `trace.decision_receipt.ccr.references` contains the hashes and status `available` even though request messages are absent. `RequestOutcome.from_stream` remains conservative and uses `availability="unobserved"` because a forwarded marker may have originated outside the current process.

- [ ] **Step 6: Verify CCR extraction and receipt persistence**

Run:

```bash
rtk pytest tests/test_ccr_markers.py tests/test_request_outcome.py tests/test_proxy_compress_endpoint.py -q
```

Expected: all tests pass; no test enables full payload logging to obtain CCR hashes.

- [ ] **Step 7: Commit CCR evidence capture**

Run:

```bash
rtk git add cutctx/ccr/markers.py cutctx/proxy/outcome.py cutctx/proxy/handlers/openai/compress.py tests/test_ccr_markers.py tests/test_request_outcome.py tests/test_proxy_compress_endpoint.py
rtk git -c core.editor=true commit -m "feat: preserve ccr evidence in receipts"
```

---

### Task 4: Trace API compatibility and direct log writers

**Files:**
- Modify: `cutctx/proxy/server.py`
- Modify: `cutctx/proxy/handlers/openai/responses.py`
- Modify: `tests/test_proxy/test_request_trace_inspector.py`

**Interfaces:**
- Consumes: `build_decision_receipt` and `build_legacy_decision_receipt` from Task 1.
- Consumes: `RequestLog.decision_receipt` from Task 2.
- Produces: additive `trace.decision_receipt` on list and detail responses.

- [ ] **Step 1: Write failing persisted and legacy API tests**

Extend `_trace_entry` to accept a receipt, then add:

```python
@pytest.mark.asyncio
async def test_trace_endpoint_returns_persisted_receipt_unchanged(app):
    expected = {
        "schema_version": 1,
        "request_id": "trace-receipt",
        "observation": {"completeness": "complete", "missing": [], "payload_capture": "disabled"},
        "routing": {"status": "retained", "reason": "workload_not_downgradeable"},
    }
    app.state.proxy.logger.log(
        _trace_entry(request_id="trace-receipt", decision_receipt=expected)
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/transformations/traces/trace-receipt", headers=_ADMIN_HEADERS
        )
    assert response.json()["trace"]["decision_receipt"] == expected


@pytest.mark.asyncio
async def test_trace_endpoint_adapts_receiptless_row_as_legacy(app):
    app.state.proxy.logger.log(_trace_entry(request_id="legacy", decision_receipt=None))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/transformations/traces/legacy", headers=_ADMIN_HEADERS)
    receipt = response.json()["trace"]["decision_receipt"]
    assert receipt["schema_version"] == 1
    assert receipt["observation"]["completeness"] == "legacy"
    assert "routing.rejected_candidates" in receipt["observation"]["missing"]


@pytest.mark.asyncio
async def test_trace_endpoint_returns_unknown_future_receipt_without_rewriting(app):
    future = {"schema_version": 2, "request_id": "future", "future_section": {"value": 1}}
    app.state.proxy.logger.log(_trace_entry(request_id="future", decision_receipt=future))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/transformations/traces/future", headers=_ADMIN_HEADERS)
    assert response.json()["trace"]["decision_receipt"] == future
```

- [ ] **Step 2: Run API tests and verify RED**

Run: `rtk pytest tests/test_proxy/test_request_trace_inspector.py -q -k 'persisted_receipt or receiptless_row'`

Expected: failures because `_build_request_trace` does not expose a receipt.

- [ ] **Step 3: Return persisted receipts and adapt legacy rows**

In `_build_request_trace`, set:

```python
payload_capture = "captured" if log_full_messages else "disabled"
decision_receipt = log.get("decision_receipt")
if not isinstance(decision_receipt, dict):
    decision_receipt = build_legacy_decision_receipt(log, payload_capture=payload_capture)
```

The helper currently closes over no request-specific configuration, so change its signature to `_build_request_trace(log, *, log_full_messages: bool)`. Pass the configured value from both list and detail endpoints. Add `"decision_receipt": decision_receipt` to the existing response without removing any field.

- [ ] **Step 4: Add direct-writer receipt tests**

Add assertions to the existing rate-limit trace test that the returned row has a partial receipt with `compression.reason="rate_limit_exceeded"` and no payload content. In `tests/test_openai_codex_ws_lifecycle.py`, attach a real in-memory `RequestLogger` to `_DummyOpenAIHandler`, complete one fake session, and assert every newly written row contains a version 1 receipt.

- [ ] **Step 5: Build partial receipts at both direct write sites**

In `record_rate_limit_denial`, build and attach this receipt before logging:

```python
receipt = build_decision_receipt(
    {
        "request_id": request_id,
        "requested_model": model,
        "effective_model": model,
        "input_tokens_original": 0,
        "input_tokens_forwarded": 0,
        "direct_tokens_saved": 0,
        "transforms": [],
        "decline_reason": "rate_limit_exceeded",
        "provider_cache_observed": False,
        "semantic_cache_evaluated": False,
        "prefix_cache_evaluated": False,
        "ccr_references": [],
        "total_saved_tokens": 0,
        "created_savings_tokens": 0,
        "observed_provider_savings_tokens": 0,
        "by_source_tokens": {},
        "by_source_usd": {},
    },
    config=self.config,
    payload_capture="disabled",
)
```

In the OpenAI Responses WebSocket session-summary direct writer, attach a partial receipt using `request_id`, `model_name`, `ws_input_tokens_total + tokens_saved`, `ws_input_tokens_total`, `tokens_saved`, `transforms_applied`, empty cache/CCR observation flags, and `payload_capture="captured"` only when `self.config.log_full_messages` is true. Do not add `ws_messages_for_log` to the evidence mapping. Keep the existing residual `RequestOutcome` row unchanged.

- [ ] **Step 6: Run the complete trace API suite**

Run:

```bash
rtk pytest tests/test_proxy/test_request_trace_inspector.py tests/test_openai_codex_ws_lifecycle.py -q
```

Expected: all selected tests pass, admin authentication behavior remains unchanged, and every new direct row has a receipt.

- [ ] **Step 7: Commit API compatibility**

Run:

```bash
rtk git add cutctx/proxy/server.py cutctx/proxy/handlers/openai/responses.py tests/test_proxy/test_request_trace_inspector.py tests/test_openai_codex_ws_lifecycle.py
rtk git -c core.editor=true commit -m "feat: expose decision receipts in request traces"
```

---

### Task 5: Render the decision receipt in the existing inspector

**Files:**
- Modify: `dashboard/src/pages/Overview.jsx`
- Modify: `dashboard/src/index.css`
- Modify: `tests/test_dashboard_overview_request_trace_inspector.py`
- Regenerate: `cutctx/dashboard/index.html`
- Regenerate: `cutctx/dashboard/assets/`

**Interfaces:**
- Consumes: `trace.decision_receipt` from Task 4.
- Produces: `DecisionReceiptSummary({ receipt })` and `DecisionReceiptEvidence({ receipt })` React components local to `Overview.jsx`.

- [ ] **Step 1: Extend the Playwright fixture with complete receipt evidence**

Create `_retained_trace_payload()` by calling `_trace_payload()`, replacing `provider.requested_model`, `provider.actual_model`, and every routing source/target with `gpt-5.4`, setting `routing.routed=False` and `routing.reason="workload_not_downgradeable"`, then adding this object under `payload["trace"]`:

```python
"decision_receipt": {
    "schema_version": 1,
    "request_id": "trace-1",
    "observation": {
        "completeness": "complete",
        "missing": [],
        "payload_capture": "disabled",
    },
    "routing": {
        "status": "retained",
        "reason": "workload_not_downgradeable",
        "explanation": "Recent tool context was classified as high-risk, so Cutctx retained the requested model.",
        "requested_model": "gpt-5.4",
        "effective_model": "gpt-5.4",
        "mechanism": "optimization_preset",
        "confidence": 0.91,
        "scorer": "heuristic_v1",
        "required_capabilities": ["tool_calling"],
        "candidates": ["gpt-5.4-mini"],
        "rejected_candidates": [
            {"candidate": "gpt-5.4-mini", "reason": "workload_not_downgradeable"}
        ],
        "transport": {"target_proven": True},
        "selection_evidence": {"signals": ["recent_tool_context"]},
        "request_overrides": None,
    },
    "compression": {
        "status": "applied",
        "reason": None,
        "input_tokens_original": 1500,
        "input_tokens_forwarded": 1000,
        "direct_tokens_saved": 300,
        "transforms": ["smart_crusher"],
        "protected_content": {"cache_protected_tokens": 200, "signals": ["recent_tool_context"]},
    },
    "cache": {
        "provider_prompt_cache": {"status": "hit", "read_tokens": 200, "write_tokens": 0, "inferred": False},
        "semantic_response_cache": {"status": "unobserved", "saved_tokens": 0},
        "self_hosted_prefix_cache": {"status": "unobserved", "saved_tokens": 0},
        "cache_safe_prefix": {"status": "protected", "protected_tokens": 200},
    },
    "ccr": {"status": "not_used", "references": [], "retrieval_outcome": "not_requested"},
    "attribution": {
        "total_saved_tokens": 500,
        "created_savings_tokens": 300,
        "observed_provider_savings_tokens": 200,
        "by_source_tokens": {"cutctx_compression": 300, "provider_prompt_cache": 200},
        "by_source_usd": {},
        "savings_basis": "estimated",
        "pricing_basis": "model_input_list_price",
    },
    "policy": {
        "routing_policy": None,
        "routing_mode": "conservative",
        "config_fingerprint": "sha256:abc",
        "cutctx_version": "0.31.0",
    },
},
```

- [ ] **Step 2: Write failing receipt-rendering assertions**

After opening the trace, assert:

```python
expect(trace_panel.get_by_text("Requested model retained", exact=True)).to_be_visible()
expect(trace_panel).to_contain_text("Recent tool context was classified as high-risk")
expect(trace_panel).to_contain_text("workload_not_downgradeable")
expect(trace_panel).to_contain_text("gpt-5.4-mini")
expect(trace_panel).to_contain_text("tool_calling")
expect(trace_panel.get_by_text("Provider prompt cache", exact=True)).to_be_visible()
expect(trace_panel).to_contain_text("CCR · Not Used")
expect(trace_panel).to_contain_text("sha256:abc")
expect(trace_panel.get_by_text("Payload capture", exact=True).first).to_be_visible()
expect(trace_panel).to_contain_text("disabled")
```

Add a second test with `observation.completeness="legacy"` and missing evidence. Assert the inspector shows `Partial evidence` and the missing field name, while no cache miss is fabricated.

- [ ] **Step 3: Run Playwright and verify RED**

Run: `rtk pytest tests/test_dashboard_overview_request_trace_inspector.py -q`

Expected: the new receipt text is absent.

- [ ] **Step 4: Implement receipt summary and evidence groups**

In `Overview.jsx`, add safe helpers:

```jsx
function titleCaseStatus(value) {
  return String(value || 'unobserved').replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatEvidence(value) {
  if (value == null) return 'Unobserved';
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}
```

Implement the components with this stable structure, expanding the same `EvidenceRow` pattern for all fields named in the fixture:

```jsx
function EvidenceRow({ label, value }) {
  return (
    <div className="diagnostic-row diagnostic-row-wrap">
      <span>{label}</span>
      <strong>{value == null || value === '' ? 'Unobserved' : String(value)}</strong>
    </div>
  );
}

function DecisionReceiptSummary({ receipt }) {
  if (!receipt || typeof receipt !== 'object') return null;
  const observation = receipt.observation || {};
  const routing = receipt.routing || {};
  const attribution = receipt.attribution || {};
  const statusLabel = routing.status === 'retained'
    ? 'Requested model retained'
    : routing.status === 'applied'
      ? 'Model route applied'
      : 'Routing evidence unavailable';
  const partial = observation.completeness !== 'complete';

  return (
    <section className={`decision-receipt-summary${partial ? ' is-partial' : ''}`}>
      <div className="decision-receipt-summary-copy">
        <div className="eyebrow">Decision receipt · schema {receipt.schema_version || 'unknown'}</div>
        <h3>{statusLabel}</h3>
        <p>{routing.explanation || 'No decision explanation was recorded.'}</p>
        <div className="decision-receipt-chip-row">
          <span className="transform-chip">{routing.reason || 'reason unobserved'}</span>
          <span className="transform-chip">
            {partial ? 'Partial evidence' : 'Complete evidence'}
          </span>
        </div>
      </div>
      <div className="decision-receipt-summary-metrics">
        <EvidenceRow
          label="Model"
          value={`${routing.requested_model || '—'} → ${routing.effective_model || '—'}`}
        />
        <EvidenceRow label="Created savings" value={formatInteger(attribution.created_savings_tokens || 0)} />
        <EvidenceRow
          label="Observed provider savings"
          value={formatInteger(attribution.observed_provider_savings_tokens || 0)}
        />
        <EvidenceRow label="Payload capture" value={observation.payload_capture || 'unobserved'} />
      </div>
    </section>
  );
}

function DecisionReceiptEvidence({ receipt }) {
  if (!receipt || typeof receipt !== 'object') return null;
  const routing = receipt.routing || {};
  const compression = receipt.compression || {};
  const cache = receipt.cache || {};
  const ccr = receipt.ccr || {};
  const attribution = receipt.attribution || {};
  const policy = receipt.policy || {};
  const missing = receipt.observation?.missing || [];

  return (
    <section className="decision-receipt-evidence" aria-label="Decision evidence">
      <details open>
        <summary>Routing evidence</summary>
        <EvidenceRow label="Mechanism" value={routing.mechanism} />
        <EvidenceRow label="Confidence" value={routing.confidence} />
        <EvidenceRow label="Scorer" value={routing.scorer} />
        <EvidenceRow label="Required capabilities" value={(routing.required_capabilities || []).join(', ')} />
        <EvidenceRow label="Candidates" value={(routing.candidates || []).join(', ')} />
        <pre className="decision-receipt-json">{formatEvidence(routing.rejected_candidates || [])}</pre>
        <pre className="decision-receipt-json">{formatEvidence(routing.transport || {})}</pre>
        <pre className="decision-receipt-json">{formatEvidence(routing.selection_evidence || {})}</pre>
      </details>
      <details>
        <summary>Context and compression</summary>
        <EvidenceRow label="Status" value={titleCaseStatus(compression.status)} />
        <EvidenceRow label="Reason" value={compression.reason} />
        <EvidenceRow label="Forwarded tokens" value={compression.input_tokens_forwarded} />
        <EvidenceRow label="Transforms" value={(compression.transforms || []).join(', ')} />
        <EvidenceRow label="Protected tokens" value={compression.protected_content?.cache_protected_tokens} />
      </details>
      <details>
        <summary>Cache and attribution</summary>
        <EvidenceRow label="Provider prompt cache" value={titleCaseStatus(cache.provider_prompt_cache?.status)} />
        <EvidenceRow label="Semantic response cache" value={titleCaseStatus(cache.semantic_response_cache?.status)} />
        <EvidenceRow label="Self-hosted prefix cache" value={titleCaseStatus(cache.self_hosted_prefix_cache?.status)} />
        <EvidenceRow label="Cache-safe prefix" value={titleCaseStatus(cache.cache_safe_prefix?.status)} />
        <pre className="decision-receipt-json">{formatEvidence(attribution.by_source_tokens || {})}</pre>
      </details>
      <details>
        <summary>CCR · {titleCaseStatus(ccr.status)}</summary>
        <EvidenceRow label="Retrieval outcome" value={titleCaseStatus(ccr.retrieval_outcome)} />
        <pre className="decision-receipt-json">{formatEvidence(ccr.references || [])}</pre>
      </details>
      <details>
        <summary>Policy and privacy</summary>
        <EvidenceRow label="Routing mode" value={policy.routing_mode} />
        <EvidenceRow label="Config fingerprint" value={policy.config_fingerprint} />
        <EvidenceRow label="Cutctx version" value={policy.cutctx_version} />
        <EvidenceRow label="Payload capture" value={receipt.observation?.payload_capture} />
        <EvidenceRow label="Missing evidence" value={missing.join(', ')} />
      </details>
    </section>
  );
}
```

Use existing `diagnostic-row` and `transform-chip` patterns. Unknown fields remain ignored, and unknown status values render through `titleCaseStatus`.

Place the summary before the current metric grid and the evidence groups before payload cards. Keep payload cards collapsed behind their existing logging gate and do not copy payload data into receipt components.

- [ ] **Step 5: Add focused receipt styles**

In `dashboard/src/index.css`, add styles scoped under `.decision-receipt-*` for the summary banner, status chips, evidence `<details>`, evidence JSON blocks, and responsive stacking. Reuse CSS variables and preserve current mobile breakpoints; do not change unrelated dashboard layout.

- [ ] **Step 6: Run source-level frontend checks**

Run from `dashboard/`:

```bash
rtk npm run test
rtk npm run lint
rtk npm run build
```

Expected: Node tests, ESLint, and Vite build pass.

- [ ] **Step 7: Synchronize packaged assets and run browser tests**

Run from the repository root:

```bash
rtk proxy python3 scripts/sync_dashboard_assets.py
rtk pytest tests/test_dashboard_overview_request_trace_inspector.py tests/test_dashboard_embedded_build.py -q
```

Expected: receipt browser tests and embedded-build contract pass against the regenerated package assets.

- [ ] **Step 8: Commit the dashboard receipt**

Run:

```bash
rtk git add dashboard/src/pages/Overview.jsx dashboard/src/index.css tests/test_dashboard_overview_request_trace_inspector.py cutctx/dashboard/index.html cutctx/dashboard/assets
rtk git -c core.editor=true commit -m "feat: explain request decisions in dashboard"
```

---

### Task 6: Documentation and full verification

**Files:**
- Modify: `docs/content/docs/proxy.mdx`
- Test: all files changed in Tasks 1–5.

**Interfaces:**
- Documents: `trace.decision_receipt` schema version, observation states, privacy boundary, legacy behavior, and example request.

- [ ] **Step 1: Add API documentation**

Document `GET /transformations/traces/{request_id}` with a compact version 1 receipt example. State explicitly:

- receipt metadata is available when full payload logging is disabled;
- `unobserved` is not a miss;
- provider prompt-cache savings are observed rather than created by Cutctx;
- CCR hashes never include retrieved content;
- legacy request-log rows return `observation.completeness="legacy"`;
- the endpoint requires local-admin authentication.

- [ ] **Step 2: Run focused Python verification**

Run:

```bash
rtk pytest tests/test_decision_receipt.py tests/test_request_outcome.py tests/test_proxy/test_request_logger.py tests/test_ccr_markers.py tests/test_proxy_compress_endpoint.py tests/test_proxy/test_request_trace_inspector.py tests/test_model_routing_trace.py tests/test_model_router.py -q
```

Expected: all focused receipt, persistence, CCR, cache-attribution, and routing tests pass.

- [ ] **Step 3: Run Python static checks**

Run:

```bash
rtk ruff check cutctx/proxy/decision_receipt.py cutctx/proxy/outcome.py cutctx/proxy/models.py cutctx/proxy/request_logger.py cutctx/ccr/markers.py cutctx/proxy/server.py cutctx/proxy/handlers/openai/compress.py cutctx/proxy/handlers/openai/responses.py tests/test_decision_receipt.py tests/test_request_outcome.py tests/test_proxy/test_request_logger.py tests/test_ccr_markers.py tests/test_proxy/test_request_trace_inspector.py tests/test_dashboard_overview_request_trace_inspector.py
rtk mypy cutctx/proxy/decision_receipt.py cutctx/proxy/outcome.py cutctx/proxy/models.py cutctx/proxy/request_logger.py cutctx/ccr/markers.py
```

Expected: no lint or type errors in changed Python modules.

- [ ] **Step 4: Run complete dashboard verification**

Run from `dashboard/`:

```bash
rtk npm run test
rtk npm run lint
rtk npm run build
```

Then run from the repository root:

```bash
rtk proxy python3 scripts/sync_dashboard_assets.py
rtk pytest tests/test_dashboard_overview_request_trace_inspector.py tests/test_dashboard_embedded_build.py tests/test_dashboard_audit.py -q
```

Expected: source tests, lint, build, packaged-asset checks, and browser audits pass.

- [ ] **Step 5: Prove repository integrity and scope**

Run:

```bash
rtk git diff --check
rtk git status --short
rtk git diff --stat HEAD~5..HEAD
```

Expected: no whitespace errors; only receipt implementation, tests, documentation, and generated dashboard assets are part of the implementation commits. Preserve the pre-existing `dashboard-cache-ttl-main.png` modification and the untracked competitive report unless the user separately requests them.

- [ ] **Step 6: Commit documentation**

Run:

```bash
rtk git add docs/content/docs/proxy.mdx
rtk git -c core.editor=true commit -m "docs: document decision receipts"
```

- [ ] **Step 7: Final completion audit**

Inspect one complete routed/retained receipt, one explicit cache miss, one unobserved cache state, one CCR-bearing receipt with payload logging disabled, one legacy row, and one rate-limit denial. Confirm each of the eight acceptance criteria in `docs/superpowers/specs/2026-07-17-context-decision-receipt-design.md` has direct test or runtime evidence before claiming completion.
