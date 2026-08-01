<!-- markdownlint-disable MD013 -->

# Verified Security Audit Report

**Date:** 2026-07-31
**Final verification:** 2026-08-01
**Assessment:** No critical or high-severity application vulnerability reproduced

## Corrected findings

| Generated claim | Verification |
| --- | --- |
| No error tracking | False. `cutctx/observability/error_tracking.py` is initialized by the proxy and tested; it is a no-op until configured. |
| No CSP | False. The proxy already emits a Content Security Policy for dashboard responses. |
| Missing auth backoff | Misframed. Per-IP admin-auth limiting and bounded bucket storage exist. Distributed-source throttling must be enforced by ingress/WAF infrastructure. |
| Egress policy should default deny | Unsafe recommendation for a provider proxy. Connected mode must reach customer-selected providers; offline mode is fail-closed. Per-request upstream overrides have independent loopback, credential, scheme, host/path, IP-literal, and egress checks. |
| K8s deny-all egress | Not implementable as a static provider allowlist without breaking custom endpoints and DNS. Cluster policy should be deployment-specific. |
| F-string SQL injection | Not reproduced. Interpolated fragments are fixed or validated and values remain parameterized. |

## Security changes made

- WebSocket resource-exhaustion protection before any upstream connection.
- Compression-cache byte and entry limits to bound attacker-influenced retained values.
- Transactional Stripe replay protection across independent SQLite connections.
- Host-specific upstream routing: OpenCode remains under `/zen/go`; DeepSeek alone receives the root default.
- Caller-owned authorization is mandatory for request-selected upstreams, preventing operator-key exfiltration.
- Dashboard dependency audit reduced from seven high findings to zero.
- WebSocket admission rejection telemetry and Prometheus alerting.

## Operational security actions still requiring owners

| Action | Status |
| --- | --- |
| Alertmanager receivers, routing tree, and on-call owner | External operations decision; not present in repository. |
| Staging test-alert acknowledgement | Requires a staging monitoring stack and named receiver. |
| Deployment-specific egress policy | Must be generated from each customer's approved provider endpoints. |
| Legal/security review of `TERMS.md` and DPA | Requires counsel/organizational approval. |
| `security.txt` publication | Low-priority website/release task; disclosure instructions already exist in `SECURITY.md`. |

## Residual risk

The main residual security risk is operational: rules can fire in Prometheus, but the repository cannot prove a human receives them. This is explicitly documented rather than represented as an application-code vulnerability.

## Reproduction record

```bash
rtk pytest tests/test_secret_pattern_hook.py tests/test_openai_per_request_base_url.py tests/test_ws_session_registry.py tests/test_capability_extensions.py
rtk proxy .venv/bin/python scripts/check_secret_patterns.py
rtk npm audit --audit-level=high
```

The focused security run passed. The secret scanner checked Git-tracked and untracked nonignored files and found no committed credential pattern. The dashboard audit reported zero vulnerabilities.
Run the npm command from `dashboard/`; run the other commands from the repository root.
