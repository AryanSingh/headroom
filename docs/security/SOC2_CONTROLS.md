# CutCtx SOC 2 Controls Mapping

**Version:** 1.0
**Effective Date:** 2026-06-15
**Audit Status:** SOC 2 Type I audit in preparation; target completion Q4 2026.

---

## Overview

CutCtx's local-first architecture significantly simplifies the SOC 2 control surface. Because all compression and tokenization occur in-process at the customer site, no customer data — prompts, completions, or derived artifacts — traverses CutCtx infrastructure. CutCtx systems handle only license key validation metadata, aggregate (non-content) telemetry where opted in, and billing information. This means the primary SOC 2 scope is limited to CutCtx's license issuance infrastructure, CI/CD systems, and the Kubernetes control plane used for internal services — not customer workloads.

The table below maps each relevant Trust Services Criteria (TSC) category to the specific controls CutCtx has implemented, the code or configuration that implements the control, and where evidence can be located for audit purposes.

---

## Trust Services Criteria Controls

| Trust Service Criteria | Control Description | Implementation | Evidence Location |
|------------------------|--------------------|--------------|--------------------|
| **CC6.1** Logical Access Controls | License keys are HMAC-SHA256 signed and validated on every request. EntitlementTier RBAC (BUILDER < TEAM < BUSINESS < ENTERPRISE) enforces feature access boundaries. No cross-tier privilege escalation is possible at runtime. | `headroom/license.py` (Python key parsing and tier enforcement); Rust `from_license_key_hmac` in `src/lib.rs` (cryptographic validation) | `src/lib.rs`, `headroom/license.py` |
| **CC6.2** Authentication Mechanisms | Enterprise tier customers authenticate via SSO/OIDC using the headroom-oauth2 plugin, supporting identity providers such as Okta, Azure AD, and Google Workspace. Team and Business tier customers authenticate via signed API key. All authentication events are recorded in structured audit logs. | `plugins/headroom-oauth2/` (OIDC flow, token validation, session management); `headroom/auth.py` (API key authentication middleware) | `plugins/headroom-oauth2/`, `headroom/auth.py` |
| **CC6.3** Access Removal | License expiry is enforced on every inbound request; expired keys return `401 Unauthorized` immediately without degraded-mode access. Mass revocation is achieved by rotating `HMAC_SECRET`, which invalidates all previously issued keys simultaneously. Targeted revocation follows the same rotation procedure scoped to the affected key series. | License validation on every request in `headroom/license.py`; `HMAC_SECRET` rotation runbook in `docs/security/SECURITY_POLICY.md` Section 3.3 | `headroom/license.py`, key management runbook |
| **CC7.1** System Monitoring | All compression events, license validation outcomes, and authentication results are written as structured JSON audit logs with timestamp, event type, license tier, and result code. A Prometheus metrics endpoint at `/metrics` exposes operational counters for external SIEM ingestion. No prompt content appears in logs. | `headroom/observability/` (log formatters, metrics exporters, audit sink) | `headroom/observability/`, Prometheus dashboard, audit log samples |
| **CC7.2** Anomaly Detection | Rate limiting is enforced per license tier to detect and suppress abnormal request volumes. Error thresholds trigger alerting when validation failure rates exceed baseline. Alerts route to the on-call channel via configured webhooks. | Rate limiting middleware in `headroom/proxy.py`; alert rules defined alongside Prometheus scrape config | `headroom/proxy.py`, alert rule definitions |
| **CC8.1** Change Management | All changes to `main` require a passing CI run and at least one approved code review from a designated code owner (enforced by GitHub branch protection and `CODEOWNERS`). Releases are built deterministically in GitHub Actions and artifacts are GPG-signed. No manual production deployments are permitted outside the pipeline. | `.github/workflows/release.yml` (build, test, sign, publish); `CODEOWNERS` (review gate) | `.github/workflows/release.yml`, GitHub PR history, signed release artifacts |
| **CC9.1** Risk Mitigation | Dependabot monitors Python and Rust dependencies weekly and opens remediation PRs automatically. `cargo audit` runs against the RustSec Advisory Database on every CI build, blocking merge on unresolved advisories. No PII or customer content is stored on CutCtx servers, eliminating the highest-impact data breach risk vector. | `.github/dependabot.yml`; `cargo audit` step in CI workflow; local-first architecture | `.github/dependabot.yml`, CI workflow logs, architecture documentation |
| **A1.1** Availability | Internal Kubernetes workloads use Horizontal Pod Autoscaler (HPA) to scale under load. Liveness and readiness probes ensure traffic is not routed to unhealthy pods. Enterprise tier carries a 99.5% monthly uptime SLA for license validation services. | `k8s/hpa.yaml` (autoscaling policy); `k8s/deployment.yaml` (probe configuration) | `k8s/hpa.yaml`, `k8s/deployment.yaml`, uptime monitoring records |

---

## Scope Clarification for Auditors

Because CutCtx is a local-first proxy, the following items are **explicitly out of scope** for a CutCtx SOC 2 audit:

- Customer prompt and completion data (processed exclusively within customer infrastructure)
- Customer LLM API keys (never transmitted to or stored by CutCtx)
- Customer Kubernetes clusters, networks, or compute environments
- Third-party LLM provider security posture (OpenAI, Anthropic, etc.)

Auditors should note that the primary residual risk surface is CutCtx's license issuance backend and internal CI/CD systems, which are the focus of the controls above.

---

## Audit Preparation Status

| Control Area | Status | Notes |
|-------------|--------|-------|
| Logical access controls | Implemented | License HMAC validation and RBAC active in production |
| Authentication | Implemented | SSO (Enterprise), API key (Team/Business) |
| Access removal | Implemented | Expiry enforced per-request; revocation runbook documented |
| System monitoring | Implemented | Structured audit logs and Prometheus metrics active |
| Anomaly detection | Implemented | Rate limiting active; alert rules defined |
| Change management | Implemented | Branch protection, CODEOWNERS, signed releases |
| Risk mitigation | Implemented | Dependabot, cargo audit in CI |
| Availability | Implemented | HPA and probes deployed in K8s |
| Formal SOC 2 Type I audit | In preparation | Target: Q4 2026 |
| SOC 2 Type II audit | Planned | To follow Type I completion |

---

*For questions about this controls mapping or to request audit evidence, contact security@headroom.dev.*
