# Adversarial Bug / Gap Ledger — 2026-07-26

Campaign: Exhaustive client adversarial verification (Claude / Codex / Cursor).
Plan: `audit/2026-07-26-exhaustive-client-adversarial-plan.md`

Severity: S0 | S1 | S2 | S3 | GAP | BLOCKED
Status: OPEN | FIXED | PASS | WAIVED | BLOCKED

Entry format:

```text
ID: ADV-YYYYMMDD-NNN
Sev: S0|S1|S2|S3|GAP|BLOCKED
Client: Claude Code|Codex|Cursor Desktop|…
Module: routing|compress|ws|…
Status: OPEN|FIXED|PASS|WAIVED|BLOCKED
Repro: exact commands + body shape
Expected vs Actual:
Root cause (if known):
Fix / waiver:
Regression test path:
Evidence:
```

---

## Prior landmines (re-verify)

### ADV-20260726-001 — Anthropic Auto body mutation + mark_mutated

```text
ID: ADV-20260726-001
Sev: S0
Client: Claude Code
Module: routing
Status: PASS (re-verify pending Phase A)
Repro: POST /v1/messages model=auto low-complexity prompt with backend=anthropic; inspect UpstreamCapture body + mutation reasons
Expected vs Actual: body["model"] rewritten to fast tier; mark_mutated("model_routing") present when routed
Root cause (if known): Previously Auto resolved but Anthropic path did not mutate upstream body
Fix / waiver: handlers/anthropic.py mutates body + mark_mutated("model_routing")
Regression test path: tests/test_model_routing_adversarial_e2e.py::test_e2e_auto_anthropic_low_and_high; tests/test_client_matrix_adversarial_e2e.py
Evidence:
```

### ADV-20260726-002 — Uncertified catalog must not block static downgrades

```text
ID: ADV-20260726-002
Sev: S0
Client: Cursor CLI / Codex
Module: routing
Status: PASS (re-verify pending Phase A)
Repro: Pollute models.json with uncertified inventory; request strong+LOW; expect static downgrade
Expected vs Actual: Downgrade to gpt-5.4-mini still occurs
Root cause (if known): _catalog_manages_source incorrectly treated uncertified inventory as authoritative
Fix / waiver: certification required for catalog-managed source
Regression test path: tests/test_model_router.py; tests/test_model_routing_adversarial_e2e.py
Evidence:
```

### ADV-20260726-003 — LiteLLM backend bypasses _retry_request mocks

```text
ID: ADV-20260726-003
Sev: S3
Client: test harness
Module: routing / test design
Status: PASS (constraint documented)
Repro: ProxyConfig(backend="openai") installs LiteLLM; monkeypatch of _retry_request never sees bodies
Expected vs Actual: Capture must use backend="anthropic" so anthropic_backend is None
Root cause (if known): LiteLLM path does not call _retry_request
Fix / waiver: All client-matrix / routing e2e fixtures use backend="anthropic"
Regression test path: tests/test_client_matrix_adversarial_e2e.py fixture docstring
Evidence:
```

### ADV-20260726-004 — uvicorn WS ping 20s → Codex mid-turn drop

```text
ID: ADV-20260726-004
Sev: S1
Client: Codex CLI
Module: ws
Status: PASS (re-verify pending Phase A)
Repro: Idle >20s between tool turns on /v1/responses WS
Expected vs Actual: Keepalive configured so mid-turn drop does not occur
Root cause (if known): Default uvicorn ping interval too aggressive
Fix / waiver: keepalive tuning
Regression test path: tests/test_codex_uvicorn_keepalive.py
Evidence:
```

### ADV-20260726-005 — Content-Encoding left after zstd decode → chatgpt.com 400

```text
ID: ADV-20260726-005
Sev: S1
Client: ChatGPT Sub Codex
Module: compress / ws
Status: PASS (re-verify pending Phase A)
Repro: Responses request with Content-Encoding: zstd; decode body then forward
Expected vs Actual: Encoding header dropped after decode so upstream does not 400
Root cause (if known): Header retained after transparent decode
Fix / waiver: drop Content-Encoding after decode
Regression test path: tests/test_openai_codex_routing.py::test_handle_openai_responses_drops_encoding_after_decoding_zstd
Evidence:
```

### ADV-20260726-006 — Custom ANTHROPIC_BASE_URL without ENABLE_TOOL_SEARCH

```text
ID: ADV-20260726-006
Sev: S1
Client: Claude Code
Module: wrap
Status: PASS (re-verify pending Phase A)
Repro: cutctx wrap claude; inspect launched env for ENABLE_TOOL_SEARCH
Expected vs Actual: ENABLE_TOOL_SEARCH=true injected so tool-search works via proxy
Root cause (if known): Claude Code disables tool-search when BASE_URL is custom unless flag set
Fix / waiver: wrap injects ENABLE_TOOL_SEARCH
Regression test path: tests/test_issue_746_tool_search.py
Evidence:
```

### ADV-20260726-007 — Subscription WS model downgrade forbidden

```text
ID: ADV-20260726-007
Sev: S0
Client: ChatGPT Sub Codex
Module: routing
Status: PASS (re-verify pending Phase A)
Repro: Subscription WS turn with allowlisted strong model + low-complexity prompt
Expected vs Actual: Requested model preserved; no Mini downgrade
Root cause (if known): Subscription path must not apply Auto downgrades
Fix / waiver: subscription websocket preserve requested model
Regression test path: tests/test_model_router.py::test_subscription_websocket_preserves_requested_model
Evidence:
```

### ADV-20260726-008 — Byte-faithful forwarding when body_mutated=False

```text
ID: ADV-20260726-008
Sev: S0
Client: all
Module: proxy
Status: PASS (re-verify pending Phase A)
Repro: Request that does not mutate body; compare original_body_bytes to upstream wire
Expected vs Actual: Exact bytes forwarded when body_mutated=False
Root cause (if known): JSON re-serialize could alter bytes
Fix / waiver: original_body_bytes path
Regression test path: tests/test_proxy_byte_faithful_forwarding.py
Evidence:
```

---

## New findings (campaign)

_(Filled as Phase A–E execute.)_

---

## LIVE-* / Desktop BLOCKED rows

_(Filled during Phase C–D.)_

---

## Summary counters

| Status | Count |
|---|---|
| OPEN S0/S1 | 0 (pending scan) |
| PASS landmines | 8 pending re-verify |
| BLOCKED live | 0 pending |
| GAP | 0 |
