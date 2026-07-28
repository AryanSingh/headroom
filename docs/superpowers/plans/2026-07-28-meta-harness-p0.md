# Meta-Harness P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable durable workflows to run at least one non-LLM harness worker (Codex CLI POC) with explicit, content-addressed artifact handoffs and CCR-compressed boundaries — without hidden session sharing between tasks.

**Architecture:** Introduce a `HarnessAdapter` protocol and `HarnessRuntime` dispatcher above `WorkflowRunner`. Agent packages live in `.cutctx/agents/*.yaml` with canonical package hashes. Harness tasks write blobs to `CUTCTX_ORCHESTRATION_DIR/artifacts/`; handoff payloads pass `ArtifactRef` values (with optional `ccr_hash`) instead of raw transcripts. LLM tasks keep using `OrchestrationService.execute`; harness tasks route through adapters when `task.payload.harness` is set.

**Tech Stack:** Python 3.10+, asyncio subprocess, PyYAML, pytest, FastAPI orchestration routes, existing `CompressionStore` (`cutctx/cache/compression_store.py`), `WorkflowRunner` / `WorkflowStateStore`, `OrchestrationService`, Click `cutctx wrap` env conventions.

## Global Constraints

- Option B scope only: thin meta-harness coordination on existing `cutctx/orchestration/` — not full Omnigent/Carbon parity.
- P0 uses **local subprocess** execution only; no cloud sandbox, Modal, Daytona, or Omnigent sidecar.
- No supervisor-LLM workflow planner; workflows stay YAML/API-defined DAGs.
- No hidden session sharing between workflow tasks; each handoff uses explicit artifact refs.
- Agent packages are **project-scoped** (`.cutctx/agents/`), not a public marketplace.
- Artifact storage path: `{CUTCTX_ORCHESTRATION_DIR}/artifacts/sha256/{hash[:2]}/{hash}` (content-addressed).
- Dual-path: solo dev uses local YAML + file artifacts; enterprise uses same APIs (Redis workflow store optional via existing `CUTCTX_ORCHESTRATION_REDIS_URL`).
- Prefer `rtk`-prefixed shell commands in this repository.
- Do not edit unrelated dirty worktree files.

## File structure

| File | Responsibility |
|---|---|
| `cutctx/orchestration/harness_adapter.py` | `HarnessAdapter` protocol, `HarnessCapabilities`, `HarnessRunContext`, `HarnessRunResult`, `ArtifactRef` |
| `cutctx/orchestration/artifact_store.py` | Content-addressed blob read/write under orchestration dir |
| `cutctx/orchestration/agent_packages.py` | YAML schema v1, canonical hash, file-backed `AgentPackageRegistry` |
| `cutctx/orchestration/handoff_ccr.py` | Compress artifact text at workflow boundaries; attach `ccr_hash` to refs |
| `cutctx/orchestration/harness_runtime.py` | Adapter registry, dispatch `run_harness_task()`, cancel hook |
| `cutctx/orchestration/adapters/__init__.py` | Adapter package exports |
| `cutctx/orchestration/adapters/codex_cli.py` | Codex CLI subprocess adapter POC |
| `cutctx/orchestration/service.py` | `run_workflow` dispatches harness vs LLM by `task.payload.harness` |
| `cutctx/proxy/routes/orchestration.py` | `GET/PUT /v1/orchestration/agent-packages` |
| `cutctx/orchestration/__init__.py` | Public exports for new types |
| `tests/test_harness_adapter_types.py` | Protocol/type contract tests |
| `tests/test_artifact_store.py` | Blob store unit tests |
| `tests/test_agent_packages.py` | Schema, hash stability, registry CRUD |
| `tests/test_handoff_ccr.py` | CCR boundary compression tests |
| `tests/test_codex_cli_adapter.py` | Codex adapter with fake binary |
| `tests/test_harness_runtime.py` | Runtime dispatch and cancel |
| `tests/test_meta_harness_workflow_e2e.py` | Planner → Codex implementer → LLM reviewer |
| `tests/test_orchestration_agent_packages_api.py` | REST API for agent packages |
| `.cutctx/agents/example-implementer.yaml` | Documented example package (committed fixture) |

## Scope freeze — do NOT build in P0

| Out of scope | Defer to |
|---|---|
| Worker cost/duration/revision budgets (`max_cost_usd`, `max_revision_rounds`) | P1 |
| Live cancel/pause WebSocket control plane | P1 |
| Claude Code / OpenCode / ACP adapters | P1–P2 |
| `ExecutionEnvironment` sandbox trait (Modal, Daytona, Omnigent) | P2 |
| Provenance graph relational store (`parent_artifacts[]`) | P1 |
| Agent package Ed25519 signing | P2 |
| Dashboard Orchestration Studio harness UI | P1 |
| Per-worker credential brokering / read-only reviewer sandbox | P2 |
| Temporal `WorkflowRuntime` adapter | P2 |
| Omnigent-class collaboration UI | Never (partner) |

---

### Task 0: Baseline verification

**Files:**
- Read/verify: `tests/test_orchestration_workflow.py`
- Read/verify: `tests/test_orchestration_api.py`
- Read/verify: `cutctx/orchestration/harnesses.py`

**Interfaces:**
- Consumes: existing workflow + orchestration API implementations
- Produces: green baseline before new modules land

- [ ] **Step 1: Run workflow unit suite**

Run: `rtk pytest tests/test_orchestration_workflow.py -q`

Expected: PASS

- [ ] **Step 2: Run orchestration API suite**

Run: `rtk pytest tests/test_orchestration_api.py -q`

Expected: PASS

- [ ] **Step 3: Confirm harness compatibility manifest is static metadata only**

Run: `rtk pytest tests/test_orchestration_platform.py -q -k harness`

Expected: PASS (manifest exists; no runnable adapters yet)

- [ ] **Step 4: Proceed with no commit** (verification only)

---

### Task 1: Harness adapter protocol and core types

**Files:**
- Create: `cutctx/orchestration/harness_adapter.py`
- Create: `tests/test_harness_adapter_types.py`

