# Cutctx SOC 2 Controls Mapping

**Version:** 1.0
**Effective Date:** 2026-06-15
**Audit Status:** SOC 2 Type I audit in preparation; target completion Q4 2026.

---

## Overview

Cutctx's local-first architecture significantly simplifies the SOC 2 control surface. Because all compression and tokenization occur in-process at the customer site, no customer data — prompts, completions, or derived artifacts — traverses Cutctx infrastructure. Cutctx systems handle only license key validation metadata, aggregate (non-content) telemetry where opted in, and billing information. This means the primary SOC 2 scope is limited to Cutctx's license issuance infrastructure, CI/CD systems, and the Kubernetes control plane used for internal services — not customer workloads.

The table below maps each relevant Trust Services Criteria (TSC) category to the specific controls Cutctx has implemented, the code or configuration that implements the control, and where evidence can be located for audit purposes.

---

## Trust Services Criteria Controls

| Trust Service Criteria | Control Description | Implementation | Evidence Location |
|------------------------|--------------------|--------------|--------------------|
| **CC6.1** Logical Access Controls | License keys are HMAC-SHA256 signed and validated on every request. EntitlementTier RBAC (BUILDER < TEAM < BUSINESS < ENTERPRISE) enforces feature access boundaries. No cross-tier privilege escalation is possible at runtime. | `cutctx_ee/billing/license_validation.py` (Python key parsing and tier enforcement); Rust `from_license_key_hmac` in `crates/cutctx-parity/` (cryptographic validation) | `cutctx_ee/billing/`, `crates/cutctx-parity/` |
| **CC6.2** Authentication Mechanisms | Enterprise tier customers authenticate via SSO/OIDC using the `cutctx_ee/sso.py` validator, supporting identity providers such as Okta, Azure AD, and Google Workspace. Team and Business tier customers authenticate via signed API key. **NOTE:** the OIDC signature verification path is currently conditional on `PyJWT` and bypasses the check if PyJWT is missing. Audit-event emission for `auth.login`, `auth.failed`, `auth.key_rotated` is defined in the enum but not yet wired into the live auth path. | `cutctx_ee/sso.py` (OIDC/JWKS validator); `cutctx/proxy/server.py:2280-2343` (admin auth + `_require_admin_auth` dependency) | `cutctx_ee/sso.py`, `cutctx/proxy/server.py` |
| **CC6.3** Access Removal | License expiry is enforced on every inbound request; expired keys return `401 Unauthorized` immediately without degraded-mode access. Mass revocation is achieved by rotating `CUTCTX_AUDIT_SECRET_KEY`, which invalidates all previously issued tamper-evident audit log hashes simultaneously. Targeted revocation follows the same rotation procedure scoped to the affected license. | `cutctx_ee/billing/license_db.py` (license validation on every request); `cutctx_ee/audit/store.py:24-50` (audit secret-key resolution) | `cutctx_ee/billing/`, `cutctx_ee/audit/store.py` |
| **CC6.6** GDPR/CCPA Data Subject Requests | End users may export or delete every record the system holds for their user_id via `/v1/me/export` and `/v1/me/delete`. The endpoints cascade the deletion across memory, spend ledger, and audit log. Best-effort: each store reports per-backend counts. **NOTE:** spend ledger and audit log delete paths require EE module extensions (`delete_spend_for_user` and `AuditLogger.delete_for_actor`) that are documented but not yet shipped. | `cutctx/proxy/routes/dsr.py` (new DSR routes); `cutctx/proxy/memory_handler.py` (`delete_for_user` + `export_for_user`) | `cutctx/proxy/routes/dsr.py`, `cutctx/proxy/memory_handler.py` |
| **CC7.1** System Monitoring | All compression events, license validation outcomes, and authentication results are written as structured JSON audit logs with timestamp, event type, license tier, and result code. A Prometheus metrics endpoint at `/metrics` exposes operational counters for external SIEM ingestion. No prompt content appears in logs. The audit log is tamper-evident via an HMAC-SHA256 hash chain over a canonical length-prefixed message. **NOTE:** `/metrics` is admin-gated; the `CUTCTX_AUDIT_SECRET_KEY` env var is now required to start the chain store (with `CUTCTX_ALLOW_DEV_AUDIT_KEY=1` for local dev only). | `cutctx/proxy/prometheus_metrics.py` (Prometheus exporter); `cutctx_ee/audit/store.py` (hash-chain log); `cutctx/proxy/server.py:1366-1375` (metrics endpoint) | `cutctx/proxy/prometheus_metrics.py`, `cutctx_ee/audit/`, Prometheus dashboard, audit log samples |
| **CC7.2** Anomaly Detection | Rate limiting is enforced per IP to detect and suppress abnormal request volumes. **GAP:** rate limiting is NOT per-license-tier or per-user; it is per-source-IP only. The LLM firewall (`cutctx/security/firewall.py`) remains regex-based and off by default, and the streaming redactor is not a completed anomaly-detection control. Alert delivery is no longer a stub: the proxy ships a signed outbound webhook dispatcher with persisted subscriptions, retry/backoff, and a dead-letter queue. Operators must configure subscriptions and monitor the DLQ. | Rate limiting middleware; `cutctx/proxy/webhooks.py`; `cutctx/proxy/webhook_stores.py` | `cutctx/proxy/server.py`, `cutctx/proxy/webhooks.py`, `cutctx/proxy/webhook_stores.py` |
| **CC8.1** Change Management | All changes to `main` require a passing CI run and at least one approved code review from a designated code owner (enforced by GitHub branch protection). Releases are built deterministically in GitHub Actions. **NOTE:** the `CODEOWNERS` file referenced in earlier drafts is NOT in this repository; review enforcement relies on GitHub branch protection alone. | `.github/workflows/release.yml` (build, test, publish); GitHub branch protection | `.github/workflows/`, GitHub PR history, release artifacts |
| **CC9.1** Risk Mitigation | Dependabot monitors Python and Rust dependencies weekly and opens remediation PRs automatically. `cargo audit` runs against the RustSec Advisory Database on every CI build, blocking merge on unresolved advisories. **GAP:** admin API key, when auto-generated, was previously logged in plaintext to the Python logger. As of commit `fe32040` the key is printed to stderr only (not the logger), and a separate log line is emitted without the key value. | `.github/dependabot.yml` (if present); `cargo audit` step in CI workflow; `cutctx/proxy/server.py:2252-2278` (admin key handling) | `.github/dependabot.yml` (if present), CI workflow logs, `cutctx/proxy/server.py` |
| **A1.1** Availability | Internal Kubernetes workloads use Horizontal Pod Autoscaler (HPA) to scale under load. Liveness and readiness probes ensure traffic is not routed to unhealthy pods. Health endpoints `/livez`, `/readyz`, `/health` are implemented and Docker healthchecks call `/readyz`. **GAP:** no DR plan, no capacity planning, no documented recovery procedure. Automated backup currently covers the memory database, spend ledger, and audit database only; the remaining EE stores are still outside the backup job scope. Enterprise tier carries a 99.5% monthly uptime SLA target. | `k8s/hpa.yaml` (autoscaling policy); `k8s/deployment.yaml` (probe configuration); `cutctx/proxy/server.py:2617-2641` (health endpoints); `k8s/backup-cronjob.yaml` (memory/spend/audit DB daily) | `k8s/`, `cutctx/proxy/server.py`, uptime monitoring records |

