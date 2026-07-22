# First Paid Pilot Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a release candidate that supports one assisted paying customer using OpenAI and Anthropic through Codex, Claude Code or Desktop, and compatible SDKs on macOS/Linux or customer-managed Docker/Kubernetes infrastructure.

**Architecture:** Keep the release boundary narrow and enforce it at deployment, runtime authentication, licensing, operations, and verification surfaces. Preserve the local loopback developer flow, fail closed on network exposure, prove the supported request paths with existing and new regression tests, and package the customer handoff as versioned runbooks plus a repeatable acceptance command.

**Tech Stack:** Python 3.10+, FastAPI, Click, pytest, SQLite, Docker Compose, Kubernetes YAML, Helm, React/Vite, Rust/PyO3, Markdown runbooks.

## Global Constraints

- Support OpenAI and Anthropic only for the pilot commitment.
- Support Codex, Claude Code, Claude Desktop MCP, and compatible SDK clients.
- Support macOS and Linux workstations.
- Support local loopback, Docker, and Kubernetes deployment modes.
- Require `CUTCTX_PROXY_API_KEY` for every non-loopback provider route.
- Require TLS termination before traffic reaches a network-exposed proxy.
- Enable paid capabilities only after a verified active or trial entitlement.
- Keep Critical and High findings at zero on the supported path.
- Preserve unrelated user changes in the dirty worktree.
- Treat legal approval, payment, contracting entity, and named support ownership as external sign-offs.

---

### Task 1: Establish the supported-path audit baseline

**Files:**
- Modify: `audit/qa-report.md`
- Modify: `audit/security-report.md`
- Modify: `audit/production-readiness.md`
- Modify: `audit/product-manager-report.md`
- Create: `audit/first-paid-pilot-baseline.md`

**Interfaces:**
- Consumes: the supported matrix in `docs/superpowers/specs/2026-07-22-first-paid-pilot-release-design.md`.
- Produces: a scoped finding table with stable IDs `PILOT-QA-*`, `PILOT-SEC-*`, `PILOT-OPS-*`, and `PILOT-PROD-*` for later remediation and final verdict mapping.

- [ ] **Step 1: Record the candidate commit and worktree state**

Run:

```bash
rtk git rev-parse HEAD
rtk git status --short --branch
```

Expected: the output identifies the candidate base and preserves the pre-existing modified files.

- [ ] **Step 2: Run the focused baseline suites**

Run:

```bash
rtk pytest -q \
  tests/test_proxy_client_auth.py \
  tests/test_agent_client_auth.py \
  tests/test_cross_harness_client_auth_e2e.py \
  tests/test_deployment_security.py \
  tests/test_product_operator_contracts.py \
  tests/test_license_validation_contract.py \
  tests/test_entitlement_request_path.py \
  tests/test_management_api_entitlements.py \
  tests/test_mcp_registry \
  tests/test_model_router.py \
  tests/test_provider_proxy_routes.py
```

Expected: failures, skips, and passes become evidence. Do not reinterpret stale audit claims as current findings.

- [ ] **Step 3: Inspect supported deployment and packaging surfaces**

Run:

```bash
rtk proxy grep -R -nE 'CUTCTX_PROXY_API_KEY|CUTCTX_ADMIN_API_KEY|CUTCTX_LICENSE_KEY|readyz|livez' \
  Dockerfile docker-compose.yml docker k8s helm .env.example docs/content/docs/proxy.mdx
rtk git diff --check
```

Expected: each non-loopback deployment exposes the required authentication and health configuration, or the baseline records a finding.

- [ ] **Step 4: Write the scoped baseline**

Use this table shape in `audit/first-paid-pilot-baseline.md`:

```markdown
| ID | Severity | Surface | Claim | Evidence | Required action |
| --- | --- | --- | --- | --- | --- |
| PILOT-SEC-001 | High | Network proxy | Non-loopback provider traffic can start without a client key | failing test or source path | fail closed and document the header |
```

Remove rows whose claims the current code or tests refute. Keep external legal and payment sign-offs in a separate section because code cannot close them.

- [ ] **Step 5: Commit only the baseline documents**

```bash
rtk git add audit/first-paid-pilot-baseline.md audit/qa-report.md audit/security-report.md audit/production-readiness.md audit/product-manager-report.md
rtk git commit -m "audit: scope first paid pilot blockers"
```

### Task 2: Fail closed on network-exposed provider traffic

**Files:**
- Modify: `cutctx/proxy/client_auth.py`
- Modify: `tests/test_proxy_client_auth.py`
- Modify: `docs/content/docs/proxy.mdx`
- Modify: `docker-compose.yml`
- Modify: `helm/cutctx/templates/deployment.yaml`
- Modify: `helm/cutctx/values.yaml`
- Modify: `tests/test_product_operator_contracts.py`

