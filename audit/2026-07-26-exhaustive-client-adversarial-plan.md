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

| ID | Result | Missing / evidence |
|---|---|---|
| LIVE-CC-1 | **BLOCKED** | `ANTHROPIC_API_KEY` unset in environment |
| LIVE-CC-2 | **BLOCKED** | same |
| LIVE-CC-3 | **BLOCKED** | same |
| LIVE-CDX-1 | **BLOCKED** | `OPENAI_API_KEY` unset (Codex CLI present `0.145.0`; `~/.codex/auth.json` exists but live spend not executed) |
| LIVE-CDX-2 | **BLOCKED** | same |
| LIVE-CDX-3 | **BLOCKED** | same |
| LIVE-CUR-1 | **BLOCKED** | `cursor` CLI binary not on PATH |
| LIVE-CUR-2 | **BLOCKED** | same |
| LIVE-MEM | **BLOCKED** | no live provider key for memory two-turn |

Claude Code CLI present (`2.1.214`). Cursor Desktop app present but CLI missing.

### Phase D — Desktops

| Checklist | Result | Notes |
|---|---|---|
| Cursor Desktop | **BLOCKED** | `/Applications/Cursor.app` present; no operator live turns executed (no base-URL override session signed) |
| Claude Desktop MCP | **PARTIAL / BLOCKED live** | Docs claim check **PASS** (`docs/superpowers/specs/2026-07-21-claude-desktop-routing-operability-design.md` correctly states hosted models cannot use Messages proxy / must not set `ANTHROPIC_BASE_URL` for hosted traffic). `cutctx mcp status`: Desktop MCP **not configured**; gateway 0 servers. Live tool-compress/retrieve not executed |
| Codex Desktop / ChatGPT | **BLOCKED** | `/Applications/ChatGPT.app` present; no operator long-WS / zstd session signed |

### Phase E — Dashboard

| Check | Result | Notes |
|---|---|---|
| Orchestrator pytest `/stats` | **PASS** | `tests/test_dashboard_orchestrator.py` + matrix `/stats` mode APIs; landmine re-run 39 passed |
| Playwright `orchestrator.spec.js` | **BLOCKED** | Chromium headless shell missing under Playwright cache; `npx playwright install` not approved in-session |

### Coverage matrix evidence IDs

| | Wrap | Auth | Compress | CCR | Routing | Memory | License | Stream/WS | MCP | Stats |
|---|---|---|---|---|---|---|---|---|---|---|
| Claude Code | W1=`#746`+wrap-e2e | A1=`test_auth_*` | C1=byte-faithful+log fidelity landmine | R1=agent_e2e | M1=matrix+routing-adv | Mem1=hermetic agent_e2e / LIVE-MEM BLOCKED | L1=pilot license pack | S1=messages matrix | — | D1=matrix `/stats` |
| Claude Desktop | W2=`mcp status` | — | C2*=docs+MCP gateway (live BLOCKED) | — | — | Mem2*=BLOCKED | L2=pilot | — | MCP1=docs PASS; install BLOCKED | D2=mcp status truthful |
| Codex CLI | W3=wrap-e2e+`test_wrap_codex` | A2=`test_auth_*` | C3=zstd ADV-005 | R2=agent_e2e | M2=matrix responses | Mem3=hermetic | L3=pilot | S2=WS packs+ADV-004 | — | D3=matrix+live harness |
| ChatGPT Sub | W4=wrap config | A3=subscription headers unit | C4=zstd drop | R3=opaque resume unit | M3†=ADV-007 | Mem4=hermetic | L4=pilot | S3=WS lifecycle | — | D4=stats |
| Cursor CLI | W5=`test_provider_cursor`+wrap help | A4=UA matrix | C5=byte-faithful | R4=agent_e2e patterns | M4=chat matrix | Mem5=hermetic | L5=pilot | S4=chat stream hermetic | — | D5=matrix |
| Cursor Desktop | W6=wrap-e2e cursor (silent pass) | A5=UA | C6=hermetic | R5=hermetic | M5=hermetic | Mem6=BLOCKED live | L6=pilot | S5=hermetic | — | D6=orchestrator unit |

\* Desktop compression via MCP gateway tool output, not Messages proxy.  
† Subscription WS must never downgrade allowlisted models — **PASS** ADV-007.

### Open S0/S1

**None** (product). Environment/process gaps logged as BLOCKED / S2 / S3 only.

### Campaign verdict

**FAIL** against full exit gate (release claim).

Reasons (all required for PASS):

1. Phase A pilot verifier not 13/13 (rust-tests disk exhaustion) — mitigated by focused `cutctx-core` green, but gate unmet.
2. Phase C all LIVE-* **BLOCKED** (missing provider keys / Cursor CLI) — allowed as BLOCKED rows, but **≠ release PASS**.
3. Phase D operator live checklists not signed (apps present; MCP Desktop not installed).
4. Phase E Playwright **BLOCKED** (browser binary missing).
5. CCR adversarial suite 21/36 (S2 debt) — waiver-eligible for named-client release but not green.

Hermetic named-client core is green: client-matrix **18/18**, process harness **16/16**, routing quality **unsafe Mini = 0**, landmines **PASS**, zero open S0/S1.
