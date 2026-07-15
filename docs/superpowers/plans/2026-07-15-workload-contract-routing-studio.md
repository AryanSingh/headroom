# Workload Contract Routing Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a versioned workload-contract routing control plane for coding-agent teams, with deterministic safety constraints, draft-aware simulation, evidence-gated rollout, unified receipts, and an accessible Routing Studio dashboard.

**Architecture:** Add workload contracts as the user-facing source of routing intent and compile them into the existing deterministic orchestration configuration. Keep model eligibility, optimization, and deployment selection as separate stages. Expose immutable versions and lifecycle transitions through authenticated APIs, then replace the current configuration-first dashboard with Contracts, Simulator, Rollouts, and Evidence workspaces.

**Tech Stack:** Python 3.11+, dataclasses, FastAPI, Pydantic, JSON persistence, pytest, React 19, Vite, Playwright, CSS.

## Global Constraints

- Preserve existing role, binding, profile, route, execution, and routing-evidence APIs during migration.
- Existing role and binding configurations must retain equivalent routing behavior after compilation.
- Hard capability, transport, provider, account, residency, classification, budget, and risk constraints run before optimization.
- Preview and live execution use the same compiled policy and receipt schema.
- A draft preview must evaluate the supplied draft, not the active server configuration.
- Provider reliability must not be labeled as answer quality.
- Streaming fallback must stop after the first visible response byte.
- The 390-pixel layout must not require horizontal page scrolling.
- Use `rtk` for every shell command.
- Follow TDD for each behavior change.

---

## File structure

### New backend files

- `cutctx/orchestration/contracts.py`: contract enums, dataclasses, validation, serialization, and legacy conversion.
- `cutctx/orchestration/contract_store.py`: immutable contract versions, lifecycle state, optimistic concurrency, and atomic JSON persistence.
- `cutctx/orchestration/compiler.py`: pure contract-to-`OrchestrationConfig` compilation and reliability-budget validation.
- `cutctx/orchestration/simulation.py`: draft/live comparison, candidate evidence, and historical receipt replay summaries.

### Modified backend files

- `cutctx/orchestration/models.py`: request and receipt fields required by compiled contracts.
- `cutctx/orchestration/service.py`: contract store composition, contract-aware routing, simulation, and lifecycle transitions.
- `cutctx/orchestration/engine.py`: expose stable candidate rejection evidence and separate model/deployment selection metadata.
- `cutctx/orchestration/policy_bundle.py`: include contract identity and compiled policy hash inputs.
- `cutctx/orchestration/__init__.py`: export contract interfaces and build the store.
- `cutctx/proxy/routes/orchestration.py`: authenticated contract, simulation, rollout, receipt, and outcome endpoints.

### New dashboard files

- `dashboard/src/components/routing-studio/RoutingStudio.jsx`: four-workspace shell and data orchestration.
- `dashboard/src/components/routing-studio/ContractList.jsx`: contract status and quality-safe savings overview.
- `dashboard/src/components/routing-studio/ContractEditor.jsx`: progressive contract editor.
- `dashboard/src/components/routing-studio/RouteSimulator.jsx`: scenario input, draft/live comparison, and candidate evidence.
- `dashboard/src/components/routing-studio/RolloutPanel.jsx`: lifecycle gates and actions.
- `dashboard/src/components/routing-studio/EvidencePanel.jsx`: quality, savings, coverage, abstention, and receipt views.
- `dashboard/src/components/routing-studio/DecisionPipeline.jsx`: accessible six-step decision explanation.
- `dashboard/src/components/routing-studio/api.js`: contract API client and response normalization.

### Modified dashboard files

- `dashboard/src/pages/Orchestrator.jsx`: mount Routing Studio and retain compatibility-provider health below it.
- `dashboard/src/index.css`: responsive Routing Studio, focus, state, and reflow styles.
- `dashboard/e2e/orchestrator.spec.js`: contract, simulation, rollout, keyboard, and mobile behavior.

### Test files

- `tests/test_orchestration_contracts.py`
- `tests/test_orchestration_contract_store.py`
- `tests/test_orchestration_compiler.py`
- `tests/test_orchestration_simulation.py`
- `tests/test_orchestration_api.py`
- `tests/test_orchestration_platform.py`
- `tests/test_dashboard_orchestrator_policy_e2e.py`

---

### Task 1: Contract domain model and legacy conversion

**Files:**
- Create: `cutctx/orchestration/contracts.py`
- Modify: `cutctx/orchestration/models.py`
- Modify: `cutctx/orchestration/__init__.py`
- Test: `tests/test_orchestration_contracts.py`

**Interfaces:**
- Consumes: `Role`, `RouteBinding`, `RoutingSettings`, and `OrchestrationConfig` from `cutctx.orchestration.models`.
- Produces: `WorkloadContract`, `ContractObjective`, `ReliabilityBudget`, `ContractEvaluationPolicy`, `ContractLifecycle`, `contract_from_dict()`, `contract_to_dict()`, and `legacy_contracts_from_config()`.