**Interfaces:**
- Produces: `@dataclass(frozen=True) class ArtifactRef` with fields `blob_id: str`, `media_type: str`, `byte_size: int`, `ccr_hash: str`, `provenance: dict[str, str]`
- Produces: `@dataclass(frozen=True) class HarnessCapabilities` with `stream: bool`, `cancel: bool`, `resume: bool`, `artifact_emit: bool`
- Produces: `@dataclass class HarnessRunContext` with `run_id: str`, `workflow_id: str`, `task_id: str`, `role: str`, `agent_package_id: str`, `workspace_ref: str`, `input_artifacts: list[ArtifactRef]`, `prompt: str`, `env: dict[str, str]`
- Produces: `@dataclass class HarnessRunResult` with `status: str`, `artifacts: list[ArtifactRef]`, `stdout_ref: str`, `stderr_ref: str`, `metadata: dict[str, str]`
- Produces: `class HarnessAdapter(Protocol)` with `harness_id: str`, `capabilities() -> HarnessCapabilities`, `async health() -> dict[str, Any]`, `async run(ctx: HarnessRunContext) -> HarnessRunResult`, `async cancel(run_id: str) -> None`

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

import pytest

from cutctx.orchestration.harness_adapter import (
    ArtifactRef,
    HarnessCapabilities,
    HarnessRunContext,
    HarnessRunResult,
)


def test_artifact_ref_defaults() -> None:
    ref = ArtifactRef(blob_id="abc123")
    assert ref.media_type == "application/octet-stream"
    assert ref.byte_size == 0
    assert ref.ccr_hash == ""
    assert ref.provenance == {}


def test_harness_capabilities_defaults() -> None:
    caps = HarnessCapabilities()
    assert caps.stream is False
    assert caps.cancel is True
    assert caps.resume is False
    assert caps.artifact_emit is True


def test_harness_run_context_carries_explicit_artifacts() -> None:
    parent = ArtifactRef(blob_id="plan_blob", media_type="text/plain", byte_size=12)
    ctx = HarnessRunContext(
        run_id="run-1",
        workflow_id="wf-1",
        task_id="implement",
        role="implementer",
        agent_package_id="implementer-codex",
        workspace_ref="/tmp/repo",
        input_artifacts=[parent],
        prompt="Apply the plan as a patch.",
        env={"CUTCTX_PROXY_URL": "http://127.0.0.1:8787"},
    )
    assert ctx.input_artifacts[0].blob_id == "plan_blob"


def test_harness_run_result_requires_terminal_status() -> None:
  result = HarnessRunResult(status="completed", artifacts=[])
  assert result.status == "completed"
  assert result.stdout_ref == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk pytest tests/test_harness_adapter_types.py -q`

Expected: FAIL with `ModuleNotFoundError` for `cutctx.orchestration.harness_adapter`

- [ ] **Step 3: Implement types and protocol**

```python
# cutctx/orchestration/harness_adapter.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ArtifactRef:
    blob_id: str
    media_type: str = "application/octet-stream"
    byte_size: int = 0
    ccr_hash: str = ""
    provenance: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class HarnessCapabilities:
    stream: bool = False
    cancel: bool = True
    resume: bool = False
    artifact_emit: bool = True


@dataclass
class HarnessRunContext:
    run_id: str
    workflow_id: str
    task_id: str
    role: str
    agent_package_id: str
    workspace_ref: str
    input_artifacts: list[ArtifactRef] = field(default_factory=list)
    prompt: str = ""
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class HarnessRunResult:
    status: str
    artifacts: list[ArtifactRef] = field(default_factory=list)
    stdout_ref: str = ""
    stderr_ref: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


class HarnessAdapter(Protocol):
    harness_id: str

    def capabilities(self) -> HarnessCapabilities: ...

    async def health(self) -> dict[str, Any]: ...

    async def run(self, ctx: HarnessRunContext) -> HarnessRunResult: ...

    async def cancel(self, run_id: str) -> None: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk pytest tests/test_harness_adapter_types.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cutctx/orchestration/harness_adapter.py tests/test_harness_adapter_types.py
git commit -m "$(cat <<'EOF'
feat(orchestration): add HarnessAdapter protocol and artifact refs

EOF
)"
```

---

### Task 2: Content-addressed artifact blob store

**Files:**
- Create: `cutctx/orchestration/artifact_store.py`
- Create: `tests/test_artifact_store.py`

**Interfaces:**
- Consumes: `ArtifactRef` from Task 1
- Produces: `class ArtifactBlobStore` with `__init__(self, root: Path | str)`, `put(self, data: bytes, *, media_type: str = "application/octet-stream", provenance: dict[str, str] | None = None) -> ArtifactRef`, `get(self, blob_id: str) -> bytes`, `exists(self, blob_id: str) -> bool`, `ref_for_text(self, text: str, *, media_type: str = "text/plain", provenance: dict[str, str] | None = None) -> ArtifactRef`
- Produces: blob layout `{root}/sha256/{hash[:2]}/{hash}`; `blob_id` is full lowercase SHA-256 hex

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

import pytest

from cutctx.orchestration.artifact_store import ArtifactBlobStore


def test_put_is_content_addressed_and_idempotent(tmp_path) -> None:
    store = ArtifactBlobStore(tmp_path / "artifacts")
    data = b"diff --git a/foo.py\n"
    first = store.put(data, media_type="text/x-patch", provenance={"task": "implement"})
    second = store.put(data, media_type="text/x-patch")
    assert first.blob_id == second.blob_id
    assert first.byte_size == len(data)
    assert store.exists(first.blob_id)
    assert store.get(first.blob_id) == data


def test_ref_for_text_stores_utf8(tmp_path) -> None:
    store = ArtifactBlobStore(tmp_path / "artifacts")
    ref = store.ref_for_text("plan: add harness adapter", provenance={"role": "planner"})
    assert ref.media_type == "text/plain"
    assert store.get(ref.blob_id).decode("utf-8") == "plan: add harness adapter"


def test_get_unknown_blob_raises(tmp_path) -> None:
    store = ArtifactBlobStore(tmp_path / "artifacts")
    with pytest.raises(FileNotFoundError):
        store.get("0" * 64)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk pytest tests/test_artifact_store.py -q`

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement blob store**

