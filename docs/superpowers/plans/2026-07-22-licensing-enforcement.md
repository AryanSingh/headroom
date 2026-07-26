# Licensing Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent unverified configuration, invalid licenses, expired trials, and unlimited instances from unlocking paid Cutctx capabilities.

**Architecture:** Initialize the proxy at Builder and only upgrade its checker from a normalized active/trial validation response. Normalize local validation responses to the reporter's public contract, and enforce the licensed instance limit in the local fallback database. Tests capture the previous bypasses before the production changes are made.

**Tech Stack:** Python 3.10+, FastAPI, httpx, pytest, SQLite.

## Global Constraints

- Builder/open-source compression continues to work with no commercial package or license.
- Raw `CUTCTX_ENTITLEMENT_TIER` must never independently unlock a paid feature.
- Only a valid `active` or `trial` validation result may select a paid plan.
- Local and remote validation clients use JSON `{ "license_key": "..." }` and produce `status` plus `plan`.
- Do not change checkout providers, pricing, or unrelated dirty worktree files.

---

### Task 1: Fail closed before license validation

**Files:**
- Modify: `tests/test_entitlement_request_path.py`
- Modify: `cutctx/proxy/server.py`

**Interfaces:**
- Consumes: `ProxyConfig.entitlement_tier`, `_apply_validated_license(proxy, LicenseInfo)`.
- Produces: a Builder checker until a `LicenseInfo(status in {"active", "trial"}, plan=...)` is applied.

- [ ] **Step 1: Write failing tests**

```python
def test_unlicensed_declared_business_tier_does_not_enable_episodic_memory() -> None:
    app = create_app(_config(episodic_memory_enabled=True, entitlement_tier="business"))
    with TestClient(app):
        assert app.state.proxy.episodic_tracker is None

def test_validated_business_license_enables_episodic_memory_after_validation() -> None:
    # apply active Business LicenseInfo, reconcile, assert tracker is enabled
```

- [ ] **Step 2: Run the two tests and verify the unlicensed-tier test fails because it enables memory.**

Run: `pytest -q tests/test_entitlement_request_path.py`

- [ ] **Step 3: Implement the minimal fail-closed initialization.**

```python
self.entitlement_checker = _load_entitlement_checker(None)
# Raw config tier is logged as a requested tier only; it does not grant access.
```

Keep `_apply_validated_license` as the only upgrade path and reconcile paid
components after validation.

- [ ] **Step 4: Run the entitlement request-path suite.**

Run: `pytest -q tests/test_entitlement_request_path.py tests/test_management_api_entitlements.py`

### Task 2: Normalize license validation contracts

**Files:**
- Modify: `tests/test_license_validation_contract.py`
- Modify: `cutctx/proxy/routes/license_validation.py`
- Modify: `cutctx/telemetry/reporter.py`
- Modify: `cutctx/cli/license.py`

**Interfaces:**
- Consumes: `POST /v1/license/validate` JSON `{license_key}`.
- Produces: `LicenseInfo(status, plan, ...)` only for valid active/trial results.

- [ ] **Step 1: Write failing contract tests.**

```python
def test_local_validate_accepts_json_and_normalizes_valid_tier(monkeypatch):
    response = client.post("/v1/license/validate", json={"license_key": "key"})
    assert response.json()["status"] == "active"
    assert response.json()["plan"] == "business"

async def test_reporter_rejects_valid_false_as_invalid(...):
    assert reporter.license_info.status == "invalid"
```

- [ ] **Step 2: Run the contract tests and verify failure.**

Run: `pytest -q tests/test_license_validation_contract.py`

- [ ] **Step 3: Implement the JSON request model and normalization.**

Return `status="active"` and `plan=result["tier"]` for valid local or
PitchToShip results; return a 403 normal invalid response otherwise. Update
the reporter and CLI to send JSON to that stable contract.

- [ ] **Step 4: Run contract and existing license route tests.**

Run: `pytest -q tests/test_license_validation_contract.py cutctx_ee/tests/test_license_e2e.py`

### Task 3: Enforce licensed instance capacity

**Files:**
- Modify: `cutctx_ee/tests/test_license_db.py`
- Modify: `cutctx_ee/billing/license_db.py`

**Interfaces:**
- Consumes: `LicenseDB.activate_instance(license_key, instance_id)` and `licenses.seats`.
- Produces: `True` for an existing activation renewal or when an unoccupied licensed instance slot exists; `False` otherwise.

- [ ] **Step 1: Write failing database tests.**

```python
def test_activation_refuses_new_instance_when_license_instance_limit_is_reached(db):
    # one-seat record, first instance true, second false

def test_activation_renews_existing_instance_at_limit(db):
    # one-seat record, same instance true twice
```

- [ ] **Step 2: Run and verify the capacity test fails.**

Run: `pytest -q cutctx_ee/tests/test_license_db.py`

- [ ] **Step 3: Implement an atomic activation-count check.**

Within the SQLite connection, count distinct activations for the license,
return true for an existing activation, and insert only when `seats <= 0` or
the count is below `seats`.

- [ ] **Step 4: Run database and endpoint tests.**

Run: `pytest -q cutctx_ee/tests/test_license_db.py cutctx_ee/tests/test_license_e2e.py cutctx_ee/tests/test_seat_lease.py`

### Task 4: Full enforcement verification

**Files:**
- Modify: `audit/licensing-enforcement-verification.md`

- [ ] **Step 1: Run all relevant suites.**

Run: `pytest -q tests/test_entitlement_request_path.py tests/test_management_api_entitlements.py tests/test_license_validation_contract.py cutctx_ee/tests/test_license_e2e.py cutctx_ee/tests/test_license_db.py cutctx_ee/tests/test_pitchtoship_client.py cutctx_ee/tests/test_seat_lease.py`

- [ ] **Step 2: Record the exact command, result, and residual scope.**

Document that anonymous provider traffic cannot be seat-metered without a
trusted end-user identity and that this pass enforces instance capacity at the
fallback authority instead.