- [ ] **Step 1: Write failing contract validation and legacy conversion tests**

```python
from cutctx.orchestration.contracts import (
    ContractLifecycle,
    WorkloadContract,
    contract_from_dict,
    legacy_contracts_from_config,
)
from cutctx.orchestration.models import OrchestrationConfig, Role, RouteBinding


def test_contract_round_trip_preserves_objective_and_reliability_budget() -> None:
    contract = contract_from_dict({
        "id": "implementation",
        "name": "Implementation",
        "version": "1",
        "state": "draft",
        "role_aliases": ["worker"],
        "requirements": {"required_capabilities": ["tool_calling"]},
        "objective": {
            "type": "lowest_cost_within_quality_sla",
            "quality_floor": 0.95,
            "maximum_cost_usd": 0.4,
        },
        "reliability": {
            "attempt_timeout_seconds": 30,
            "total_deadline_seconds": 90,
            "attempts_per_deployment": 2,
            "maximum_deployments": 1,
        },
    })
    assert isinstance(contract, WorkloadContract)
    assert contract.state == ContractLifecycle.DRAFT.value
    assert contract.objective.quality_floor == 0.95
    assert contract.reliability.total_deadline_seconds == 90


def test_legacy_roles_compile_to_behavior_preserving_contracts() -> None:
    config = OrchestrationConfig(
        roles=[Role(id="worker", name="Worker", required_capabilities={"tool_calling"})],
        bindings=[RouteBinding(id="worker-default", role="worker", model="openai:gpt-5")],
    )
    contracts = legacy_contracts_from_config(config)
    assert contracts[0].id == "worker"
    assert contracts[0].baseline_model == "openai:gpt-5"
    assert contracts[0].requirements.required_capabilities == {"tool_calling"}
    assert contracts[0].objective.type == "exact_assignment"
```

- [ ] **Step 2: Run the tests and confirm the module is missing**

Run: `rtk pytest tests/test_orchestration_contracts.py -q`

Expected: FAIL with `ModuleNotFoundError: cutctx.orchestration.contracts`.

- [ ] **Step 3: Implement the domain types and strict parser**

```python
class ContractLifecycle(str, Enum):
    DRAFT = "draft"
    SHADOW = "shadow"
    CANARY = "canary"
    ACTIVE = "active"
    PAUSED = "paused"
    RETIRED = "retired"


class ContractObjectiveType(str, Enum):
    EXACT_ASSIGNMENT = "exact_assignment"
    LOWEST_COST_WITHIN_QUALITY_SLA = "lowest_cost_within_quality_sla"
    LOWEST_LATENCY_WITHIN_QUALITY_BUDGET = "lowest_latency_within_quality_budget"
    HIGHEST_QUALITY_WITHIN_BUDGET = "highest_quality_within_budget"
    RELIABILITY_FIRST = "reliability_first"
    CUSTOM = "custom"


@dataclass(frozen=True)
class ContractRequirements:
    required_capabilities: set[str] = field(default_factory=set)
    minimum_context_tokens: int | None = None
    minimum_output_tokens: int | None = None
    allowed_providers: set[str] = field(default_factory=set)
    allowed_accounts: set[str] = field(default_factory=set)
    allowed_regions: set[str] = field(default_factory=set)
    allowed_data_classifications: set[str] = field(default_factory=set)
    retention_policy: str | None = None


@dataclass(frozen=True)
class ContractObjective:
    type: str = ContractObjectiveType.EXACT_ASSIGNMENT.value
    quality_floor: float = 1.0
    maximum_cost_usd: float | None = None
    maximum_ttft_ms: float | None = None
    maximum_total_latency_ms: float | None = None
    weights: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ContractEvaluationPolicy:
    accepted_outcome_signals: set[str] = field(default_factory=set)
    minimum_samples: int = 20
    unsafe_quality_floor: float = 0.8
    maximum_unsafe_rate: float = 0.01
    canary_percentage: float = 0.1
    automatic_rollback_conditions: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ReliabilityBudget:
    connect_timeout_seconds: float = 10.0
    first_token_timeout_seconds: float = 30.0
    attempt_timeout_seconds: float = 120.0
    stream_idle_timeout_seconds: float = 30.0
    total_deadline_seconds: float = 240.0
    attempts_per_deployment: int = 2
    maximum_deployments: int = 1
    fallback_triggers: set[str] = field(default_factory=set)
    maximum_fallback_cost_usd: float | None = None


@dataclass(frozen=True)
class WorkloadContract:
    id: str
    name: str
    version: str
    state: str = ContractLifecycle.DRAFT.value
    description: str = ""
    role_aliases: tuple[str, ...] = ()
    selectors: dict[str, str] = field(default_factory=dict)
    task_types: set[str] = field(default_factory=set)
    baseline_model: str | None = None
    fallback_models: tuple[str, ...] = ()
    requirements: ContractRequirements = field(default_factory=ContractRequirements)
    objective: ContractObjective = field(default_factory=ContractObjective)
    reliability: ReliabilityBudget = field(default_factory=ReliabilityBudget)
    evaluation: ContractEvaluationPolicy = field(default_factory=ContractEvaluationPolicy)
```