**Interfaces:**
- Consumes: `ProxyConfig.host`, `ProxyConfig.proxy_api_key`, and the `X-Cutctx-Proxy-Key` request header.
- Produces: `require_http_proxy_client(request, config)` and `require_websocket_proxy_client(websocket, config)` behavior that permits zero-config loopback use and rejects missing credentials on non-loopback binds.

- [ ] **Step 1: Keep or add the HTTP regression test**

```python
def test_non_loopback_http_requires_configured_proxy_key() -> None:
    with pytest.raises(ProxyClientAuthError, match="configure CUTCTX_PROXY_API_KEY"):
        require_http_proxy_client(_request(), ProxyConfig(host="0.0.0.0"))
```

- [ ] **Step 2: Add the matching WebSocket regression test**

```python
def test_non_loopback_websocket_requires_configured_proxy_key() -> None:
    with pytest.raises(ProxyClientAuthError, match="configure CUTCTX_PROXY_API_KEY"):
        require_websocket_proxy_client(_websocket(), ProxyConfig(host="0.0.0.0"))
```

- [ ] **Step 3: Run the tests and confirm the unprotected path fails**

Run:

```bash
rtk pytest -q tests/test_proxy_client_auth.py
```

Expected before implementation: the new non-loopback test fails if the runtime still permits a missing key. If the current uncommitted implementation passes, preserve it and verify the diff instead of rewriting it.

- [ ] **Step 4: Apply the minimal fail-closed check**

In the shared client-auth validator, retain this behavior:

```python
if not expected:
    if not is_loopback_host(getattr(config, "host", None)):
        raise ProxyClientAuthError(
            "A non-loopback proxy requires a provider-route credential; "
            "configure CUTCTX_PROXY_API_KEY."
        )
    return
```

- [ ] **Step 5: Make deployment examples supply the boundary**

Add explicit variables to `docker-compose.yml`:

```yaml
environment:
  - CUTCTX_HOST=0.0.0.0
  - CUTCTX_ADMIN_API_KEY=${CUTCTX_ADMIN_API_KEY:?set CUTCTX_ADMIN_API_KEY}
  - CUTCTX_PROXY_API_KEY=${CUTCTX_PROXY_API_KEY:?set CUTCTX_PROXY_API_KEY}
```

Require the Helm value at render time when the chart binds to a network interface:

```yaml
{{- $proxyApiKey := required "enterprise.proxyApiKey is required for a non-loopback Cutctx deployment" .Values.enterprise.proxyApiKey }}
- name: CUTCTX_PROXY_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "cutctx.fullname" . }}-secrets
      key: proxy-api-key
```

Document key generation and `X-Cutctx-Proxy-Key` use in `docs/content/docs/proxy.mdx` and the Compose comments.

- [ ] **Step 6: Lock the operator contract in tests**

Add assertions:

```python
def test_root_compose_requires_network_auth_keys() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "CUTCTX_ADMIN_API_KEY=${CUTCTX_ADMIN_API_KEY:?" in compose
    assert "CUTCTX_PROXY_API_KEY=${CUTCTX_PROXY_API_KEY:?" in compose


def test_helm_requires_provider_route_key() -> None:
    deployment = (ROOT / "helm/cutctx/templates/deployment.yaml").read_text(encoding="utf-8")
    assert 'required "enterprise.proxyApiKey is required' in deployment
```

- [ ] **Step 7: Verify the full security cluster**

Run:

```bash
rtk pytest -q \
  tests/test_proxy_client_auth.py \
  tests/test_agent_client_auth.py \
  tests/test_cross_harness_client_auth_e2e.py \
  tests/test_deployment_security.py \
  tests/test_product_operator_contracts.py
```

Expected: zero failures.

- [ ] **Step 8: Commit the network boundary**

```bash
rtk git add cutctx/proxy/client_auth.py tests/test_proxy_client_auth.py \
  docs/content/docs/proxy.mdx docker-compose.yml \
  helm/cutctx/templates/deployment.yaml helm/cutctx/values.yaml \
  tests/test_product_operator_contracts.py
rtk git commit -m "fix: require auth for pilot network deployments"
```

### Task 3: Prove SQLite contention and license-state durability

**Files:**
- Modify: `tests/test_storage_backends.py`
- Modify: `cutctx_ee/tests/test_license_db.py`
- Modify only if evidence fails: `cutctx/storage/sqlite.py`
- Modify only if evidence fails: `cutctx_ee/billing/license_db.py`

