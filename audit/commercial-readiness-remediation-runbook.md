# Commercial Readiness Remediation Runbook

> Actionable, agent-executable steps to close the gaps identified in the
> commercial-readiness assessment of Cutctx v0.30.0. Each task has an
> objective, implementation steps, file references, and verification steps.
>
> Priority order: P0 (savings validation) → P1 (billing/licensing) →
> P2 (error messages) → P2 (circuit breaker) → P3 (enterprise distribution).
>
> Note: test files named `tests/test_savings_shadow.py`,
> `tests/test_savings_negative_guard.py`, `tests/test_billing_e2e.py`,
> `tests/test_circuit_breaker.py`, `tests/test_proxy_retry_circuit.py`,
> and `tests/test_proxy_timeout.py` are **proposed new tests** — they do not
> exist yet. All other referenced tests and line numbers were verified against
> the tree on 2026-07-06.

---

## Task 1 (P0): Establish Savings Validation Protocol

**Problem:** Savings are *estimated* (tokens removed) not *validated* against real
cost deltas. There is no baseline measurement, so a compression that breaks an
agent into costly retry loops would still report "savings."

**Target files:**
- `cutctx/proxy/savings_tracker.py`
- `cutctx/savings/orchestrator.py`
- `cutctx/proxy/cost.py`
- New: `cutctx/savings/shadow.py` (shadow-mode comparator)

### Implementation steps

1. **Add a shadow-mode toggle.**
   - Add `CUTCTX_SHADOW_MODE` env var + `shadow_mode_enabled: bool = False` to
     `ProxyConfig` in `cutctx/proxy/models.py`.
   - When enabled, the proxy sends BOTH the compressed and uncompressed request
     to the provider (or replays uncompressed on a sampled %), records both
     token counts and USD costs, and stores the delta.

2. **Record ground-truth baseline.**
   - In `savings_tracker.py`, add fields to the persisted record:
     `baseline_input_tokens`, `baseline_output_tokens`, `baseline_cost_usd`,
     `actual_cost_usd`, `measured_delta_usd`.
   - Distinguish `estimated_savings_usd` (current behavior) from
     `measured_savings_usd` (shadow-mode ground truth).

3. **Add sampling control.**
   - `CUTCTX_SHADOW_SAMPLE_RATE` (default `0.0`, e.g. `0.05` = 5% of traffic).
   - Only sampled requests incur the double-call cost.

4. **Surface confidence in reporting.**
   - Extend `/stats` and the dashboard to show measured vs. estimated savings
     and a confidence interval when shadow samples exist.
   - Add a clear disclaimer field `savings_basis: "estimated" | "measured"`.

5. **Guard against negative savings.**
   - When `measured_delta_usd < 0` (compression cost MORE), log a WARNING and
     surface a dashboard alert; do not silently report positive savings.

### Verification steps

```bash
# 1. Unit: shadow comparator computes correct deltas
pytest tests/test_savings_shadow.py -q

# 2. Integration: proxy in shadow mode records both baseline + actual
CUTCTX_SHADOW_MODE=1 CUTCTX_SHADOW_SAMPLE_RATE=1.0 \
  cutctx proxy --port 8788 &
# send a known request, then:
curl -s http://127.0.0.1:8788/stats -H "Authorization: Bearer $ADMIN_KEY" \
  | python -m json.tool | grep -E "measured_savings|baseline_cost|savings_basis"

# 3. Negative-savings guard fires (inject a compressor that expands tokens)
pytest tests/test_savings_negative_guard.py -q

# 4. Dashboard shows measured vs estimated
pytest tests/test_dashboard_savings_by_model.py -q
```

**Done when:** `/stats` returns `savings_basis: "measured"` for shadow-sampled
requests, `measured_savings_usd` is present, and negative deltas produce a
WARNING log + dashboard alert.

---

## Task 2 (P1): Test & Document License / Stripe Integration End-to-End

**Problem:** License validation, seat leasing, trial, and Stripe webhook routes
exist in OSS (`cutctx/proxy/routes/license.py`,
`cutctx/proxy/routes/license_validation.py`) but actual enforcement lives in the
proprietary `cutctx_ee.billing.*` module and is untested from the OSS surface.