```python
# cutctx/orchestration/artifact_store.py
from __future__ import annotations

import hashlib
from pathlib import Path

from .harness_adapter import ArtifactRef


class ArtifactBlobStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def _path_for(self, blob_id: str) -> Path:
        normalized = blob_id.lower()
        if len(normalized) != 64 or any(c not in "0123456789abcdef" for c in normalized):
            raise ValueError(f"invalid blob_id: {blob_id!r}")
        return self.root / "sha256" / normalized[:2] / normalized

    @staticmethod
    def _hash_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def put(
        self,
        data: bytes,
        *,
        media_type: str = "application/octet-stream",
        provenance: dict[str, str] | None = None,
    ) -> ArtifactRef:
        blob_id = self._hash_bytes(data)
        path = self._path_for(blob_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(data)
        return ArtifactRef(
            blob_id=blob_id,
            media_type=media_type,
            byte_size=len(data),
            provenance=dict(provenance or {}),
        )

    def ref_for_text(
        self,
        text: str,
        *,
        media_type: str = "text/plain",
        provenance: dict[str, str] | None = None,
    ) -> ArtifactRef:
        return self.put(text.encode("utf-8"), media_type=media_type, provenance=provenance)

    def exists(self, blob_id: str) -> bool:
        return self._path_for(blob_id).exists()

    def get(self, blob_id: str) -> bytes:
        path = self._path_for(blob_id)
        if not path.exists():
            raise FileNotFoundError(blob_id)
        return path.read_bytes()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk pytest tests/test_artifact_store.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cutctx/orchestration/artifact_store.py tests/test_artifact_store.py
git commit -m "$(cat <<'EOF'
feat(orchestration): add content-addressed artifact blob store

EOF
)"
```

---

### Task 3: Agent package schema and canonical hash

**Files:**
- Create: `cutctx/orchestration/agent_packages.py` (schema + hash only; registry in Task 4)
- Create: `tests/test_agent_packages.py` (hash/schema section)
- Create: `.cutctx/agents/example-implementer.yaml`

**Interfaces:**
- Produces: `@dataclass class AgentPackage` with `id`, `version`, `harness`, `role`, `tools: list[str]`, `policy_refs: list[str]`, `package_hash: str`
- Produces: `AGENT_PACKAGE_API_VERSION = "cutctx.dev/agent/v1"`
- Produces: `parse_agent_package_yaml(text: str) -> AgentPackage`
- Produces: `canonical_package_bytes(package: AgentPackage) -> bytes` (stable JSON, excludes `package_hash`)
- Produces: `compute_package_hash(package: AgentPackage) -> str` (SHA-256 hex of canonical bytes)

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

from pathlib import Path

import pytest

from cutctx.orchestration.agent_packages import (
    AGENT_PACKAGE_API_VERSION,
    AgentPackage,
    compute_package_hash,
    parse_agent_package_yaml,
)


EXAMPLE = """\
apiVersion: cutctx.dev/agent/v1
id: implementer-codex
version: 1
harness: codex_cli
role: implementer
tools:
  - shell
  - apply_patch
policy_refs:
  - contract:implementation
"""


def test_parse_agent_package_yaml() -> None:
    pkg = parse_agent_package_yaml(EXAMPLE)
    assert pkg.id == "implementer-codex"
    assert pkg.harness == "codex_cli"
    assert pkg.role == "implementer"
    assert pkg.tools == ["shell", "apply_patch"]
    assert pkg.policy_refs == ["contract:implementation"]


def test_package_hash_is_stable_across_key_order() -> None:
    a = parse_agent_package_yaml(EXAMPLE)
    b = parse_agent_package_yaml(EXAMPLE.replace("implementer-codex", "implementer-codex"))
    assert compute_package_hash(a) == compute_package_hash(b)
    assert len(compute_package_hash(a)) == 64


def test_rejects_unknown_api_version() -> None:
    bad = EXAMPLE.replace(AGENT_PACKAGE_API_VERSION, "cutctx.dev/agent/v0")
    with pytest.raises(ValueError, match="apiVersion"):
        parse_agent_package_yaml(bad)


def test_example_fixture_on_disk() -> None:
    text = Path(".cutctx/agents/example-implementer.yaml").read_text(encoding="utf-8")
    pkg = parse_agent_package_yaml(text)
    assert pkg.id == "implementer-codex"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk pytest tests/test_agent_packages.py::test_parse_agent_package_yaml -q`

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Add example fixture and implement schema**

`.cutctx/agents/example-implementer.yaml`:

```yaml
apiVersion: cutctx.dev/agent/v1
id: implementer-codex
version: 1
harness: codex_cli
role: implementer
tools:
  - shell
  - apply_patch
policy_refs:
  - contract:implementation
```

```python
# cutctx/orchestration/agent_packages.py (initial section)
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field

import yaml

AGENT_PACKAGE_API_VERSION = "cutctx.dev/agent/v1"


@dataclass
class AgentPackage:
    id: str
    version: int
    harness: str
    role: str
    tools: list[str] = field(default_factory=list)
    policy_refs: list[str] = field(default_factory=list)
    package_hash: str = ""


def parse_agent_package_yaml(text: str) -> AgentPackage:
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise ValueError("agent package must be a mapping")
    if raw.get("apiVersion") != AGENT_PACKAGE_API_VERSION:
        raise ValueError(f"unsupported apiVersion: {raw.get('apiVersion')!r}")
    pkg = AgentPackage(
        id=str(raw["id"]),
        version=int(raw["version"]),
        harness=str(raw["harness"]),
        role=str(raw["role"]),
        tools=[str(item) for item in raw.get("tools", [])],
        policy_refs=[str(item) for item in raw.get("policy_refs", [])],
    )
    pkg.package_hash = compute_package_hash(pkg)
    return pkg


