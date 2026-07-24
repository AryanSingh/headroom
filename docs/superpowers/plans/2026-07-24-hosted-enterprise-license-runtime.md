# Hosted Enterprise License Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Accept and enforce hosted CutCtx Enterprise keys throughout the runtime.

**Architecture:** A small hosted-license transport maps Supabase Edge Function responses into the runtime's existing verification and seat-leasing contracts. Existing offline signed-token and local SQLite paths remain fallbacks only for transport/configuration failures; a definitive hosted rejection is never bypassed.

**Tech Stack:** Python 3, `urllib.request`, `httpx`, FastAPI, pytest, Supabase Edge Functions.

## Global Constraints

- Use only the public Supabase anon key; never add a service-role key to source or runtime configuration.
- Do not log complete license keys.
- Hosted invalid/expired responses fail closed.
- Keep offline signed-token and legacy local SQLite behavior for a true hosted-service outage.

---

### Task 1: Hosted validation transport

**Files:**
- Modify: `cutctx_ee/billing/pitchtoship_client.py`
- Test: `cutctx_ee/tests/test_pitchtoship_client.py`

**Interfaces:**
- Produces: `verify_license(license_key: str, hwid: str) -> dict[str, Any] | None`
- Consumes: `POST /functions/v1/verify-license` with `{ "key": license_key }`

- [ ] Add failing tests asserting the hosted URL, `apikey` header, response mapping, definitive invalid response, and transport failure.
- [ ] Run `pytest -q cutctx_ee/tests/test_pitchtoship_client.py` and confirm the new cases fail.
- [ ] Add a hosted JSON request helper and make `verify_license` use the hosted endpoint before legacy compatibility paths.
- [ ] Run the focused tests and confirm they pass.

### Task 2: Hosted seat leasing

**Files:**
- Modify: `cutctx_ee/billing/client.py`
- Test: `cutctx_ee/tests/test_billing_client.py`

**Interfaces:**
- Produces: `checkout_seat(license_key: str, user_id: str) -> bool`
- Consumes: `POST /functions/v1/seat-heartbeat` with `{ "key": license_key, "hwid": user_id }`

- [ ] Add failing tests for accepted, capacity-rejected, and transport-failure responses.
- [ ] Run `pytest -q cutctx_ee/tests/test_billing_client.py` and confirm the new cases fail.
- [ ] Route hosted CutCtx licenses to the heartbeat endpoint, preserving strict-mode behavior for network failures.
- [ ] Run the focused tests and confirm they pass.

### Task 3: Enterprise-key acceptance suite

**Files:**
- Modify: `tests/test_license_validation_contract.py`
- Test: `tests/test_enterprise_smoke.py`

**Interfaces:**
- Consumes: a hosted `{ valid: true, tier: "enterprise", seatsLimit: 500 }` validation result
- Produces: runtime plan `enterprise`, accepted seat lease, and all mapped Enterprise feature gates enabled.

- [ ] Add a failing proxy test that validates an Enterprise result through the runtime client and checks the plan is normalized.
- [ ] Run the focused contract test and confirm it fails.
- [ ] Implement only the compatibility changes required by Tasks 1–2.
- [ ] Run `pytest -q tests/test_license_validation_contract.py tests/test_enterprise_smoke.py` and confirm it passes.

### Task 4: Live and regression verification

**Files:**
- Verify only.

- [ ] Use the real portal-issued Enterprise key through the hosted verification and heartbeat functions without printing it.
- [ ] Run focused billing, contract, and Enterprise smoke tests, then the relevant full test suite.
- [ ] Confirm source contains no service-role credential and git diff is whitespace-clean.
- [ ] Commit the implementation and publish it only after all checks pass.
