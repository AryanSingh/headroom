# Comprehensive Product Validation, Governance & Best-in-Class Review — 2026-07-19

**Method.** Every claim below was verified by exercising the running product,
not by reading labels/tests/docs. Two proxies were used: the live builder-tier
instance on `:8787` (production data, restored to its exact pre-audit flag
snapshot — verified zero drift) and an **isolated enterprise-tier test
instance** on `:8899` (throwaway workspace dir, throwaway admin key,
`CUTCTX_ENTITLEMENT_TIER=enterprise`) that never touched `~/.cutctx`. The
dashboard was driven in a real browser; APIs were hit with real payloads
including failure/boundary cases. Three fixes landed and were re-verified.

## 1. Executive summary

| Dimension | Maturity | Basis |
|---|---|---|
| Governance | **Strong** | Toggles apply + persist + enforce server-side; failure paths safe; gated flags 403 with structured detail |
| Security | **Strong (after fix)** | Auth enforced server-side on every admin/data endpoint; hardening headers added this audit; no secret/stack-trace leakage |
| Memory | **Adequate / gated** | Episodic gate functions by tier; dashboard degrades gracefully; Team Memory Service (`/v1/memory/*`) is EE-mounted-only |
| Replay | **Adequate, honestly scoped** | Endpoint wired, structured 404, clear UI copy; it is *policy-decision trace inspection*, not deterministic re-execution — and the UI says so |
| Enterprise gating | **Strong (after fix)** | Tier now actually reachable via documented env; gates prove 403/200 split by tier |
| UI/UX | **Strong** | All 10 routes render in both themes/3 viewports, zero console errors, graceful empty/error/gated states |
| Commercial readiness | **Beta-ready; paid-tier software-complete** | Enforcement + value-meter solid; open blockers are business actions (domain, counsel-approved TERMS) |

**Top risks closed this audit:** (1) enterprise features were **untestable
through the real product** — the CLI silently dropped the tier setting;
(2) **no security hardening headers** on a product that documents
network-facing deployment. **Top remaining risk:** live-provider paths are
still only mock-verified (long-standing, disclosed).

## 2. Primary questions — answered

1. **All governance options tested with real payloads?** Yes — every live
   toggle (dedup, ccr, task-aware, semantic-dedup, context-budget, profiles,
   cost-forecast, autopilot), the routing-mode control, and the gated
   memory/audit/RBAC rows were exercised via the exact `/config/flags`
   payloads the UI sends.
2. **Do they behave as expected?** Yes. Enable→`applied_live` echo→re-read
   shows `source: runtime` enabled→restore. Persistence within process
   confirmed.
3. **Any stubbed/misleading/disconnected options?** One nuance, not a defect:
   the dashboard **Memory** page queries `/v1/memory/query` (Team Memory
   Service) which is **404 when the EE memory router isn't mounted**; the page
   degrades cleanly to the "Business feature" state (the 404 is swallowed by
   the unsupported-endpoint handler). Minor backend consistency nit: the
   intended 501-with-EE-message stub isn't mounted, so clients see 404 rather
   than an explanatory 501. No user-facing breakage.
4. **Why are options unavailable/disabled?** Precise reasons: `episodic_memory`
   & `cross_agent_memory` = **missing BUSINESS entitlement** (403,
   `required_tier: business`); `audit_logs`, `rbac` = **missing ENTERPRISE
   entitlement** (403, `required_tier: enterprise`); firewall/rate-limiter
   metrics = **feature not enabled in this proxy's config** (restart-required
   flags); Replay data = **no recorded session events** (needs traffic with
   `CUTCTX_REPLAY=1`). All server-side, all with structured reasons.
5. **Restricted intentionally / gated wrong / unfinished?** All intentional
   and correctly gated. The one true **defect** found was that the gate was
   *unreachable for testing* (see §Fixes), now resolved.
6. **How to test Enterprise features?** **Now works** (was broken):
   see §3 Enterprise Testing Guide.
