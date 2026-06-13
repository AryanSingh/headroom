# Headroom Pricing Sheet

**Date:** June 13, 2026  
**Version:** v2.0  
**Status:** Aligned to current implementation

## Pricing Overview

| Tier | Monthly | Annual | Target Buyer |
|------|---------|--------|--------------|
| **Builder** | $0 | $0 | Individual engineers and OSS evaluators |
| **Team** | $1,500 | $18,000 | Single engineering team adopting shared AI workflows |
| **Business** | $3,500 | $42,000 | Platform teams and multi-project organizations |
| **Enterprise** | Custom | $60,000-$150,000+ | Security-sensitive organizations with procurement requirements |

**Billing policy**
- Annual contracts are the default.
- Monthly billing is available at a 20% premium.
- Enterprise contracts should target one-year minimum terms.

## Packaging Summary

### Builder
- Core compression engine
- Proxy, CLI wrap, SDK, MCP
- Local dashboard
- Memory and CCR
- Docker deployment
- Community support

### Team
- Org analytics
- Team analytics dashboard
- Usage reports
- Savings profiles
- Policy presets
- Budget controls
- Business-hours support

### Business
- Workspace model
- Project model
- Historical reporting
- Exportable reports
- Multi-project analytics
- Kubernetes manifests
- Helm deployment path
- Deployment advisory

### Enterprise
- SSO or JWT/OIDC admin authentication
- RBAC
- Audit logs and export
- Retention controls
- Fleet management
- SCIM provisioning APIs
- Air-gap deployment support
- Premium support and security review support

## Tier Detail

### Builder

**For**
- Individual engineers
- OSS trial users
- Technical evaluators

**Includes**
- Full compression pipeline
- Multimodal compression
- Cross-provider support
- Agent compatibility
- Local-first deployment

**Does not include**
- Shared admin features
- Team analytics
- Enterprise governance

### Team

**For**
- One engineering team running AI-assisted development
- Teams that want ROI visibility before a platform rollout

**Includes everything in Builder, plus**
- `/analytics/dashboard`
- `/reports/savings`
- `/reports/usage`
- Team analytics and policy presets
- Shared admin visibility

**Commercial trigger**
- More than 5 regular users
- Need a shared savings dashboard
- Need team-wide governance without formal procurement

### Business

**For**
- Platform teams
- Multi-workspace deployments
- Organizations needing rollups and segmentation

**Includes everything in Team, plus**
- Org, workspace, and project management
- Historical and exportable reporting
- Project analytics
- Kubernetes and Helm deployment packaging
- Structured deployment support

**Commercial trigger**
- Multiple teams
- Shared AI budget owner
- Need project- or workspace-level reporting

### Enterprise

**For**
- Security-reviewed environments
- Regulated or procurement-heavy buyers
- Central platform teams standardizing agent governance

**Includes everything in Business, plus**
- SSO-protected admin plane
- Role-based access control
- Audit logging
- Retention controls
- Fleet management APIs
- SCIM-style provisioning APIs
- Air-gap support path
- Security review packet and deployment hardening support

**Commercial trigger**
- SSO mandate
- Audit requirement
- Retention or compliance review
- Multiple deployments to monitor centrally

## Add-Ons

| Add-On | Price | Description |
|--------|-------|-------------|
| Onboarding Package | $5,000 | Environment setup, admin enablement, team training |
| Deployment Hardening | $3,000 | Kubernetes review, Helm values review, rollout guidance |
| Premium SLA Upgrade | $10,000/year | 24/7 coverage with 1-hour critical response |
| Security Review Support | $7,500 | Questionnaire support, architecture walk-through, packet prep |
| Custom Integration Work | Custom | Identity, observability, or platform-specific work |

## Deal Rules

### Discount Rules

| Scenario | Discount | Approval |
|----------|----------|----------|
| Design partner | 30-40% | Founder |
| Annual prepay | Included in list | Standard |
| Multi-year term | 10-15% | Founder or sales lead |
| Lighthouse logo with case study | 15-25% | Founder |
| Competitive displacement | Up to 15% | Sales lead |

### Guardrails
- Do not discount below 60% of list without explicit founder approval.
- Keep pilots time-boxed to 14 or 30 days.
- Do not offer unlimited custom work inside base subscription pricing.

## ROI Framing

Use four value buckets in every commercial conversation:

1. Token savings
2. Higher effective context utility
3. Fewer retries and failure loops
4. Governance and procurement unblockers

**Pricing rule of thumb**
- Target 10-20% of measurable annual customer value.

## Quote Skeleton

```text
HEADROOM COMMERCIAL QUOTE

Customer:
Primary contact:
Tier:
Contract term:
Annual price:

Included:
- Core tier features
- Named add-ons
- Support coverage

Success criteria:
- Baseline token spend captured
- 14-day ROI checkpoint
- Admin plane deployed

Commercial terms:
- Net 30
- Annual prepay unless otherwise agreed
- Renewal notice: 60 days
```

## What Still Requires External Work

- Contract redlines and legal approval
- Tax handling and invoicing setup
- Payment collection workflow
- Formal certification work such as SOC 2 or HIPAA-related paperwork