`contract_from_dict()` must reject unknown lifecycle or objective values, empty IDs, non-positive deadlines, invalid quality ranges, and retry/deployment counts outside 1 through 10.

- [ ] **Step 4: Run the contract tests**

Run: `rtk pytest tests/test_orchestration_contracts.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the contract model**

```bash
rtk git add cutctx/orchestration/contracts.py cutctx/orchestration/models.py cutctx/orchestration/__init__.py tests/test_orchestration_contracts.py
rtk git commit -m "feat(orchestration): add workload contract model"
```

---

### Task 2: Immutable contract store and lifecycle transitions

**Files:**
- Create: `cutctx/orchestration/contract_store.py`
- Test: `tests/test_orchestration_contract_store.py`

**Interfaces:**
- Consumes: `WorkloadContract`, `contract_from_dict()`, and `contract_to_dict()`.
- Produces: `ContractStore`, `ContractConflictError`, `ContractTransitionError`, `list_contracts()`, `get_version()`, `put_draft()`, and `transition()`.

- [ ] **Step 1: Write failing persistence and transition tests**

```python
def test_put_draft_uses_optimistic_version_and_keeps_versions_immutable(tmp_path) -> None:
    store = ContractStore(tmp_path / "contracts.json")
    first = store.put_draft(_contract("implementation", "1"), expected_revision=0)
    assert first.revision == 1
    second = store.put_draft(_contract("implementation", "2"), expected_revision=1)
    assert second.revision == 2
    assert store.get_version("implementation", "1").version == "1"


def test_contract_lifecycle_requires_valid_order(tmp_path) -> None:
    store = ContractStore(tmp_path / "contracts.json")
    store.put_draft(_contract("implementation", "1"), expected_revision=0)
    with pytest.raises(ContractTransitionError):
        store.transition("implementation", "1", "active")
    store.transition("implementation", "1", "shadow")
    store.transition("implementation", "1", "canary")
    active = store.transition("implementation", "1", "active")
    assert active.state == "active"
```

- [ ] **Step 2: Verify tests fail**

Run: `rtk pytest tests/test_orchestration_contract_store.py -q`

Expected: FAIL because `ContractStore` does not exist.

- [ ] **Step 3: Implement atomic persistence and lifecycle rules**

```python
_TRANSITIONS = {
    "draft": {"shadow", "retired"},
    "shadow": {"draft", "canary", "paused", "retired"},
    "canary": {"active", "paused", "draft", "retired"},
    "active": {"paused", "retired"},
    "paused": {"draft", "canary", "active", "retired"},
    "retired": set(),
}


@dataclass(frozen=True)
class StoredContract:
    contract: WorkloadContract
    revision: int
    updated_at: str


class ContractStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()

    def put_draft(
        self,
        contract: WorkloadContract,
        *,
        expected_revision: int,
    ) -> StoredContract:
        if contract.state != ContractLifecycle.DRAFT.value:
            raise ContractTransitionError("Only draft contracts may be written")
        with self._lock:
            payload = self._load()
            revision = int(payload.get("revision", 0))
            if revision != expected_revision:
                raise ContractConflictError(
                    f"Expected revision {expected_revision}, found {revision}"
                )
            versions = payload.setdefault("contracts", {}).setdefault(contract.id, {})
            versions[contract.version] = contract_to_dict(contract)
            next_revision = revision + 1
            payload["revision"] = next_revision
            self._save(payload)
            return StoredContract(
                contract=contract,
                revision=next_revision,
                updated_at=datetime.now(timezone.utc).isoformat(),
            )

    def transition(self, contract_id: str, version: str, target: str) -> WorkloadContract:
        with self._lock:
            payload = self._load()
            values = payload.get("contracts", {}).get(contract_id, {}).get(version)
            if values is None:
                raise KeyError(f"Unknown contract version: {contract_id}@{version}")
            contract = contract_from_dict(values)
            if target not in _TRANSITIONS[contract.state]:
                raise ContractTransitionError(
                    f"Cannot transition {contract.state} to {target}"
                )
            updated = replace(contract, state=target)
            payload["contracts"][contract_id][version] = contract_to_dict(updated)
            if target == ContractLifecycle.ACTIVE.value:
                for other_version, other_values in payload["contracts"][contract_id].items():
                    if other_version == version:
                        continue
                    other = contract_from_dict(other_values)
                    if other.state == ContractLifecycle.ACTIVE.value:
                        payload["contracts"][contract_id][other_version] = contract_to_dict(
                            replace(other, state=ContractLifecycle.RETIRED.value)
                        )
            payload["revision"] = int(payload.get("revision", 0)) + 1
            self._save(payload)
            return updated