7. **Security/Memory/Replay tested e2e?** Yes — §5/§6/§7 below.
8. **Every claimed capability verified?** Matrix in §8.
9. **Intuitive for a new user?** Yes — labels, gated states, and failure copy
   are all self-explanatory (verified rendered states, zero raw errors).
10. **Commercially ready?** Beta-ready; software-complete for paid tiers.
11. **What's needed for best-in-class?** §9.

## 3. Enterprise Feature Testing Guide (verified working)

The documented dev/QA path now functions after the CLI fix:

```bash
# Isolated enterprise instance — never touches ~/.cutctx
CUTCTX_WORKSPACE_DIR=/tmp/cutctx-ent \
CUTCTX_ADMIN_API_KEY=<throwaway-key> \
CUTCTX_ENTITLEMENT_TIER=enterprise \
CUTCTX_EPISODIC_MEMORY_ENABLED=1 CUTCTX_REPLAY=1 \
  python -m cutctx.cli.main proxy --port 8899
```

**Safety properties (verified):** dev-only by construction (isolated
workspace, throwaway key); a validated license key still overrides the
declared tier at startup; on an OSS build (no `cutctx_ee`) the fail-closed
checker ignores the declared tier, so it **cannot grant paid features for
free**; the honor-system declaration is logged loudly at startup.
`GET /entitlements` then reports `tier: enterprise` with all gated features
`available: true`, and gate behavior flips 403→200 by tier (proven).

## 4. Governance Verification Matrix (representative)

| Feature | UI state | Payload | Result | Enforcement | Persist | Availability reason |
|---|---|---|---|---|---|---|
| dedup toggle | live | `{"dedup_enabled":true}` | 200, `applied_live` | source→runtime | re-read enabled | free |
| malformed body | — | `{bad json` | **400** | — | — | validation |
| unknown flag | — | `{"totally_fake_flag":true}` | 200, surfaced under `unknown` (not applied) | — | — | ignored safely |
| episodic (builder) | disabled+tier badge | `{"episodic_memory_enabled":true}` | **403** `feature_not_available` `required_tier:business` | server-side | n/a | missing BUSINESS entitlement |
| episodic (enterprise) | enabled | same | **200 applied** | server-side | applied_live | entitled |
| routing mode | segmented control | `{"orchestrator_mode":"off"}` | 200 (prior audit) | live | runtime | free |
| unauth any admin ep | — | no key | **401** | server-side | — | auth required |

## 5. Security Test Report

| Check | Result |
|---|---|
| Auth on `/stats`, `/config/flags`, `/stats-history`, `/transformations/feed`, `/entitlements`, `/safe-savings/status` | **401** no-auth & wrong-key; 200 valid — server-side |
| Enterprise-gated `/audit/events` with valid builder key | **403** (entitlement enforced beyond authn) |
| Rate limiter | Active — 429s under rapid probing |
| 404 body | Empty, **no stack trace** |
| Admin key echoed in any error body | **No** |
| Secret leakage in errors | None observed |
| **Security headers (before)** | **MISSING** — only `Server: uvicorn` (framework fingerprint); no CSP/X-Frame/nosniff/Referrer → clickjacking + MIME-sniff exposure for network-facing dashboard. **Severity: Medium (High for network-facing).** |
| **Security headers (after fix)** | CSP (`frame-ancestors 'none'`, `script-src 'self'`), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, single non-fingerprinting `Server: cutctx`. Dashboard verified to render under CSP with zero violations. |

## 6. Memory Test Report

- **Two distinct concepts** (a real source of user confusion — see §9):
  *episodic memory* (session tracker, BUSINESS-gated, governance toggle) vs
  *Team Memory Service* (`/v1/memory/*`, EE org-scoped, dashboard Memory page).
- Episodic gate **enforced by tier**: enable blocked 403 on builder, applied
  200 on enterprise.
- Dashboard Memory page renders cleanly on both tiers (Business-feature badge,
  RTK/session stats); the `/v1/memory/query` 404 degrades gracefully — **no
  raw error, no crash**.
- Isolation: the enterprise test instance used a **separate workspace dir** and
  shared no state with production `~/.cutctx` — verified (production flag
  snapshot unchanged).