**Interfaces:**
- Consumes: `SQLiteStorage.save(RequestMetrics)` and `LicenseDB.activate_instance(license_key, instance_id)`.
- Produces: regression evidence that a short external write lock waits within the configured busy timeout and commits without data loss.

- [ ] **Step 1: Add a metrics-store contention test**

```python
def test_save_waits_for_short_external_write_lock(tmp_path: Path) -> None:
    path = tmp_path / "metrics.db"
    storage = SQLiteStorage(str(path))
    blocker = sqlite3.connect(path)
    blocker.execute("BEGIN IMMEDIATE")

    timer = threading.Timer(0.1, blocker.commit)
    timer.start()
    try:
        storage.save(_metrics(request_id="locked-write"))
    finally:
        timer.join()
        blocker.close()

    assert storage.get("locked-write") is not None
```

- [ ] **Step 2: Add a license activation contention test**

Create two `LicenseDB` instances against the same temporary path, hold a short
`BEGIN IMMEDIATE` lock in one connection, then assert the second instance can
activate the licensed instance after the first commits. Use a timer no longer
than 0.1 seconds and assert the activation row exists once.

- [ ] **Step 3: Run both contention tests**

Run:

```bash
rtk pytest -q \
  tests/test_storage_backends.py::test_save_waits_for_short_external_write_lock \
  cutctx_ee/tests/test_license_db.py::test_activation_waits_for_short_external_write_lock
```

Expected: pass with the existing busy timeouts. A failure confirms a current pilot blocker.

- [ ] **Step 4: If required, align connection timeouts**

Use a 30-second connection and SQLite busy timeout in the failing store:

```python
_BUSY_TIMEOUT_MS = 30_000
self._conn = sqlite3.connect(str(path), timeout=_BUSY_TIMEOUT_MS / 1000)
self._conn.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
self._conn.execute("PRAGMA journal_mode=WAL")
```

Do not add unbounded retries. SQLite's busy handler supplies the bounded wait.

- [ ] **Step 5: Run storage and license regression suites**

Run:

```bash
rtk pytest -q tests/test_storage_backends.py cutctx_ee/tests/test_license_db.py \
  tests/test_license_validation_contract.py tests/test_entitlement_request_path.py
```

Expected: zero failures and no duplicate activation records.

- [ ] **Step 6: Commit the durability evidence**

```bash
rtk git add tests/test_storage_backends.py cutctx_ee/tests/test_license_db.py \
  cutctx/storage/sqlite.py cutctx_ee/billing/license_db.py
rtk git commit -m "test: prove pilot sqlite contention handling"
```

### Task 4: Create the assisted-pilot operating kit

**Files:**
- Create: `docs/pilot/README.md`
- Create: `docs/pilot/environment-worksheet.md`
- Create: `docs/pilot/onboarding-checklist.md`
- Create: `docs/pilot/customer-acceptance-test.md`
- Create: `docs/pilot/support-and-escalation.md`
- Create: `docs/pilot/incident-response.md`
- Create: `docs/pilot/backup-restore.md`
- Create: `docs/pilot/upgrade-rollback.md`
- Create: `docs/pilot/license-billing-handoff.md`
- Create: `docs/pilot/known-limitations.md`
- Create: `tests/test_pilot_release_docs.py`

**Interfaces:**
- Consumes: current CLI commands, Docker/Kubernetes paths, health routes, MCP registration commands, and license validation behavior.
- Produces: one linked customer handoff with commands that an operator can copy without consulting internal audit files.

- [ ] **Step 1: Add a failing document-contract test**

```python
REQUIRED_DOCS = {
    "environment-worksheet.md": ("CUTCTX_PROXY_API_KEY", "OpenAI", "Anthropic"),
    "onboarding-checklist.md": ("cutctx config-check", "cutctx mcp status"),
    "customer-acceptance-test.md": ("/readyz", "X-Cutctx-Proxy-Key", "rollback"),
    "support-and-escalation.md": ("Critical", "response target"),
    "incident-response.md": ("containment", "customer communication"),
    "backup-restore.md": ("integrity_check", "restore"),
    "upgrade-rollback.md": ("kubectl rollout undo", "previous image"),
    "license-billing-handoff.md": ("payment", "license", "redact"),
    "known-limitations.md": ("Claude Desktop", "Windows", "OpenAI", "Anthropic"),
}


def test_pilot_operating_kit_contains_required_contracts() -> None:
    for filename, needles in REQUIRED_DOCS.items():
        text = (ROOT / "docs/pilot" / filename).read_text(encoding="utf-8")
        for needle in needles:
            assert needle in text


def test_pilot_index_links_each_required_document() -> None:
    index = (ROOT / "docs/pilot/README.md").read_text(encoding="utf-8")
    for filename in REQUIRED_DOCS:
        assert f"]({filename})" in index
```

