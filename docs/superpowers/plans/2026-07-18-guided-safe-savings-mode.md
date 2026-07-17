# Guided Safe Savings Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a feature-flagged, read-only Safe Savings status API, CLI summary, and dashboard panel with an explicit rollback-to-Off action, without changing model-routing behavior.

**Architecture:** A new pure Python presentation module normalizes live router configuration and an optional persisted routing trace into one stable JSON-safe status object. The orchestration router exposes that object through an authenticated read-only endpoint supplied by the proxy assembly; the CLI and dashboard consume the same response. The only mutation is the existing authenticated `orchestrator_mode: "off"` configuration path.

**Tech Stack:** Python 3.10+, FastAPI, Click, httpx, pytest, React, Vite, Playwright.

## Global Constraints

- No new complexity heuristics or scorer behavior.
- No provider-family wildcards, automatic cross-provider selection, or new fallback behavior.
- Do not relax capability, account, credential, transport, or subscription safety checks.
- Status reads perform zero provider calls and zero state writes.
- Do not expose API keys, credential references, prompt/response text, or raw workspace identity.
- `CUTCTX_SAFE_SAVINGS_EXPERIENCE` controls discoverability only; it never enables routing.
- Missing and legacy data must produce a valid partial representation rather than invented evidence.
- All production changes follow a witnessed RED → GREEN → REFACTOR cycle.

## File map

- Create `cutctx/proxy/safe_savings_status.py`: pure status/explanation builder and environment feature-flag parser.
- Create `tests/test_safe_savings_status.py`: exhaustive unit behavior and mutation-safety tests.
- Modify `cutctx/proxy/routes/orchestration.py`: authenticated `GET /v1/orchestration/safe-savings/status`.
- Modify `cutctx/proxy/server.py`: supply live router, preset, and latest persisted routing metadata to the endpoint.
- Modify `tests/test_orchestration_platform.py`: endpoint authentication, no-call, enabled/Off, and legacy-data tests.
- Create `cutctx/cli/routing.py`: `cutctx routing status` command and terminal formatter.
- Create `tests/test_cli/test_routing_status.py`: Click and HTTP behavior.
- Modify `cutctx/cli/main.py`: lazy command registration and help grouping.
- Create `dashboard/src/components/SafeSavingsPanel.jsx`: read-only status panel and confirmed Off action.
- Modify `dashboard/src/pages/Orchestrator.jsx`: fetch/render the feature-flagged panel and reuse the existing mode mutation.
- Modify `dashboard/src/index.css`: focused Safe Savings layout styles.
- Modify `tests/test_dashboard_orchestrator_policy_e2e.py`: applied, blocked, Off, and mutation-failure flows.
- Modify `docs/content/docs/model-routing-presets.mdx`: operator documentation for status API, CLI, flag, and rollback behavior.

---

### Task 1: Pure Safe Savings status and explanation model

**Files:**
- Create: `cutctx/proxy/safe_savings_status.py`
- Create: `tests/test_safe_savings_status.py`
- Reference: `cutctx/proxy/model_router.py`
- Reference: `cutctx/proxy/decision_receipt.py`

**Interfaces:**
- Consumes: `ModelRouter | None`, `preset: str | None`, and `recent_requests: Sequence[Mapping[str, Any]]`.
- Produces:
  - `safe_savings_experience_enabled(env: Mapping[str, str] | None = None) -> bool`
  - `build_safe_savings_status(*, router: Any | None, preset: str | None, recent_requests: Sequence[Mapping[str, Any]] = (), experience_enabled: bool | None = None) -> dict[str, Any]`
  - `explain_safe_savings_reason(reason: str | None, *, selection_evidence: Mapping[str, Any] | None = None) -> dict[str, str]`

- [ ] **Step 1: Write failing feature-flag and Off-state tests**

