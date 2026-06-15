# CutCtx Vendor Security Questionnaire

**Version:** 1.0
**Effective Date:** 2026-06-15
**Prepared by:** Security Engineering, CutCtx
**Contact:** security@headroom.dev

This document provides pre-filled responses to common enterprise security questionnaire questions. For questions not addressed here, or to request supporting documentation (penetration test executive summary, SOC 2 report when available), contact security@headroom.dev.

---

## Data Security

**Q1. Where is customer data stored?**

Customer data — including all prompts, completions, and derived content — is never transmitted to or stored by CutCtx. CutCtx is a local-first proxy: all compression and tokenization occur in-process within the customer's own infrastructure. The only data CutCtx stores is license key metadata (tier, expiry, issuance timestamp) and, where opted in, aggregate non-content telemetry (e.g., compression ratios, token counts without content).

**Q2. Is data encrypted at rest?**

Yes, for all data that CutCtx does store. Proxy state files are encrypted using Fernet (AES-128-CBC + HMAC-SHA256 authenticated encryption). License key signing secrets are stored in a secrets manager with encryption at rest. Customer prompt data is not stored by CutCtx under any circumstances.

**Q3. Is data encrypted in transit?**

Yes. All communications with CutCtx services (license validation, telemetry opt-in) use TLS 1.2 minimum; TLS 1.3 is preferred. TLS 1.0 and 1.1 are explicitly disabled. The local proxy itself, when operating in HTTPS mode, also enforces TLS 1.2+ for connections between the customer application and the proxy.

**Q4. What is your data retention policy?**

CutCtx retains license metadata for the duration of the customer relationship plus 12 months (for billing dispute resolution), after which it is deleted. Aggregate telemetry, where opted in, is retained for 24 months. Customer prompts and completions are never retained by CutCtx because they are never received.

**Q5. Are backups encrypted?**

Yes. All backups of CutCtx-managed data (license registry, billing records) are encrypted at rest using the same standards as primary storage. Backup encryption keys are managed separately from production keys.

**Q6. What is your backup frequency and recovery capability?**

The license issuance backend is backed up daily with point-in-time recovery capability. Recovery Time Objective (RTO) is 4 hours; Recovery Point Objective (RPO) is 24 hours for standard tier; Enterprise customers may negotiate enhanced RPO/RTO as part of their agreement.

**Q7. How is data destroyed upon contract termination?**

Upon contract termination, CutCtx deletes all customer account data (license records, billing information, opted-in telemetry) within 30 days of termination date. A deletion confirmation is provided upon request. Because customer prompts are never stored by CutCtx, no customer content destruction is required.

**Q8. Do you share customer data with third parties?**

No customer content is shared because none is received. License metadata and billing information are shared with payment processors (subject to PCI DSS) and, in limited cases, required by law. A current sub-processors list is available upon request.

**Q9. Do you perform data loss prevention (DLP) scanning?**

DLP controls are applied to CutCtx internal systems (CI/CD, code repositories, communication tools) to prevent inadvertent exposure of confidential data such as signing secrets. DLP scanning of customer prompts is not applicable because that data never reaches CutCtx systems.

**Q10. Is there a data processing agreement (DPA) available?**

Yes. CutCtx provides a standard DPA aligned with GDPR Article 28 requirements. The DPA is available upon request and is required for customers in the EU/EEA. For Enterprise customers, custom DPA terms may be negotiated.

---

## Access Control

**Q11. Is multi-factor authentication (MFA) required?**

Yes, MFA is required for all CutCtx employee access to production systems, code repositories, CI/CD pipelines, and the customer billing portal. Customers are encouraged but not currently required to enable MFA on their CutCtx account portal.

**Q12. Is Single Sign-On (SSO) supported?**

Yes. Enterprise tier customers can configure SSO/OIDC authentication via the headroom-oauth2 plugin, supporting major identity providers including Okta, Azure Active Directory, Google Workspace, and any OIDC-compliant IdP. Team and Business tier customers use signed API key authentication.

**Q13. Is SCIM-based user provisioning supported?**

SCIM provisioning is on the Enterprise roadmap. Current Enterprise customers can manage license seat assignments through the customer portal or via the management API. Contact sales@headroom.dev to discuss provisioning integration requirements.

