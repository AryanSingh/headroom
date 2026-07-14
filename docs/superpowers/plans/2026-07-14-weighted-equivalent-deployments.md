# Weighted Equivalent Deployments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deterministically allocate traffic across explicit, same-model equivalent deployments while respecting all eligibility and cooldown guards.

**Architecture:** A binding declares optional non-negative weights keyed by its primary or explicit equivalent deployment. The engine filters candidates with its existing eligibility path before deterministically choosing from positive-weight candidates using a SHA-256 request-ID cohort. It falls back to the existing reliability ranking when no eligible weights apply.

**Tech Stack:** Python dataclasses, hashlib, pytest, existing orchestration receipt API.

## Global Constraints

- Weights apply only to a binding primary and its explicit same-model equivalents.
- All policy, transport, capability, account, and cooldown checks precede allocation.
- Strict mode must never select a different-model fallback.
- Empty/unusable weight maps preserve existing reliability selection.

---

### Task 1: Validate serialized equivalent weights

**Files:**

- Modify: `cutctx/orchestration/models.py`
- Modify: `cutctx/orchestration/service.py`
- Test: `tests/test_orchestration_platform.py`

**Interfaces:**

- Adds `RouteBinding.equivalent_deployment_weights: dict[str, float]` with an empty-map default.

- [ ] **Step 1: Write the failing test**

```python
def test_binding_rejects_invalid_or_non_equivalent_deployment_weights(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    service.config.bindings[0].equivalent_deployment_weights = {"anthropic:anthropic-main:claude-worker": 1.0}

    with pytest.raises(ValueError, match="equivalent deployment weights"):
        service.replace_config(service.config)
```

- [ ] **Step 2: Verify RED**

Run: `rtk pytest tests/test_orchestration_platform.py::test_binding_rejects_invalid_or_non_equivalent_deployment_weights -q`

Expected: FAIL because the binding has no weighted-target validation.

- [ ] **Step 3: Implement validation**

Add the map field. In `_validate_config`, require string keys and finite, non-negative numeric values. The allowed keys are the binding model plus `equivalent_deployments`; require every resolved weight target to preserve the primary model identity.

- [ ] **Step 4: Verify GREEN**

Run the Task 1 test. Expected: PASS.

### Task 2: Deterministic weighted selection

**Files:**

- Modify: `cutctx/orchestration/engine.py`
- Test: `tests/test_orchestration_platform.py`

**Interfaces:**

- Consumes binding weights and `RoutingRequest.request_id`.
- Produces `selection_evidence` with `strategy: "equivalent_weighted"`, selected deployment, cohort fraction, eligible weights, and rejected candidates.

- [ ] **Step 1: Write the failing test**

```python
def test_weighted_equivalents_are_stable_and_cover_each_positive_weight_target() -> None:
    primary = _model("openai", "shared", account_id="account-a")
    equivalent = _model("openai", "shared", account_id="account-b")
    binding = RouteBinding(
        id="worker", role="worker", model=primary.deployment_key,
        equivalent_deployments=[equivalent.deployment_key],
        equivalent_deployment_weights={primary.deployment_key: 1.0, equivalent.deployment_key: 1.0},
    )
    engine = _engine(OrchestrationConfig(roles=[Role(id="worker", name="Worker")], bindings=[binding]), primary, equivalent)

    repeated = [engine.route(RoutingRequest(role="worker", request_id="stable")).account_id for _ in range(2)]
    selected = {engine.route(RoutingRequest(role="worker", request_id=f"cohort-{index}")).account_id for index in range(100)}

    assert repeated == [repeated[0], repeated[0]]
    assert selected == {"account-a", "account-b"}


def test_weighted_selection_excludes_a_cooled_deployment() -> None:
    primary = _model("openai", "shared", account_id="account-a")
    equivalent = _model("openai", "shared", account_id="account-b")
    registry = DynamicModelRegistry()
    registry.register(primary)
    registry.register(equivalent)
    registry.cool_down(primary.deployment_key, 30)
    binding = RouteBinding(
        id="worker", role="worker", model=primary.deployment_key,
        equivalent_deployments=[equivalent.deployment_key],
        equivalent_deployment_weights={primary.deployment_key: 1.0, equivalent.deployment_key: 1.0},
    )
    engine = DeterministicRoutingEngine(
        OrchestrationConfig(roles=[Role(id="worker", name="Worker")], bindings=[binding]), registry,
    )

    decision = engine.route(RoutingRequest(role="worker", request_id="cooled"))

    assert decision.account_id == "account-b"
    assert decision.selection_evidence["strategy"] == "equivalent_weighted"
    assert {"model": primary.deployment_key, "reason": "cooling_down"} in decision.selection_evidence["rejected"]
```

- [ ] **Step 2: Verify RED**

Run: `rtk pytest tests/test_orchestration_platform.py::test_weighted_equivalents_are_stable_and_cover_each_positive_weight_target -q`

Expected: FAIL because routing always uses reliability ranking.

- [ ] **Step 3: Implement the minimum allocator**

Pass binding weights into `_select_primary_or_equivalent`. After eligibility filtering, collect candidates with a positive configured weight. Hash `request.request_id` with SHA-256 to a `[0, 1)` fraction, choose the corresponding normalized cumulative weight, and return the receipt evidence. Do not allocate to a zero-weight candidate. If no candidate has a positive eligible weight, retain the existing scoring code.

- [ ] **Step 4: Verify GREEN**

Run the Task 2 test. Expected: PASS.

### Task 3: Document and verify the weighted control

**Files:**

- Modify: `docs/content/docs/model-routing-presets.mdx`

- [ ] **Step 1: Review the completed receipt contract**

Confirm Task 2's cooled-deployment assertion proves allocation occurs only after existing eligibility/cooldown filtering and retains the `cooling_down` rejection entry.

- [ ] **Step 2: Add the operator documentation**

Add a `Weighted equivalent deployments` section that says weights are configured through `equivalent_deployment_weights`, apply only to explicit same-model equivalents, use stable request-ID cohorts, and give cooled/otherwise ineligible deployments zero traffic.

- [ ] **Step 3: Verify and package**

Run:

```bash
rtk pytest tests/test_orchestration_platform.py tests/test_orchestration_api.py -q
rtk ruff check cutctx/orchestration/models.py cutctx/orchestration/engine.py cutctx/orchestration/service.py tests/test_orchestration_platform.py
rtk git diff --check
```

Expected: all commands exit 0.