```python
from cutctx.proxy.safe_savings_status import (
    build_safe_savings_status,
    safe_savings_experience_enabled,
)


def test_safe_savings_experience_flag_is_explicit_opt_in() -> None:
    assert safe_savings_experience_enabled({}) is False
    assert safe_savings_experience_enabled({"CUTCTX_SAFE_SAVINGS_EXPERIENCE": "true"}) is True
    assert safe_savings_experience_enabled({"CUTCTX_SAFE_SAVINGS_EXPERIENCE": "0"}) is False


def test_safe_savings_status_without_router_is_off_and_read_only() -> None:
    status = build_safe_savings_status(
        router=None,
        preset=None,
        recent_requests=[],
        experience_enabled=True,
    )
    assert status == {
        "schema_version": 1,
        "experience_enabled": True,
        "enabled": False,
        "mode": "off",
        "preset": None,
        "route_count": 0,
        "routes": [],
        "transport_safe_targets": [],
        "decision": None,
        "rollback_available": False,
    }
```

- [ ] **Step 2: Run tests and verify RED**

Run: `rtk pytest tests/test_safe_savings_status.py -q`

Expected: FAIL during import because `cutctx.proxy.safe_savings_status` does not exist.

- [ ] **Step 3: Implement the flag parser and Off representation**

```python
"""Privacy-safe presentation model for conservative model routing."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import Any

from cutctx.proxy.model_router import model_routing_mode_for_state

SAFE_SAVINGS_STATUS_SCHEMA_VERSION = 1
_TRUE_VALUES = {"1", "true", "yes", "on"}


def safe_savings_experience_enabled(
    env: Mapping[str, str] | None = None,
) -> bool:
    values = os.environ if env is None else env
    return str(values.get("CUTCTX_SAFE_SAVINGS_EXPERIENCE", "")).strip().lower() in _TRUE_VALUES


def build_safe_savings_status(
    *,
    router: Any | None,
    preset: str | None,
    recent_requests: Sequence[Mapping[str, Any]] = (),
    experience_enabled: bool | None = None,
) -> dict[str, Any]:
    config = getattr(router, "config", None)
    routes = list(getattr(config, "routes", []) or [])
    enabled = bool(getattr(config, "enabled", False))
    return {
        "schema_version": SAFE_SAVINGS_STATUS_SCHEMA_VERSION,
        "experience_enabled": (
            safe_savings_experience_enabled()
            if experience_enabled is None
            else bool(experience_enabled)
        ),
        "enabled": enabled,
        "mode": model_routing_mode_for_state(
            enabled=enabled,
            preset=preset,
            route_count=len(routes),
        ),
        "preset": preset,
        "route_count": len(routes),
        "routes": [],
        "transport_safe_targets": sorted(
            str(item) for item in (getattr(config, "transport_safe_targets", set()) or set())
        ),
        "decision": None,
        "rollback_available": enabled,
    }
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `rtk pytest tests/test_safe_savings_status.py -q`

Expected: `2 passed`.

- [ ] **Step 5: Write failing exact-route and applied-decision tests**

```python
from cutctx.proxy.model_router import ModelRouter, ModelRouterConfig


def test_safe_savings_status_lists_exact_routes_and_applied_decision() -> None:
    router = ModelRouter(ModelRouterConfig.codex_gpt54mini_high_preset())
    recent = [{
        "request_id": "req-1",
        "routing_metadata": {
            "requested_model": "gpt-5.6-sol",
            "actual_model": "gpt-5.4-mini",
            "reason": "downgrade_applied",
            "routed": True,
            "confidence": 0.9,
            "signals": ["explicit_low_complexity"],
        },
    }]
    before_routes = list(router.config.routes)

    status = build_safe_savings_status(
        router=router,
        preset="codex-gpt54mini-high",
        recent_requests=recent,
        experience_enabled=True,
    )

    assert status["routes"][0].keys() >= {
        "source_model",
        "low_target_model",
        "medium_target_model",
        "low_target_capabilities",
        "medium_target_capabilities",
        "low_target_transport_safe",
        "medium_target_transport_safe",
    }
    assert status["decision"] == {
        "request_id": "req-1",
        "requested_model": "gpt-5.6-sol",
        "effective_model": "gpt-5.4-mini",
        "candidate_model": "gpt-5.4-mini",
        "applied": True,
        "reason": "downgrade_applied",
        "title": "Safe route applied",
        "explanation": (
            "The request passed the configured safety and compatibility gates "
            "for the selected lower-cost model."
        ),
        "scorer": None,
        "confidence": 0.9,
        "signals": ["explicit_low_complexity"],
        "required_capabilities": [],
        "missing_capabilities": [],
        "transport": {},
    }
    assert list(router.config.routes) == before_routes