---

## Scope Clarification for Auditors

Because Cutctx is a local-first proxy, the following items are **explicitly out of scope** for a Cutctx SOC 2 audit:

- Customer prompt and completion data (processed exclusively within customer infrastructure)
- Customer LLM API keys (never transmitted to or stored by Cutctx)
- Customer Kubernetes clusters, networks, or compute environments
- Third-party LLM provider security posture (OpenAI, Anthropic, etc.)

Auditors should note that the primary residual risk surface is Cutctx's license issuance backend and internal CI/CD systems, which are the focus of the controls above.

---

## Audit Preparation Status

| Control Area | Status | Notes |
|-------------|--------|-------|
| Logical access controls | **Implemented** | License HMAC validation and RBAC active in production. All EE routes (spend, policy, audit, memory, license, providers) are now behind admin auth + RBAC. |
| Authentication | **Partial** | SSO (Enterprise, OIDC) and API key (Team/Business) are both implemented. OIDC signature verification has a known gap when PyJWT is missing. MFA and SAML are not yet implemented. |
| Access removal | **Implemented** | Expiry enforced per-request; revocation runbook documented; tamper-evident audit log secret rotation invalidates all hashes simultaneously. |
| GDPR/CCPA DSR | **Partial** | `/v1/me/export` and `/v1/me/delete` endpoints are wired and require admin auth. Spend ledger + audit log delete paths require EE module extensions that are documented but not yet shipped. |
| System monitoring | **Partial** | Structured audit logs and Prometheus metrics active. Hash-chain store is implemented. 8+ enum events (`auth.login`, `auth.failed`, etc.) are defined but not emitted. |
| Anomaly detection | **Partial** | Rate limiting active (per-IP only — not per-tier). LLM firewall regex-based, off by default. Streaming redactor is not a completed detection control. Signed webhook dispatch, retries, and DLQ are shipped; subscriptions/DLQ monitoring remain operational requirements. |
| Change management | **Partial** | Branch protection enabled. `CODEOWNERS` file is missing; relies on GitHub branch protection alone for review enforcement. |
| Risk mitigation | **Partial** | `cargo audit` in CI. Admin API key no longer logged in plaintext (commit `fe32040`). Dependabot file not present in this checkout. |
| Availability | **Partial** | HPA and probes deployed in K8s. Health endpoints implemented. No DR plan, no capacity planning, no documented recovery procedure. Automated backup currently covers memory, spend-ledger, and audit databases only. |
| Formal SOC 2 Type I audit | In preparation | Target: Q4 2026 |
| SOC 2 Type II audit | Planned | To follow Type I completion |

---

*For questions about this controls mapping or to request audit evidence, contact security@cutctx.com.*