- [ ] **Step 2: Run the contract test and confirm missing files fail**

Run:

```bash
rtk pytest -q tests/test_pilot_release_docs.py
```

Expected before document creation: failure on the first missing file.

- [ ] **Step 3: Write the pilot index and supported matrix**

`docs/pilot/README.md` must link every runbook and state:

```markdown
This pilot supports OpenAI and Anthropic through Codex, Claude Code, Claude
Desktop MCP, and compatible SDKs on macOS/Linux workstations or
customer-managed Docker/Kubernetes deployments.
```

- [ ] **Step 4: Write backup and restore commands**

The runbook must stop writes, copy SQLite databases with the SQLite backup API
or `.backup`, preserve orchestration keys separately, restore file ownership,
run `PRAGMA integrity_check`, start the candidate, and verify `/readyz` plus a
licensed request. Include Docker volume and Kubernetes PVC examples.

- [ ] **Step 5: Write upgrade and rollback commands**

Cover workstation package pinning, Docker image digests, `docker compose up -d`,
Kubernetes `kubectl rollout status`, `kubectl rollout undo`, Helm rollback, and
the condition that triggers rollback.

- [ ] **Step 6: Write onboarding, support, incident, and handoff checklists**

Use blank owner and date fields for human sign-off, but no unspecified product
steps. List the support channel, severity definitions, response target chosen by
the release owner, evidence bundle location, license-key redaction rule, and
customer communication owner.

- [ ] **Step 7: Write the executable customer acceptance sequence**

Include exact commands for config validation, health checks, an authenticated
OpenAI request, an authenticated Anthropic request, `cutctx mcp status`, a large
MCP gateway tool result, operator metrics, invalid-key rejection, rollback,
restore, and uninstall.

- [ ] **Step 8: Run the document contract and link checks**

Run:

```bash
rtk pytest -q tests/test_pilot_release_docs.py
```

Expected: zero failures and no missing links from the pilot index.

- [ ] **Step 9: Commit the operating kit**

```bash
rtk git add docs/pilot tests/test_pilot_release_docs.py
rtk git commit -m "docs: add assisted pilot operating kit"
```

### Task 5: Add a repeatable pilot release verifier

**Files:**
- Create: `scripts/verify_pilot_release.py`
- Create: `tests/test_verify_pilot_release.py`
- Modify: `Makefile`

**Interfaces:**
- Produces: `python scripts/verify_pilot_release.py --output audit/pilot-verification.json` with JSON fields `candidate_commit`, `checks`, `passed`, `failed`, `skipped`, and `external_signoffs`.
- Consumes: subprocess commands declared in one `CHECKS` tuple and writes no product state outside the requested report path.

- [ ] **Step 1: Write parser and result-shape tests**

```python
def test_build_report_marks_failed_command(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(verifier, "run_check", lambda check: {"name": check.name, "status": "failed", "returncode": 1})
    report = verifier.build_report((verifier.Check("unit", ("python", "-V")),))
    assert report["passed"] is False
    assert report["failed"] == 1


def test_write_report_emits_json(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    verifier.write_report(output, {"passed": True, "checks": []})
    assert json.loads(output.read_text())["passed"] is True
```

- [ ] **Step 2: Run the tests and confirm the module is missing**

Run:

```bash
rtk pytest -q tests/test_verify_pilot_release.py
```

Expected: import failure for `scripts.verify_pilot_release`.

- [ ] **Step 3: Implement the verifier data model**

```python
@dataclass(frozen=True)
class Check:
    name: str
    command: tuple[str, ...]
    required: bool = True


def run_check(check: Check) -> dict[str, object]:
    completed = subprocess.run(check.command, cwd=ROOT, text=True, capture_output=True)
    return {
        "name": check.name,
        "command": list(check.command),
        "required": check.required,
        "status": "passed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }
```

Keep commands as argument tuples. Do not use `shell=True`.

- [ ] **Step 4: Define the supported-path checks**

Include focused pytest clusters, Ruff on changed Python files, dashboard tests
and build, Rust format/clippy/tests, Helm render, Docker build or config check,
package/version/license-boundary checks, and pilot document contracts. Mark live
provider calls and real-cluster recovery drills as external/manual checks rather
than silently passing them.

- [ ] **Step 5: Add the Make target**

```make
.PHONY: verify-pilot-release

verify-pilot-release:
	$(PYTHON) scripts/verify_pilot_release.py --output audit/pilot-verification.json
```

