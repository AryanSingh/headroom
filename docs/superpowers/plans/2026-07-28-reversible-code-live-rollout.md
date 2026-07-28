# Reversible Code Compression Live Rollout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable the safe reversible-code path by default and give the running proxy an authenticated no-restart toggle.

**Architecture:** `ProxyConfig.enable_reversible_code` becomes default-on for new processes. The existing configuration-flags API updates each live `ContentRouterConfig` in place, so no listener, HTTP client, or WebSocket lifecycle component is recreated.

**Tech Stack:** Python 3, FastAPI, Starlette TestClient, pytest, Ruff 0.9.4.

## Global Constraints

- Preserve the reversible compressor's CCR storage, parse, skeleton, and no-inflation contracts.
- Never restart or signal the running proxy during runtime enablement.
- Apply the toggle only to ContentRouter instances; do not enable lossy code-aware compression.
- Require the existing local admin authentication for read and write access.

---

### Task 1: Define default and live-router update semantics

**Files:**

- Modify: `cutctx/proxy/models.py`
- Modify: `cutctx/proxy/server.py`
- Test: `tests/test_reversible_code_compressor.py`

**Interfaces:**

- Consumes: `ProxyConfig.enable_reversible_code: bool`.
- Produces: default `True` and a helper that updates every `ContentRouter` in
  the proxy's Anthropic/OpenAI pipelines without replacing those pipelines.

- [ ] **Step 1: Write a failing default-and-explicit-off test**

```python
def test_reversible_code_defaults_on_but_explicit_off_is_preserved() -> None:
    assert ProxyConfig().enable_reversible_code is True
    assert ProxyConfig(enable_reversible_code=False).enable_reversible_code is False
```

- [ ] **Step 2: Run it and verify it fails because the current default is false**

Run: `python -m pytest tests/test_reversible_code_compressor.py -q -k defaults_on`

Expected: FAIL with `False is True`.

- [ ] **Step 3: Change the dataclass default and add the scoped router update helper**

```python
enable_reversible_code: bool = True

def _set_live_reversible_code(proxy: CutctxProxy, enabled: bool) -> int:
    # Update only ContentRouter.config.enable_reversible_code in both pipelines.
    # Return the number of unique routers changed; do not replace a pipeline.
```

- [ ] **Step 4: Run the focused test and inspect identity preservation**

Run: `python -m pytest tests/test_reversible_code_compressor.py -q -k reversible_code`

Expected: PASS; pipeline and router objects retain identity.

### Task 2: Expose an authenticated no-restart management toggle

**Files:**

- Modify: `cutctx/proxy/server.py`
- Test: `tests/test_proxy_dynamic_init.py`

**Interfaces:**

- Consumes: `POST /config/flags` or `POST /admin/config/flags` body
  `{ "reversible_code": boolean }` and the existing admin key.
- Produces: response state `reversible_code`, `applied_live.reversible_code`,
  and immediate router-config updates without an application restart.

- [ ] **Step 1: Write failing API tests**

```python
def test_reversible_code_live_toggle_updates_all_routers_without_replacement():
    # Save pipeline/router identities, POST enabled then disabled, and assert
    # values change while every saved identity is unchanged.

def test_reversible_code_toggle_requires_existing_admin_auth():
    # POST without the admin key and assert 401/403 with no config mutation.
```

- [ ] **Step 2: Run the focused API test and verify it fails because the key is ignored**

Run: `python -m pytest tests/test_proxy_dynamic_init.py -q -k reversible_code`

Expected: FAIL because `reversible_code` is absent from the live flags API.

- [ ] **Step 3: Add the allowed boolean key to GET/POST flags handling**

```python
if "reversible_code" in payload:
    enabled = bool(payload["reversible_code"])
    config.enable_reversible_code = enabled
    updated = _set_live_reversible_code(proxy, enabled)
    applied_live["reversible_code"] = {"enabled": enabled, "routers_updated": updated}
```

- [ ] **Step 4: Run the focused API test**

Run: `python -m pytest tests/test_proxy_dynamic_init.py -q -k reversible_code`

Expected: PASS.

### Task 3: Demonstrate protocol and session safety

**Files:**

- Modify: `tests/test_openai_responses_compression_units.py`
- Modify: `tests/test_openai_codex_ws_lifecycle.py`
- Test: `tests/test_openai_responses_compression_units.py`
- Test: `tests/test_openai_codex_ws_lifecycle.py`

**Interfaces:**

- Consumes: a valid Python `function_call_output`, the live flag API, and the
  existing fake Codex WebSocket transport.
- Produces: CCR markers only for enabled eligible code, and a WebSocket that
  remains open while the future-request setting changes.

- [ ] **Step 1: Write failing HTTP and WebSocket regression tests**

```python
def test_live_toggle_changes_only_future_openai_responses_code_units():
    # Explicit false preserves source; true emits a marker; false again
    # preserves the next source without altering protocol fields.

async def test_live_reversible_toggle_does_not_close_active_codex_websocket():
    # Toggle between two frames; assert both are forwarded and neither fake
    # client nor upstream transport received close().
```

- [ ] **Step 2: Run the tests before implementation and verify the flag API test fails**

Run: `python -m pytest tests/test_openai_responses_compression_units.py tests/test_openai_codex_ws_lifecycle.py -q -k reversible_code`

Expected: FAIL only because the live API key is unimplemented; protocol
preservation assertions remain valid.

- [ ] **Step 3: Run the tests after Task 2**

Run: `python -m pytest tests/test_openai_responses_compression_units.py tests/test_openai_codex_ws_lifecycle.py -q -k reversible_code`

Expected: PASS.

### Task 4: Validate and activate without restart

**Files:**

- Modify: `docs/reversible-code-compression.md`
- Test: targeted suites plus `tests/`

**Interfaces:**

- Consumes: a healthy local proxy and its active-session telemetry.
- Produces: a documented live activation command and before/after health proof.

- [ ] **Step 1: Document default-on and the immediate kill switch**

```markdown
New proxies enable reversible code compression by default. To change a live
proxy without restart, POST `{ "reversible_code": true|false }` to
`/admin/config/flags` with the configured local admin key.
```

- [ ] **Step 2: Run targeted and full regression suites**

Run: `python -m pytest tests/test_proxy_dynamic_init.py tests/test_reversible_code_compressor.py tests/test_openai_responses_compression_units.py tests/test_openai_codex_ws_lifecycle.py -q && python -m pytest tests/ -q`

Expected: PASS.

- [ ] **Step 3: Run pinned static checks**

Run: `uvx ruff@0.9.4 check cutctx/proxy/models.py cutctx/proxy/server.py tests/test_proxy_dynamic_init.py tests/test_reversible_code_compressor.py tests/test_openai_responses_compression_units.py tests/test_openai_codex_ws_lifecycle.py && uvx ruff@0.9.4 format --check cutctx/proxy/models.py cutctx/proxy/server.py tests/test_proxy_dynamic_init.py tests/test_reversible_code_compressor.py tests/test_openai_responses_compression_units.py tests/test_openai_codex_ws_lifecycle.py`

Expected: PASS.

- [ ] **Step 4: Capture live health, toggle in process, and capture health again**

```bash
curl -fsS http://127.0.0.1:8787/livez
curl -fsS -X POST http://127.0.0.1:8787/admin/config/flags \
  -H "X-Cutctx-Admin-Key: $CUTCTX_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  --data '{"reversible_code":true}'
curl -fsS http://127.0.0.1:8787/livez
```

Expected: identical process uptime and nondecreasing active-session count; no
signal or restart command is issued.
