# CutCtx — Vendor Security Questionnaire

Pre-filled answers to common enterprise security questionnaire questions.

---

## 1. Data Handling

**Q: Where is customer data stored?**
A: All prompt data and LLM context remains on customer infrastructure. CutCtx operates as a local-first compression proxy. No prompt data ever leaves the customer's environment.

**Q: Is any customer data transmitted to third parties?**
A: No. CutCtx does not transmit prompt data to any third party. Anonymized usage metrics (compression ratios, token counts) may be transmitted unless opted out.

**Q: How is customer data encrypted?**
A: State data uses Fernet encryption (AES-128-CBC + HMAC-SHA256). License keys use HMAC-SHA256 signatures. Content hashing uses BLAKE3. Data in transit should use TLS 1.2+.

**Q: What is your data retention policy?**
A: Customer-configurable. Default: audit logs 90 days, CCR cache 7 days, episodic memory 30 days. All retention controls are configurable via CLI flags.

**Q: Can customer data be exported?**
A: Yes. All data is stored in standard SQLite databases. Export available via audit log JSONL export and direct file access.

---

## 2. Access Control

**Q: How are admin access controls implemented?**
A: Auto-generated 32-byte API key on first startup. RBAC with three roles: Viewer (read-only), Operator (read + stats), Admin (full access). All admin endpoints require authentication.

**Q: Do you support SSO/SAML?**
A: Yes. JWT/JWKS validation, OIDC discovery, and RFC 7662 token introspection. Configurable via environment variables.

**Q: Is multi-factor authentication supported?**
A: MFA is handled at the identity provider level (Okta, Azure AD, etc.) when SSO is configured. CutCtx does not manage MFA directly.

**Q: How are API keys managed?**
A: API keys are stored locally. License keys use HMAC-SHA256 signatures for validation. No central key management service required.

---

## 3. Network Security

**Q: What network ports does CutCtx use?**
A: Default proxy port: 8787. All other communication is outbound (to LLM providers). No inbound connections required for core functionality.

**Q: Is TLS supported?**
A: Yes. CutCtx supports TLS termination at the proxy level. Recommended for production deployments.

**Q: How do you prevent SSRF?**
A: Structured output module validates API endpoint URLs against an allowlist of approved hosts (api.anthropic.com, api.openai.com, generativelanguage.googleapis.com).

**Q: What rate limiting is in place?**
A: Token bucket rate limiting on proxy endpoints. Configurable requests-per-minute and tokens-per-minute. Returns 429 with Retry-After header.

---

## 4. Application Security

**Q: How do you handle vulnerabilities?**
A: Security policy with responsible disclosure program. GitHub Security Advisories enabled. Response time: acknowledgment within 48 hours.

**Q: Do you perform security testing?**
A: Yes. Fuzz testing with cargo-fuzz for Rust core. 7,600+ automated tests. Static analysis via Clippy. Decompression bomb protection.

**Q: Is there an audit trail?**
A: Yes. SQLite WAL audit log with structured events (auth, license, config, stats, entitlement, policy, retention, system). Queryable via API and exportable as JSONL.

**Q: How do you handle secrets?**
A: No hardcoded secrets. Environment variable configuration. Auto-generated admin keys. License keys use HMAC-SHA256 signatures.

---

## 5. Compliance

**Q: Are you SOC 2 certified?**
A: SOC 2 Type II readiness controls are implemented (see SOC2_CONTROLS.md). Formal audit targeted for Q2 2026.

**Q: Do you support GDPR/CCPA?**
A: Yes. Data processing addendum available. Local-first architecture means minimal PII processing. Right to deletion supported via retention controls.

**Q: Is there a DPA available?**
A: Yes. See docs/legal/DPA_TEMPLATE.md for the Data Processing Addendum template.

**Q: Do you support air-gapped deployments?**
A: Yes. CutCtx can operate completely offline. All compression, caching, and license validation work locally.

---

## 6. Deployment

**Q: What deployment options are available?**
A: Local (pip install), Docker, Kubernetes (manifests + Helm chart), air-gapped. Single binary for Rust proxy (~50MB).

**Q: What are the resource requirements?**
A: Minimum: 256MB RAM, 1 CPU. Recommended: 512MB RAM, 2 CPU. Storage depends on CCR cache size.

**Q: Is there a health check endpoint?**
A: Yes. `/healthz` (full health), `/readyz` (readiness), `/livez` (liveness). Compatible with Kubernetes probes.

**Q: How do you handle updates?**
A: Standard package manager updates (pip, npm). Docker images tagged by version. Helm chart supports rolling updates.

---

## 7. Incident Response

**Q: What is your incident response process?**
A: Triage within 1 hour, containment within 4 hours, customer notification within 24 hours, remediation within 72 hours, post-incident review within 1 week.

**Q: How are security incidents communicated?**
A: Email to affected customers. Security advisory published on GitHub. Audit log events for forensic analysis.

---

*Last updated: [DATE]*
*For questions: security@cutctx.dev*
