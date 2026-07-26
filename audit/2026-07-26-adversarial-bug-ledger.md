# Adversarial Bug / Gap Ledger — 2026-07-26

Campaign: Exhaustive client adversarial verification (Claude / Codex / Cursor).
Plan: `audit/2026-07-26-exhaustive-client-adversarial-plan.md`

Severity: S0 | S1 | S2 | S3 | GAP | BLOCKED
Status: OPEN | FIXED | PASS | WAIVED | BLOCKED

---

## Prior landmines (re-verify)

### ADV-20260726-001 — Anthropic Auto body mutation + mark_mutated

```text
ID: ADV-20260726-001
Sev: S0
Client: Claude Code
Module: routing
Status: PASS
Repro: POST /v1/messages model=auto low-complexity; UpstreamCapture model in FAST
Expected vs Actual: routed model applied on Anthropic path
Root cause (if known): Previously Auto resolved but body not mutated
Fix / waiver: handlers/anthropic.py + mark_mutated("model_routing")
Regression test path: tests/test_model_routing_adversarial_e2e.py; tests/test_client_matrix_adversarial_e2e.py::test_messages_auto_low_routes_fast
Evidence: Phase A pack1 + client-matrix 18/18 (2026-07-26)
```

### ADV-20260726-002 — Uncertified catalog must not block static downgrades

```text
ID: ADV-20260726-002
Sev: S0
Client: Cursor CLI / Codex
Module: routing
Status: PASS
Repro: strong+LOW with routing preset; expect Mini downgrade
Expected vs Actual: gpt-5.4-mini
Regression test path: tests/test_model_router.py; tests/test_model_routing_adversarial_e2e.py
Evidence: Phase A pack3 model_router suite green
```

### ADV-20260726-003 — LiteLLM backend bypasses _retry_request mocks

```text
ID: ADV-20260726-003
Sev: S3
Client: test harness
Module: routing / test design
Status: PASS (constraint documented)
Repro: backend="openai" bypasses capture
Expected vs Actual: fixtures use backend="anthropic"
Regression test path: tests/test_client_matrix_adversarial_e2e.py fixture docstring
Evidence: suite green with capture
```

### ADV-20260726-004 — uvicorn WS ping 20s → Codex mid-turn drop

```text
ID: ADV-20260726-004
Sev: S1
Client: Codex CLI
Module: ws
Status: PASS
Repro: run_server kwargs ws_ping_interval/timeout
Expected vs Actual: 600/600
Regression test path: tests/test_codex_uvicorn_keepalive.py; matrix test_adv_ws_keepalive_config
Evidence: landmine re-verify 2026-07-26 PASS
```

### ADV-20260726-005 — Content-Encoding left after zstd decode → chatgpt.com 400

```text
ID: ADV-20260726-005
Sev: S1
Client: ChatGPT Sub Codex
Module: compress / ws
Status: PASS
Repro: zstd-encoded Responses body
Expected vs Actual: content-encoding dropped after decode
Regression test path: tests/test_openai_codex_routing.py::test_handle_openai_responses_drops_encoding_after_decoding_zstd
Evidence: landmine re-verify PASS; matrix HTTP path asserts no encoding on JSON POST
```

### ADV-20260726-006 — Custom ANTHROPIC_BASE_URL without ENABLE_TOOL_SEARCH

```text
ID: ADV-20260726-006
Sev: S1
Client: Claude Code
Module: wrap
Status: PASS
Repro: cutctx wrap claude injects ENABLE_TOOL_SEARCH
Expected vs Actual: ENABLE_TOOL_SEARCH=true
Regression test path: tests/test_issue_746_tool_search.py
Evidence: landmine re-verify PASS; wrap-e2e log shows ENABLE_TOOL_SEARCH=true
```

### ADV-20260726-007 — Subscription WS model downgrade forbidden

