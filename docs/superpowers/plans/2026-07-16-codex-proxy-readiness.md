# Codex Proxy Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure Codex never starts against the local Cutctx proxy until port 8787 is fully traffic-ready.

**Architecture:** `com.cutctx.proxy` owns the persistent proxy process. Both shell launch paths use `/readyz` as the traffic-readiness signal, wait up to 180 seconds for cold model warmup, and exit non-zero on a timeout. The launch agent is bootstrapped into the active GUI domain so it can recover the proxy across logins.

**Tech Stack:** bash, launchd, curl, pytest.

## Global Constraints

- Preserve the user’s existing proxy port (`8787`) and model-routing configuration.
- Do not launch a second proxy when a process already owns port 8787.
- Poll `http://127.0.0.1:<port>/readyz`; do not treat `/livez` or `/health` as sufficient readiness.
- Use a 180-second cold-start deadline and fail closed on expiry.
- Do not modify unrelated dirty worktree files.

---

### Task 1: Lock the readiness contract in regression tests

**Files:**
- Create: `tests/test_codex_proxy_launchers.py`
- Test: `tests/test_codex_proxy_launchers.py`

**Interfaces:**
- Consumes: `~/.local/bin/codex-cutctx-lib.sh` and `restart-proxy.sh`.
- Produces: static regression checks for the shared launcher readiness contract.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_codex_launcher_waits_for_readyz_and_fails_closed() -> None:
    script = Path.home() / ".local/bin/codex-cutctx-lib.sh"
    source = script.read_text()

    assert 'local url="http://127.0.0.1:${port}/readyz"' in source
    assert 'deadline=$(( $(date +%s) + 180 ))' in source
    assert 'return 1' in source[source.index('codex_cutctx_ensure_proxy'):]
    assert 'continuing anyway' not in source


def test_manual_restart_waits_for_readyz_and_exits_on_timeout() -> None:
    source = (ROOT / "restart-proxy.sh").read_text()

    assert '/readyz' in source
    assert 'seq 1 180' in source
    assert 'exit 1' in source
    assert 'READY!' in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_codex_proxy_launchers.py`

Expected: FAIL because the current shared launcher has a 90-second deadline and warns before continuing, while `restart-proxy.sh` probes `/health` for only 30 seconds.

- [ ] **Step 3: Run the focused test after each implementation change**

Run: `pytest -q tests/test_codex_proxy_launchers.py`

Expected: PASS after Tasks 2 and 3.

- [ ] **Step 4: Commit the regression test**

```bash
git add tests/test_codex_proxy_launchers.py
git commit -m "test: cover Codex proxy readiness launchers"
```

### Task 2: Make the Codex launcher fail closed

**Files:**
- Modify: `~/.local/bin/codex-cutctx-lib.sh:161-207`
- Test: `tests/test_codex_proxy_launchers.py`

**Interfaces:**
- Consumes: port selected by `codex_cutctx_port` and launchd label `com.cutctx.proxy`.
- Produces: `codex_cutctx_ensure_proxy` exits non-zero if `/readyz` does not return HTTP 200 within 180 seconds.

- [ ] **Step 1: Write the minimal implementation**

Replace the timeout block in `codex_cutctx_ensure_proxy` with:

```bash
  local deadline
  deadline=$(( $(date +%s) + 180 ))
  printf 'Waiting for cutctx proxy readiness' >&2
  while true; do
    if curl -sf --max-time 2 "$url" >/dev/null 2>&1; then
      printf ' ready.\n' >&2
      return 0
    fi
    if [[ $(date +%s) -ge $deadline ]]; then
      printf '\nERROR: cutctx proxy did not become ready within 180s. See %s.\n' "$log_file" >&2
      return 1
    fi
    printf '.' >&2
    sleep 1
  done
```

Keep the existing no-second-proxy behavior when the port is already in use.

- [ ] **Step 2: Run the focused test to verify it passes**

Run: `pytest -q tests/test_codex_proxy_launchers.py::test_codex_launcher_waits_for_readyz_and_fails_closed`

Expected: PASS.

- [ ] **Step 3: Commit the launcher change**

```bash
git add ~/.local/bin/codex-cutctx-lib.sh tests/test_codex_proxy_launchers.py
git commit -m "fix: wait for Cutctx readiness before Codex launch"
```

### Task 3: Make the manual restart path truthful

**Files:**
- Modify: `restart-proxy.sh:55-65`
- Test: `tests/test_codex_proxy_launchers.py`

**Interfaces:**
- Consumes: `CUTCTX_PROXY_PORT`, `CUTCTX_ADMIN_API_KEY`, and proxy `/readyz`.
- Produces: an exit code of 1 when the manually restarted proxy is not ready after 180 seconds.

- [ ] **Step 1: Write the minimal implementation**

Replace the 30-iteration `/health` loop with:

```bash
echo -n "Waiting for proxy readiness..."
READY=0
for _ in $(seq 1 180); do
  sleep 1
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://$HOST:$PORT/readyz" 2>/dev/null || echo "000")
  if [ "$STATUS" = "200" ]; then
    READY=1
    echo " READY!"
    break
  fi
  echo -n "."
done
if [ "$READY" -ne 1 ]; then
  echo ""
  echo "ERROR: proxy never became ready; inspect /tmp/cutctx_restart.log" >&2
  exit 1
fi
```

- [ ] **Step 2: Run the focused test to verify it passes**

Run: `pytest -q tests/test_codex_proxy_launchers.py::test_manual_restart_waits_for_readyz_and_exits_on_timeout`

Expected: PASS.

- [ ] **Step 3: Commit the restart change**

```bash
git add restart-proxy.sh tests/test_codex_proxy_launchers.py
git commit -m "fix: fail manual proxy restart until ready"
```

### Task 4: Bootstrap and verify the persistent proxy service

**Files:**
- Modify: `~/Library/LaunchAgents/com.cutctx.proxy.plist` only if `launchctl bootstrap` reports malformed configuration.
- Test: live launchd and `/readyz` checks.

**Interfaces:**
- Consumes: `~/Library/LaunchAgents/com.cutctx.proxy.plist`.
- Produces: a loaded `gui/<uid>/com.cutctx.proxy` launch service which owns port 8787.

- [ ] **Step 1: Bootstrap the service only if it is absent**

```bash
launchctl print "gui/$(id -u)/com.cutctx.proxy" >/dev/null 2>&1 || \
  launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.cutctx.proxy.plist"
```

- [ ] **Step 2: Verify service registration and readiness**

```bash
launchctl print "gui/$(id -u)/com.cutctx.proxy"
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:8787/readyz
```

Expected: launchctl prints the service state and curl exits 0 with a ready payload.

- [ ] **Step 3: Run the complete regression test**

Run: `pytest -q tests/test_codex_proxy_launchers.py`

Expected: PASS.

- [ ] **Step 4: Commit project-owned files only**

```bash
git add restart-proxy.sh tests/test_codex_proxy_launchers.py
git commit -m "fix: enforce Cutctx proxy readiness"
```
