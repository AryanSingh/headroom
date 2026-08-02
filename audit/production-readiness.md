# Production Readiness Assessment — Private EE

**Date:** 2026-08-02
**Candidate source:** `a33f67831a2e17f8fa229a5e08909a742c3dbe7d`

## Score

**Production readiness: 92/100 — Engineering Go for the supported private-release lane.**

| Area | Status | Evidence |
| --- | --- | --- |
| Configuration | Ready | Config validation, environment-based deployment, health/config endpoint |
| Secrets | Ready with external setup | Signing, private index, admin, provider, and client credentials are secret-backed and fail closed |
| Monitoring | Ready | Structured logs, Prometheus metrics, health/readiness endpoints, optional Sentry-compatible tracking |
| Alerting | Repository-ready; receiver setup external | Prometheus rules exist; production receiver and escalation owner must be named |
| Health checks | Ready | `/livez`, `/readyz`, `/health`, `/health/config` |
| Backups and restore | Documented | Backup manifests and restore runbooks exist |
| Rollback | Documented | Pilot upgrade/rollback procedures and release evidence contracts exist |
| CI/CD | Ready | Signed native EE build, archive verification, isolated smoke, evidence upload, and real private-index upload |
| Scalability | Supported lane constrained | Single-replica mutable state remains intentional until state is externalized |

## Artifact evidence

- Wheel: `cutctx_ee-0.31.0-cp312-cp312-macosx_26_0_arm64.whl`
- Wheel SHA-256: `c7b871a79a495ee6ad97f5eaa68969df12910586e4787c1315ad173a82f1fca2`
- Manifest SHA-256: `974fe7146aedbc76776cbccdf1ee8ffcb2ca4a2bd09bb2f4a2c26128bdd5acc2`
- Native modules: 33
- Verification and evidence: `/tmp/cutctx-ee-release.PT4EH6/`

The local artifact proves the release contract on macOS arm64/Python 3.12. The tag-triggered private workflow builds its declared Linux/Python 3.11 target and publishes only after verification.

## Required production configuration

1. Configure `CUTCTX_LICENSE_HMAC_SECRET`.
2. Configure `PRIVATE_PYPI_URL` and `PRIVATE_PYPI_TOKEN`.
3. Configure distinct admin, provider-route, and agent-client credentials.
4. Configure TLS termination, alert receivers, on-call ownership, and acknowledgement targets.
5. Run live provider acceptance plus backup/restore and rollback drills in the customer environment.