```text
ID: ADV-20260726-007
Sev: S0
Client: ChatGPT Sub Codex
Module: routing
Status: PASS
Repro: prepare_model_routing(..., implicit_downgrade_allowed=False, allow_transport_safe_targets=False)
Expected vs Actual: gpt-5.6-sol preserved
Regression test path: tests/test_model_router.py::test_subscription_websocket_preserves_requested_model
Evidence: landmine re-verify PASS
```

### ADV-20260726-008 — Byte-faithful forwarding when body_mutated=False

```text
ID: ADV-20260726-008
Sev: S0
Client: all
Module: proxy
Status: PASS
Repro: tests/test_proxy_byte_faithful_forwarding.py
Expected vs Actual: original bytes forwarded
Regression test path: tests/test_proxy_byte_faithful_forwarding.py
Evidence: Phase A pack2 PASS
```

---

## New findings (campaign)

### ADV-20260726-009 — Tool surface defaults slim 100+ tools to 16

```text
ID: ADV-20260726-009
Sev: S3
Client: Cursor CLI / Codex (chat tools)
Module: compress / tool_surface
Status: PASS (by design)
Repro: POST /v1/chat/completions with 120 tools
Expected vs Actual: upstream receives <= CUTCTX_TOOL_SURFACE_MAX_TOOLS (default 16); request 200
Root cause (if known): cutctx/proxy/tool_surface.py default max 16
Fix / waiver: By design; Claude tool-search path uses ENABLE_TOOL_SEARCH instead of eager schemas
Regression test path: tests/test_client_matrix_adversarial_e2e.py::test_adv_protocol_oversized_tools_chat
Evidence: matrix suite PASS
```

### ADV-20260726-010 — Pilot rust-tests disk exhaustion

```text
ID: ADV-20260726-010
Sev: S3
Client: CI / operator machine
Module: build
Status: BLOCKED (env)
Repro: scripts/verify_pilot_release.py → cargo test --workspace
Expected vs Actual: link failed errno=28 No space left on device
Root cause (if known): large target/ + sandbox cargo cache; ~25G free but linker write failed mid-build
Fix / waiver: Free disk / clean target; focused cargo test -p cutctx-core --lib = 896 passed
Regression test path: n/a (environment)
Evidence: /tmp/phase_a_pilot.txt; /tmp/phase_a_rust_core.txt
```

### ADV-20260726-011 — Wrap e2e OpenClaw npm tsup failure

```text
ID: ADV-20260726-011
Sev: S3
Client: OpenClaw (non-goal for this campaign)
Module: wrap
Status: OPEN (out of named-client scope)
Repro: e2e/wrap/run.py → cutctx wrap openclaw --plugin-path …
Expected vs Actual: npm run build fails Cannot find module './chunk-DI5BO6XE.js' (tsup)
Root cause (if known): local plugin npm install incomplete/corrupt chunk
Fix / waiver: Out of campaign non-goals; named clients Claude/Codex/Cursor verified earlier in same run
Regression test path: e2e/wrap/run.py
Evidence: /tmp/phase_a_wrap.txt
```

### ADV-20260726-012 — CCR adversarial suite AttributeError debt

```text
ID: ADV-20260726-012
Sev: S2
Client: compression benchmark (not single named client path)
Module: compress / SmartCrusher
Status: OPEN
Repro: .venv/bin/python benchmarks/adversarial_ccr_tests.py → 21/36
Expected vs Actual: 4 CRITICAL failures AttributeError: 'str' object has no attribute 'get' on nested/string shapes; several EXTREME scale timeouts treated as fail
Root cause (if known): adversarial harness assumes dict-shaped tool outputs in places
Fix / waiver: Track as benchmark debt; named-client byte-faithful + log fidelity landmines PASS. Waiver candidate for pilot if not on Messages/Responses happy path.
Regression test path: benchmarks/adversarial_ccr_tests.py
Evidence: /tmp/phase_a_ccr.txt
```

### ADV-20260726-013 — Playwright Chromium missing

