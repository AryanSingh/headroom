# Exhaustive Adversarial Verification Plan — Claude / Codex / Cursor

> Copied from approved plan for execution. Results filled during this campaign.
> Source plan (do not edit): `.cursor/plans/exhaustive_client_adversarial_plan_e417c781.plan.md`
> Executed: 2026-07-26

## Mission

Prove that **every core module** behaves correctly under **adversarial and realistic traffic** from Claude Code, Claude Desktop (MCP), Codex/ChatGPT, and Cursor CLI/Desktop.

**Non-goals:** VS Code/JetBrains extensions, non-named agents full matrix, EE multi-tenant, K8s restore drill.

Deliverable artifacts:

- `audit/2026-07-26-exhaustive-client-adversarial-plan.md` — this plan + results
- `audit/2026-07-26-adversarial-bug-ledger.md` — findings ledger
- `tests/test_client_matrix_adversarial_e2e.py` — new hermetic suite (18 passed)
- `scripts/verify_client_matrix_live.py` — process harness (16/16 passed)
- Progress: `audit/release-readiness-progress-2026-07-26.md`

---

## Severity taxonomy

| Sev | Definition | Exit impact |
|---|---|---|
| **S0** | Data corruption, wrong upstream model on adversarial HIGH, auth leak, broken live turn | Campaign **FAIL** until fixed |
| **S1** | Feature broken for a named client | Campaign **FAIL** until fixed |
| **S2** | Incorrect savings/stats/docs; recoverable UX gap | Must fix or explicit waiver |
| **S3** | Flake, polish, missing Ideal UX | Track; does not block if mitigated |

---

## Results

### Phase A — Hermetic baseline

| Pack | Command | Result | Notes |
|---|---|---|---|
| Pilot verifier | `.venv/bin/python scripts/verify_pilot_release.py` | **FAIL (env)** | 12/13 required checks passed; `rust-tests` failed with `ld: write() failed, errno=28 (No space left on device)` while linking. Focused retry `cargo test -p cutctx-core --lib` → **896 passed**. Evidence: `/tmp/phase_a_pilot.txt`, `/tmp/phase_a_rust_core.txt`. Ledger: ADV-20260726-010 |
| Routing L0+L1 | `pytest tests/test_model_routing_adversarial_e2e.py` + `tests/test_model_router.py` | **PASS** | Included in pack1 (100) + pack3 (143) |
| Auth | `test_auth_mode`, `test_auth_adversarial`, `test_header_isolation` | **PASS** | Pack1 |
| Byte-faithful | `tests/test_proxy_byte_faithful_forwarding.py` | **PASS** | Pack2 (56 with WS) |
| Codex WS | `test_openai_codex_ws_*` + keepalive | **PASS** | Pack2; landmine ADV-004 re-verified |
| Wrap config | wrap unit + e2e named clients | **PASS*** | `test_wrap_codex` + `test_provider_cursor` + `#746` = 77 passed. Full `e2e/wrap/run.py` reached OpenClaw and failed on npm `tsup` chunk (out of named-client scope). Claude/Codex/Cursor wrap verified before that (cursor via silent Popen success → cline continued). Ledger: ADV-20260726-011 |
| Agent protocol | `pytest tests/agent_e2e/` | **PASS** | Pack3 |
| Quality | `python -m benchmarks.model_routing_quality --ci` | **PASS** | `unsafe_downgrade_rate == 0.0` (75 cases) |
| Compression adversarial | `benchmarks/adversarial_ccr_tests.py` | **FAIL (benchmark debt)** | 21/36; 4 CRITICAL AttributeError on nested/string shapes. Not named-client S0; logged ADV-20260726-012 (S2) |
| Client matrix suite | `pytest tests/test_client_matrix_adversarial_e2e.py` | **PASS** | **18/18** |

\* Named-client wrap path PASS; full multi-agent wrap script FAIL on OpenClaw (non-goal).

### Phase B — Process harness

| Check | Result | Notes |
|---|---|---|
| `scripts/verify_client_matrix_live.py` | **PASS** | 16/16: livez/readyz/stats, Messages/Chat/Responses routing, mode toggle ack, `cutctx wrap {claude,codex,cursor} --help`, `cutctx routing status`. `CUTCTX_SKIP_UPSTREAM_CHECK=1` |

### Phase C — Live agents

Resumed 2026-07-26 with Claude **subscription** OAuth (CLI), Codex **ChatGPT** auth (`~/.codex/auth.json` `auth_mode=chatgpt`), and project `CUTCTX_UPSTREAM_OPENAI_API_KEY` → session `OPENAI_API_KEY`. Ephemeral proxy `--model-routing-preset auto` on port `55756`. Nested-Claude runs require `unset CLAUDECODE`. Default Codex model `gpt-5.6-terra` rejected by CLI 0.145.0 — live CDX used `-m gpt-5.4`.