## 7. Replay Test Report

- **What Replay actually is (verified):** inspection of *structured
  context-policy decision events* recorded for a session — **not** deterministic
  re-execution, not model re-invocation. The UI copy states this correctly:
  *"Inspect the structured context-policy events captured for an operator
  session"*, flag-gated with `CUTCTX_REPLAY=1`.
- Endpoint `/v1/sessions/{id}/replay` is **wired** (not a stub): unknown
  session → structured `404 replay_not_found`; UI renders *"Replay unavailable —
  No replay events found for that session, or replay is disabled."* No crash.
- Guarantee clarity: **Good** — the product does not over-claim deterministic
  reproduction. (Recommendation in §9 to make the "trace inspection, not
  re-execution" distinction even more explicit in a tooltip.)

## 8. Capability Verification Matrix (this audit's scope)

| Capability | Status | Evidence |
|---|---|---|
| Server-side auth enforcement | **Verified** | 401 matrix across all admin/data endpoints |
| Entitlement gating (request path) | **Verified** | 403/200 tier split on episodic + audit + config flags |
| Governance flag apply/persist/restore | **Verified** | applied_live echo + runtime re-read |
| Governance input validation | **Verified** | malformed→400, unknown key surfaced not applied |
| Enterprise tier via documented env | **Verified (after fix)** | `/entitlements` tier: enterprise, features available |
| Security hardening headers | **Verified (after fix)** | header assertions + browser CSP render |
| Replay trace inspection | **Verified** | wired endpoint, structured 404, clear UI |
| Episodic memory (BUSINESS) | **Verified-gated** | enforced 403/200 by tier |
| Team Memory Service (`/v1/memory/*`) | **Enterprise-gated / EE-mount-only** | 404 without EE memory router; graceful UI |
| Rate limiting | **Verified** | 429 under load |
| Dashboard (10 routes, 2 themes, 3 viewports) | **Verified** | prior UI audit + this session, zero console errors |

## 9. Fixes landed (all TDD, re-verified)

1. **`CUTCTX_ENTITLEMENT_TIER` honored in the proxy CLI** (`fix: honor…`,
   `d2ea10f1`). Root cause: `cli/proxy.py` built `ProxyConfig` without the
   tier, so the documented enterprise-test path (and open-core tier
   declaration) was dead — the proxy always ran builder. **This is why
   enterprise features could not be exercised through the product.** Safe:
   license override + OSS fail-closed preserved. Tests:
   `tests/test_cli/test_proxy_entitlement_tier.py`.
2. **Security hardening headers + framework-fingerprint suppression**
   (`fix: add security hardening headers…`, `a01e5f62`). CSP/X-Frame/nosniff/
   Referrer on every response; `Server: cutctx`. Dashboard verified under CSP.
   Test: `tests/test_proxy_healthchecks.py::test_security_headers_present…`.
3. (Prior session, same day) trace-inspector event-loop stall, `/health`
   flap, entitlement request-path enforcement, dead-link repointing.

## 10. Recommendations for best-in-class (not blockers)

- **Disambiguate the two "memory" concepts** in the UI — the Memory page
  should distinguish episodic (session) memory from the Team Memory Service,
  and name the tier each needs.
- **Mount the memory stub 501** even when EE memory is absent, so API clients
  get the explanatory "Enterprise Edition feature" message instead of a bare
  404.
- **Replay tooltip**: one line clarifying "policy-decision trace inspection,
  not deterministic re-execution."
- Business actions unchanged from the release audit: live docs domain,
  counsel-approved TERMS, SLA credit percentages, live-provider validation.

## 11. Final release verdict

**Release-ready with documented limitations** for internal/beta/paid-individual/
paid-team use; **software-complete for enterprise** (gating, auth, headers,
value-meter all verified) with the enterprise *commercial* close still gated on
business actions (domain, terms, compliance evidence) — not code. Security-
conscious/network-facing deployments are materially safer after the headers
fix. No Critical/High defect remains open; the one High-impact defect found
(enterprise untestable via product) is fixed and verified.
