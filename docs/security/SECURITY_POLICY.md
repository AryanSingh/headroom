# CutCtx Security Policy

**Version:** 1.0
**Effective Date:** 2026-06-15
**Owner:** Security Engineering, CutCtx
**Review Cycle:** Annual (or after any material architecture change)

---

## 1. Overview & Scope

CutCtx is a local-first LLM context compression proxy. All compression, tokenization, and state management occur **in-process at the customer site**. No customer prompts, completions, or derived data are transmitted to CutCtx infrastructure under any operational condition.

This policy governs:

- The CutCtx proxy binary and Python package (`cutctx`)
- License key issuance, validation, and revocation infrastructure
- Encrypted state files written to disk by the proxy
- CI/CD pipelines and release signing
- The cutctx-oauth2 SSO plugin (Enterprise tier)
- Kubernetes deployment manifests in `k8s/`

**Out of scope:** Third-party LLM provider security (OpenAI, Anthropic, etc.), customer network infrastructure, and customer-managed secrets such as LLM API keys.

**Security Owner:** security@cutctx.dev
For vulnerability reports, see Section 7 and `SECURITY.md` at the repository root.

---

## 2. Data Classification

CutCtx recognizes four data classification tiers. All handling decisions must align with the most restrictive tier that applies to any piece of data in a given context.

| Tier | Definition | Examples | Handling Requirements |
|------|-----------|----------|----------------------|
| **Public** | Information approved for unrestricted external distribution | Documentation, changelog, open-source code | No restrictions |
| **Internal** | Non-sensitive operational data limited to CutCtx personnel and systems | Aggregate compression metrics (no content), build logs, issue tracker entries | Access limited to employees; not published externally without review |
| **Confidential** | Business-sensitive data that could cause competitive or financial harm if disclosed | License key HMAC secrets, customer billing records, employee PII | Encrypted at rest; access on need-to-know basis; not transmitted in plaintext |
| **Restricted** | Highest sensitivity; regulatory or contractual obligations apply | Customer prompts and completions, PII within prompts | Must never leave customer infrastructure; no CutCtx system may receive or store this data |

**Customer prompt data is classified as Restricted.** The local-first architecture enforces this by design: the proxy intercepts and compresses traffic entirely within the customer's process boundary. CutCtx employees have no technical pathway to access prompt content.

---

## 3. Access Control Policy

### 3.1 License Key Issuance

License keys encode an `EntitlementTier` (BUILDER, TEAM, BUSINESS, or ENTERPRISE) and are signed with HMAC-SHA256 using a server-side secret (`HMAC_SECRET`).

**Issuance process:**

1. A CutCtx account holder completes purchase or trial activation via the customer portal.
2. The billing system invokes `cutctx license generate` with the customer's tier and optional expiry timestamp.
3. The resulting signed key is delivered to the customer over TLS; it is never transmitted in plaintext or logged.
4. Keys are recorded in the license registry with issuance timestamp, tier, and customer account ID.

**Who may run `cutctx license generate`:**

- Automated billing pipeline (service account, audited)
- On-call engineers with explicit approval in the issue tracker (break-glass procedure, audit-logged)
- No other personnel or systems

### 3.2 Entitlement Tier RBAC

Feature gates are enforced by the `EntitlementTier` hierarchy at runtime:

```
BUILDER < TEAM < BUSINESS < ENTERPRISE
```

A request presenting a TEAM key cannot access BUSINESS or ENTERPRISE features regardless of client-side configuration. Enforcement occurs in `cutctx/license.py` and the Rust `from_license_key_hmac` validator in `src/lib.rs`.

### 3.3 License Revocation

Revocation is effected by rotating the `HMAC_SECRET`. All previously issued keys immediately fail HMAC validation on the next request. Steps:

1. Generate new `HMAC_SECRET` via the key management system.
2. Re-issue replacement keys to all customers not subject to revocation.
3. Update the secret in all deployment environments (K8s secrets, CI/CD vault).
4. Confirm revocation by verifying the targeted key returns `401 Unauthorized`.
5. Document the revocation event in the incident or compliance log.

For individual key revocation (targeted compromise), the same rotation procedure applies; the scope of replacement issuance is limited to unaffected customers.

---

## 4. Encryption Standards

### 4.1 State Files at Rest

Proxy state files are encrypted using **Fernet** (AES-128-CBC with PKCS7 padding + HMAC-SHA256 authentication) as implemented in `cutctx/security/state_crypto.py`. Fernet provides authenticated encryption: any tampering with ciphertext is detected before decryption.

- Keys are derived per-deployment and must not be hardcoded or committed to source control.
- State file keys are rotated on license key rotation.
- Plaintext state must never be written to disk, even temporarily.

### 4.2 License Key Integrity

License key signatures use **HMAC-SHA256**. The signing secret (`HMAC_SECRET`) must:

- Be at least 256 bits of cryptographically random entropy.
- Be stored in a secrets manager (e.g., AWS Secrets Manager, HashiCorp Vault, Kubernetes Secret with envelope encryption).
- Never appear in logs, environment variable dumps, or error messages.

### 4.3 Data in Transit