```text
ID: ADV-20260726-013
Sev: BLOCKED→PASS
Client: dashboard
Module: stats/dash
Status: PASS
Repro: cd dashboard && npx playwright test e2e/orchestrator.spec.js
Expected vs Actual: Chromium installed; suite green (21/22 then flake retry of unmount abort → PASS)
Root cause (if known): Playwright browsers not installed initially
Fix / waiver: npx playwright install chromium
Regression test path: dashboard/e2e/orchestrator.spec.js
Evidence: Phase E resume 2026-07-26; flake retry log /tmp/cutctx-live-phasec/playwright_flake_retry.log
```

---

## LIVE-* / Desktop rows (updated resume)

```text
ID: ADV-20260726-014
Sev: was BLOCKED
Client: Claude Code
Module: live
Status: PASS
Repro: LIVE-CC-1/2/3 via ANTHROPIC_BASE_URL + Claude subscription OAuth (unset CLAUDECODE for nested)
Expected vs Actual: sessions aab87cdb… / d35be415… / 1c546512…; model claude-sonnet-4-6
Evidence: /tmp/cutctx-live-phasec/results_final.jsonl + *.parsed.json
```

```text
ID: ADV-20260726-015
Sev: was BLOCKED
Client: Codex CLI / ChatGPT Sub
Module: live
Status: PASS
Repro: LIVE-CDX-1/2/3 with OPENAI_BASE_URL + ChatGPT auth; -m gpt-5.4 (terra rejected by CLI 0.145.0)
Expected vs Actual: tokens ZZCODEXHTTP77 / ZZWSLONG55 / ZZSUBMODEL88 in agent_message events
Evidence: live_cdx*f.out.meta.json; proxy openai requests observed
```

```text
ID: ADV-20260726-016
Sev: BLOCKED
Client: Cursor CLI
Module: live
Status: BLOCKED
Repro: LIVE-CUR-1/2
Expected vs Actual: cursor agent binary present under Cursor.app but requires cursor agent login / CURSOR_API_KEY
Evidence: Phase C resume 2026-07-26
```

```text
ID: ADV-20260726-017
Sev: was BLOCKED
Client: Claude Desktop
Module: mcp
Status: PARTIAL
Repro: cutctx mcp install --agent claude-desktop --gateway
Expected vs Actual: Desktop MCP configured; gateway 0 other servers; operator restart + live tool-compress still pending
Evidence: mcp status after install 2026-07-26
```

```text
ID: ADV-20260726-018
Sev: BLOCKED
Client: Cursor Desktop / Codex Desktop
Module: desktop operator
Status: BLOCKED
Repro: Phase D operator turns
Expected vs Actual: Apps present; GUI live sessions not signed (CLI ChatGPT-sub covered by LIVE-CDX)
Evidence: /Applications/{Cursor,Claude,ChatGPT}.app present
```

```text
ID: ADV-20260726-019
Sev: S3
Client: Codex CLI
Module: live / models
Status: OPEN (env/compat)
Repro: default model gpt-5.6-terra via ChatGPT sub
Expected vs Actual: 400 "requires a newer version of Codex" on CLI 0.145.0; workaround -m gpt-5.4
Root cause (if known): CLI/model catalog skew vs ChatGPT default
Fix / waiver: document supported model pin for live harness; upgrade Codex when available
Evidence: live_cdx1.out turn.failed prior to model pin
```

---

## Summary counters

| Status | Count |
|---|---|
| OPEN S0/S1 | **0** |
| PASS landmines | 8 |
| LIVE PASS | CC-1/2/3, CDX-1/2/3, MEM |
| BLOCKED remaining | CUR-1/2 + Desktop GUI (018) |
| PARTIAL | Claude Desktop MCP (017) |
| OPEN S2 (CCR debt) | 1 (012) |
| OPEN S3 | OpenClaw wrap / disk / terra CLI skew (010–011, 019) |
| PASS by-design S3 | 1 (009) |
| Playwright | PASS (013) |