```

- [ ] **Step 6: Run the new test and verify RED**

Run: `rtk pytest tests/test_safe_savings_status.py::test_safe_savings_status_lists_exact_routes_and_applied_decision -q`

Expected: FAIL because `routes` and `decision` remain empty.

- [ ] **Step 7: Implement exact route serialization and decision normalization**

Add these helpers to `cutctx/proxy/safe_savings_status.py` and call them from
`build_safe_savings_status`:

```python
from cutctx.proxy.decision_receipt import explain_routing_reason

_REASON_TITLES = {
    "account_transport_mismatch": "Account proof blocked routing",
    "calibrated_scorer_required": "Calibration required",
    "confidence_below_threshold": "Confidence protected the request",
    "cost_lookup_failed": "Cost proof unavailable",
    "downgrade_applied": "Safe route applied",
    "downgrade_blocked_unproven_transport": "Transport proof blocked routing",
    "no_route_for_model": "No exact route configured",
    "router_disabled": "Routing is off",
    "router_error": "Routing retained the requested model",
    "target_missing_capabilities": "Capability proof blocked routing",
    "transport_mismatch": "Provider transport blocked routing",
    "workload_not_downgradeable": "Workload retained on requested model",
}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(item) for item in value if item is not None]


def explain_safe_savings_reason(
    reason: str | None,
    *,
    selection_evidence: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    return {
        "title": _REASON_TITLES.get(reason or "", "Routing decision recorded"),
        "explanation": explain_routing_reason(reason, selection_evidence),
    }


def _route_status(route: Any, safe_targets: set[str]) -> dict[str, Any]:
    low = str(route.target)
    medium = str(route.medium_target) if route.medium_target else None
    return {
        "source_model": str(route.source),
        "low_target_model": low,
        "medium_target_model": medium,
        "low_target_capabilities": sorted(str(item) for item in route.target_capabilities),
        "medium_target_capabilities": sorted(
            str(item) for item in route.medium_target_capabilities
        ),
        "low_target_transport_safe": low in safe_targets,
        "medium_target_transport_safe": bool(medium and medium in safe_targets),
    }


def _latest_decision(
    recent_requests: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    for row in reversed(recent_requests):
        summary = row.get("routing_metadata")
        if not isinstance(summary, Mapping) or not summary:
            continue
        reason = str(summary.get("reason") or "") or None
        applied = bool(summary.get("routed", False))
        requested = summary.get("requested_model")
        effective = summary.get("actual_model") or row.get("model") or requested
        explanation = explain_safe_savings_reason(reason)
        return {
            "request_id": str(row.get("request_id") or ""),
            "requested_model": requested,
            "effective_model": effective,
            "candidate_model": summary.get("target_model") or effective,
            "applied": applied,
            "reason": reason,
            **explanation,
            "scorer": summary.get("scorer"),
            "confidence": summary.get("confidence"),
            "signals": _string_list(summary.get("signals")),
            "required_capabilities": _string_list(summary.get("required_capabilities")),
            "missing_capabilities": _string_list(summary.get("missing_capabilities")),
            "transport": (
                dict(summary.get("transport"))
                if isinstance(summary.get("transport"), Mapping)
                else {}
            ),
        }
    return None
```

In `build_safe_savings_status`, compute `safe_targets` once, serialize every
configured route with `_route_status`, and set `decision` with
`_latest_decision(recent_requests)`.

- [ ] **Step 8: Add exhaustive blocked/unknown/legacy reason tests**

Parametrize over all current terminal reasons:

```python
import pytest


@pytest.mark.parametrize("reason", [
    "account_transport_mismatch",
    "calibrated_scorer_required",
    "confidence_below_threshold",
    "cost_lookup_failed",
    "downgrade_applied",
    "downgrade_blocked_unproven_transport",
    "no_route_for_model",
    "router_disabled",
    "router_error",
    "target_missing_capabilities",
    "transport_mismatch",
    "workload_not_downgradeable",
])
def test_every_terminal_reason_has_stable_operator_copy(reason: str) -> None:
    explanation = explain_safe_savings_reason(reason)
    assert explanation["title"]
    assert explanation["explanation"]
    assert reason not in explanation["explanation"]


def test_unknown_reason_and_partial_legacy_metadata_are_safe() -> None:
    status = build_safe_savings_status(
        router=None,
        preset=None,
        recent_requests=[{
            "request_id": "legacy",
            "model": "requested-model",
            "routing_metadata": {"reason": "future_reason"},
        }],
        experience_enabled=True,
    )
    assert status["decision"]["reason"] == "future_reason"
    assert status["decision"]["title"] == "Routing decision recorded"
    assert status["decision"]["effective_model"] == "requested-model"
    assert status["decision"]["confidence"] is None
```

- [ ] **Step 9: Verify Task 1 GREEN**

Run: `rtk pytest tests/test_safe_savings_status.py -q`

Expected: all tests pass with no warnings.

- [ ] **Step 10: Commit Task 1**

```bash
rtk git add cutctx/proxy/safe_savings_status.py tests/test_safe_savings_status.py
rtk git commit -m "feat add safe savings status model"
```

---

### Task 2: Authenticated status API wired to live proxy state

**Files:**
- Modify: `cutctx/proxy/routes/orchestration.py`
- Modify: `cutctx/proxy/server.py`
- Modify: `tests/test_orchestration_platform.py`
- Modify: `tests/test_dashboard_orchestrator.py`

**Interfaces:**
- Consumes: Task 1 `build_safe_savings_status`.
- Produces:
  - optional `safe_savings_status_provider: Callable[[], dict[str, Any]]` argument on `create_orchestration_router`
  - `GET /v1/orchestration/safe-savings/status`

- [ ] **Step 1: Write failing router authentication and response tests**

Add a focused test using a local FastAPI app and dependency counters:

```python
def test_safe_savings_status_endpoint_is_authenticated_and_read_only(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    calls = {"provider": 0}

    def status_provider() -> dict[str, Any]:
        calls["provider"] += 1
        return {
            "schema_version": 1,
            "experience_enabled": True,
            "enabled": False,
            "mode": "off",
            "preset": None,
            "route_count": 0,
            "routes": [],
            "transport_safe_targets": [],
            "decision": None,
            "rollback_available": False,
        }

    app = FastAPI()
    app.include_router(
        create_orchestration_router(
            service,
            require_admin_auth=lambda: None,
            safe_savings_status_provider=status_provider,
        )
    )
    client = TestClient(app)

    response = client.get("/v1/orchestration/safe-savings/status")

    assert response.status_code == 200
    assert response.json()["mode"] == "off"
    assert calls == {"provider": 1}
```

Also assert the route returns `503` when no provider callback is supplied, so
old embeddings fail explicitly rather than inventing state.

- [ ] **Step 2: Run endpoint test and verify RED**

Run: `rtk pytest tests/test_orchestration_platform.py -k safe_savings_status_endpoint -q`

Expected: FAIL because `safe_savings_status_provider` is not a recognized
constructor argument and the route does not exist.

- [ ] **Step 3: Implement the read-only route**

Extend the constructor:

```python
def create_orchestration_router(
    service: OrchestrationService,
    require_admin_auth: Callable[..., Any] | None = None,
    require_rbac_permission: Callable[..., Any] | None = None,
    enable_direct_execution: bool | None = None,
    safe_savings_status_provider: Callable[[], dict[str, Any]] | None = None,
) -> APIRouter:
```

Add after `/config`:

```python
@router.get("/safe-savings/status", dependencies=read_deps)
async def safe_savings_status() -> dict[str, Any]:
    if safe_savings_status_provider is None:
        raise HTTPException(status_code=503, detail="Safe Savings status is unavailable")
    return safe_savings_status_provider()
```

- [ ] **Step 4: Wire the proxy callback and write the failing live-state test**

In `create_app`, define:

```python
def _safe_savings_status() -> dict[str, Any]:
    from cutctx.proxy.safe_savings_status import build_safe_savings_status

    recent_requests = proxy.logger.get_recent(20) if proxy.logger else []
    return build_safe_savings_status(
        router=getattr(proxy, "_model_router", None),
        preset=getattr(proxy.config, "model_routing_preset", None),
        recent_requests=recent_requests,
    )
```

Pass it to `create_orchestration_router`.

Before implementation, add this failing integration assertion to
`tests/test_dashboard_orchestrator.py`:

```python
response = client.get(
    "/v1/orchestration/safe-savings/status",
    headers={"x-cutctx-admin-key": "admin_12345"},
)
assert response.status_code == 200
assert response.json()["preset"] == "codex-gpt54mini-high"
assert response.json()["route_count"] == len(
    ModelRouterConfig.codex_gpt54mini_high_preset().routes
)
```

- [ ] **Step 5: Verify endpoint GREEN and regression safety**

Run:

```bash
rtk pytest tests/test_safe_savings_status.py tests/test_orchestration_platform.py -k "safe_savings or status" -q
rtk pytest tests/test_dashboard_orchestrator.py tests/test_model_router.py tests/test_model_router_presets.py -q
```

Expected: all selected tests pass; no routing expectations change.

- [ ] **Step 6: Commit Task 2**

```bash
rtk git add cutctx/proxy/routes/orchestration.py cutctx/proxy/server.py tests/test_orchestration_platform.py tests/test_dashboard_orchestrator.py
rtk git commit -m "feat expose safe savings status api"
```

---

### Task 3: Read-only `cutctx routing status` CLI

**Files:**
- Create: `cutctx/cli/routing.py`
- Create: `tests/test_cli/test_routing_status.py`
- Modify: `cutctx/cli/main.py`

**Interfaces:**
- Consumes: `GET /v1/orchestration/safe-savings/status`.
- Produces: `cutctx routing status --proxy-url URL --admin-key KEY`.

- [ ] **Step 1: Write failing CLI registration, Off, and enabled tests**

```python
from click.testing import CliRunner
from cutctx.cli.main import main


def test_routing_status_reports_off_without_mutation(monkeypatch) -> None:
    calls = []

    class Response:
        status_code = 200
        def raise_for_status(self) -> None:
            return None
        def json(self):
            return {
                "schema_version": 1,
                "experience_enabled": True,
                "enabled": False,
                "mode": "off",
                "preset": None,
                "route_count": 0,
                "routes": [],
                "transport_safe_targets": [],
                "decision": None,
                "rollback_available": False,
            }

    def get(url, **kwargs):
        calls.append(("GET", url, kwargs))
        return Response()

    monkeypatch.setattr("httpx.get", get)
    result = CliRunner().invoke(
        main,
        ["routing", "status", "--proxy-url", "http://127.0.0.1:8787"],
    )

    assert result.exit_code == 0
    assert "Safe Savings: Off" in result.output
    assert "Requests retain the originally requested model." in result.output
    assert [item[0] for item in calls] == ["GET"]
```

Add an enabled response test asserting exact low/medium route lines, the recent
decision, confidence, and transport-safe marker. Add an error test asserting a
401 becomes `click.ClickException` copy without printing the key.

- [ ] **Step 2: Run CLI tests and verify RED**

Run: `rtk pytest tests/test_cli/test_routing_status.py -q`

Expected: FAIL because the `routing` command is not registered.

- [ ] **Step 3: Implement the command**

Create `cutctx/cli/routing.py`:

```python
from __future__ import annotations

import os

import click
import httpx

from cutctx.cli.main import main
from cutctx.proxy.safe_savings_status import safe_savings_experience_enabled


def _headers(admin_key: str) -> dict[str, str]:
    return {"x-cutctx-admin-key": admin_key} if admin_key else {}


@main.group("routing", hidden=not safe_savings_experience_enabled())
def routing_group() -> None:
    """Inspect conservative model-routing decisions."""


@routing_group.command("status")
@click.option("--proxy-url", envvar="CUTCTX_PROXY_URL", default="http://127.0.0.1:8787")
@click.option("--admin-key", envvar="CUTCTX_ADMIN_API_KEY", default="")
def routing_status(proxy_url: str, admin_key: str) -> None:
    """Show Safe Savings eligibility and the latest routing decision."""
    url = f"{proxy_url.rstrip('/')}/v1/orchestration/safe-savings/status"
    try:
        response = httpx.get(url, headers=_headers(admin_key), timeout=10)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise click.ClickException(f"Unable to read Safe Savings status: {exc}") from exc
    payload = response.json()
    mode = str(payload.get("mode") or "off")
    click.echo(f"Safe Savings: {mode.title()}")
    if mode == "off":
        click.echo("Requests retain the originally requested model.")
        return
    preset = payload.get("preset") or "custom"
    click.echo(f"Preset: {preset}")
    click.echo("Eligible exact routes:")
    for route in payload.get("routes", []):
        low_safe = "transport-safe" if route.get("low_target_transport_safe") else "restricted"
        click.echo(
            f"  {route['source_model']} -> {route['low_target_model']} "
            f"(low, {low_safe})"
        )
        if route.get("medium_target_model"):
            medium_safe = (
                "transport-safe"
                if route.get("medium_target_transport_safe")
                else "restricted"
            )
            click.echo(
                f"  {route['source_model']} -> {route['medium_target_model']} "
                f"(medium, {medium_safe})"
            )
    decision = payload.get("decision")
    if not isinstance(decision, dict):
        click.echo("Recent decision: none observed")
        return
    state = "applied" if decision.get("applied") else "retained"
    click.echo(
        f"Recent decision: {state} "
        f"{decision.get('requested_model')} -> {decision.get('effective_model')}"
    )
    click.echo(f"Reason: {decision.get('title')}")
    click.echo(str(decision.get("explanation") or ""))
    if decision.get("confidence") is not None:
        click.echo(f"Confidence: {float(decision['confidence']):.2f}")
```

Register `"routing": "routing"` in `_SIDE_EFFECT_COMMAND_MODULES` and add
`"routing"` to the “Optimize and Evaluate” help group.

- [ ] **Step 4: Verify CLI GREEN**

Run:

```bash
CUTCTX_SAFE_SAVINGS_EXPERIENCE=true rtk pytest tests/test_cli/test_routing_status.py -q
rtk pytest tests/test_cli/test_main_help_version.py -q
```

Expected: all tests pass; top-level help includes Routing only when the
environment flag is true.

- [ ] **Step 5: Commit Task 3**

```bash
rtk git add cutctx/cli/routing.py cutctx/cli/main.py tests/test_cli/test_routing_status.py
rtk git commit -m "feat add safe savings cli status"
```

---

### Task 4: Dashboard Safe Savings panel and authoritative Off action

**Files:**
- Create: `dashboard/src/components/SafeSavingsPanel.jsx`
- Modify: `dashboard/src/pages/Orchestrator.jsx`
- Modify: `dashboard/src/index.css`
- Modify: `tests/test_dashboard_orchestrator_policy_e2e.py`

**Interfaces:**
- Consumes: Task 2 status endpoint and existing
  `patchDashboardConfig({orchestrator_mode: "off"})`.
- Produces: `SafeSavingsPanel({status, loading, error, disabling, disableError, onDisable})`.

- [ ] **Step 1: Extend the Playwright route fixture and write failing render tests**

In `_install_dashboard_routes`, fulfill
`/v1/orchestration/safe-savings/status` with an enabled payload containing an
applied decision. Add:

```python
def test_safe_savings_panel_renders_exact_routes_and_applied_decision() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1400})
            page.add_init_script(
                "window.localStorage.setItem('cutctxAdminKey', 'testkey');"
            )
            _install_dashboard_routes(page)
            page.goto("http://cutctx.local/dashboard/orchestrator")
            page.wait_for_load_state("networkidle")

            expect(page.get_by_text("Safe Savings", exact=True)).to_be_visible()
            expect(page.get_by_text("gpt-5.6-sol → gpt-5.4-mini", exact=True)).to_be_visible()
            expect(page.get_by_text("Safe route applied", exact=True)).to_be_visible()
            expect(page.get_by_text("Confidence 0.90", exact=True)).to_be_visible()
        finally:
            browser.close()
```

Add a blocked fixture/test asserting “Transport proof blocked routing,” the
requested model remains visible, and no bypass action exists.

- [ ] **Step 2: Run the UI tests and verify RED**

Run: `rtk pytest tests/test_dashboard_orchestrator_policy_e2e.py -k safe_savings -q`

Expected: FAIL because the panel does not exist.

- [ ] **Step 3: Implement the focused component**

Create `SafeSavingsPanel.jsx` with this public structure:

```jsx
export default function SafeSavingsPanel({
  status,
  loading,
  error,
  disabling,
  disableError,
  onDisable,
}) {
  if (loading) return <section className="panel safe-savings-panel">Loading Safe Savings…</section>;
  if (error) return null;
  if (!status?.experience_enabled) return null;

  const decision = status.decision;
  return (
    <section className="panel safe-savings-panel" aria-labelledby="safe-savings-title">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Safe Savings</span>
          <h2 id="safe-savings-title">Conservative model routing</h2>
          <p>Exact routes with capability and transport protection.</p>
        </div>
        <strong>{status.mode === "off" ? "Off" : status.mode}</strong>
      </div>
      {status.mode === "off" ? (
        <p>Requests retain the originally requested model.</p>
      ) : (
        <>
          <p>Preset: {status.preset || "Custom"}</p>
          <div className="safe-savings-routes">
            {status.routes.map((route) => (
              <div key={`${route.source_model}:${route.low_target_model}`}>
                <strong>{route.source_model} → {route.low_target_model}</strong>
                <span>
                  {route.low_target_transport_safe ? "Transport-safe target" : "Restricted transport"}
                </span>
              </div>
            ))}
          </div>
          {decision ? (
            <div className="safe-savings-decision">
              <strong>{decision.title}</strong>
              <span>
                {decision.requested_model} → {decision.effective_model}
              </span>
              <p>{decision.explanation}</p>
              {decision.confidence != null ? (
                <span>Confidence {Number(decision.confidence).toFixed(2)}</span>
              ) : null}
              {decision.missing_capabilities?.length ? (
                <span>Missing capabilities: {decision.missing_capabilities.join(", ")}</span>
              ) : null}
            </div>
          ) : <p>No recent routing decision.</p>}
          <button type="button" onClick={onDisable} disabled={disabling}>
            {disabling ? "Turning off…" : "Turn Safe Savings off"}
          </button>
          {disableError ? <div role="alert">{disableError}</div> : null}
        </>
      )}
    </section>
  );
}
```

- [ ] **Step 4: Integrate fetch state and write the failing Off-action test**

In `Orchestrator.jsx`, add state for status/loading/error/disabling/disableError.
Load status in the existing effect through:

```jsx
const data = await fetchDashboardJson("/v1/orchestration/safe-savings/status");
```

Add an Off handler that confirms, calls the existing mode path, and refreshes
status only after acknowledgement:

```jsx
const handleSafeSavingsDisable = async () => {
  if (!window.confirm("Turn Safe Savings off? New requests will retain the requested model.")) {
    return;
  }
  setSafeSavingsDisabling(true);
  setSafeSavingsDisableError(null);
  try {
    const response = await patchDashboardConfig({ orchestrator_mode: "off" });
    if (acknowledgedRoutingMode(response) !== "off") {
      throw new Error("Server did not acknowledge routing mode off");
    }
    const next = await fetchDashboardJson("/v1/orchestration/safe-savings/status");
    setSafeSavingsStatus(next);
    await refresh?.();
  } catch (err) {
    setSafeSavingsDisableError(err?.message || "Unable to turn Safe Savings off");
  } finally {
    setSafeSavingsDisabling(false);
  }
};
```

The Playwright test must intercept POST `/config/flags`, assert the JSON body is
`{"orchestrator_mode":"off"}`, return an acknowledgement, then fulfill the
second status GET with Off. A failure variant returns 500 and asserts the
previous enabled display remains plus an alert.

- [ ] **Step 5: Add scoped responsive styles**

Add only `.safe-savings-*` selectors in `dashboard/src/index.css`; reuse
existing color, border, spacing, and typography variables. Ensure route rows
wrap under 760px and status text is present independently of color.

- [ ] **Step 6: Verify dashboard GREEN**

Run:

```bash
rtk pytest tests/test_dashboard_orchestrator_policy_e2e.py -k "safe_savings or orchestrator" -q
rtk npm run lint --prefix dashboard
rtk npm run build --prefix dashboard
```

Expected: all selected tests pass; lint and build exit 0 without new warnings.

- [ ] **Step 7: Commit Task 4**

```bash
rtk git add dashboard/src/components/SafeSavingsPanel.jsx dashboard/src/pages/Orchestrator.jsx dashboard/src/index.css tests/test_dashboard_orchestrator_policy_e2e.py
rtk git commit -m "feat add safe savings dashboard panel"
```

---

### Task 5: Documentation and full regression audit

**Files:**
- Modify: `docs/content/docs/model-routing-presets.mdx`
- Modify: `audit/model-routing-commercial-product-assessment-2026-07-18.md`

**Interfaces:**
- Consumes: completed API, CLI, and dashboard behavior.
- Produces: accurate operator documentation and implementation evidence.

- [ ] **Step 1: Add documentation assertions before docs changes**

Add to the existing documentation test file that checks model-routing docs, or
create `tests/test_safe_savings_docs.py`:

```python
from pathlib import Path


def test_safe_savings_docs_name_flag_status_command_and_rollback() -> None:
    text = Path("docs/content/docs/model-routing-presets.mdx").read_text()
    assert "CUTCTX_SAFE_SAVINGS_EXPERIENCE" in text
    assert "cutctx routing status" in text
    assert "/v1/orchestration/safe-savings/status" in text
    assert "orchestrator_mode" in text
    assert '"off"' in text
```

- [ ] **Step 2: Run the docs test and verify RED**

Run: `rtk pytest tests/test_safe_savings_docs.py -q`

Expected: FAIL because the new operator workflow is not yet documented.

- [ ] **Step 3: Document truthful enablement and safety boundaries**

Add a “Guided Safe Savings” section covering:

```bash
export CUTCTX_SAFE_SAVINGS_EXPERIENCE=true
cutctx routing status --proxy-url http://127.0.0.1:8787
```

Document that the flag exposes status UI/CLI only, routing remains separately
opt-in, the status endpoint is authenticated, and Off uses the existing
`{"orchestrator_mode":"off"}` mutation. Explicitly state that status does not
perform provider calls or bypass account/capability/transport proof.

- [ ] **Step 4: Run the complete focused regression set**

Run:

```bash
rtk pytest tests/test_safe_savings_status.py tests/test_safe_savings_docs.py tests/test_cli/test_routing_status.py tests/test_orchestration_platform.py tests/test_dashboard_orchestrator.py tests/test_dashboard_orchestrator_policy_e2e.py tests/test_model_router.py tests/test_model_router_presets.py tests/test_model_routing_quality_benchmark.py -q
```

Expected: all pass with no warnings.

- [ ] **Step 5: Run broader Python and dashboard gates**

Run:

```bash
rtk pytest tests/test_cli tests/test_openai_codex_routing.py tests/test_openai_chat_model_routing_shadow.py tests/test_openai_responses_model_routing_shadow.py tests/test_anthropic_model_routing.py tests/test_proxy_gemini_integration.py tests/test_proxy_gemini_native_integration.py -q
rtk ruff check cutctx/proxy/safe_savings_status.py cutctx/proxy/routes/orchestration.py cutctx/cli/routing.py tests/test_safe_savings_status.py tests/test_cli/test_routing_status.py
rtk mypy cutctx/proxy/safe_savings_status.py cutctx/cli/routing.py
rtk npm run lint --prefix dashboard
rtk npm run build --prefix dashboard
```

Expected: every command exits 0.

- [ ] **Step 6: Update commercial assessment evidence**

Change the Safe Savings opportunity status from “recommended” to “implemented”
only after the gates above pass. Record the exact test counts and any provider
paths not covered by authenticated live credentials; do not claim live-provider
validation from mocked tests.

- [ ] **Step 7: Final diff and safety audit**

Run:

```bash
rtk git diff --check
rtk git status --short
rtk proxy rg -n "api_key|credential_ref|request_messages|response_content" cutctx/proxy/safe_savings_status.py dashboard/src/components/SafeSavingsPanel.jsx
```

Expected:

- no whitespace errors;
- only scoped feature files plus the pre-existing unrelated
  `dashboard-cache-ttl-main.png` change appear;
- the secret/content scan finds no status serialization of those fields.

- [ ] **Step 8: Commit Task 5**

```bash
rtk git add docs/content/docs/model-routing-presets.mdx tests/test_safe_savings_docs.py audit/model-routing-commercial-product-assessment-2026-07-18.md
rtk git commit -m "docs explain guided safe savings"
```

## Completion criteria

- The feature flag exposes, but never enables, Safe Savings.
- Backend, CLI, and dashboard render one shared status schema.
- Exact route pairs, applied/retained state, confidence/signals,
  missing-capability data, and transport posture are visible when observed.
- The Off action uses only the existing authoritative configuration mutation.
- Viewing status is proven not to mutate router state or make provider calls.
- Existing router, orchestration, compatibility, CLI, and dashboard behavior
  remains green.
- Documentation and the commercial assessment match verified runtime behavior.
