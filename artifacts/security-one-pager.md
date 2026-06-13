# Headroom Security One-Pager

**Audience:** Security reviewers, procurement teams, platform teams  
**Status:** Implementation-aligned

## Product Posture

Headroom is a self-hosted control layer for AI agent traffic. It optimizes context locally, forwards requests to the customer-selected model provider, and keeps operational data in customer-managed local stores.

## Security Claims We Can Support Today

- Local-first deployment
- No hosted prompt analytics requirement
- SSO or JWT/OIDC admin authentication
- RBAC
- Audit logging
- Retention controls
- Fleet inventory APIs
- SCIM-style provisioning APIs
- Kubernetes and Helm deployment paths
- Air-gap compatible deployment path

## Data Handling Summary

| Category | Default Handling |
|----------|------------------|
| Prompt and response content | In-memory processing |
| Local retrieval state | Customer-managed local storage |
| Admin audit records | Customer-managed local storage |
| Identity and org metadata | Customer-managed local storage |
| Optional telemetry | Aggregate only and license-gated |

## Questions Procurement Will Ask

### Where does data live?
- In the customer environment by default
- In upstream provider traffic chosen by the customer

### Can the admin plane be protected with central identity?
- Yes, via SSO-aware admin auth and RBAC

### Can actions be audited?
- Yes, via audit log query and export

### Can retention be controlled?
- Yes, via retention controls for enterprise environments

### Can deployments be managed across environments?
- Yes, via fleet management APIs

### Can users and groups be provisioned centrally?
- Yes, via SCIM-style provisioning APIs

## What Still Needs External Validation

- Formal certifications such as SOC 2
- Contractual documents such as DPA and MSA
- Third-party audit reports

## Recommended Attachments

- [SECURITY.md](/Users/aryansingh/Documents/Claude/Projects/headroom/SECURITY.md)
- [docs/security-and-privacy.md](/Users/aryansingh/Documents/Claude/Projects/headroom/docs/security-and-privacy.md)
- [docs/deployment-architecture.md](/Users/aryansingh/Documents/Claude/Projects/headroom/docs/deployment-architecture.md)
- [k8s/README.md](/Users/aryansingh/Documents/Claude/Projects/headroom/k8s/README.md)