**Q14. Does your product follow a least-privilege access model?**

Yes. The EntitlementTier RBAC model (BUILDER < TEAM < BUSINESS < ENTERPRISE) enforces strict least-privilege at the feature level: a customer's license key grants access only to features at or below their contracted tier. This is enforced cryptographically on every request and cannot be overridden by client-side configuration.

**Q15. How is privileged access to production systems managed?**

CutCtx uses a just-in-time privileged access model. Production access requires an approved issue tracker entry for the specific task (break-glass procedure). All privileged sessions are logged and reviewed. Standing privileged access is not granted to any individual.

**Q16. How frequently are access rights reviewed?**

CutCtx conducts quarterly access reviews for all internal systems. Contractor and vendor access is reviewed monthly. Terminated employees are deprovisioned within 24 hours of separation.

**Q17. Is role-based access control (RBAC) implemented?**

Yes, at two levels. Internally, CutCtx employees access systems based on role-defined permissions with least-privilege enforcement. For customers, the EntitlementTier RBAC model controls feature access as described above. Kubernetes deployments use K8s RBAC with network policies to enforce pod-level access boundaries.

**Q18. How are shared accounts or service accounts managed?**

Shared accounts are prohibited for human users. Service accounts (e.g., the billing pipeline's license generation account) are purpose-limited, rotated quarterly, and have their activity logged. Service account credentials are stored in the secrets manager, not in code or environment variables.

---

## Infrastructure

**Q19. Is CutCtx cloud-based or on-premises?**

CutCtx's license issuance and management infrastructure is cloud-hosted. The CutCtx proxy itself — which handles all customer data — runs entirely on-premises within the customer's own infrastructure. This hybrid model means customer data never leaves the customer's environment.

**Q20. Which cloud provider(s) do you use for your own infrastructure?**

CutCtx's internal infrastructure runs on AWS. Specific region and availability zone information is available under NDA for Enterprise customers with legitimate compliance needs.

**Q21. What is your disaster recovery / business continuity plan (DR/BCP)?**

CutCtx maintains a documented DR/BCP for its license issuance backend. In the event of a regional outage, the service fails over to a secondary region. The DR plan is tested annually. Note that because the customer-side proxy operates locally, a CutCtx infrastructure outage does not interrupt a customer's existing compression operations — only new license validations and renewals would be affected.

**Q22. What are your RTO and RPO targets?**

Standard tier: RTO 4 hours, RPO 24 hours.
Enterprise tier: RTO 1 hour, RPO 4 hours (subject to Enterprise SLA terms).

**Q23. In which geographic regions does CutCtx operate?**

CutCtx's control plane infrastructure operates in US-East and EU-West regions. Customers in regulated jurisdictions (e.g., EU) can request that their license metadata be stored exclusively in the EU-West region. The customer-side proxy has no geographic restriction because it runs entirely within the customer's own infrastructure.

**Q24. How is network segmentation implemented?**

CutCtx's Kubernetes deployments use K8s network policies to enforce pod-level network segmentation. The license issuance service is isolated from other internal services and only accepts traffic from the authenticated management API. Egress is restricted to necessary endpoints. Internal network segmentation is reviewed annually as part of the penetration test.

---

## Software Development

**Q25. Do you have a documented secure development lifecycle (SDLC)?**

Yes. CutCtx's SDLC is documented in `docs/security/SECURITY_POLICY.md` Section 5. It includes mandatory code review, static analysis (bandit for Python, clippy for Rust), secrets scanning, dependency auditing, and signed releases.

**Q26. Are code reviews required before deployment?**

Yes. All changes to the main branch require at least one approved review from a code owner listed in `CODEOWNERS`, enforced by GitHub branch protection rules. Security-sensitive code paths (cryptography, license validation, authentication) require review from a security-designated reviewer. Force-pushes to main are disabled.

**Q27. Is static analysis / SAST performed?**

Yes. Python code is scanned with `bandit` in CI. Rust code is analyzed with `clippy`. Secrets scanning runs on every push to detect accidentally committed credentials. Results are reviewed before merge.

**Q28. Is dependency scanning performed?**

Yes. Dependabot monitors Python and Rust dependencies on a weekly schedule and opens remediation PRs automatically. `cargo audit` runs on every CI build against the RustSec Advisory Database (RUSTSEC), blocking merge on unresolved critical advisories.

**Q29. Is penetration testing performed?**

Yes. CutCtx conducts an annual third-party penetration test covering the proxy HTTP/HTTPS surface, license key validation and forgery attempts, state file cryptography, SSO/OIDC flows, and Kubernetes RBAC. Enterprise customers may request the executive summary under NDA.

**Q30. Do you operate a bug bounty program?**

CutCtx does not currently operate a public bug bounty program. We operate a private responsible disclosure program (see `SECURITY.md`). Researchers who report valid vulnerabilities are credited in security advisories with their permission. We are evaluating a formal bug bounty program for 2027.

**Q31. What is your vulnerability disclosure process?**

Security vulnerabilities are reported to security@headroom.dev. CutCtx acknowledges reports within 48 hours, assesses severity within 7 days, and targets remediation within 90 days (7 days for critical issues, CVSS 9.0+). CVEs are requested where applicable. The full process is described in `SECURITY.md` and `docs/security/SECURITY_POLICY.md` Section 7.

**Q32. How are security patches deployed?**

Security patches follow the standard CI/CD pipeline with an expedited review SLA for P1/P2 severity. Critical patches targeting CVSS 9.0+ vulnerabilities are deployed within 7 days of confirmation. Customers are notified of security releases via the changelog and, for critical issues, direct email.

---

## Compliance

**Q33. Do you have a SOC 2 report?**

CutCtx is preparing for its SOC 2 Type I audit, with target completion in Q4 2026. A SOC 2 Type II audit is planned to follow. In the interim, this questionnaire and `docs/security/SOC2_CONTROLS.md` document our controls mapping against the Trust Services Criteria. Enterprise customers may request an in-depth briefing from our security team.

**Q34. Do you hold ISO 27001 certification?**

CutCtx does not currently hold ISO 27001 certification. Our security controls are aligned with ISO 27001 principles. ISO 27001 certification is on the roadmap following SOC 2 Type II completion.

**Q35. Are you GDPR compliant?**

Yes. CutCtx's local-first architecture means no customer personal data (including prompts that may contain PII) is processed by CutCtx. For the limited personal data CutCtx does process (customer account information, billing data), CutCtx acts as a data controller and complies with GDPR requirements including lawful basis, data subject rights, and breach notification. A DPA is available for customers requiring one.

**Q36. Are you CCPA compliant?**

Yes. CutCtx does not sell customer personal information. California residents whose personal information CutCtx processes (account and billing data) may exercise their CCPA rights by contacting privacy@headroom.dev. Given the local-first architecture, CutCtx does not process the personal information that may appear within customer prompts.

**Q37. Can you provide a list of sub-processors?**

Yes. CutCtx's current sub-processors are limited to:
- Payment processor (billing and invoicing)
- Cloud infrastructure provider (AWS, for CutCtx's control plane only)
- Email delivery provider (transactional notifications)

A current sub-processors list with names and data processing purposes is available upon request. Customers are notified of material sub-processor changes with 30 days' notice.

---

## Incident Response

**Q38. What is your breach notification SLA?**

CutCtx commits to notifying affected customers within **72 hours** of confirming a security breach that may affect their data. Given the local-first architecture, a breach of CutCtx's own infrastructure does not expose customer prompt data. The 72-hour SLA applies to any confirmed breach of customer account metadata, billing information, or license records.

**Q39. Do you have a documented incident response plan?**

Yes. CutCtx's incident response plan is documented in `docs/security/SECURITY_POLICY.md` Section 6. It covers five phases: Detect, Contain, Eradicate, Recover, and Post-mortem. SLAs include 24-hour initial triage, 72-hour customer notification, and 7-day critical patch deployment. The plan is reviewed and tested annually.

**Q40. Who is the security contact for incidents and questions?**

**Email:** security@headroom.dev
**Response SLA:** 48 hours for non-urgent inquiries; 24 hours for potential security incidents.
For urgent incidents outside business hours, Enterprise customers have access to a dedicated escalation path provided in their onboarding documentation.
