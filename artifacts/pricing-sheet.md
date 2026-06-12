# Headroom Pricing Sheet

**Date:** June 13, 2026  
**Version:** v1.0 — Introductory pricing

---

## Pricing Overview

| Tier | Monthly | Annual | Target Buyer |
|------|---------|--------|--------------|
| **Builder** (Free) | $0 | $0 | Individual engineers |
| **Team** | $1,500 | $18,000 | Small engineering teams |
| **Business** | $3,500 | $42,000 | Platform teams, multi-project orgs |
| **Enterprise** | Custom | $60k–$150k+ | Security-sensitive, compliance-heavy |

**Billing:** Annual contracts preferred. Monthly available at 20% premium.

---

## Builder (Free OSS)

**For:** Individual engineers evaluating or using Headroom personally.

**Includes:**
- Core proxy (`headroom proxy`)
- Library usage (`compress()`)
- CLI wrap for all supported agents
- MCP server
- All 6 compression algorithms + multimodal
- CCR reversible retrieval
- Local dashboard
- Cross-agent memory
- Episodic memory
- headroom learn
- Community Discord support
- Full documentation

**Limits:**
- Single-user, local-first
- Community support only
- No org/project features
- No admin controls
- No exportable reports

**Success criterion:** A single engineer can install and realize value without talking to sales.

---

## Team ($1,500/month | $18,000/year)

**For:** Small engineering teams sharing agent infrastructure.

**Includes everything in Builder, plus:**
- Multi-user orgs and workspaces
- Org-level analytics dashboard
- Historical usage reporting
- Project and team rollups
- Downloadable reports (CSV)
- Policy presets by team or agent class
- Admin controls for memory, learning, and compression safety profiles
- Email support (business hours)
- Deployment assistance (Docker, local)
- Onboarding support

**Upgrade trigger:**
- More than 1 team member using agents
- Repeated request for reporting
- Need to govern how agents use context

**ROI justification:** If your team spends $10k+/month on LLM tokens, Team tier typically pays for itself in <6 months through token savings alone.

---

## Business ($3,500/month | $42,000/year)

**For:** Platform teams and multi-project organizations.

**Includes everything in Team, plus:**
- Workspace segmentation
- Cross-team analytics
- Role-aware admin actions
- Support SLA (business hours, 4-hour response)
- Deployment advisory (architecture review)
- Helm chart for Kubernetes
- Onboarding package (2 sessions)
- Priority feature requests

**Upgrade trigger:**
- Multiple teams or projects
- Platform owner or AI lead exists
- Need cross-team visibility
- Want workspace segmentation

**ROI justification:** If your org spends $25k+/month on LLM tokens across multiple teams, Business tier provides the governance and analytics to optimize spend systematically.

---

## Enterprise ($60,000–$150,000+/year)

**For:** Security-sensitive organizations with compliance requirements.

**Includes everything in Business, plus:**
- SSO / SAML integration
- Role-based access control (RBAC)
- Audit logging for all admin actions
- Data retention controls
- Central policy engine
- Fleet management across deployments
- Air-gapped deployment support
- Architecture review and deployment hardening
- Dedicated support engineer
- Premium support SLA (24/7, 1-hour response for critical issues)
- Security review packet
- Compliance documentation (SOC 2, HIPAA readiness)
- Onboarding package (unlimited sessions)
- Custom enterprise integrations
- Quarterly business reviews

**Upgrade trigger:**
- Security review required
- SSO/SAML mandate
- Compliance requirements (SOC2, HIPAA)
- Multi-business-unit rollout
- Air-gapped deployment needed
- Procurement/legal review

**ROI justification:** Enterprise tier eliminates procurement blockers and provides the governance layer that security and platform teams require. Pricing captures 10-20% of measurable value.

---

## Add-Ons

