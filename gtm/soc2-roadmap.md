# Cutctx SOC 2 Compliance Roadmap

## Overview

SOC 2 Type II compliance demonstrates that Cutctx maintains appropriate security, availability, and confidentiality controls. This roadmap covers the journey from readiness assessment to audit completion.

## Timeline

| Phase | Duration | Milestone |
|-------|----------|-----------|
| 1. Readiness Assessment | Weeks 1-2 | Gap analysis complete |
| 2. Control Implementation | Weeks 3-8 | All controls in place |
| 3. Evidence Collection | Weeks 9-12 | Documentation complete |
| 4. Audit Period | Weeks 13-24 | 6-month observation period |
| 5. Audit Execution | Weeks 25-28 | Type II audit |
| 6. Report Delivery | Week 30 | SOC 2 Type II report |

**Total: ~7.5 months from start to report**

## Trust Service Criteria

Cutctx will pursue SOC 2 Type II under these criteria:

### Security (Common Criteria)
- [x] Logical access controls (SSO/OIDC, RBAC)
- [x] Network security (firewalls, encryption in transit)
- [x] Data encryption (Fernet AES-128-CBC + HMAC-SHA256 at rest, TLS 1.3 in transit)
- [x] Tamper-evident audit log (HMAC hash chain) — see `cutctx_ee/audit/store.py`
- [x] Admin API key handling (no plaintext log on auto-generation) — see `cutctx/proxy/server.py:2252-2278`
- [x] EE route surface behind admin auth + RBAC (Blocker-1 fix in commit `2b49ee76`)
- [ ] Vulnerability management program
- [ ] MFA on admin access
- [ ] SAML SSO
- [ ] Incident response plan
- [ ] Security monitoring and alerting

### Availability
- [x] Uptime monitoring (99.9% SLA target)
- [x] Backup and recovery procedures (memory DB daily, spend ledger TODO)
- [x] Health endpoints (`/livez`, `/readyz`, `/health`)
- [x] Per-provider circuit breaker (`cutctx/proxy/routing/failover.py`)
- [x] Pipeline circuit breaker (`cutctx/transforms/pipeline.py`)
- [ ] Disaster recovery plan
- [ ] Capacity planning
- [ ] Performance monitoring

### Confidentiality
- [x] Data classification
- [x] Access controls on sensitive data
- [x] GDPR/CCPA DSR endpoints (Blocker-2 fix in commit `<DSR>`)
- [ ] Data retention policies (RetentionManager exists; not yet on by default)
- [ ] Third-party risk management
- [ ] Confidentiality agreements

## Required Controls

### Access Controls
| Control | Status | Owner | Notes |
|---------|--------|-------|-------|
| SSO/OIDC for all employees | ⚠️ Partial | Engineering | Implemented but PyJWT path bypasses signature verification |
| RBAC for production systems | ✅ Implemented | Engineering | 4 roles, 25+ permissions, ~40 admin routes enforce |
| MFA for all admin access | 📋 To implement | Security | Not implemented |
| Quarterly access reviews | 📋 To implement | Security | |
| Principle of least privilege | ✅ Implemented | Engineering | All EE routes gated; `_require_rbac_permission` factory |

### Data Protection
| Control | Status | Owner | Notes |
|---------|--------|-------|-------|
| Encryption at rest (AES-256) | ⚠️ Partial | Engineering | **Fernet = AES-128-CBC + HMAC-SHA256** (NOT AES-256). See `cutctx/security/state_crypto.py` |
| Encryption in transit (TLS 1.3) | ✅ Implemented | Engineering | Mitigated by deployment (uTLS/ingress) |
| Key management (rotation) | ⚠️ Partial | Security | `CUTCTX_AUDIT_SECRET_KEY` enforced (Blocker-9 fix); admin key rotation is manual |
| Data classification | ✅ Implemented | Security | |
| Secure deletion procedures | ⚠️ Partial | Engineering | DSR endpoints added (Blocker-2 fix); VACUUM pass is post-DSR follow-up |

### Monitoring & Logging
| Control | Status | Owner | Notes |
|---------|--------|-------|-------|
| Audit logging | ✅ Implemented | Engineering | Hash-chain store (Blocker-9 fix); 8+ enum events defined but not all emitted |
| Centralized log aggregation | 📋 To implement | DevOps | No SIEM integration; logs are local files |
| Security alerting | 📋 To implement | Security | `cutctx_ee/abuse.py` generates alerts but does not deliver them |
| Incident response plan | 📋 To implement | Security | |
| Regular security scans | 📋 To implement | Security | |

### Business Continuity
| Control | Status | Owner | Notes |
|---------|--------|-------|-------|
| Automated backups | ✅ Implemented | DevOps | `k8s/backup-cronjob.yaml` covers `cutctx_memory.db`, `spend_ledger.db`, and `audit.db`; 30-day retention in S3; pruned via `aws s3api list-objects-v2` |
| Recovery procedures | 📋 To implement | DevOps | |
| DR plan documentation | 📋 To implement | DevOps | |
| Regular DR testing | 📋 To implement | DevOps | |
| Capacity planning | 📋 To implement | DevOps | |

## Action Items

### Phase 1: Readiness (Weeks 1-2)
1. Engage SOC 2 auditor (recommend Vanta or Drata)
2. Complete gap analysis against Trust Service Criteria
3. Document current controls and identify gaps
4. Create remediation plan

### Phase 2: Implementation (Weeks 3-8)
1. Implement missing controls (see tables above)
2. Create policies:
   - Information Security Policy
   - Acceptable Use Policy
   - Incident Response Plan
   - Business Continuity Plan
   - Vendor Management Policy
   - Data Retention Policy
3. Set up continuous monitoring
4. Train employees on security policies

### Phase 3: Evidence Collection (Weeks 9-12)
1. Collect evidence for all controls
2. Document procedures and workflows
3. Set up automated evidence collection
4. Create auditor access procedures

### Phase 4: Audit Period (Weeks 13-24)
1. Maintain controls for 6 months
2. Collect ongoing evidence
3. Address any findings from auditor observations
4. Conduct internal reviews

### Phase 5: Audit Execution (Weeks 25-28)
1. Auditor performs testing
2. Respond to auditor inquiries
3. Address any exceptions
4. Review draft report

### Phase 6: Report Delivery (Week 30)
1. Receive final SOC 2 Type II report
2. Share with customers as needed
3. Plan for annual renewal

## Cost Estimate

| Item | Cost |
|------|------|
| Auditor (Vanta/Drata) | $10,000-20,000/yr |
| Audit firm | $15,000-30,000 |
| Internal time (~200 hours) | ~$20,000 |
| **Total** | **$45,000-70,000** |

## Benefits

1. **Enterprise sales**: Many enterprises require SOC 2 before purchasing
2. **Trust**: Demonstrates security commitment to customers
3. **Competitive advantage**: Differentiator vs competitors without SOC 2
4. **Risk reduction**: Identifies and fixes security gaps
5. **Insurance**: May reduce cyber insurance premiums

## Next Steps

1. [ ] Select auditor (Vanta recommended for startups)
2. [ ] Schedule readiness assessment
3. [ ] Assign control owners
4. [ ] Begin Phase 1

---

*Last updated: June 2026*
*Owner: Cutctx Security Team*
