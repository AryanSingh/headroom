# First Paid Pilot Baseline

**Date:** 2026-07-22  
**Scope:** One assisted paying customer using OpenAI and Anthropic through
Codex, Claude Code or Desktop, and compatible SDKs on macOS/Linux or
customer-managed Docker/Kubernetes infrastructure.

## Candidate state

- Base branch: `main`
- Design commit: `8a4ceac`
- Plan commit: `9bc1c78`
- The worktree contains pre-existing release audit, client-authentication,
  documentation, and screenshot changes. This release pass preserves them.

## Current automated evidence

The supported-path baseline command passed 281 tests:

```text
tests/test_proxy_client_auth.py
tests/test_agent_client_auth.py
tests/test_cross_harness_client_auth_e2e.py
tests/test_deployment_security.py
tests/test_product_operator_contracts.py
tests/test_license_validation_contract.py
tests/test_entitlement_request_path.py
tests/test_management_api_entitlements.py
tests/test_mcp_registry/
tests/test_model_router.py
tests/test_provider_proxy_routes.py
```

## Confirmed findings

| ID | Severity | Surface | Claim | Evidence | Required action |
| --- | --- | --- | --- | --- | --- |
| PILOT-SEC-001 | High, remediation present | Network proxy | A non-loopback provider route must reject traffic when `CUTCTX_PROXY_API_KEY` is absent. | `cutctx/proxy/client_auth.py`, `tests/test_proxy_client_auth.py`; focused cluster passes. | Preserve the fail-closed change, add the matching WebSocket regression, and verify deployment examples. |
| PILOT-OPS-001 | High | Root Docker Compose | `docker-compose.yml` binds to `0.0.0.0` without requiring admin or provider-route credentials. The hardened runtime will refuse this configuration. | `docker-compose.yml` environment block. | Require distinct `CUTCTX_ADMIN_API_KEY` and `CUTCTX_PROXY_API_KEY` variables. |
| PILOT-OPS-002 | High | Helm | The chart can render a network deployment without `enterprise.proxyApiKey`; the pod then fails the runtime deployment-security gate. | `helm/cutctx/templates/deployment.yaml`, `helm/cutctx/values.yaml`. | Fail Helm rendering with an actionable message when the key is empty. |
| PILOT-OPS-003 | High | Recovery | No customer-facing pilot runbook proves backup restore and rollback for workstation, Docker, and Kubernetes paths. | No `docs/pilot/` operating kit exists. | Add backup, restore, upgrade, rollback, and incident procedures with exact commands. |
| PILOT-QA-001 | High | Customer acceptance | The repository has broad tests but no single customer acceptance sequence for the supported pilot matrix. | No `docs/pilot/customer-acceptance-test.md` exists. | Add a deterministic acceptance checklist and contract tests. |
| PILOT-QA-002 | High | Release evidence | No machine-readable verifier combines the supported runtime, deployment, package, dashboard, and native checks. | No `scripts/verify_pilot_release.py` exists. | Add a bounded verifier that records failures and external/manual gates. |
| PILOT-OPS-004 | Pending evidence | SQLite durability | Older audits claim `SQLITE_BUSY` has no handling, while primary metrics and license stores configure WAL and busy timeouts. | `cutctx/storage/sqlite.py`, `cutctx_ee/billing/license_db.py`. | Add cross-connection contention regressions before accepting or refuting the claim. |

## Refuted or out-of-scope legacy claims

- Licensing and entitlement enforcement pass the focused contract suites.
- MCP registration and gateway coverage pass the focused registry suite.
- The supported OpenAI and Anthropic provider proxy paths pass their focused
  tests.
- Learn, memory-sync, DSR, and protocol-stub claims in `audit/release-audit.md`
  were refuted by `audit/release-audit-verification.md` or sit outside the
  supported pilot path.
- Self-serve checkout, SOC 2 procurement, Windows support, hosted Cutctx, and
  providers other than OpenAI and Anthropic are outside this assisted-pilot
  commitment.

## External launch sign-offs

The software work cannot close these items. The release owner must record them
before giving the customer paid access:

| Sign-off | Status |
| --- | --- |
| Contracting entity and approved pilot agreement | Open |
| Legal review of terms, privacy terms, and required DPA | Open |
| Payment or invoice confirmation | Open |
| Named support owner and response target | Open |
| Customer approval of data handling and telemetry | Open |
| Production change window and rollback owner | Open |

Open external sign-offs require a Conditional Go even if every software gate
passes.

## Remediation result

Candidate `b88669e3a19db4b42b2a71a15edf91c3725f67d5` closes every confirmed
software finding in this baseline:

- `PILOT-SEC-001`: resolved and covered for HTTP and WebSocket traffic.
- `PILOT-OPS-001`: resolved with required Compose credentials.
- `PILOT-OPS-002`: resolved with fail-fast Helm credential validation.
- `PILOT-OPS-003`: resolved through the pilot recovery and operations kit.
- `PILOT-QA-001`: resolved through the customer acceptance test.
- `PILOT-QA-002`: resolved through `scripts/verify_pilot_release.py`.
- `PILOT-OPS-004`: refuted by cross-connection SQLite contention tests.

The final verifier records 13 passed checks, zero failures, and zero skips in
`audit/pilot-verification.json`.
