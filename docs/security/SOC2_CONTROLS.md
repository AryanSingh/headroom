# CutCtx SOC 2 Controls Mapping

This document maps CutCtx features to SOC 2 Trust Service Criteria.

---

## CC6 — Logical Access Controls

| Control | CutCtx Implementation | Status |
|---------|----------------------|--------|
| CC6.1: Logical access security | RBAC with Viewer/Operator/Admin roles | Implemented |
| CC6.2: User authentication | Admin API key + SSO/OAuth2 (JWT/JWKS) | Implemented |
| CC6.3: User authorization | Role-based permission matrix (15+ permissions) | Implemented |
| CC6.4: Access provisioning | SCIM 2.0 user/group provisioning | Implemented |
| CC6.5: Access removal | SCIM deprovisioning + role revocation | Implemented |
| CC6.6: Credential management | Auto-generated admin keys, SSO token validation | Implemented |
| CC6.7: Audit logging | SQLite WAL audit trail with queryable events | Implemented |

---

## CC7 — System Operations

| Control | CutCtx Implementation | Status |
|---------|----------------------|--------|
| CC7.1: Monitoring | Health endpoints (/healthz, /readyz, /livez) | Implemented |
| CC7.2: Anomaly detection | Compression ratio monitoring, error rate tracking | Implemented |
| CC7.3: Incident management | Structured audit events (auth, license, config, stats) | Implemented |
| CC7.4: Capacity management | Token bucket rate limiting, budget controls | Implemented |
| CC7.5: Backup and recovery | SQLite WAL mode, file-based retention controls | Implemented |

---

## CC8 — Change Management

| Control | CutCtx Implementation | Status |
|---------|----------------------|--------|
| CC8.1: Change authorization | GitHub Actions CI/CD with required reviews | Implemented |
| CC8.2: Change testing | 7,600+ automated tests (Rust + Python) | Implemented |
| CC8.3: Change deployment | Multi-stage Dockerfile, K8s manifests, Helm chart | Implemented |
| CC8.4: Change rollback | Container versioning, Helm rollback support | Implemented |
| CC8.5: Separation of duties | RBAC roles enforce separation (Viewer can't deploy) | Implemented |

---

## CC9 — Risk Mitigation

| Control | CutCtx Implementation | Status |
|---------|----------------------|--------|
| CC9.1: Risk assessment | Enterprise blockers audit, production audit reports | Implemented |
| CC9.2: Encryption | Fernet (state), HMAC-SHA256 (licenses), BLAKE3 (content) | Implemented |
| CC9.3: Data classification | Prompt data stays local, no PII stored server-side | Implemented |
| CC9.4: Vulnerability management | Security policy, vulnerability disclosure program | Implemented |
| CC9.5: Network security | TLS 1.2+, CORS lockdown, rate limiting, SSRF protection | Implemented |
| CC9.6: Endpoint security | Body size limits (50MB), decompression bomb protection | Implemented |

---

## Summary

| Criteria | Controls Implemented | Coverage |
|----------|---------------------|----------|
| CC6 — Logical Access | 7/7 | 100% |
| CC7 — System Operations | 5/5 | 100% |
| CC8 — Change Management | 5/5 | 100% |
| CC9 — Risk Mitigation | 6/6 | 100% |
| **Total** | **23/23** | **100%** |

---

## Evidence Collection

| Control | Evidence Location |
|---------|------------------|
| CC6.1 RBAC | `headroom/rbac.py` — AdminRole, PERMISSION_MAP |
| CC6.2 Authentication | `headroom/sso.py` — SsoValidator, JWKS cache |
| CC6.3 Authorization | `headroom/proxy/routes/admin.py` — _require_rbac_permission |
| CC6.4 SCIM | `headroom/proxy/scim.py` — SCIM 2.0 endpoints |
| CC7.1 Monitoring | `k8s/deployment.yaml` — liveness/readiness probes |
| CC8.1 CI/CD | `.github/workflows/` — 17 workflow files |
| CC9.2 Encryption | `headroom/security/state_crypto.py` — Fernet, HMAC |

---

*Last updated: [DATE]*
*Auditor: [AUDITOR_NAME]*