```

Use a lock, `tempfile.mkstemp`, `fsync`, and `os.replace`, matching `LayeredConfigStore`. When a version becomes active, retire the previous active version for the same contract ID.

- [ ] **Step 4: Run store tests**

Run: `rtk pytest tests/test_orchestration_contract_store.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the store**

```bash
rtk git add cutctx/orchestration/contract_store.py tests/test_orchestration_contract_store.py
rtk git commit -m "feat(orchestration): persist contract versions"
```

---

### Task 3: Pure contract compiler and reliability-budget validation

**Files:**
- Create: `cutctx/orchestration/compiler.py`
- Modify: `cutctx/orchestration/policy_bundle.py`
- Test: `tests/test_orchestration_compiler.py`

**Interfaces:**
- Consumes: `WorkloadContract`, infrastructure `OrchestrationConfig`, and optional organization policy.
- Produces: `CompiledRoutingPolicy`, `compile_contract()`, and `ContractCompilationError`.

- [ ] **Step 1: Write failing compilation tests**

```python
def test_compiler_preserves_exact_assignment_and_hard_constraints() -> None:
    compiled = compile_contract(
        _implementation_contract(),
        _infrastructure_config(),
    )
    assert compiled.config.roles[0].id == "implementation"
    assert compiled.config.bindings[0].model == "openai:primary:gpt-5"
    assert compiled.config.settings.allowed_providers == {"openai"}
    assert compiled.objective.type == "lowest_cost_within_quality_sla"
    assert compiled.policy_hash


def test_compiler_rejects_retry_plan_larger_than_total_deadline() -> None:
    contract = replace(
        _implementation_contract(),
        reliability=ReliabilityBudget(
            attempt_timeout_seconds=60,
            total_deadline_seconds=100,
            attempts_per_deployment=2,
            maximum_deployments=1,
        ),
    )
    with pytest.raises(ContractCompilationError, match="total deadline"):
        compile_contract(contract, _infrastructure_config())
```

- [ ] **Step 2: Verify tests fail**

Run: `rtk pytest tests/test_orchestration_compiler.py -q`

Expected: FAIL because `compile_contract` is undefined.

- [ ] **Step 3: Implement compilation and stable hashing**

```python
@dataclass(frozen=True)
class CompiledRoutingPolicy:
    contract_id: str
    contract_version: str
    lifecycle_state: str
    config: OrchestrationConfig
    objective: ContractObjective
    reliability: ReliabilityBudget
    evaluation: ContractEvaluationPolicy
    policy_hash: str


def compile_contract(
    contract: WorkloadContract,
    infrastructure: OrchestrationConfig,
) -> CompiledRoutingPolicy:
    worst_case = (
        contract.reliability.attempt_timeout_seconds
        * contract.reliability.attempts_per_deployment
        * contract.reliability.maximum_deployments
    )
    if worst_case > contract.reliability.total_deadline_seconds:
        raise ContractCompilationError(
            f"Configured attempts require {worst_case:g}s but total deadline is "
            f"{contract.reliability.total_deadline_seconds:g}s"
        )
    role = Role(
        id=contract.id,
        name=contract.name,
        description=contract.description,
        required_capabilities=set(contract.requirements.required_capabilities),
    )
    binding = RouteBinding(
        id=f"{contract.id}-default",
        role=contract.id,
        model=contract.baseline_model or "",
        selectors=dict(contract.selectors),
        fallback_chain=list(contract.fallback_models),
        required_capabilities=set(contract.requirements.required_capabilities),
    )
    settings = replace(
        infrastructure.settings,
        allowed_providers=set(contract.requirements.allowed_providers),
        allowed_regions=set(contract.requirements.allowed_regions),
        allowed_data_classifications=set(
            contract.requirements.allowed_data_classifications
        ),
        retries=contract.reliability.attempts_per_deployment - 1,
        timeout_seconds=contract.reliability.attempt_timeout_seconds,
    )
    config = replace(
        infrastructure,
        roles=[role],
        bindings=[binding],
        settings=settings,
    )
    hash_payload = {
        "contract": contract_to_dict(contract),
        "config": to_dict(config),
    }
    policy_hash = hashlib.sha256(
        json.dumps(hash_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return CompiledRoutingPolicy(
        contract_id=contract.id,
        contract_version=contract.version,
        lifecycle_state=contract.state,
        config=config,
        objective=contract.objective,
        reliability=contract.reliability,
        evaluation=contract.evaluation,
        policy_hash=policy_hash,
    )
```

The hash must use canonical JSON with sorted keys and SHA-256. Include contract identity, requirements, objective, reliability, evaluation, generated role/bindings, and constrained settings.

- [ ] **Step 4: Run compiler and policy-bundle tests**

