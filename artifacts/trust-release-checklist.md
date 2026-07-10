# Trust Release Checklist

Version: 1.0

This checklist is the release gate for reviewer-facing trust claims. A claim is
only marked available when the listed code, test, and documentation evidence
are current for the release.

| Claim | Status | Code/Test Evidence | Owner | External Dependency |
|---|---|---|---|---|
| Admin authentication and RBAC | Available | `tests/test_ccr_admin_auth.py`, `tests/test_route_modules.py` | Engineering | None |
| Audit and retention controls | Available | `docs/audit-compliance.md`, `docs/security-and-privacy.md` | Engineering | Customer configuration |
| Webhook delivery and dead-letter handling | Available | `cutctx/proxy/webhooks.py`, `cutctx/proxy/webhook_stores.py`, webhook tests | Engineering | Operator subscription/DLQ monitoring |
| Rate-limit anomaly control | Partial | `tests/test_rate_limiter.py` | Engineering | Per-license/user limiting remains planned |
| Remote hosted proof | Pending external staging | `scripts/run_remote_hosted_smoke.py` | Platform | Staging URL and API key |
| Design-partner telemetry | Pending external collection | `cutctx report agent-context` | Customer Success | Two consented seven-day snapshots |
| DPA/MSA approval | External legal review required | `artifacts/legal/DPA_TEMPLATE.md`, `artifacts/legal/MSA_TEMPLATE.md` | Legal | Signed review |
| SOC 2 / penetration testing | Not represented as completed | `docs/security/SOC2_CONTROLS.md` | Security | External audit/test engagement |

## Release Rules

- Do not describe a `Partial`, `Pending`, or `External` row as shipped.
- Attach the benchmark release manifest and remote-hosted/staged-gateway
  artifacts when available.
- Revalidate this checklist for every release that changes proxy auth,
  retention, rate limiting, telemetry, or webhook behavior.
- Follow `docs/release-evidence-runbook.md` for staging execution, benchmark
  regeneration, and the two design-partner evidence submissions.
