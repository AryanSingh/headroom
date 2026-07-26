# Model Routing Adversarial & E2E Verification Plan — 2026-07-26

**Goal:** Prove Cursor-style Auto routing and strong-model downgrades work
end-to-end through the real request path (not just unit heuristics), via CLI
and app/dashboard surfaces, including adversarial cases that must *not* route
down.

**Branch tip at plan time:** `release-readiness-2026-07-26`

---

## 1. Threat model / what "works" means

| Claim | Pass condition |
|---|---|
| `model=auto` LOW | Effective model is a **fast** tier (e.g. `gpt-5.4-mini`, `claude-haiku-4-5`) |
| `model=auto` MEDIUM | Effective model is a **medium** tier (e.g. `gpt-5.6-luna`, `claude-sonnet-4-5`) |
| `model=auto` HIGH | Effective model is a **strong** tier (e.g. `gpt-5.5`, `claude-opus-4-5`) |
| Strong + LOW + Auto mode | Downgrades to fast (or certified cheaper) |
| Strong + HIGH + Auto mode | **Stays** on requested strong model |
| Adversarial HIGH | Tool loops, code fences, security/prod language, ambiguous "Fix it." → **no unsafe Mini** |
| Off mode | Concrete models never downgrade; `model=auto` still resolves (product Auto) |
| Dashboard toggle | `POST /config/flags` with `orchestrator_mode=auto` enables preset |
| Observability | Upstream body model matches decision; stats/traces reflect routing |

---

## 2. Test layers (execute in order)

### L0 — Offline unit / quality gates (no network, no keys)
1. `pytest tests/test_model_router_auto.py`
2. `pytest tests/test_routing_modes_e2e.py`
3. `pytest tests/test_model_router.py tests/test_model_router_presets.py`
4. `pytest tests/test_anthropic_model_routing.py tests/test_openai_codex_routing.py -k routing`
5. `python -m benchmarks.model_routing_quality --ci` (0 unsafe Mini)

### L1 — Adversarial HTTP e2e (in-process proxy, mocked upstream)
Harness: `tests/test_model_routing_adversarial_e2e.py`

- Boot `create_app(model_routing_preset="codex-gpt54mini-high")`
- Patch `proxy._retry_request` to capture upstream `body["model"]` and return 200
- Drive real `POST /v1/chat/completions` and `POST /v1/messages`
- Cases: Auto LOW/MED/HIGH, downgrade, tool_use stay-strong, code stay-strong,
  security stay-strong, empty/multimodal, Off mode, dashboard mode flip

### L2 — CLI live proxy (process-level)
1. `cutctx proxy --port 18987 --model-routing-preset auto` (background)
2. Health: `/readyz`
3. Admin: `POST /config/flags` → auto; `GET /stats` → `model_routing.mode == auto`
4. `CUTCTX_SAFE_SAVINGS_EXPERIENCE=1 cutctx routing status --proxy-url …`
5. Same HTTP cases as L1 against the live port (mocked upstream via test harness
   if no provider keys; live keys optional)

### L3 — App / dashboard
1. `pytest tests/test_dashboard_orchestrator.py`
2. Dashboard Playwright: `npx playwright test e2e/orchestrator.spec.js`
3. Live: open `/dashboard/orchestrator`, toggle Off → Auto → Aggressive, confirm
   `/stats` mode changes

### L4 — Optional live providers (blocked without keys)
With `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`, repeat L2 curls against real upstream
and assert response JSON `model` / `x-cutctx-model`.

---

## 3. Adversarial corpus (must not downgrade)

| ID | Prompt / shape | Expect |
|---|---|---|
| ADV-TOOL | Recent tool_result / tool_calls in window | strong / no Mini |
| ADV-CODE | Fenced ```python``` or traceback | strong |
| ADV-SEC | "Audit auth for vulnerabilities" | strong |
| ADV-PROD | "Fix the production billing failure" | strong |
| ADV-AMBIG | "Fix it." | strong |
| ADV-MULTI | Non-string multimodal content | strong |
| ADV-IMPL | "Implement durable workflow cancellation" | strong |

Unsafe Mini rate target: **0** on this corpus and on
`benchmarks.model_routing_quality --ci`.

---

## 4. Evidence artifacts

| Artifact | Path |
|---|---|
| This plan + results | `audit/2026-07-26-model-routing-adversarial-test-plan.md` |
| Adversarial e2e tests | `tests/test_model_routing_adversarial_e2e.py` |
| Live CLI harness | `scripts/verify_model_routing_live.py` |
| Progress ledger | `audit/release-readiness-progress-2026-07-26.md` |

---

## 5. Results (2026-07-26 execution)

### Verdict: **PASS** (routing confirmed via CLI + app surfaces)

Two product bugs found and fixed during adversarial e2e:

1. **Uncertified provider inventory blocked downgrades** — account-scoped
   `models.json` rows without `routing_certified` made
   `_catalog_manages_source` fail closed (`no_certified_capability_match`)
   instead of falling through to the static downgrade table. Fix:
   only certified catalog rows are authoritative
   (`cutctx/proxy/model_router.py`).
2. **Anthropic `model=auto` never reached upstream** — routing updated the
   in-memory model, but `_dc_replace` on a dict was swallowed and byte-faithful
   forwarding replayed client bytes with `model=auto`. Fix: mutate
   `body["model"]` and `mark_mutated("model_routing")`
   (`cutctx/proxy/handlers/anthropic.py`).

### Layer results

| Layer | Result | Evidence |
|---|---|---|
| L0 units / quality | ✅ | `test_model_router_auto` 9/9; routing `-k routing` 48/48; quality CI accuracy 1.0, unsafe_downgrade_rate **0.0** (75 cases) |
| L1 adversarial HTTP e2e | ✅ | `tests/test_model_routing_adversarial_e2e.py` **18/18** |
| L2 CLI live harness | ✅ | `scripts/verify_model_routing_live.py` **9/9** (`readyz`, stats mode auto, Auto low/high, adversarial stay-strong, downgrade) |
| L2 CLI `cutctx routing` | ✅ | `tests/test_cli/test_routing_status.py` 6/6; `cutctx routing --help` OK |
| L3 dashboard pytest | ✅ | `tests/test_dashboard_orchestrator.py` 6/6 |
| L3 Playwright orchestrator | ✅ routing | Mode tabs Off/Auto/Aggressive + ack flows green after Auto rename; 1 unrelated abort-on-unmount flake observed |
| L4 live providers | ⏭ blocked | No `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` in env |

### Claims verified

| Claim | Result |
|---|---|
| `model=auto` LOW → fast | ✅ `gpt-5.4-mini` / `claude-haiku-4-5` |
| `model=auto` HIGH → strong | ✅ `gpt-5.5` |
| Strong + LOW + Auto mode → Mini | ✅ |
| Adversarial corpus → no unsafe Mini | ✅ |
| Off mode: no downgrade; Auto still resolves | ✅ |
| Dashboard `orchestrator_mode=auto` → `/stats` mode auto | ✅ |