Run: `rtk pytest tests/test_orchestration_compiler.py tests/test_orchestration_platform.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the compiler**

```bash
rtk git add cutctx/orchestration/compiler.py cutctx/orchestration/policy_bundle.py tests/test_orchestration_compiler.py tests/test_orchestration_platform.py
rtk git commit -m "feat(orchestration): compile workload contracts"
```

---

### Task 4: Contract-aware simulation and unified decision receipts

**Files:**
- Create: `cutctx/orchestration/simulation.py`
- Modify: `cutctx/orchestration/models.py`
- Modify: `cutctx/orchestration/engine.py`
- Modify: `cutctx/orchestration/service.py`
- Test: `tests/test_orchestration_simulation.py`
- Test: `tests/test_orchestration_platform.py`

**Interfaces:**
- Consumes: `CompiledRoutingPolicy`, `RoutingRequest`, contract draft payloads, and execution receipts.
- Produces: `ContractDecisionReceipt`, `SimulationResult`, `OrchestrationService.simulate_contract()`, and `OrchestrationService.replay_contract()`.

- [ ] **Step 1: Write failing draft/live simulation tests**

```python
def test_simulation_uses_supplied_draft_without_mutating_live_service(service) -> None:
    live = service.route(RoutingRequest(role="implementation", request_id="req-1"))
    result = service.simulate_contract(
        _draft_contract(baseline_model="anthropic:sonnet"),
        RoutingRequest(role="implementation", request_id="req-1"),
    )
    assert result.executed is False
    assert result.draft_receipt.selected_model == "anthropic:sonnet"
    assert result.live_receipt.selected_model == live.actual_model
    assert service.route(RoutingRequest(role="implementation")).actual_model == live.actual_model


def test_receipt_lists_every_rejected_candidate_with_stable_reason(service) -> None:
    result = service.simulate_contract(_draft_contract(), _restricted_request())
    assert {item.reason for item in result.draft_receipt.rejected_candidates} >= {
        "provider_not_allowed",
        "unsupported_capabilities",
    }
```

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `rtk pytest tests/test_orchestration_simulation.py -q`

Expected: FAIL because contract simulation and receipts do not exist.

- [ ] **Step 3: Implement simulation with an isolated engine**

```python
def simulate_contract(
    self,
    contract: WorkloadContract,
    request: RoutingRequest,
) -> SimulationResult:
    compiled = compile_contract(contract, self.config)
    draft_engine = DeterministicRoutingEngine(
        compiled.config,
        self.model_registry,
        require_configured_accounts=True,
    )
    live_decision = self.route(request, allow_overrides=True)
    draft_decision = draft_engine.route(request, allow_overrides=True)
    return compare_decisions(
        live=self._contract_receipt(live_decision),
        draft=self._contract_receipt(draft_decision, compiled=compiled),
    )
```

Extend `RoutingDecision` with optional `contract_id`, `contract_version`, `contract_state`, `policy_hash`, `eligible_candidates`, `rejected_candidates`, `selected_model`, `selected_deployment`, `evidence`, and `reliability_budget`. Preserve schema version 1 fields and add receipt schema version 2.

- [ ] **Step 4: Run simulation and platform tests**

Run: `rtk pytest tests/test_orchestration_simulation.py tests/test_orchestration_platform.py tests/test_model_routing_trace.py -q`

Expected: PASS.

- [ ] **Step 5: Commit simulation and receipts**

```bash
rtk git add cutctx/orchestration/simulation.py cutctx/orchestration/models.py cutctx/orchestration/engine.py cutctx/orchestration/service.py tests/test_orchestration_simulation.py tests/test_orchestration_platform.py
rtk git commit -m "feat(orchestration): simulate contract routes"
```

---

### Task 5: Contract and rollout APIs

**Files:**
- Modify: `cutctx/proxy/routes/orchestration.py`
- Modify: `cutctx/orchestration/service.py`
- Modify: `cutctx/orchestration/__init__.py`
- Test: `tests/test_orchestration_api.py`

**Interfaces:**
- Consumes: contract store, compiler, simulation, evidence reports, and outcome telemetry.
- Produces: `/contracts`, `/contracts/{id}/draft`, `/contracts/{id}/simulate`, lifecycle actions, `/receipts/{request_id}`, and `/outcomes`.

- [ ] **Step 1: Write failing authenticated API tests**

```python
def test_draft_simulation_uses_request_payload_without_saving(client, headers) -> None:
    response = client.post(
        "/v1/orchestration/contracts/implementation/simulate",
        headers=headers,
        json={
            "contract": _contract_payload(version="2", baseline_model="anthropic:sonnet"),
            "scenario": {"role": "implementation", "request_id": "preview-1"},
        },
    )
    assert response.status_code == 200
    assert response.json()["executed"] is False
    assert response.json()["draft_receipt"]["contract_version"] == "2"