| ID | Result | Missing / evidence |
|---|---|---|
| LIVE-CC-1 | **PASS** | Rename `greet`→`say_hello` via `ANTHROPIC_BASE_URL` + Claude Code 2.1.63; session `aab87cdb-9137-45ee-a479-b7aadb373a83`; model `claude-sonnet-4-6` |
| LIVE-CC-2 | **PASS** | Fixed `bug.py` add(); code fence present; session `d35be415-1814-4d26-8cf1-4ae42f27be3a`; no unsafe GPT Mini |
| LIVE-CC-3 | **PASS** | `ENABLE_TOOL_SEARCH=true`; marker `ZZTOOLSEARCH99`; session `1c546512-1d36-44f7-8792-387d32dae038` |
| LIVE-CDX-1 | **PASS** | `codex exec -m gpt-5.4` via `OPENAI_BASE_URL`; agent_message `ZZCODEXHTTP77` |
| LIVE-CDX-2 | **PASS** | `sleep 35` tool loop; agent_message `ZZWSLONG55`; no mid-turn disconnect; rc=0 |
| LIVE-CDX-3 | **PASS** | ChatGPT-sub path `-m gpt-5.4`; agent_message `ZZSUBMODEL88` (ADV-007 hermetic still covers downgrade forbid) |
| LIVE-CUR-1 | **BLOCKED** | Cursor.app CLI present (`…/Cursor.app/Contents/Resources/app/bin/cursor`); `cursor agent` requires `cursor agent login` / `CURSOR_API_KEY` |
| LIVE-CUR-2 | **BLOCKED** | same auth gate |
| LIVE-MEM | **PASS** | Two-turn recall session `608f6c95-788e-4dc0-9918-cb282c74a8ad`; `ZZMEM2:ZZMEMCODE42` |

Regression after live: hermetic client-matrix **18/18**; `verify_client_matrix_live.py` **16/16**.

### Phase D — Desktops

| Checklist | Result | Notes |
|---|---|---|
| Cursor Desktop | **BLOCKED** | `/Applications/Cursor.app` present; no operator live turns executed (no base-URL override session signed) |
| Claude Desktop MCP | **PARTIAL** | Docs claim check **PASS**. `cutctx mcp install --agent claude-desktop --gateway` → Desktop MCP **configured** (`~/Library/Application Support/Claude/claude_desktop_config.json`). Gateway 0 other servers wrapped. Operator must restart Claude Desktop; live tool-compress/retrieve not signed this session |
| Codex Desktop / ChatGPT | **BLOCKED** | `/Applications/ChatGPT.app` present; no operator long-WS / zstd GUI session signed (CLI ChatGPT-sub covered by LIVE-CDX-*) |

### Phase E — Dashboard

| Check | Result | Notes |
|---|---|---|
| Orchestrator pytest `/stats` | **PASS** | `tests/test_dashboard_orchestrator.py` + matrix `/stats` mode APIs; landmine re-run 39 passed |
| Playwright `orchestrator.spec.js` | **PASS*** | Chromium installed (`npx playwright install chromium`). Full suite 21/22 then flake retry of `silently aborts a pending load on unmount` → **PASS**. Net: orchestrator e2e green after one flake retry |

### Coverage matrix evidence IDs

| | Wrap | Auth | Compress | CCR | Routing | Memory | License | Stream/WS | MCP | Stats |
|---|---|---|---|---|---|---|---|---|---|---|
| Claude Code | W1=`#746`+wrap-e2e+LIVE-CC | A1=`test_auth_*`+sub OAuth live | C1=byte-faithful+LIVE-CC | R1=agent_e2e | M1=matrix+LIVE-CC | Mem1=LIVE-MEM PASS | L1=pilot license pack | S1=messages matrix+LIVE-CC | MCP2=install attempted | D1=matrix `/stats` |
| Claude Desktop | W2=`mcp status` configured | — | C2*=docs+MCP install | — | — | Mem2*=operator pending | L2=pilot | — | MCP1=docs PASS; Desktop MCP configured | D2=mcp status truthful |
| Codex CLI | W3=wrap-e2e+LIVE-CDX-1/2 | A2=`test_auth_*`+ChatGPT tokens | C3=zstd ADV-005 | R2=agent_e2e | M2=matrix+LIVE-CDX | Mem3=hermetic | L3=pilot | S2=LIVE-CDX-2 long tool | — | D3=matrix+live harness |
| ChatGPT Sub | W4=wrap+LIVE-CDX-3 | A3=subscription live | C4=zstd drop | R3=opaque resume unit | M3†=ADV-007+LIVE-CDX-3 | Mem4=hermetic | L4=pilot | S3=LIVE-CDX-2/3 | — | D4=stats |
| Cursor CLI | W5=`test_provider_cursor`+CLI present | A4=UA matrix; agent login BLOCKED | C5=byte-faithful | R4=agent_e2e patterns | M4=chat matrix | Mem5=hermetic | L5=pilot | S4=chat stream hermetic | — | D5=matrix |
| Cursor Desktop | W6=wrap-e2e cursor (silent pass) | A5=UA | C6=hermetic | R5=hermetic | M5=hermetic | Mem6=BLOCKED live | L6=pilot | S5=hermetic | — | D6=orchestrator+Playwright |

\* Desktop compression via MCP gateway tool output, not Messages proxy.  
† Subscription WS must never downgrade allowlisted models — **PASS** ADV-007.

### Open S0/S1

**None** (product). Environment/process gaps logged as BLOCKED / S2 / S3 only.

### Campaign verdict

**FAIL** against full exit gate (release claim) — narrowed residual gaps.

Reasons remaining:

1. Phase A pilot verifier not 13/13 (rust-tests disk exhaustion) — mitigated by focused `cutctx-core` green, but gate unmet.
2. Phase C LIVE-CUR-1/2 **BLOCKED** (`cursor agent` login / `CURSOR_API_KEY` missing). Other LIVE-* **PASS**.
3. Phase D Cursor Desktop + ChatGPT Desktop GUI operator turns still unsigned; Claude Desktop MCP configured but live tool-compress after app restart not signed.
4. CCR adversarial suite 21/36 (S2 debt) — waiver-eligible for named-client release but not green.

Cleared this resume: Phase C Claude/Codex/MEM live, Phase E Playwright (after Chromium install), Claude Desktop MCP install, hermetic 18/18 + harness 16/16 re-verified. Zero open S0/S1.