- [ ] **Step 6: Run unit tests and a dry verification**

Run:

```bash
rtk pytest -q tests/test_verify_pilot_release.py
rtk proxy python scripts/verify_pilot_release.py --list
```

Expected: tests pass and `--list` prints each check without executing it.

- [ ] **Step 7: Commit the verifier**

```bash
rtk git add scripts/verify_pilot_release.py tests/test_verify_pilot_release.py Makefile
rtk git commit -m "build: add paid pilot release verifier"
```

### Task 6: Run release verification, remediate confirmed blockers, and issue the verdict

**Files:**
- Modify as required by confirmed Critical or High supported-path failures.
- Create: `audit/pilot-verification.json`
- Modify: `audit/qa-report.md`
- Modify: `audit/security-report.md`
- Modify: `audit/production-readiness.md`
- Modify: `audit/product-manager-report.md`
- Create: `audit/final-verdict.md`

**Interfaces:**
- Consumes: stable finding IDs from Task 1 and machine-readable check results from Task 5.
- Produces: a launch decision with feature completeness, security score, production-readiness score, residual risks, external sign-offs, and a Go, Conditional Go, or No-Go recommendation.

- [ ] **Step 1: Run the complete automated verifier**

Run:

```bash
rtk proxy python scripts/verify_pilot_release.py --output audit/pilot-verification.json
```

Expected: the JSON records every check. A required failed check blocks a Go verdict.

- [ ] **Step 2: Diagnose each failed required check before changing code**

For each failure, record:

```markdown
- Claim that failed
- Reproduction command
- Root cause
- Smallest safe fix
- Regression test
- Verification command
```

Apply test-driven fixes only inside the supported path. Keep unrelated Medium
or Low cleanup out of this release unless it blocks evidence.

- [ ] **Step 3: Run manual local acceptance evidence**

Execute every customer-safe step available on the current macOS/Linux host from
`docs/pilot/customer-acceptance-test.md`. Do not spend provider funds or mutate
an external cluster without existing credentials and authorization. Record
unavailable live checks as external sign-offs, not passes.

- [ ] **Step 4: Re-run the verifier after remediation**

Run:

```bash
rtk proxy python scripts/verify_pilot_release.py --output audit/pilot-verification.json
rtk git diff --check
```

Expected: all required automated checks pass before a positive software verdict.

- [ ] **Step 5: Re-audit the supported path**

Update the four audit reports with current evidence. Each report must separate:

- supported pilot findings;
- unsupported or experimental product findings;
- external legal, payment, and staffing sign-offs;
- stale claims that current evidence refuted.

- [ ] **Step 6: Write `audit/final-verdict.md`**

Use this decision block:

```markdown
## Launch recommendation

**Decision:** Go | Conditional Go | No-Go

**Feature completeness:** N/100
**Security score:** N/100
**Production readiness:** N/100

### Supported pilot matrix
- OpenAI and Anthropic provider traffic through Codex, Claude Code, and compatible SDKs.
- Claude Desktop MCP tool-output gateway coverage.
- macOS/Linux workstations plus customer-managed Docker/Kubernetes deployments.

### Automated evidence
- Candidate commit and verifier report path.
- Required check totals, failures, and skips.
- Package, runtime, deployment, dashboard, Rust, and documentation results.

### Manual evidence and external sign-offs
- Workstation acceptance steps completed on the current host.
- Live-provider and customer-cluster steps still awaiting the customer environment.
- Legal, payment, support-owner, and change-window sign-off status.

### Open Medium and Low risks
- Finding ID, owner, workaround, and planned release for each accepted risk.
```

Choose `Conditional Go` when software checks pass but legal, payment, named
support ownership, live provider acceptance, or customer-cluster recovery
evidence remains unsigned. Choose `No-Go` for any open Critical or High issue on
the supported path.

- [ ] **Step 7: Verify report consistency**

Run:

```bash
rtk proxy python - <<'PY'
import json
from pathlib import Path

report = json.loads(Path("audit/pilot-verification.json").read_text())
verdict = Path("audit/final-verdict.md").read_text()
assert str(report["candidate_commit"]) in verdict
if report["passed"]:
    assert "required automated checks pass" in verdict.lower()
else:
    assert "No-Go" in verdict
PY
rtk git diff --check
```

Expected: zero failures.

- [ ] **Step 8: Commit the verified release verdict**

```bash
rtk git add audit/pilot-verification.json audit/qa-report.md audit/security-report.md \
  audit/production-readiness.md audit/product-manager-report.md audit/final-verdict.md
rtk git commit -m "audit: issue first paid pilot launch verdict"
```