def test_promotion_rejects_insufficient_evidence(client, headers) -> None:
    response = client.post(
        "/v1/orchestration/contracts/implementation/versions/2/promote",
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["detail"]["reason"] == "insufficient_evidence"
```

- [ ] **Step 2: Run API tests and verify 404 failures**

Run: `rtk pytest tests/test_orchestration_api.py -q`

Expected: FAIL with missing contract routes.

- [ ] **Step 3: Add strict Pydantic payloads and endpoints**

```python
class ContractSimulationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contract: dict[str, Any]
    scenario: RoutingPayload


@router.post("/contracts/{contract_id}/simulate", dependencies=read_deps)
async def simulate_contract(
    contract_id: str,
    payload: ContractSimulationPayload,
) -> dict[str, Any]:
    contract = contract_from_dict(payload.contract)
    if contract.id != contract_id:
        raise HTTPException(status_code=400, detail="Contract id does not match route")
    return to_dict(service.simulate_contract(contract, _request(payload.scenario)))
```

All write endpoints require write dependencies, accept `expected_revision`, and return 409 for revision conflict, invalid lifecycle transition, failed evidence gate, or routing unavailability.

- [ ] **Step 4: Run API and authorization tests**

Run: `rtk pytest tests/test_orchestration_api.py tests/test_admin_surface_guards.py -q`

Expected: PASS.

- [ ] **Step 5: Commit API resources**

```bash
rtk git add cutctx/proxy/routes/orchestration.py cutctx/orchestration/service.py cutctx/orchestration/__init__.py tests/test_orchestration_api.py
rtk git commit -m "feat(api): expose workload contract lifecycle"
```

---

### Task 6: Enforce compiled reliability budgets during execution

**Files:**
- Modify: `cutctx/orchestration/service.py`
- Modify: `cutctx/orchestration/models.py`
- Test: `tests/test_orchestration_platform.py`

**Interfaces:**
- Consumes: `ReliabilityBudget` from the active compiled contract.
- Produces: bounded attempt execution, total deadline enforcement, and receipt timing fields.

- [ ] **Step 1: Write failing deadline and streaming tests**

```python
@pytest.mark.asyncio
async def test_total_deadline_stops_retry_and_fallback_expansion(service) -> None:
    service.activate_contract(_contract_with_budget(
        attempt_timeout_seconds=1,
        total_deadline_seconds=1.5,
        attempts_per_deployment=2,
        maximum_deployments=2,
    ))
    with pytest.raises(RoutingUnavailableError) as exc:
        await service.execute(RoutingRequest(role="worker"), messages=[])
    assert exc.value.reason == "total_deadline_exceeded"


@pytest.mark.asyncio
async def test_stream_idle_timeout_does_not_switch_after_first_chunk(service) -> None:
    chunks = []
    with pytest.raises(TimeoutError):
        async for _decision, chunk in service.stream(
            RoutingRequest(role="worker"), messages=[]
        ):
            chunks.append(chunk)
    assert chunks == [b"first"]
    assert service.telemetry.list()[0].fallback_used is False
```

- [ ] **Step 2: Confirm the old global timeout behavior fails these tests**

Run: `rtk pytest tests/test_orchestration_platform.py -k 'total_deadline or stream_idle' -q`

Expected: FAIL because execution reads only global `timeout_seconds`.

- [ ] **Step 3: Implement one monotonic deadline and per-stage limits**

```python
deadline = time.perf_counter() + budget.total_deadline_seconds

def remaining() -> float:
    value = deadline - time.perf_counter()
    if value <= 0:
        raise RoutingUnavailableError(
            "The contract total deadline was exhausted",
            assigned_model=decision.assigned_model,
            reason="total_deadline_exceeded",
        )
    return value

attempt_timeout = min(budget.attempt_timeout_seconds, remaining())
response = await asyncio.wait_for(adapter.invoke(payload), timeout=attempt_timeout)
```

Count attempts and distinct deployment keys against the compiled budget. For streaming, enforce first-token and idle deadlines separately while keeping the total monotonic deadline.

- [ ] **Step 4: Run orchestration execution tests**

Run: `rtk pytest tests/test_orchestration_platform.py tests/test_orchestration_api.py -q`

Expected: PASS.

- [ ] **Step 5: Commit reliability-budget execution**

```bash
rtk git add cutctx/orchestration/service.py cutctx/orchestration/models.py tests/test_orchestration_platform.py
rtk git commit -m "feat(orchestration): enforce contract reliability budgets"
```

---

### Task 7: Build the Contracts and Simulator workspaces

**Files:**
- Create: `dashboard/src/components/routing-studio/api.js`
- Create: `dashboard/src/components/routing-studio/RoutingStudio.jsx`
- Create: `dashboard/src/components/routing-studio/ContractList.jsx`
- Create: `dashboard/src/components/routing-studio/ContractEditor.jsx`
- Create: `dashboard/src/components/routing-studio/RouteSimulator.jsx`
- Create: `dashboard/src/components/routing-studio/DecisionPipeline.jsx`
- Modify: `dashboard/src/pages/Orchestrator.jsx`
- Modify: `dashboard/src/index.css`
- Test: `dashboard/e2e/orchestrator.spec.js`

**Interfaces:**
- Consumes: contract list/draft/simulate APIs, model registry, provider accounts, and harness manifest.
- Produces: accessible Contracts and Simulator workspaces with draft/live labeling and decision evidence.

- [ ] **Step 1: Add failing browser tests for contract creation and draft simulation**

```javascript
test('creates a coding-agent contract and previews the visible draft', async ({ page }) => {
  await mockRoutingStudio(page);
  await page.goto('/orchestrator');
  await page.getByRole('button', { name: 'New contract' }).click();
  await page.getByLabel('Contract template').selectOption('implementation');
  await page.getByLabel('Quality floor').fill('0.95');
  await page.getByRole('tab', { name: 'Simulator' }).click();
  await page.getByRole('button', { name: 'Run draft simulation' }).click();
  await expect(page.getByText('Draft version 2', { exact: true })).toBeVisible();
  await expect(page.getByText('anthropic:sonnet', { exact: true })).toBeVisible();
});

test('routing studio tabs use arrow keys and one active tab stop', async ({ page }) => {
  await mockRoutingStudio(page);
  await page.goto('/orchestrator');
  const contracts = page.getByRole('tab', { name: 'Contracts' });
  await contracts.focus();
  await contracts.press('ArrowRight');
  await expect(page.getByRole('tab', { name: 'Simulator' })).toBeFocused();
  await expect(page.getByRole('tabpanel', { name: 'Simulator' })).toBeVisible();
});
```

- [ ] **Step 2: Run Playwright and confirm missing workspace failures**

Run: `rtk test npx playwright test dashboard/e2e/orchestrator.spec.js --project=chromium`

Expected: FAIL because Routing Studio components do not exist.

- [ ] **Step 3: Implement API normalization and the workspace shell**

```javascript
export const WORKSPACES = ['contracts', 'simulator', 'rollouts', 'evidence'];

export function RoutingStudio() {
  const [workspace, setWorkspace] = useState('contracts');
  const [contracts, setContracts] = useState([]);
  const [draft, setDraft] = useState(null);
  const [simulation, setSimulation] = useState(null);

  function onTabKeyDown(event, index) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const next = nextTabIndex(event.key, index, WORKSPACES.length);
    setWorkspace(WORKSPACES[next]);
    document.getElementById(`routing-tab-${WORKSPACES[next]}`)?.focus();
  }

  return <section className="routing-studio">{/* labeled tabs and panels */}</section>;
}
```

Each tab sets `id`, `aria-controls`, `aria-selected`, and `tabIndex`. Each panel sets `role="tabpanel"`, `aria-labelledby`, and `hidden`.

- [ ] **Step 4: Implement contract fields and simulation evidence**

The editor must render labeled controls for baseline, objective, quality floor, cost ceiling, latency target, capabilities, allowed providers, attempt timeout, total deadline, retry count, maximum deployments, evidence samples, unsafe floor, and canary percentage.

The simulator must send the current draft payload and display selected model/deployment, estimated measures, contract version, rejected candidates, evidence source, and worst-case deadline.

- [ ] **Step 5: Add responsive CSS and run browser tests**

```css
@media (max-width: 720px) {
  .app-sidebar { transform: translateX(-100%); }
  .app-sidebar.open { transform: translateX(0); }
  .app-main { margin-left: 0; width: 100%; min-width: 0; }
  .routing-studio-grid,
  .contract-editor-grid { grid-template-columns: minmax(0, 1fr); }
  .routing-table { display: block; overflow-x: auto; max-width: 100%; }
}
```

Run: `rtk test npx playwright test dashboard/e2e/orchestrator.spec.js --project=chromium`

Expected: PASS.

- [ ] **Step 6: Commit Contracts and Simulator**

```bash
rtk git add dashboard/src/components/routing-studio dashboard/src/pages/Orchestrator.jsx dashboard/src/index.css dashboard/e2e/orchestrator.spec.js
rtk git commit -m "feat(dashboard): add workload contract routing studio"
```

---

### Task 8: Build Rollouts, Evidence, migration, and release verification

**Files:**
- Create: `dashboard/src/components/routing-studio/RolloutPanel.jsx`
- Create: `dashboard/src/components/routing-studio/EvidencePanel.jsx`
- Modify: `dashboard/src/components/routing-studio/RoutingStudio.jsx`
- Modify: `cutctx/orchestration/service.py`
- Modify: `cutctx/proxy/routes/orchestration.py`
- Modify: `docs/content/docs/model-routing-presets.mdx`
- Modify: `docs/content/docs/api-reference.mdx`
- Test: `tests/test_orchestration_api.py`
- Test: `tests/test_orchestration_platform.py`
- Test: `tests/test_dashboard_orchestrator_policy_e2e.py`
- Test: `dashboard/e2e/orchestrator.spec.js`

**Interfaces:**
- Consumes: lifecycle endpoints, routing evidence, outcome telemetry, execution receipts, and legacy config.
- Produces: shadow/canary/promotion/rollback UI, quality-safe savings reporting, legacy migration, and release evidence.

- [ ] **Step 1: Write failing lifecycle-gate and dashboard tests**

```python
def test_canary_requires_evidence_and_rollback_restores_previous_active(service) -> None:
    service.contract_store.put_draft(_contract("1"), expected_revision=0)
    service.contract_store.transition("implementation", "1", "shadow")
    with pytest.raises(ContractTransitionError, match="evidence"):
        service.promote_contract("implementation", "1", target="canary")
    service.record_contract_evidence("implementation", "1", _passing_evidence())
    service.promote_contract("implementation", "1", target="canary")
    service.promote_contract("implementation", "1", target="active")
    assert service.rollback_contract("implementation").version == "0"
