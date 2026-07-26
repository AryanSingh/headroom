# Exhaustive Adversarial Verification Plan — Claude / Codex / Cursor

> Copied from approved plan for execution. Results filled during this campaign.
> Source plan (do not edit): `.cursor/plans/exhaustive_client_adversarial_plan_e417c781.plan.md`

## Mission

Prove that **every core module** behaves correctly under **adversarial and realistic traffic** from:

| Client | Attach path |
|---|---|
| Claude Code CLI | `cutctx wrap claude` → `ANTHROPIC_BASE_URL` → `POST /v1/messages` |
| Claude Desktop | MCP + gateway only (hosted models **cannot** use Messages proxy); optional experimental intercept |
| Codex CLI | `cutctx wrap codex` → `OPENAI_BASE_URL` + `~/.codex/config.toml` → HTTP/WS `/v1/responses` (+ aliases) |
| ChatGPT-subscription Codex | Same Responses path → `chatgpt.com/backend-api/codex/responses` (HTTP + WSS) |
| Cursor CLI / agent | OpenAI-compatible base URL → chat/responses/messages |
| Cursor Desktop | Manual Settings override → `http://127.0.0.1:8787[/p/<proj>]/v1` |

**Non-goals for this campaign (explicit):** VS Code/JetBrains extensions, non-named agents (Aider/Windsurf/etc.), full EE multi-tenant matrix, K8s restore drill. Those stay on the existing post-pilot backlog unless a named-client path hits them.

**Default assumption:** Live provider keys and installed Claude/Codex/Cursor apps are available for Phase C–D. If a key/app is missing, that phase is marked **BLOCKED** (not PASS) — never silently skipped.

Deliverable artifacts:

- `audit/2026-07-26-exhaustive-client-adversarial-plan.md` — this plan + results
- `audit/2026-07-26-adversarial-bug-ledger.md` — every finding (bug/gap/flake) with severity + repro
- Expanded automated suites under `tests/` + `scripts/verify_client_matrix_live.py`
- Progress updates in `audit/release-readiness-progress-2026-07-26.md`

---

## Architecture under test

Core module owners (code to attack):

| Module | Primary code |
|---|---|
| Proxy integrity / streaming / byte-faithful | `cutctx/proxy/server.py`, `handlers/anthropic.py`, `handlers/openai/`, `helpers.py` |
| Auth modes | `cutctx/proxy/auth_mode.py`, `docs/auth-modes.md` |
| Compression + SmartCrusher + logs | `cutctx/transforms/`, `crates/cutctx-core/` |
| CCR | `cutctx/ccr/` |
| Model routing / Auto | `cutctx/proxy/model_router.py` |
| Memory | `cutctx/memory/` |
| Licensing / seats | `cutctx/proxy/license_validation.py`, EE billing facades |
| Wrap / install | `cutctx/cli/wrap.py`, `cutctx/providers/{claude,codex,cursor}/` |
| MCP / Desktop gateway | `cutctx/mcp_gateway.py`, `cutctx/mcp_server.py` |
| Observability | `/stats`, `/readyz`, dashboard Orchestrator/Savings |

Reuse (do not reinvent): routing adversarial suite already green (`tests/test_model_routing_adversarial_e2e.py`); agent protocol suite (`tests/agent_e2e/`); wrap e2e (`e2e/wrap/run.py`); byte-faithful (`tests/test_proxy_byte_faithful_forwarding.py`); Codex WS keepalive (`tests/test_codex_uvicorn_keepalive.py`); issue #746 tool search (`tests/test_issue_746_tool_search.py`).

---

## Severity taxonomy (every finding must use this)

| Sev | Definition | Exit impact |
|---|---|---|
| **S0** | Data corruption, wrong upstream model on adversarial HIGH, auth leak, broken live turn | Campaign **FAIL** until fixed |
| **S1** | Feature broken for a named client (wrap, WS drop, compression breaks tools) | Campaign **FAIL** until fixed |
| **S2** | Incorrect savings/stats/docs; recoverable UX gap | Must fix or explicit waiver |
| **S3** | Flake, polish, missing Ideal UX | Track; does not block if mitigated |

