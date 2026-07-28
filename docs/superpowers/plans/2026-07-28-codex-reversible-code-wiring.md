# Codex Reversible Code Compression Wiring Implementation Plan

> **Status:** Superseded by the default-on live rollout in
> `2026-07-28-reversible-code-live-rollout.md`. This file preserves the original
> default-off wiring sequence for implementation history; it is not the current
> product policy.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the documented opt-in reversible code-compression switch activate safely for live Codex and ChatGPT proxy requests.

**Architecture:** Keep the existing default-off policy and the reversible compressor's parse/retrieval guards unchanged. Add one configuration field, expose it through the user-facing Click proxy command and the direct proxy entry point, then pass it into `ContentRouterConfig` so the already-tested OpenAI Responses unit path can use it.

**Tech Stack:** Python 3, Click, FastAPI proxy, pytest.

## Global Constraints

- Preserve the default of `False`; ordinary proxy traffic must remain byte-for-byte on the existing path.
- Do not enable lossy `code_aware` compression or widen protected OpenAI Responses item extraction.
- Retain the existing CCR-backed, syntax-checked reversible compressor as the only newly activated code transformation.
- Add negative-control coverage proving enabled and disabled proxy configurations differ only when explicitly requested.

---

### Task 1: Wire the opt-in configuration through both proxy launch paths

**Files:**

- Modify: `cutctx/proxy/models.py`
- Modify: `cutctx/proxy/server.py`
- Test: `tests/test_cli_proxy_env.py`

**Interfaces:**

- Consumes: `CUTCTX_REVERSIBLE_CODE`, `--enable-reversible-code`, and `ProxyConfig`.
- Produces: `ProxyConfig.enable_reversible_code: bool` and `ContentRouterConfig.enable_reversible_code: bool` with a default value of `False`.

- [ ] **Step 1: Write the failing configuration tests**

```python
def test_reversible_code_enabled_from_env(self, runner):
    # invoke `cutctx proxy` with CUTCTX_REVERSIBLE_CODE=1 and assert the
    # intercepted ProxyConfig has enable_reversible_code is True.

def test_reversible_code_enabled_from_cli_flag(self, runner):
    # invoke `cutctx proxy --enable-reversible-code` and assert True.
```

- [ ] **Step 2: Run the focused configuration test to verify it fails**

Run: `python -m pytest tests/test_cli_proxy_env.py -q -k reversible_code`

Expected: FAIL because the CLI does not recognize the flag and the config has no attribute.

- [ ] **Step 3: Write the minimal configuration implementation**

```python
# ProxyConfig
enable_reversible_code: bool = False

# proxy CLI parser
parser.add_argument("--enable-reversible-code", action="store_true", ...)

# config construction and worker environment reconstruction
enable_reversible_code=args.enable_reversible_code or _get_env_bool(
    "CUTCTX_REVERSIBLE_CODE", False
)

# ContentRouter construction
enable_reversible_code=config.enable_reversible_code
```

- [ ] **Step 4: Run the focused configuration test to verify it passes**

Run: `python -m pytest tests/test_cli_proxy_env.py -q -k reversible_code`

Expected: PASS.

### Task 2: Prove activation on a real Codex Responses payload without changing the default path

**Files:**

- Modify: `tests/test_openai_responses_compression_units.py`
- Test: `tests/test_openai_responses_compression_units.py`

**Interfaces:**

- Consumes: `CutctxProxy(ProxyConfig(enable_reversible_code=True))` and a `function_call_output` containing valid Python source.
- Produces: a compressed output with a `cutctx:code_elided` marker only when the explicit opt-in is present.

- [ ] **Step 1: Write the failing live-path regression test**

```python
def test_openai_responses_reversible_code_requires_explicit_proxy_opt_in():
    # Build the normal proxy/router from ProxyConfig.
    # Assert default config leaves code unchanged.
    # Assert enabled config inserts the retrieval marker, reduces tokens,
    # preserves valid Python, and leaves non-code protocol fields unchanged.
```

- [ ] **Step 2: Run the focused Responses test to verify it fails**

Run: `python -m pytest tests/test_openai_responses_compression_units.py -q -k reversible_code`

Expected: FAIL because the enablement value never reaches ContentRouter.

- [ ] **Step 3: Run the focused test after Task 1's wiring**

Run: `python -m pytest tests/test_openai_responses_compression_units.py -q -k reversible_code`

Expected: PASS; default remains untouched and opt-in produces a CCR marker.

### Task 3: Verify the behavior and correct the operator documentation

**Files:**

- Modify: `docs/reversible-code-compression.md`
- Test: `tests/test_cli_proxy_env.py`
- Test: `tests/test_openai_responses_compression_units.py`
- Test: `tests/test_reversible_code_compressor.py`

**Interfaces:**

- Consumes: completed activation tests and existing compression contracts.
- Produces: documentation that accurately names the now-functional flag and a clean focused regression suite.

- [ ] **Step 1: Amend the activation documentation**

```markdown
`--enable-reversible-code` / `CUTCTX_REVERSIBLE_CODE=1` explicitly enables
CCR-backed Python body elision; it remains off by default.
```

- [ ] **Step 2: Run focused regression checks**

Run: `python -m pytest tests/test_cli_proxy_env.py tests/test_openai_responses_compression_units.py tests/test_reversible_code_compressor.py -q`

Expected: PASS.

- [ ] **Step 3: Run static checks on changed Python files**

Run: `uvx ruff@0.9.4 check cutctx/proxy/models.py cutctx/proxy/server.py tests/test_cli_proxy_env.py tests/test_openai_responses_compression_units.py && uvx ruff@0.9.4 format --check cutctx/proxy/models.py cutctx/proxy/server.py tests/test_cli_proxy_env.py tests/test_openai_responses_compression_units.py`

Expected: PASS.