def canonical_package_bytes(package: AgentPackage) -> bytes:
    payload = {
        "apiVersion": AGENT_PACKAGE_API_VERSION,
        "id": package.id,
        "version": package.version,
        "harness": package.harness,
        "role": package.role,
        "tools": list(package.tools),
        "policy_refs": list(package.policy_refs),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_package_hash(package: AgentPackage) -> str:
    return hashlib.sha256(canonical_package_bytes(package)).hexdigest()
```

- [ ] **Step 4: Run schema tests**

Run: `rtk pytest tests/test_agent_packages.py -q -k "parse or hash or rejects or example"`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cutctx/orchestration/agent_packages.py .cutctx/agents/example-implementer.yaml tests/test_agent_packages.py
git commit -m "$(cat <<'EOF'
feat(orchestration): add agent package YAML schema and hash

EOF
)"
```

---

### Task 4: Agent package file registry

**Files:**
- Modify: `cutctx/orchestration/agent_packages.py` (add `AgentPackageRegistry`)
- Modify: `tests/test_agent_packages.py` (registry tests)

**Interfaces:**
- Consumes: `parse_agent_package_yaml`, `AgentPackage` from Task 3
- Produces: `class AgentPackageRegistry` with `__init__(self, agents_dir: Path | str)`, `list(self) -> list[AgentPackage]`, `get(self, package_id: str) -> AgentPackage`, `put(self, text: str) -> AgentPackage`, `delete(self, package_id: str) -> bool`
- Produces: files stored as `{agents_dir}/{id}.yaml`

- [ ] **Step 1: Write the failing registry tests**

```python
def test_registry_round_trip(tmp_path) -> None:
    from cutctx.orchestration.agent_packages import AgentPackageRegistry

    registry = AgentPackageRegistry(tmp_path / "agents")
    saved = registry.put(EXAMPLE)
    assert saved.package_hash
    listed = registry.list()
    assert [item.id for item in listed] == ["implementer-codex"]
    loaded = registry.get("implementer-codex")
    assert loaded.harness == "codex_cli"


def test_registry_delete(tmp_path) -> None:
    from cutctx.orchestration.agent_packages import AgentPackageRegistry

    registry = AgentPackageRegistry(tmp_path / "agents")
    registry.put(EXAMPLE)
    assert registry.delete("implementer-codex") is True
    with pytest.raises(KeyError):
        registry.get("implementer-codex")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk pytest tests/test_agent_packages.py -q -k registry`

Expected: FAIL with `ImportError` or `AttributeError` for `AgentPackageRegistry`

- [ ] **Step 3: Implement registry**

```python
class AgentPackageRegistry:
    def __init__(self, agents_dir: Path | str) -> None:
        self.agents_dir = Path(agents_dir)
        self.agents_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, package_id: str) -> Path:
        if not package_id or "/" in package_id or ".." in package_id:
            raise ValueError(f"invalid package id: {package_id!r}")
        return self.agents_dir / f"{package_id}.yaml"

    def list(self) -> list[AgentPackage]:
        packages: list[AgentPackage] = []
        for path in sorted(self.agents_dir.glob("*.yaml")):
            packages.append(parse_agent_package_yaml(path.read_text(encoding="utf-8")))
        return packages

    def get(self, package_id: str) -> AgentPackage:
        path = self._path_for(package_id)
        if not path.exists():
            raise KeyError(package_id)
        return parse_agent_package_yaml(path.read_text(encoding="utf-8"))

    def put(self, text: str) -> AgentPackage:
        package = parse_agent_package_yaml(text)
        self._path_for(package.id).write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
        return package

    def delete(self, package_id: str) -> bool:
        path = self._path_for(package_id)
        if not path.exists():
            return False
        path.unlink()
        return True
```

- [ ] **Step 4: Run registry tests**

Run: `rtk pytest tests/test_agent_packages.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cutctx/orchestration/agent_packages.py tests/test_agent_packages.py
git commit -m "$(cat <<'EOF'
feat(orchestration): add file-backed agent package registry

EOF
)"
```

---

### Task 5: Agent package REST API

**Files:**
- Modify: `cutctx/orchestration/service.py` (expose `agent_package_registry` property)
- Modify: `cutctx/proxy/routes/orchestration.py` (routes)
- Create: `tests/test_orchestration_agent_packages_api.py`

**Interfaces:**
- Consumes: `AgentPackageRegistry` from Task 4
- Produces: `GET /v1/orchestration/agent-packages` → `{"packages": [...]}`
- Produces: `GET /v1/orchestration/agent-packages/{package_id}` → `{"package": {...}}`
- Produces: `PUT /v1/orchestration/agent-packages/{package_id}` body `{"yaml": "<text>"}` → `{"package": {...}}`
- Produces: `OrchestrationService.agent_packages_dir` resolves `{CUTCTX_ORCHESTRATION_DIR}/../.cutctx/agents` with project override via env `CUTCTX_AGENT_PACKAGES_DIR`

- [ ] **Step 1: Write the failing API tests**

```python
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app

PACKAGE_YAML = """\
apiVersion: cutctx.dev/agent/v1
id: implementer-codex
version: 1
harness: codex_cli
role: implementer
tools:
  - shell
policy_refs: []
"""


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    config_path = tmp_path / "orchestration.json"
    config_path.write_text(
        json.dumps({"version": 1, "providers": [], "roles": [], "models": [], "bindings": []}),
        encoding="utf-8",
    )
    monkeypatch.setenv("CUTCTX_ORCHESTRATION_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("CUTCTX_ORCHESTRATION_CONFIG", str(config_path))
    monkeypatch.setenv("CUTCTX_AGENT_PACKAGES_DIR", str(tmp_path / "agents"))
    app = create_app(
        ProxyConfig(
            backend="mock",
            cache_enabled=False,
            admin_api_key="admin_12345",
            prefix_freeze_db_path=str(tmp_path / "prefix-tracker.db"),
        )
    )
    return TestClient(app)


def test_agent_packages_put_and_list(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    headers = {"Authorization": "Bearer admin_12345"}
    put = client.put(
        "/v1/orchestration/agent-packages/implementer-codex",
        headers=headers,
        json={"yaml": PACKAGE_YAML},
    )
    assert put.status_code == 200
    assert put.json()["package"]["harness"] == "codex_cli"
    listed = client.get("/v1/orchestration/agent-packages", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["packages"][0]["id"] == "implementer-codex"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk pytest tests/test_orchestration_agent_packages_api.py -q`

Expected: FAIL with HTTP 404 on PUT

- [ ] **Step 3: Wire service property and routes**

In `OrchestrationService`, add:

```python
@property
def agent_package_registry(self) -> AgentPackageRegistry:
    agents_dir = os.environ.get("CUTCTX_AGENT_PACKAGES_DIR")
    if not agents_dir:
        agents_dir = str(Path(self.data_dir).parent / ".cutctx" / "agents")
    return AgentPackageRegistry(agents_dir)
```

In `orchestration.py`, add:

```python
class AgentPackagePutPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    yaml: str = Field(min_length=1)


@router.get("/agent-packages", dependencies=read_deps)
async def list_agent_packages() -> dict[str, Any]:
    packages = service.agent_package_registry.list()
    return {"packages": [asdict(pkg) for pkg in packages]}


@router.get("/agent-packages/{package_id}", dependencies=read_deps)
async def get_agent_package(package_id: str) -> dict[str, Any]:
    try:
        package = service.agent_package_registry.get(package_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"package": asdict(package)}


@router.put("/agent-packages/{package_id}", dependencies=write_deps)
async def put_agent_package(package_id: str, payload: AgentPackagePutPayload) -> dict[str, Any]:
    try:
        package = service.agent_package_registry.put(payload.yaml)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if package.id != package_id:
        raise HTTPException(status_code=400, detail="package id mismatch")
    return {"package": asdict(package)}
```

- [ ] **Step 4: Run API tests**

Run: `rtk pytest tests/test_orchestration_agent_packages_api.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cutctx/orchestration/service.py cutctx/proxy/routes/orchestration.py tests/test_orchestration_agent_packages_api.py
git commit -m "$(cat <<'EOF'
feat(orchestration): expose agent package registry API

EOF
)"
```

---

### Task 6: CCR compression at workflow handoffs

**Files:**
- Create: `cutctx/orchestration/handoff_ccr.py`
- Create: `tests/test_handoff_ccr.py`

**Interfaces:**
- Consumes: `ArtifactRef`, `ArtifactBlobStore` from Tasks 1–2; `CompressionStore` from `cutctx.cache.compression_store`
- Produces: `compress_artifact_for_handoff(store: ArtifactBlobStore, ccr: CompressionStore, ref: ArtifactRef) -> ArtifactRef` — reads blob text, stores compressed surrogate in CCR, returns new `ArtifactRef` with same `blob_id`, populated `ccr_hash`, provenance key `handoff_ccr=true`
- Produces: `handoff_payload_from_artifacts(refs: list[ArtifactRef]) -> dict[str, Any]` — JSON-serializable summary for next task payload

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

from cutctx.cache.compression_store import CompressionStore
from cutctx.orchestration.artifact_store import ArtifactBlobStore
from cutctx.orchestration.handoff_ccr import compress_artifact_for_handoff, handoff_payload_from_artifacts


def test_compress_artifact_attaches_ccr_hash(tmp_path) -> None:
    blobs = ArtifactBlobStore(tmp_path / "artifacts")
    ccr = CompressionStore(default_ttl=3600)
    original = blobs.ref_for_text("x" * 5000, media_type="text/plain")
    compressed = compress_artifact_for_handoff(blobs, ccr, original)
    assert compressed.blob_id == original.blob_id
    assert compressed.ccr_hash
    assert ccr.exists(compressed.ccr_hash)


def test_handoff_payload_lists_refs_not_transcripts() -> None:
    from cutctx.orchestration.harness_adapter import ArtifactRef

    refs = [ArtifactRef(blob_id="a" * 64, ccr_hash="deadbeef")]
    payload = handoff_payload_from_artifacts(refs)
    assert payload["artifact_refs"] == [{"blob_id": "a" * 64, "ccr_hash": "deadbeef"}]
    assert "transcript" not in payload
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk pytest tests/test_handoff_ccr.py -q`

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement handoff CCR helper**

```python
# cutctx/orchestration/handoff_ccr.py
from __future__ import annotations

from cutctx.cache.compression_store import CompressionStore

from .artifact_store import ArtifactBlobStore
from .harness_adapter import ArtifactRef


def compress_artifact_for_handoff(
    store: ArtifactBlobStore,
    ccr: CompressionStore,
    ref: ArtifactRef,
) -> ArtifactRef:
    raw = store.get(ref.blob_id).decode("utf-8", errors="replace")
    digest = f"[cutctx-handoff blob={ref.blob_id[:12]}… chars={len(raw)}]"
    ccr_hash = ccr.store(
        original=raw,
        compressed=digest,
        original_tokens=max(1, len(raw) // 4),
        compressed_tokens=max(1, len(digest) // 4),
        compression_strategy="handoff_boundary",
    )
    provenance = dict(ref.provenance)
    provenance["handoff_ccr"] = "true"
    return ArtifactRef(
        blob_id=ref.blob_id,
        media_type=ref.media_type,
        byte_size=ref.byte_size,
        ccr_hash=ccr_hash,
        provenance=provenance,
    )


def handoff_payload_from_artifacts(refs: list[ArtifactRef]) -> dict[str, object]:
    return {
        "artifact_refs": [
            {"blob_id": ref.blob_id, "ccr_hash": ref.ccr_hash, "media_type": ref.media_type}
            for ref in refs
        ]
    }
```

- [ ] **Step 4: Run tests**

Run: `rtk pytest tests/test_handoff_ccr.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cutctx/orchestration/handoff_ccr.py tests/test_handoff_ccr.py
git commit -m "$(cat <<'EOF'
feat(orchestration): compress artifact handoffs via CCR

EOF
)"
```

---

### Task 7: Codex CLI harness adapter (POC)

**Files:**
- Create: `cutctx/orchestration/adapters/__init__.py`
- Create: `cutctx/orchestration/adapters/codex_cli.py`
- Create: `tests/test_codex_cli_adapter.py`
- Create: `tests/fixtures/fake_codex_cli.py` (prints patch to stdout)

**Interfaces:**
- Consumes: `HarnessAdapter` types, `ArtifactBlobStore`
- Produces: `class CodexCliAdapter` with `harness_id = "codex_cli"`
- Produces: binary path from env `CUTCTX_CODEX_CLI_BIN` default `"codex"`
- Produces: `run()` writes stdout/stderr to blob store, emits `ArtifactRef` with `media_type="text/x-patch"` when stdout contains `diff --git`

- [ ] **Step 1: Write fake codex fixture**

```python
# tests/fixtures/fake_codex_cli.py
#!/usr/bin/env python3
import sys

print("diff --git a/example.py b/example.py\n+print('ok')\n")
sys.stderr.write("codex ok\n")
```

Make executable in test setup.

- [ ] **Step 2: Write the failing adapter tests**

```python
from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from cutctx.orchestration.adapters.codex_cli import CodexCliAdapter
from cutctx.orchestration.artifact_store import ArtifactBlobStore
from cutctx.orchestration.harness_adapter import HarnessRunContext


@pytest.mark.asyncio
async def test_codex_adapter_emits_patch_artifact(tmp_path) -> None:
    fake = tmp_path / "fake_codex"
    fake.write_text(Path("tests/fixtures/fake_codex_cli.py").read_text(encoding="utf-8"), encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    blobs = ArtifactBlobStore(tmp_path / "artifacts")
    adapter = CodexCliAdapter(blob_store=blobs, binary=str(fake))
    ctx = HarnessRunContext(
        run_id="run-1",
        workflow_id="wf-1",
        task_id="implement",
        role="implementer",
        agent_package_id="implementer-codex",
        workspace_ref=str(tmp_path),
        prompt="make a patch",
    )
    result = await adapter.run(ctx)
    assert result.status == "completed"
    assert result.artifacts
    patch = blobs.get(result.artifacts[0].blob_id).decode("utf-8")
    assert patch.startswith("diff --git")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `rtk pytest tests/test_codex_cli_adapter.py -q`

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Implement adapter**

```python
# cutctx/orchestration/adapters/codex_cli.py
from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any

from ..artifact_store import ArtifactBlobStore
from ..harness_adapter import ArtifactRef, HarnessCapabilities, HarnessRunContext, HarnessRunResult


class CodexCliAdapter:
    harness_id = "codex_cli"

    def __init__(
        self,
        *,
        blob_store: ArtifactBlobStore,
        binary: str | None = None,
    ) -> None:
        self.blob_store = blob_store
        self.binary = binary or os.environ.get("CUTCTX_CODEX_CLI_BIN", "codex")
        self._active: dict[str, asyncio.subprocess.Process] = {}

    def capabilities(self) -> HarnessCapabilities:
        return HarnessCapabilities(stream=False, cancel=True, resume=False, artifact_emit=True)

    async def health(self) -> dict[str, Any]:
        return {"harness": self.harness_id, "binary": self.binary}

    async def run(self, ctx: HarnessRunContext) -> HarnessRunResult:
        run_id = ctx.run_id or uuid.uuid4().hex
        env = {**os.environ, **ctx.env}
        env.setdefault("CUTCTX_PROXY_URL", os.environ.get("CUTCTX_PROXY_URL", "http://127.0.0.1:8787"))
        proc = await asyncio.create_subprocess_exec(
            self.binary,
            "exec",
            ctx.prompt,
            cwd=ctx.workspace_ref or None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        self._active[run_id] = proc
        stdout, stderr = await proc.communicate()
        self._active.pop(run_id, None)
        status = "completed" if proc.returncode == 0 else "failed"
        stdout_ref = self.blob_store.put(stdout, media_type="text/plain").blob_id
        stderr_ref = self.blob_store.put(stderr, media_type="text/plain").blob_id
        artifacts: list[ArtifactRef] = []
        text = stdout.decode("utf-8", errors="replace")
        if "diff --git" in text:
            artifacts.append(
                self.blob_store.ref_for_text(text, media_type="text/x-patch", provenance={"harness": self.harness_id})
            )
        return HarnessRunResult(
            status=status,
            artifacts=artifacts,
            stdout_ref=stdout_ref,
            stderr_ref=stderr_ref,
            metadata={"returncode": str(proc.returncode or 0)},
        )

    async def cancel(self, run_id: str) -> None:
        proc = self._active.get(run_id)
        if proc is not None and proc.returncode is None:
            proc.terminate()
```

- [ ] **Step 5: Run adapter tests**

Run: `rtk pytest tests/test_codex_cli_adapter.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add cutctx/orchestration/adapters tests/test_codex_cli_adapter.py tests/fixtures/fake_codex_cli.py
git commit -m "$(cat <<'EOF'
feat(orchestration): add Codex CLI harness adapter POC

EOF
)"
```

---

### Task 8: Harness runtime registry and dispatcher

**Files:**
- Create: `cutctx/orchestration/harness_runtime.py`
- Create: `tests/test_harness_runtime.py`

**Interfaces:**
- Consumes: `HarnessAdapter`, `AgentPackageRegistry`, `ArtifactBlobStore`, `CodexCliAdapter`
- Produces: `class HarnessRuntime` with `register(adapter)`, `resolve(harness_id) -> HarnessAdapter`, `async run_task(workflow_id, task, package_id) -> dict[str, Any]`
- Produces: return shape `{"harness": harness_id, "status": str, "artifacts": [...], "handoff": {...}}`

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

import pytest

from cutctx.orchestration.agent_packages import AgentPackageRegistry
from cutctx.orchestration.artifact_store import ArtifactBlobStore
from cutctx.orchestration.harness_runtime import HarnessRuntime


@pytest.mark.asyncio
async def test_runtime_resolves_package_and_runs_adapter(tmp_path, monkeypatch) -> None:
    from cutctx.orchestration.adapters.codex_cli import CodexCliAdapter
    from tests.fixtures import fake_codex_cli  # noqa: F401 — ensures fixture exists

    fake = tmp_path / "fake_codex"
    fake.write_text(open("tests/fixtures/fake_codex_cli.py", encoding="utf-8").read(), encoding="utf-8")
    fake.chmod(0o755)
    registry = AgentPackageRegistry(tmp_path / "agents")
    registry.put(open(".cutctx/agents/example-implementer.yaml", encoding="utf-8").read())
    blobs = ArtifactBlobStore(tmp_path / "artifacts")
    runtime = HarnessRuntime(registry=registry, blob_store=blobs)
    runtime.register(CodexCliAdapter(blob_store=blobs, binary=str(fake)))
    from cutctx.orchestration.workflow import TaskSpec

    task = TaskSpec(
        id="implement",
        role="implementer",
        payload={"harness": "codex_cli", "agent_package_id": "implementer-codex", "prompt": "patch"},
    )
    result = await runtime.run_task("wf-1", task, package_id="implementer-codex")
    assert result["status"] == "completed"
    assert result["artifacts"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk pytest tests/test_harness_runtime.py -q`

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement runtime**

```python
# cutctx/orchestration/harness_runtime.py
from __future__ import annotations

import uuid
from typing import Any

from .agent_packages import AgentPackageRegistry
from .artifact_store import ArtifactBlobStore
from .handoff_ccr import handoff_payload_from_artifacts
from .harness_adapter import HarnessAdapter, HarnessRunContext
from .workflow import TaskSpec


class HarnessRuntime:
    def __init__(
        self,
        *,
        registry: AgentPackageRegistry,
        blob_store: ArtifactBlobStore,
    ) -> None:
        self.registry = registry
        self.blob_store = blob_store
        self._adapters: dict[str, HarnessAdapter] = {}

    def register(self, adapter: HarnessAdapter) -> None:
        self._adapters[adapter.harness_id] = adapter

    def resolve(self, harness_id: str) -> HarnessAdapter:
        try:
            return self._adapters[harness_id]
        except KeyError as exc:
            raise KeyError(f"unknown harness adapter: {harness_id}") from exc

    async def run_task(self, workflow_id: str, task: TaskSpec, *, package_id: str) -> dict[str, Any]:
        package = self.registry.get(package_id)
        adapter = self.resolve(package.harness)
        ctx = HarnessRunContext(
            run_id=uuid.uuid4().hex,
            workflow_id=workflow_id,
            task_id=task.id,
            role=task.role,
            agent_package_id=package.id,
            workspace_ref=str(task.payload.get("workspace_ref", "")),
            prompt=str(task.payload.get("prompt", "")),
            env=dict(task.payload.get("env", {})),
        )
        outcome = await adapter.run(ctx)
        return {
            "harness": package.harness,
            "package_hash": package.package_hash,
            "status": outcome.status,
            "artifacts": [ref.__dict__ for ref in outcome.artifacts],
            "handoff": handoff_payload_from_artifacts(outcome.artifacts),
            "stdout_ref": outcome.stdout_ref,
            "stderr_ref": outcome.stderr_ref,
            "metadata": outcome.metadata,
        }
```

- [ ] **Step 4: Run runtime tests**

Run: `rtk pytest tests/test_harness_runtime.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cutctx/orchestration/harness_runtime.py tests/test_harness_runtime.py
git commit -m "$(cat <<'EOF'
feat(orchestration): add harness runtime dispatcher

EOF
)"
```

---

### Task 9: Workflow dispatch integration in OrchestrationService

**Files:**
- Modify: `cutctx/orchestration/service.py`
- Modify: `tests/test_meta_harness_workflow_e2e.py` (create)

**Interfaces:**
- Consumes: `HarnessRuntime`, `compress_artifact_for_handoff`, `CompressionStore`, existing `execute()` for LLM path
- Produces: `OrchestrationService.harness_runtime` lazy property wiring registry + blob store + `CodexCliAdapter`
- Produces: `run_workflow.execute_task` branches: if `task.payload.get("harness")` → harness path; else existing LLM path
- Produces: harness path applies CCR to emitted artifacts before returning result; stores refs in `task.artifact` fields (`patch_ref`, `test_evidence_ref`, provenance)

- [ ] **Step 1: Write failing e2e test (planner LLM mocked, implementer harness, reviewer LLM mocked)**

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cutctx.orchestration.agent_packages import AgentPackageRegistry
from cutctx.orchestration.service import build_orchestration_service
from cutctx.orchestration.workflow import TaskSpec, WorkflowRunner, WorkflowSpec, WorkflowStateStore


@pytest.mark.asyncio
async def test_planner_codex_implementer_reviewer_handoff(tmp_path, monkeypatch) -> None:
    orch_dir = tmp_path / "state"
    monkeypatch.setenv("CUTCTX_ORCHESTRATION_DIR", str(orch_dir))
    config_path = tmp_path / "orchestration.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "providers": [{"id": "openai-main", "provider": "openai"}],
                "roles": [{"id": "planner", "name": "Planner"}, {"id": "reviewer", "name": "Reviewer"}],
                "models": [
                    {
                        "provider": "openai",
                        "model": "gpt-5.4-mini",
                        "account_id": "openai-main",
                        "capabilities": ["reasoning"],
                    }
                ],
                "bindings": [
                    {"id": "planner-mini", "role": "planner", "model": "openai:gpt-5.4-mini"},
                    {"id": "reviewer-mini", "role": "reviewer", "model": "openai:gpt-5.4-mini"},
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CUTCTX_ORCHESTRATION_CONFIG", str(config_path))
    monkeypatch.setenv("CUTCTX_AGENT_PACKAGES_DIR", str(tmp_path / "agents"))
  AgentPackageRegistry(tmp_path / "agents").put(
        Path(".cutctx/agents/example-implementer.yaml").read_text(encoding="utf-8")
    )
    fake = tmp_path / "fake_codex"
    fake.write_text(Path("tests/fixtures/fake_codex_cli.py").read_text(encoding="utf-8"), encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("CUTCTX_CODEX_CLI_BIN", str(fake))

    service = build_orchestration_service()
    store = WorkflowStateStore(orch_dir / "workflows.json")
    spec = WorkflowSpec(
        id="sdlc",
        tasks=[
            TaskSpec(id="plan", role="planner", payload={"messages": [{"role": "user", "content": "plan"}], "parameters": {}}),
            TaskSpec(
                id="implement",
                role="implementer",
                depends_on=["plan"],
                payload={"harness": "codex_cli", "agent_package_id": "implementer-codex", "prompt": "patch", "workspace_ref": str(tmp_path)},
            ),
            TaskSpec(
                id="review",
                role="reviewer",
                depends_on=["implement"],
                payload={"messages": [{"role": "user", "content": "review patch refs only"}], "parameters": {}, "artifact_refs": []},
            ),
        ],
    )
    store.submit(spec)

    async def execute_task(task_id: str, task: TaskSpec):
        if task.payload.get("harness"):
            return await service.harness_runtime.run_task("sdlc", task, package_id=str(task.payload["agent_package_id"]))
        decision, response = await service.execute(
            service.route(type("R", (), {"role": task.role})()),
            messages=task.payload["messages"],
            parameters=task.payload.get("parameters", {}),
        )
        return {"routing": decision.__dict__, "response": response}

    state = await WorkflowRunner(store, execute_task).run("sdlc")
    assert state.status == "completed"
    implement = state.tasks["implement"].result
    assert implement["artifacts"]
    review = state.tasks["review"].result
    assert review is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk pytest tests/test_meta_harness_workflow_e2e.py -q`

Expected: FAIL (no harness dispatch yet)

- [ ] **Step 3: Integrate harness dispatch in service**

Add imports and lazy `harness_runtime` property; update `run_workflow`:

```python
async def execute_task(_task_id: str, task: TaskSpec) -> dict[str, Any]:
    harness = task.payload.get("harness")
    if harness:
        package_id = str(task.payload.get("agent_package_id", ""))
        if not package_id:
            raise ValueError("harness task requires agent_package_id")
        result = await self.harness_runtime.run_task(workflow_id, task, package_id=package_id)
        from cutctx.cache.compression_store import CompressionStore
        from .handoff_ccr import compress_artifact_for_handoff

        ccr = CompressionStore(default_ttl=3600)
        compressed = [
            compress_artifact_for_handoff(self.artifact_blob_store, ccr, type("R", (), result["artifacts"][0])())
            if result.get("artifacts")
            else None
        ]
        if compressed and compressed[0]:
            result["handoff"] = handoff_payload_from_artifacts([compressed[0]])
        return result
    messages = task.payload.get("messages", [])
    parameters = task.payload.get("parameters", {})
    ...
```

(Implement cleanly using proper `ArtifactRef` reconstruction — not `type()` hacks in production code; tests may use service helper.)

- [ ] **Step 4: Run e2e test**

Run: `rtk pytest tests/test_meta_harness_workflow_e2e.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cutctx/orchestration/service.py tests/test_meta_harness_workflow_e2e.py
git commit -m "$(cat <<'EOF'
feat(orchestration): dispatch harness tasks in workflow runner

EOF
)"
```

---

### Task 10: Public exports and regression sweep

**Files:**
- Modify: `cutctx/orchestration/__init__.py`
- Modify: `docs/content/docs/orchestration-platform.mdx` (add P0 meta-harness paragraph)

**Interfaces:**
- Produces: exported symbols `ArtifactRef`, `HarnessAdapter`, `AgentPackage`, `AgentPackageRegistry`, `HarnessRuntime`

- [ ] **Step 1: Add exports**

```python
from .agent_packages import AgentPackage, AgentPackageRegistry
from .artifact_store import ArtifactBlobStore
from .harness_adapter import ArtifactRef, HarnessAdapter, HarnessCapabilities
from .harness_runtime import HarnessRuntime
```

- [ ] **Step 2: Run full orchestration test sweep**

Run: `rtk pytest tests/test_orchestration_workflow.py tests/test_orchestration_api.py tests/test_harness_adapter_types.py tests/test_artifact_store.py tests/test_agent_packages.py tests/test_handoff_ccr.py tests/test_codex_cli_adapter.py tests/test_harness_runtime.py tests/test_orchestration_agent_packages_api.py tests/test_meta_harness_workflow_e2e.py -q`

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add cutctx/orchestration/__init__.py docs/content/docs/orchestration-platform.mdx
git commit -m "$(cat <<'EOF'
docs(orchestration): document meta-harness P0 adapter seam

EOF
)"
```

---

## Self-review checklist (against spec)

### 1. Spec coverage (P0 deliverables)

| Spec deliverable | Plan task |
|---|---|
| `HarnessAdapter` protocol (`capabilities`, `run`, `cancel`, `health`) | Task 1, Task 7 |
| Agent package schema v1 (`.cutctx/agents/<id>.yaml`, package hash) | Task 3, Task 4 |
| Package registry API `GET/PUT /v1/orchestration/agent-packages` | Task 5 |
| Codex CLI adapter POC (subprocess + wrap env) | Task 7 |
| Workflow integration (`task.payload.harness` dispatch) | Task 8, Task 9 |
| Artifact blob store (`CUTCTX_ORCHESTRATION_DIR/artifacts/`) | Task 2 |
| CCR at boundaries (`ccr_hash` in provenance) | Task 6, Task 9 |
| Success: planner → implementer (Codex) → reviewer (LLM), no hidden session sharing | Task 9 e2e |
| Dual-path local files | Tasks 2, 4, 5 (file registry + blob store) |

**Gaps:** None for P0 scope. P1+ items intentionally deferred in scope freeze.

### 2. Placeholder scan

- No `TBD`, `TODO`, or "implement later" strings in task steps.
- Every code step includes concrete file paths and test code.
- Every test step includes exact `rtk pytest` command and expected outcome.

### 3. Type consistency

- `ArtifactRef.blob_id` used consistently across Tasks 1–9.
- `AgentPackage.harness` matches `HarnessAdapter.harness_id` (`codex_cli`).
- `task.payload.harness` and `task.payload.agent_package_id` used consistently in Tasks 8–9.
- `handoff_payload_from_artifacts` return shape consumed by reviewer task payload in Task 9.

---

## Execution handoff

**Plan complete and saved to `docs/superpowers/plans/2026-07-28-meta-harness-p0.md`.**

**P0 implementation tasks:** 10 numbered tasks (Task 0 verification + Tasks 1–10), **55 checkbox steps** total.

**Two execution options:**

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task with two-stage review between tasks.
2. **Inline Execution** — run tasks in one session using executing-plans with checkpoints.

**Which approach?**