```

```javascript
test('shows quality-safe savings and blocks unsafe promotion', async ({ page }) => {
  await mockRoutingStudio(page, { evidenceStatus: 'quality_blocked' });
  await page.goto('/orchestrator');
  await page.getByRole('tab', { name: 'Evidence' }).click();
  await expect(page.getByText('Quality-safe savings')).toBeVisible();
  await page.getByRole('tab', { name: 'Rollouts' }).click();
  await expect(page.getByRole('button', { name: 'Promote to canary' })).toBeDisabled();
  await expect(page.getByText('Quality floor not met')).toBeVisible();
});
```

- [ ] **Step 2: Verify lifecycle tests fail**

Run: `rtk pytest tests/test_orchestration_api.py tests/test_orchestration_platform.py -k 'contract or canary or rollback' -q`

Expected: FAIL because evidence gates and rollback activation are incomplete.

- [ ] **Step 3: Implement lifecycle gates and quality-safe evidence summary**

```python
def promote_contract(self, contract_id: str, version: str, *, target: str) -> WorkloadContract:
    evidence = self.contract_evidence(contract_id, version)
    if target in {"canary", "active"}:
        if evidence.status == "collecting":
            raise ContractTransitionError("insufficient_evidence")
        if evidence.status == "quality_blocked":
            raise ContractTransitionError("quality_floor_not_met")
    contract = self.contract_store.transition(contract_id, version, target)
    if target == "active":
        self._activate_compiled_contract(contract)
    return contract