**Rule:** A phase cannot be marked PASS with open S0/S1. Gaps without repro are still logged as **GAP** (not ignored).

---

## Client × module coverage matrix (must be fully green)

Rows = clients; columns = modules. Each cell needs at least one automated or operator evidence ID.

| | Wrap/Install | Auth | Compress | CCR | Routing | Memory | License | Stream/WS | MCP | Stats/Dash |
|---|---|---|---|---|---|---|---|---|---|---|
| Claude Code | W1 | A1 | C1 | R1 | M1 | Mem1 | L1 | S1 | — | D1 |
| Claude Desktop | W2 | — | C2* | — | — | Mem2* | L2 | — | MCP1 | D2 |
| Codex CLI | W3 | A2 | C3 | R2 | M2 | Mem3 | L3 | S2 | — | D3 |
| ChatGPT Sub Codex | W4 | A3 | C4 | R3 | M3† | Mem4 | L4 | S3 | — | D4 |
| Cursor CLI | W5 | A4 | C5 | R4 | M4 | Mem5 | L5 | S4 | — | D5 |
| Cursor Desktop | W6 | A5 | C6 | R5 | M5 | Mem6 | L6 | S5 | — | D6 |

\* Desktop compression via MCP gateway tool output, not Messages proxy.  
† Subscription WS must **never** downgrade allowlisted models (`test_subscription_websocket_preserves_requested_model`).

---

## Phase plan (execute in order; stop on S0)

### Phase A — Hermetic gates (no live keys)

**Goal:** Prove module invariants with mocked upstream; capture exact upstream bytes/models.

1. **Baseline CI packs** (must be 100% green before expanding):
   - Pilot verifier: `scripts/verify_pilot_release.py`
   - Routing: existing L0+L1 from `audit/2026-07-26-model-routing-adversarial-test-plan.md`
   - Auth: `tests/test_auth_mode.py`, `tests/test_auth_adversarial.py`, `tests/test_header_isolation.py`
   - Byte-faithful: `tests/test_proxy_byte_faithful_forwarding.py`
   - Codex WS unit: `tests/test_openai_codex_ws_*.py`, keepalive test
   - Wrap config: `e2e/wrap/run.py`, `tests/test_cli/test_wrap_codex.py`, `tests/test_provider_cursor.py`, `tests/test_issue_746_tool_search.py`
   - Agent protocol: `tests/agent_e2e/` (Claude messages resume, Codex WS/HTTP resume, subscription overrides)
   - Quality: `python -m benchmarks.model_routing_quality --ci` (unsafe Mini = 0)
   - Compression adversarial: `benchmarks/adversarial_ccr_tests.py` (or documented subset)

2. **New hermetic suite** `tests/test_client_matrix_adversarial_e2e.py`:
   - One fixture per wire format (Messages / Chat Completions / Responses HTTP / Responses WS frame)
   - Capture via `_retry_request` with `backend=anthropic` (no LiteLLM bypass — lesson from prior routing work)
   - Isolate `CUTCTX_ORCHESTRATION_DIR` + savings + prefix tracker under `tmp_path`
   - Assert: upstream body model, `body_mutated` reasons include `model_routing` when routed, headers stripped correctly, stream frames intact

3. **Adversarial corpora** (every case gets ID in bug ledger even if pass): ADV-PROTOCOL, ADV-COMPRESS, ADV-CCR, ADV-ROUTE, ADV-AUTH, ADV-MEMORY, ADV-LICENSE, ADV-MCP

### Phase B — Process-level CLI (local proxy process)

**Harness:** `scripts/verify_client_matrix_live.py` (expand from `scripts/verify_model_routing_live.py`).

1. Start proxy with `CUTCTX_SKIP_UPSTREAM_CHECK=1` when mocked.
2. Assert `/livez`, `/readyz`, `/stats` shape.
3. Drive each wire format against the live port (mock upstream).
4. CLI: wrap dry-run / routing status / mcp where applicable.
5. Failure injection: kill proxy mid-WS; restart; confirm actionable error.

