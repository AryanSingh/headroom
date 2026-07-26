# Claude Desktop Routing Operability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Claude Desktop integration diagnosable and truthful while preserving verified intelligent routing for compatible transports.

**Architecture:** Keep proxy model routing and Claude Desktop MCP integration as separate paths. Add read-only Desktop inspection to the MCP CLI, update user-facing capability scope, and strengthen Playwright readiness checks.

**Tech Stack:** Python 3.10+, Click, React 19, Playwright, pytest.

## Global Constraints

- Keep `codex-gpt54mini-high` as the canonical Balanced preset.
- Keep `economy` as the Aggressive preset.
- Do not claim Claude Desktop hosted model traffic reaches the proxy.
- Preserve user MCP servers and make gateway wrapping reversible.
- Add no dependencies.

---

### Task 1: Claude Desktop status and install guidance

**Files:**
- Modify: `tests/test_cli/test_mcp.py`
- Modify: `cutctx/cli/mcp.py`

**Interfaces:**
- Consumes: `ClaudeDesktopRegistrar.detect()`, `get_server()`, and `wrap_servers_with_gateway()`.
- Produces: Desktop-specific lines in `cutctx mcp status` and accurate install next steps.

- [ ] Add tests that inject a temporary Desktop config and assert detected, configured, gateway-count, restart, and hosted-model boundary output.
- [ ] Run the new tests and confirm they fail because status only inspects Claude Code.
- [ ] Add a small Desktop status helper and call it from `mcp_status()`.
- [ ] Adjust install guidance to separate Claude Desktop MCP from base-URL proxy routing.
- [ ] Run `rtk pytest -q tests/test_cli/test_mcp.py tests/test_mcp_registry/test_claude_desktop_registrar.py tests/test_mcp_registry/test_gateway.py` and require zero failures.

### Task 2: Capability and Orchestrator copy

**Files:**
- Modify: `dashboard/src/data/capabilities.js`
- Modify: `dashboard/src/pages/Orchestrator.jsx`
- Modify: `tests/test_dashboard_live_savings_fallback.py`

**Interfaces:**
- Consumes: existing static capability groups and routing mode state.
- Produces: explicit transport scope in the Capabilities page and mode descriptions based on behavior rather than internal preset names alone.

- [ ] Add source-contract tests for Claude Desktop MCP scope, compatible-client proxy scope, and truthful SSE semantics.
- [ ] Run the tests and confirm they fail on current copy.
- [ ] Update the capability cards and mode descriptions with concise user-facing wording.
- [ ] Run dashboard source-contract tests, unit tests, lint, and build.

### Task 3: Visual audit readiness

**Files:**
- Modify: `tests/test_dashboard_audit.py`

**Interfaces:**
- Consumes: route-specific visible headings from the dashboard.
- Produces: screenshots captured only after each route leaves the loading shell.

- [ ] Add an Orchestrator readiness assertion that requires `Routing mode control` before teardown.
- [ ] Run the focused audit and confirm the assertion exposes the premature screenshot path.
- [ ] Add route-ready locators and wait for them before yielding the audit page.
- [ ] Run `rtk pytest -q tests/test_dashboard_audit.py -k orchestrator` and inspect desktop/mobile screenshots.
- [ ] Run the complete targeted routing, orchestration, MCP, capabilities, and dashboard verification set.

