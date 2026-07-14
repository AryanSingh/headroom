# Truthful Setup Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `cutctx setup` accurately report whether the requested proxy setup succeeded.

**Architecture:** Keep orchestration in `cutctx/cli/setup.py`. Derive the final result from the `start` option and final health check, render healthy, intentional-skip, or attention-required output, and test the public Click command with external boundaries mocked.

**Tech Stack:** Python 3.10+, Click, pytest, Click `CliRunner`, Markdown.

## Global Constraints

- Do not change proxy launch semantics, configuration formats, or agent/MCP support.
- Requested startup exits `1` when final proxy health is unhealthy; `--no-start` exits `0`.
- Tests must mock startup, health, installation, detection, and registration; never launch a real proxy.
- Retain manual wrapper, proxy, global-routing, SDK, and capability guidance in the README.

---

### Task 1: Test and implement honest final setup state

**Files:**

- Create: `tests/test_cli/test_setup.py`
- Modify: `cutctx/cli/setup.py:112-187`

**Interfaces:**

- Consumes: `setup(port: int, auto_detect: bool, start: bool, do_register_mcp: bool) -> None`.
- Produces: output containing exactly one final state heading: `Setup Complete!`, `Setup skipped proxy start.`, or `Setup needs attention`.

- [x] **Step 1: Write the failing test module**

```python
from click.testing import CliRunner
from cutctx.cli.setup import setup


def _invoke(monkeypatch, *, health, started=False, args=()):
    monkeypatch.setattr("cutctx.cli.setup._check_cutctx_installed", lambda: True)
    monkeypatch.setattr("cutctx.cli.setup._detect_agents", lambda: [])
    monkeypatch.setattr("cutctx.cli.setup._start_proxy", lambda _port: started)
    checks = iter(health)
    monkeypatch.setattr("cutctx.cli.setup._check_health", lambda _port: next(checks))
    return CliRunner().invoke(setup, list(args))


def test_setup_exits_nonzero_and_explains_recovery_when_unhealthy(monkeypatch):
    result = _invoke(monkeypatch, health=[{"running": False, "status": None}] * 2)
    assert result.exit_code == 1, result.output
    assert "Setup needs attention" in result.output
    assert "cutctx proxy --port 8787" in result.output
    assert "https://cutctx.com/docs/troubleshooting" in result.output
    assert "Setup Complete!" not in result.output


def test_setup_succeeds_when_final_health_is_healthy(monkeypatch):
    result = _invoke(monkeypatch, health=[{"running": False, "status": None}, {"running": True, "status": 200}], started=True)
    assert result.exit_code == 0, result.output
    assert "Setup Complete!" in result.output


def test_setup_succeeds_for_an_already_healthy_proxy(monkeypatch):
    result = _invoke(monkeypatch, health=[{"running": True, "status": 200}])
    assert result.exit_code == 0, result.output
    assert "Already running" in result.output


def test_setup_no_start_exits_zero_and_describes_skip(monkeypatch):
    result = _invoke(monkeypatch, health=[{"running": False, "status": None}], args=("--no-start",))
    assert result.exit_code == 0, result.output
    assert "Setup skipped proxy start." in result.output
```

- [x] **Step 2: Verify the tests fail against current behavior**

Run: `pytest tests/test_cli/test_setup.py -q`

Expected: FAIL because an unhealthy requested startup currently prints `Setup Complete!` and exits `0`.

- [x] **Step 3: Implement the minimal final-state rendering**

```python
if health["running"]:
    heading = ("Setup Complete!", "cyan")
elif start:
    heading = ("Setup needs attention", "yellow")
else:
    heading = ("Setup skipped proxy start.", "yellow")
click.echo(click.style(heading[0], fg=heading[1], bold=True))

if not health["running"]:
    click.echo(f"\n  Start proxy: cutctx proxy --port {port}")
    click.echo("  Troubleshooting: https://cutctx.com/docs/troubleshooting")
if start and not health["running"]:
    raise click.exceptions.Exit(1)
```

- [x] **Step 4: Verify the focused tests pass**

Run: `pytest tests/test_cli/test_setup.py -q`

Expected: PASS with four tests.

- [x] **Step 5: Commit the behavior change**

Run: `git add cutctx/cli/setup.py tests/test_cli/test_setup.py && git commit -m "fix: report incomplete setup honestly"`

Expected: one commit containing only the setup behavior and its tests.

### Task 2: Lead agent onboarding with unified setup

**Files:**

- Modify: `README.md:95-118`
- Modify: `tests/test_cli/test_setup.py`

**Interfaces:**

- Consumes: the verified `cutctx setup` behavior from Task 1.
- Produces: a quickstart that introduces `cutctx setup` before manual agent wrapping while retaining manual modes.

- [x] **Step 1: Write the failing README ordering test**

```python
def test_readme_promotes_unified_setup_before_manual_agent_wrapping():
    readme = Path("README.md").read_text()
    start = readme.index("## Get started (60 seconds)")
    end = readme.index("**Accuracy guard**", start)
    quickstart = readme[start:end]
    assert quickstart.index("cutctx setup") < quickstart.index("cutctx wrap claude")
```

- [x] **Step 2: Verify the assertion fails**

Run: `pytest tests/test_cli/test_setup.py::test_readme_promotes_unified_setup_before_manual_agent_wrapping -q`

Expected: FAIL because the current quickstart introduces `cutctx wrap claude` first.

- [x] **Step 3: Update the README quickstart**

```markdown
# 2 — Set up an AI coding agent (recommended)
cutctx setup                         # detects agents, registers MCP, starts and verifies the proxy

# Or choose a manual mode
cutctx wrap claude                    # wrap a coding agent
cutctx proxy --port 8787              # drop-in proxy, zero code changes
```

- [x] **Step 4: Verify focused behavior and help tests**

Run: `pytest tests/test_cli/test_setup.py tests/test_cli/test_main_help_version.py -q`

Expected: PASS.

- [x] **Step 5: Commit the documentation change**

Run: `git add README.md tests/test_cli/test_setup.py && git commit -m "docs: lead onboarding with unified setup"`

Expected: one commit containing the README onboarding update and its assertion.

## Plan self-review

- Task 1 covers truthful state, recovery guidance, exit status, and healthy/already-running/failed/no-start paths.
- Task 2 promotes the unified setup route while retaining advanced manual choices.
- The plan contains no placeholders; every changed public behavior has a focused verifier.