### Phase C — Live agent CLIs

**Requires:** `ANTHROPIC_API_KEY` and/or Claude OAuth; `OPENAI_API_KEY` and/or ChatGPT Codex auth; Cursor CLI installed.

### Phase D — Desktop apps (manual operator + instrumented proxy)

### Phase E — Dashboard / observability cross-check

### Phase F — Close the loop

---

## Pass / fail exit gate

**PASS** only if:

1. Phase A packs green + new client-matrix hermetic suite green  
2. Phase B live harness green  
3. Phase C: all LIVE-* rows PASS or explicitly BLOCKED with missing credential (BLOCKED ≠ PASS for release claim)  
4. Phase D: Cursor Desktop + Claude Desktop MCP + Codex Desktop (if installed) operator checklist signed in ledger  
5. Bug ledger: zero open S0/S1; every matrix cell has evidence ID  
6. Quality: `unsafe_downgrade_rate == 0`  

**FAIL** if any S0/S1 remains or any matrix cell has no evidence.

---

## Results

### Phase A — Hermetic baseline

| Pack | Command | Result | Notes |
|---|---|---|---|
| Pilot verifier | `.venv/bin/python scripts/verify_pilot_release.py` | _pending_ | |
| Routing L0+L1 | `pytest tests/test_model_routing_adversarial_e2e.py tests/test_model_router.py` | _pending_ | |
| Auth | `pytest tests/test_auth_mode.py tests/test_auth_adversarial.py tests/test_header_isolation.py` | _pending_ | |
| Byte-faithful | `pytest tests/test_proxy_byte_faithful_forwarding.py` | _pending_ | |
| Codex WS | `pytest tests/test_openai_codex_ws_*.py tests/test_codex_uvicorn_keepalive.py` | _pending_ | |
| Wrap config | `e2e/wrap/run.py` + wrap/provider/issue746 tests | _pending_ | |
| Agent protocol | `pytest tests/agent_e2e/` | _pending_ | |
| Quality | `python -m benchmarks.model_routing_quality --ci` | _pending_ | |
| Compression adversarial | `benchmarks/adversarial_ccr_tests.py` (subset) | _pending_ | |
| Client matrix suite | `pytest tests/test_client_matrix_adversarial_e2e.py` | _pending_ | |

### Phase B — Process harness

| Check | Result | Notes |
|---|---|---|
| `scripts/verify_client_matrix_live.py` | _pending_ | |

### Phase C — Live agents

| ID | Result | Missing / evidence |
|---|---|---|
| LIVE-CC-1 | _pending_ | |
| LIVE-CC-2 | _pending_ | |
| LIVE-CC-3 | _pending_ | |
| LIVE-CDX-1 | _pending_ | |
| LIVE-CDX-2 | _pending_ | |
| LIVE-CDX-3 | _pending_ | |
| LIVE-CUR-1 | _pending_ | |
| LIVE-CUR-2 | _pending_ | |
| LIVE-MEM | _pending_ | |

### Phase D — Desktops

| Checklist | Result | Notes |
|---|---|---|
| Cursor Desktop | _pending_ | |
| Claude Desktop MCP | _pending_ | |
| Codex Desktop | _pending_ | |

### Phase E — Dashboard

| Check | Result | Notes |
|---|---|---|
| Orchestrator pytest /stats | _pending_ | |
| Playwright orchestrator.spec.js | _pending_ | |

### Coverage matrix evidence IDs

| | Wrap | Auth | Compress | CCR | Routing | Memory | License | Stream/WS | MCP | Stats |
|---|---|---|---|---|---|---|---|---|---|---|
| Claude Code | | | | | | | | | — | |
| Claude Desktop | | — | | — | — | | | — | | |
| Codex CLI | | | | | | | | | — | |
| ChatGPT Sub | | | | | | | | | — | |
| Cursor CLI | | | | | | | | | — | |
| Cursor Desktop | | | | | | | | | — | |

### Campaign verdict

**_pending_** — filled at finalize-pass-gate.
