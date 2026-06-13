# Headroom Feature Packaging Matrix

**Date:** June 13, 2026  
**Status:** Canonical commercialization matrix

## Summary

| Tier | Annual Price | Primary Value |
|------|--------------|---------------|
| **Builder** | $0 | Individual adoption and OSS growth |
| **Team** | $18,000 | Shared visibility and basic team governance |
| **Business** | $42,000 | Multi-project reporting and deployment standardization |
| **Enterprise** | $60,000-$150,000+ | Security, identity, auditability, and central control |

## Core Product

| Capability | Builder | Team | Business | Enterprise |
|------------|:-------:|:----:|:--------:|:----------:|
| Core compression pipeline | ✅ | ✅ | ✅ | ✅ |
| CCR reversible retrieval | ✅ | ✅ | ✅ | ✅ |
| Multimodal compression | ✅ | ✅ | ✅ | ✅ |
| Proxy mode | ✅ | ✅ | ✅ | ✅ |
| CLI wrap | ✅ | ✅ | ✅ | ✅ |
| SDK and MCP surfaces | ✅ | ✅ | ✅ | ✅ |
| Cross-agent memory | ✅ | ✅ | ✅ | ✅ |
| Multi-provider support | ✅ | ✅ | ✅ | ✅ |
| Local dashboard | ✅ | ✅ | ✅ | ✅ |
| Docker deployment | ✅ | ✅ | ✅ | ✅ |

## Team and Business Operations

| Capability | Builder | Team | Business | Enterprise |
|------------|:-------:|:----:|:--------:|:----------:|
| Team analytics | ❌ | ✅ | ✅ | ✅ |
| Usage reports | ❌ | ✅ | ✅ | ✅ |
| Savings profiles | ❌ | ✅ | ✅ | ✅ |
| Policy presets | ❌ | ✅ | ✅ | ✅ |
| Budget controls | ❌ | ✅ | ✅ | ✅ |
| Workspace model | ❌ | ❌ | ✅ | ✅ |
| Project model | ❌ | ❌ | ✅ | ✅ |
| Historical reporting | ❌ | ❌ | ✅ | ✅ |
| Exportable reports | ❌ | ❌ | ✅ | ✅ |
| Project analytics | ❌ | ❌ | ✅ | ✅ |
| Kubernetes manifests | ❌ | ❌ | ✅ | ✅ |
| Helm chart | ❌ | ❌ | ✅ | ✅ |

## Enterprise Governance

| Capability | Builder | Team | Business | Enterprise |
|------------|:-------:|:----:|:--------:|:----------:|
| SSO or JWT/OIDC admin auth | ❌ | ❌ | ❌ | ✅ |
| RBAC | ❌ | ❌ | ❌ | ✅ |
| Audit logs | ❌ | ❌ | ❌ | ✅ |
| Retention controls | ❌ | ❌ | ❌ | ✅ |
| Fleet management APIs | ❌ | ❌ | ❌ | ✅ |
| SCIM provisioning APIs | ❌ | ❌ | ❌ | ✅ |
| Air-gap deployment support | ❌ | ❌ | ❌ | ✅ |
| Security review packet | ❌ | ❌ | ❌ | ✅ |
| Premium support and SLA | ❌ | ❌ | ❌ | ✅ |

## Support

| Capability | Builder | Team | Business | Enterprise |
|------------|:-------:|:----:|:--------:|:----------:|
| Community support | ✅ | ✅ | ✅ | ✅ |
| Email support | ❌ | ✅ | ✅ | ✅ |
| Deployment assistance | ❌ | ✅ | ✅ | ✅ |
| Architecture review | ❌ | ❌ | ✅ | ✅ |
| Named support owner | ❌ | ❌ | ❌ | ✅ |
| 24/7 escalation path | ❌ | ❌ | ❌ | ✅ |

## Upgrade Triggers

### Builder to Team
- More than one regular user
- Need for shared reports
- Need for team-wide controls

### Team to Business
- Multiple projects or workspaces
- Need exportable or historical reports
- Platform team wants centralized rollout standards

### Business to Enterprise
- SSO requirement
- Audit or retention review
- Central identity provisioning requirement
- Multiple deployments to monitor
- Procurement-driven security review

## Notes

- Keep the compression engine and developer adoption surface in Builder to maximize OSS pull.
- Gate management, reporting, and governance features rather than technical core capability.
- Keep formal certifications out of the SKU matrix until they are actually achieved.