```

Quality-safe savings counts only decisions whose evidence segment met the contract quality floor at decision time. Report raw routed savings separately.

- [ ] **Step 4: Implement Rollouts and Evidence panels**

Rollouts must display the lifecycle timeline, gate status, canary cohort, pause, promote, and rollback actions. Evidence must display quality-safe savings, evidence coverage, unsafe rate, acceptance rate, fallback rate, abstention reasons, and receipt lookup.

- [ ] **Step 5: Add legacy migration and documentation**

On service startup, when the contract store is empty and roles/bindings exist, expose generated legacy contracts without writing them. The first draft save materializes a contract version. Document legacy policy mappings, draft simulation, lifecycle endpoints, reliability budgets, and quality-safe savings.

- [ ] **Step 6: Run the full verification matrix**

Run:

```bash
rtk pytest tests/test_orchestration_contracts.py tests/test_orchestration_contract_store.py tests/test_orchestration_compiler.py tests/test_orchestration_simulation.py tests/test_orchestration_api.py tests/test_orchestration_platform.py tests/test_model_router.py tests/test_model_router_presets.py tests/test_model_routing_trace.py tests/test_dashboard_orchestrator_policy_e2e.py -q
rtk npm run lint
rtk npm run build
rtk test npx playwright test dashboard/e2e/orchestrator.spec.js --project=chromium
```

Expected: all commands exit 0.

- [ ] **Step 7: Perform visual and completion verification**

Capture and inspect Contracts and Simulator at desktop and 390×844. Verify no horizontal page scroll, all controls remain visible, focus order follows the interface, draft/live state is explicit, and promotion cannot proceed with blocked evidence.

- [ ] **Step 8: Commit rollout, evidence, migration, and docs**

```bash
rtk git add dashboard/src/components/routing-studio dashboard/e2e/orchestrator.spec.js cutctx/orchestration/service.py cutctx/proxy/routes/orchestration.py docs/content/docs/model-routing-presets.mdx docs/content/docs/api-reference.mdx tests/test_orchestration_api.py tests/test_orchestration_platform.py tests/test_dashboard_orchestrator_policy_e2e.py
rtk git commit -m "feat(orchestration): ship evidence-gated routing studio"
```

---

## Completion audit

Before declaring the feature complete, collect evidence for every acceptance criterion in the design specification:

1. Contract template creation and understandable preview: Playwright test and desktop screenshot.
2. Legacy behavior equivalence: compiler and platform tests using existing role fixtures.
3. Draft-aware preview: API and simulation tests proving live state remains unchanged.
4. Non-bypassable hard constraints: engine/compiler matrix tests.
5. Quality versus reliability separation: receipt schema assertions and dashboard copy test.
6. Bounded reliability budget: deadline and streaming tests.
7. Evidence-gated promotion and rollback: lifecycle tests and UI disabled-state test.
8. Unified receipt schema: preview/live receipt equality assertions.
9. 390-pixel responsive operation: screenshot and horizontal-overflow browser assertion.
10. Quality-safe savings: evidence calculation test and dashboard metric assertion.