**Target files:**
- `cutctx/proxy/routes/license.py`
- `cutctx/proxy/routes/license_validation.py`
- `cutctx_ee/billing/license_db.py` (commercial)
- `docs/BILLING_INTEGRATION.md` (exists — extend it)

### Implementation steps

1. **Verify webhook signature validation.**
   - Confirm `/webhooks/stripe` validates the `Stripe-Signature` header using the
     signing secret before processing. If not present in OSS shim, document that
     it MUST be enforced in `cutctx_ee.billing.pitchtoship_client`.

2. **Write an end-to-end billing test harness** (`tests/test_billing_e2e.py`):
   - trial start → seat checkout → license activate → entitlement enforced →
     seat revoke → entitlement denied.
   - Use Stripe test-mode keys + the Stripe CLI (`stripe listen`) to replay
     webhook events against a local proxy.

3. **Clarify seat-limit enforcement.**
   - Confirm `checkout_seat` in `license.py` (lines 76-84) actually rejects when
     `seat_count > licensed_seats`. Currently both branches return
     `{"status": "seat_leased"}` — verify the EE `db.checkout_seat` returns
     `False` on overage and the route should surface a 402/409, not success.

4. **Document the runbook** in `docs/BILLING_INTEGRATION.md`:
   - How to configure Stripe keys/env vars, webhook endpoint URL, signing secret.
   - Overage handling, dunning/grace period behavior, offline license tolerance.

### Verification steps

```bash
# 1. Webhook signature rejection
pytest tests/test_billing_e2e.py::test_webhook_rejects_bad_signature -q

# 2. Full lifecycle (requires cutctx_ee + Stripe test keys)
STRIPE_SECRET_KEY=sk_test_... pytest tests/test_billing_e2e.py -q

# 3. Seat overage is rejected (not silently accepted)
pytest tests/test_billing_e2e.py::test_seat_overage_rejected -q

# 4. Stripe CLI replay
stripe listen --forward-to localhost:8787/webhooks/stripe &
stripe trigger checkout.session.completed
# confirm license row created:
curl -s localhost:8787/v1/license/crl -H "Authorization: Bearer $ADMIN_KEY"
```

**Done when:** the lifecycle test passes with EE installed, bad signatures are
rejected, seat overage returns a non-2xx status, and
`docs/BILLING_INTEGRATION.md` documents the full config + overage behavior.

---

## Task 3 (P2): Improve HTTP Error Messages with Remediation Hints

**Problem:** Errors like `501 "Enterprise billing module not installed"` and
generic `401 "Unauthorized"` give no remediation path.

**Target files:**
- `cutctx/proxy/routes/license.py` (line 46)
- `cutctx/proxy/routes/secrets.py`, `rbac.py`, `spend.py`
- `cutctx/proxy/server.py` (lines 5644, 5659, 5663 — the 401s)

### Implementation steps

1. **Add a structured error body** with a `remediation` field:
   ```python
   raise HTTPException(
       status_code=501,
       detail={
           "error": "enterprise_module_missing",
           "message": "Enterprise billing module not installed",
           "remediation": "Install the commercial package: pip install cutctx-ai[ee]. See LICENSING.md.",
       },
   )
   ```

2. **Make 401/403 specific:** distinguish "no credentials provided" from
   "invalid credentials" from "insufficient permission (RBAC)". Include the
   expected header name (`Authorization: Bearer` or `x-api-key`) in the message.

3. **Centralize** these in a small helper (e.g. `cutctx/proxy/errors.py`) so all
   routes share the same shape.

### Verification steps

```bash
# 1. 501 includes remediation
curl -s -o /dev/null -w "%{http_code}" localhost:8787/v1/license/activate \
  -H "Authorization: Bearer $ADMIN_KEY" -d '{}' # (OSS, no EE)
curl -s localhost:8787/v1/license/crl -H "Authorization: Bearer $ADMIN_KEY" \
  | grep remediation

# 2. 401 distinguishes missing vs invalid
pytest tests/test_admin_surface_guards.py -q
pytest tests/test_proxy_dashboard_html_auth_bypass.py -q

# 3. No regression in existing auth tests
pytest -q -k "auth or 401 or unauthorized"
```

**Done when:** every 4xx/5xx from admin/license/secrets routes returns a
`remediation` string, and 401 responses name the missing/invalid credential.

---

## Task 4 (P2): Add Circuit Breaker for Upstream Providers

