# CutCtx Security Policy

## 1. Data Classification

| Data Type | Classification | Storage | Retention |
|-----------|---------------|---------|-----------|
| Prompt content / LLM context | **Customer Confidential** | Customer infrastructure only | Customer-controlled |
| License keys | **Confidential** | Encrypted SQLite (local) | Duration of subscription |
| Usage telemetry (anonymized) | **Internal** | Provider infrastructure | 90 days |
| Audit logs | **Confidential** | Customer SQLite (WAL mode) | Customer-configurable (default 90 days) |
| Organization/user data | **Confidential** | Customer SQLite | Duration of subscription |

**Key principle:** No prompt data or LLM interactions ever leave Customer infrastructure.

---

## 2. Access Control Policy

### License Key Management
- License keys are generated using HMAC-SHA256 signatures
- Keys are format: `{tier}-{base64_payload}.{hmac_hex}`
- HMAC secret stored in environment variable `HEADROOM_LICENSE_HMAC_SECRET`
- Key validation is performed locally (no network call required)

### Admin Access
- Admin API key auto-generated on first startup (32-byte random)
- Can be overridden via `HEADROOM_ADMIN_API_KEY` environment variable
- All admin endpoints require authentication by default
- RBAC roles: Viewer (read-only), Operator (read + stats), Admin (full access)

### SSO/SAML
- JWT/JWKS validation with configurable JWKS cache TTL
- OIDC discovery endpoint support
- RFC 7662 token introspection
- Timing-safe comparison for all claim validation

---

## 3. Incident Response Procedure

### Detection
- Monitor audit log for anomalous patterns (failed auth, unusual access)
- Review compression error rates for potential data exposure
- Monitor system health endpoints (/health, /readyz)

### Response Steps
1. **Triage** (within 1 hour): Assess severity and scope
2. **Contain** (within 4 hours): Isolate affected systems
3. **Notify** (within 24 hours): Inform affected customers
4. **Remediate** (within 72 hours): Apply fix and verify
5. **Review** (within 1 week): Post-incident review and documentation

### Escalation
- Security incidents: [SECURITY_EMAIL]
- Data breaches: [DPO_EMAIL] + legal counsel
- System outages: [ONCALL_PHONE]

---

## 4. Vulnerability Disclosure

### Reporting
- Email: security@cutctx.dev
- GitHub Security Advisories: enabled on repository
- Response time: acknowledgment within 48 hours

### Scope
- CutCtx core (Rust + Python)
- Proxy server
- SDK clients
- Documentation site

### Safe Harbor
We will not pursue legal action against researchers who:
- Follow responsible disclosure practices
- Do not access customer data
- Do not disrupt production systems
- Report vulnerabilities promptly

---

## 5. Encryption Standards

| Use Case | Algorithm | Implementation |
|----------|-----------|---------------|
| State encryption | Fernet (AES-128-CBC + HMAC-SHA256) | `headroom/security/state_crypto.py` |
| License key signing | HMAC-SHA256 | `headroom/security/state_crypto.py` |
| Content hashing (CCR) | BLAKE3 (16-hex) | `crates/headroom-core/src/ccr/mod.rs` |
| Content hashing (SmartCrusher) | SHA-256 (12-hex) | `crates/headroom-core/src/transforms/smart_crusher/` |
| Data in transit | TLS 1.2+ | Recommended for proxy deployment |
| Data at rest | AES-256 | Recommended for SQLite databases |

---

## 6. Network Security

### Proxy Endpoints
- `/livez`, `/readyz` — Health probes (open, no auth required)
- `/v1/messages`, `/v1/chat/completions`, `/v1/responses` — Compression proxy (API key required)
- All other endpoints — Admin auth required

### CORS Policy
- Default: Closed (empty allowed origins list)
- Configurable via `HEADROOM_CORS_ORIGINS` environment variable
- Wildcard (`*`) only for development

### Rate Limiting
- Token bucket per-client rate limiting on proxy endpoints
- Configurable requests-per-minute and tokens-per-minute limits
- 429 response with `Retry-After` header when exceeded

---

## 7. Compliance Roadmap

### SOC 2 Type II (Target: Q2 2026)
- [ ] CC6: Logical access controls (RBAC, SSO, SCIM) — Implemented
- [ ] CC7: System operations (health checks, observability) — Implemented
- [ ] CC8: Change management (CI/CD, code review) — Implemented
- [ ] CC9: Risk mitigation (encryption, local-first) — Implemented
- [ ] Documentation and policy review — In Progress

### GDPR/CCPA
- Data processing addendum (DPA) available
- Right to deletion supported via retention controls
- No PII stored server-side (local-first architecture)

### ISO 27001 (Target: Q4 2026)
- Security management system documentation
- Risk assessment and treatment
- Internal audit program

---

*Last updated: [DATE]*
*Review frequency: Quarterly*