| Add-On | Price | Description |
|--------|-------|-------------|
| Onboarding Package | $5,000 | 4 sessions, custom deployment, team training |
| Deployment Support | $3,000 | K8s/Helm setup, architecture review |
| Premium Support SLA | $10,000/yr | 24/7 support, 1-hour critical response |
| Custom Integrations | Custom | SAML, SCIM, custom dashboards |
| Training Workshop | $2,500 | Half-day team training on compression strategies |

---

## Pricing Logic

### Value-Based Framing

Price based on value created, not infrastructure cost:

| Value Driver | How We Frame It |
|-------------|-----------------|
| Token savings | "Reduce your $X/month LLM spend by 60-95%" |
| Context efficiency | "Fit more usable context, fewer retries" |
| Reliability | "Fewer context-limit failures, faster agent runs" |
| Governance | "Visibility into AI spend across teams" |
| Privacy | "Local-first deployment, no data leaves your infra" |
| Compliance | "SSO, RBAC, audit logs for procurement approval" |

### Capture Rule

**Capture 10-20% of measurable customer value.**

Example: If Headroom saves a customer $60k/year in token costs + engineering time, pricing at $18k/year (30%) is aggressive but justified for early lighthouse accounts. Standard pricing targets 15-20%.

### Discount Rules

| Scenario | Discount | Approval |
|----------|----------|----------|
| Design partner (first 5) | 30-50% | Founder |
| Annual commit (vs monthly) | 20% | Standard |
| Multi-year (2+ years) | 15-25% | Sales lead |
| Nonprofit / education | 25% | Sales lead |
| Lighthouse account (case study) | 20-30% | Founder |
| Competitive displacement | 10-20% | Sales lead |

**Floor:** Never discount below 50% of list price. If the deal requires deeper discounting, the prospect is not a good fit.

---

## Competitive Pricing Comparison

| Solution | Tier | Annual Cost | What You Get |
|----------|------|-------------|--------------|
| **Headroom Builder** | Free | $0 | Full compression, local, reversible |
| **Headroom Team** | Team | $18,000 | + analytics, policy, support |
| **Headroom Business** | Business | $42,000 | + workspace, SLA, Helm |
| **Headroom Enterprise** | Enterprise | $60k-150k | + SSO, RBAC, audit, air-gap |
| Token Company (hosted) | Pro | $36k+ | Lossy compression, cloud-only |
| Morph Compact (hosted) | Business | $24k+ | Verbatim deletion, cloud-only |
| Kompact (OSS) | Free | $0 | 8 transforms, alpha quality |
| Native caching (provider) | Free | $0 | Provider-locked, no governance |

---

## Quote Template

```
HEADROOM — QUOTE

Date: [Date]
Valid for: 30 days
Customer: [Company Name]
Contact: [Name, Email]

─────────────────────────────────────────

Tier:           [Team / Business / Enterprise]
Billing:        Annual
Price:          $[X]/year ($[Y]/month)

Includes:
- [List features based on tier]
- [Any negotiated add-ons]

─────────────────────────────────────────

Payment terms: Net 30
Contract term: 12 months
Auto-renewal: Yes, with 60-day notice

─────────────────────────────────────────

Accepted by: _________________________
Date: _________________________

HEADROOM LABS
hello@headroomlabs.ai
```

---

## Pricing FAQ

**Q: Is there a free trial?**  
A: The Builder tier is free forever. For paid tiers, we offer a 14-day pilot with measurable success criteria.

**Q: Can I switch tiers mid-contract?**  
A: Yes. Upgrades take effect immediately with prorated billing. Downgrades take effect at renewal.

**Q: What's included in "deployment assistance"?**  
A: Help with Docker, docker-compose, K8s setup. Architecture review for your specific environment.

**Q: Do you offer month-to-month billing?**  
A: Yes, at a 20% premium over annual pricing. Annual contracts are recommended for cost optimization.

**Q: What's the support SLA?**  
A: Team: email, business hours. Business: 4-hour response, business hours. Enterprise: 1-hour critical response, 24/7.

**Q: Can I self-host without a license key?**  
A: Yes. The Builder tier is fully functional without a license key. All compression features work. Paid tiers require a license key for org/admin features.