**Problem:** Failover (`cutctx/proxy/routes/failover.py`) can mark a provider
unhealthy but there is no time-window backoff — risk of retry storms during
outages. Streaming requests are also not retried.

**Target files:**
- `cutctx/proxy/routes/failover.py`
- `cutctx/proxy/server.py` (`_retry_request`, lines 1627-1743)
- New: `cutctx/proxy/circuit_breaker.py`

### Implementation steps

1. **Implement a per-provider circuit breaker** (CLOSED → OPEN → HALF_OPEN):
   - Track rolling failure rate; OPEN after N consecutive failures.
   - While OPEN, fail fast (skip the provider) for a cooldown window
     (`CUTCTX_CIRCUIT_COOLDOWN_S`, default 30s), then HALF_OPEN a probe request.

2. **Wire it into the retry loop** in `server.py` so retries respect the breaker
   state instead of hammering a down provider.

3. **Add a proxy-level request timeout** (`CUTCTX_UPSTREAM_TIMEOUT_S`) so hanging
   upstream requests are bounded independent of provider defaults.

4. **Expose breaker state** on `/stats` and `/v1/failover` health.

### Verification steps

```bash
# 1. Breaker opens after N failures, fails fast during cooldown
pytest tests/test_circuit_breaker.py -q

# 2. Retry loop respects OPEN state (no upstream calls while open)
pytest tests/test_proxy_retry_circuit.py -q

# 3. Upstream timeout enforced
CUTCTX_UPSTREAM_TIMEOUT_S=2 pytest tests/test_proxy_timeout.py -q

# 4. Breaker state visible
curl -s localhost:8787/v1/failover -H "Authorization: Bearer $ADMIN_KEY" \
  | grep -E "circuit_state|cooldown"
```

**Done when:** breaker transitions are unit-tested, the retry loop short-circuits
on OPEN, upstream timeout is enforced, and breaker state appears in `/stats`.

---

## Task 5 (P3): Clarify Enterprise (cutctx-ee) Distribution

**Problem:** How to obtain the proprietary `cutctx-ee` wheel is undocumented
(private PyPI? GitHub releases? artifacts?).

**Target files:**
- `LICENSING.md`
- `ENTERPRISE.md`
- `packaging/cutctx-ee/pyproject.toml`
- New: `docs/enterprise-install.md`

### Implementation steps

1. **Document the acquisition path:** private index URL, auth token flow, or
   sales-gated download. Include the exact `pip install` invocation with the
   index URL.
2. **Document version pinning** so `cutctx-ai` and `cutctx-ee` stay compatible
   (they should share the `0.30.0` line — see `scripts/compile_ee.py`).
3. **Add an SLA reference** for commercial support response time.

### Verification steps

```bash
# 1. Version alignment holds
python scripts/verify-versions.py

# 2. EE compiles at the canonical repo version (not 0.1.0)
python scripts/compile_ee.py --check

# 3. Docs mention the install index + auth
grep -R "extra-index-url\|--index-url\|pip install cutctx-ai\[ee\]" docs/enterprise-install.md
```

**Done when:** `docs/enterprise-install.md` gives a copy-paste install command
for the EE wheel, version-alignment check passes, and support SLA is stated.

---

## Global Verification (run before declaring remediation complete)

```bash
# Full targeted suite touched by these tasks
pytest -q \
  tests/test_savings_shadow.py \
  tests/test_savings_negative_guard.py \
  tests/test_billing_e2e.py \
  tests/test_admin_surface_guards.py \
  tests/test_circuit_breaker.py \
  tests/test_proxy_retry_circuit.py

# Lint + type
ruff check cutctx/
mypy cutctx/proxy/

# Version integrity
python scripts/verify-versions.py

# Dashboard build (reporting changes)
cd dashboard && npm run build
```

**Sign-off checklist:**
- [ ] `savings_basis: "measured"` present in `/stats` under shadow mode
- [ ] Negative-savings guard produces WARNING + dashboard alert
- [ ] Billing lifecycle test passes; bad Stripe signature rejected; seat overage non-2xx
- [ ] All admin/license/secrets 4xx/5xx carry a `remediation` field
- [ ] Circuit breaker opens/half-opens/closes correctly; upstream timeout enforced
- [ ] `docs/enterprise-install.md` published; `verify-versions.py` passes