- All proxy HTTPS mode connections require **TLS 1.2 minimum**; TLS 1.3 is preferred.
- TLS 1.0 and 1.1 are explicitly disabled in proxy configuration.
- Certificates must be issued by a trusted CA; self-signed certificates are permitted only in development/test environments with explicit opt-in.
- SSO/OIDC flows in the Enterprise tier use TLS for all token exchanges (see `plugins/cutctx-oauth2/`).

### 4.4 Prohibited Algorithms

The following algorithms are **prohibited** in all new code and must not be introduced via dependencies without explicit security review:

- MD5 (any use, including non-cryptographic)
- SHA-1 (except where mandated by legacy interoperability requirements, with documented justification)
- DES, 3DES, RC4
- RSA keys shorter than 2048 bits
- ECDH/ECDSA curves below 256 bits

---

## 5. Secure Development Lifecycle

### 5.1 Code Review

- All changes to `main` require at least one approved pull request review from a code owner listed in `CODEOWNERS`.
- Security-sensitive paths (crypto, license validation, auth) require review from a security-designated reviewer.
- Review approval is enforced via GitHub branch protection; force-pushes to `main` are disabled.

### 5.2 Dependency Management

- **Dependabot** is configured (`.github/dependabot.yml`) to open PRs for Python and Rust dependency updates on a weekly schedule.
- All Dependabot PRs require the same review gate as manual PRs.
- No dependency may be pinned to a version with a known critical CVE.

### 5.3 Rust Security Audits

- `cargo audit` runs on every CI build against the RustSec Advisory Database (`RUSTSEC`).
- A failing audit blocks merge unless a project maintainer explicitly marks the advisory as inapplicable with written justification in the PR.
- Advisory exceptions are reviewed at the next scheduled security review.

### 5.4 Static Analysis

- Python: `bandit` runs in CI for common security anti-patterns.
- Rust: `clippy` with `#![deny(unsafe_code)]` unless unsafe blocks are explicitly justified and reviewed.
- Secrets scanning: `gitleaks` or equivalent runs on every push to detect accidentally committed credentials.

### 5.5 Release Signing

- Release artifacts are signed using the project's GPG signing key.
- The signing key is held in the CI/CD secrets vault and never on developer machines.
- Release provenance follows the `release.yml` workflow in `.github/workflows/`.

---

## 6. Incident Response

CutCtx follows a five-phase incident response process:

### Phase 1: Detect

- Automated alerting via Prometheus metrics and structured audit log anomaly detection.
- Manual reports via security@cutctx.dev or internal escalation.
- All potential incidents are assigned a severity (P1-P4) within **24 hours** of detection.

### Phase 2: Contain

- Affected systems are isolated (license revocation, K8s network policy tightening, feature flag disable).
- Evidence is preserved before remediation; logs are exported to tamper-evident storage.
- Incident commander is assigned; communication channel opened.

### Phase 3: Eradicate

- Root cause identified and confirmed.
- Vulnerability patched or mitigated; affected credentials rotated.
- Patch deployed through normal CI/CD pipeline with expedited review for P1/P2.

### Phase 4: Recover

- Systems restored to normal operation after confirming eradication.
- Monitoring heightened for 72 hours post-recovery.
- Customer-facing services validated end-to-end.

### Phase 5: Post-mortem

- Blameless post-mortem completed within 5 business days for P1/P2 incidents.
- Action items tracked in the issue tracker with assigned owners and due dates.
- Post-mortem summary shared internally; redacted version provided to affected customers on request.

### SLAs

| Event | SLA |
|-------|-----|
| Initial triage and severity assignment | 24 hours |
| Customer notification for confirmed data breach | 72 hours |
| Critical (P1) patch deployment | 7 days |
| Post-mortem completion (P1/P2) | 5 business days |

---

## 7. Vulnerability Disclosure

CutCtx operates a responsible disclosure program.

**To report a vulnerability:** Email security@cutctx.dev with the information described in `SECURITY.md`. Do not open a public GitHub issue for unpatched vulnerabilities.

**Process:**

1. CutCtx acknowledges receipt within 48 hours.
2. CutCtx assesses severity and scope within 7 days.
3. Reporter is kept informed of remediation progress.
4. CutCtx targets a fix within **90 days** of confirmed report. Critical issues (CVSS 9.0+) are prioritized for resolution within 7 days.
5. A CVE is requested where applicable; the reporter is credited in the security advisory (with their permission).

**Safe harbor:** CutCtx will not pursue legal action against researchers who report in good faith, avoid accessing customer data, and do not disrupt service availability.

---

## 8. Penetration Testing

CutCtx conducts an annual penetration test covering the following scope:

| Test Area | Description |
|-----------|-------------|
| Proxy HTTP/HTTPS surface | All endpoints exposed by the proxy, including `/metrics`, compression routes, and any admin interfaces |
| License key validation | Attempts to forge, replay, or downgrade license keys; HMAC bypass; tier escalation |
| State file cryptography | Attempts to decrypt or tamper with Fernet-encrypted state files; key extraction |
| SSO/OIDC flow (Enterprise) | OAuth2 code flow, token validation, redirect URI manipulation |
| K8s deployment | Network policy bypass, pod escape, RBAC misconfiguration |

**Findings** are tracked as security issues with severity ratings. Critical and High findings block the next release until resolved. Medium and Low findings are scheduled within the following quarter.

Third-party customers may request access to the most recent penetration test executive summary under NDA.
