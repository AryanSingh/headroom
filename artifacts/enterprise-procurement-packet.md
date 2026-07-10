# Enterprise Procurement Packet

This packet is meant to be handed to legal, security, and IT reviewers
without requiring product-code inspection. It separates controls that ship in
the current product from workstreams that still require external legal,
compliance, or audit completion.

## Current Scope

- Product state: pilot-ready, not broadly launched.
- Deployment model: local-first proxy and control plane, with customer-managed
  storage by default.
- Intended use today: design-partner pilots, enterprise POCs, and
  engineering-led evaluations.

## Fixed Checklist

| Area | Status | Evidence | Notes |
|---|---|---|---|
| Deployment posture | Available now | `docs/security-and-privacy.md`, `docs/air-gap-deployment.md` | Local-first, private-network, Helm and air-gap guidance documented. |
| Identity and authentication | Available now | `docs/security-and-privacy.md`, `PRODUCT_GUIDE.md`, `docs/security/SOC2_CONTROLS.md` | Admin auth, SSO/OIDC path, and RBAC are product features. |
| Auditability | Available now | `docs/audit-compliance.md`, `docs/security-and-privacy.md` | Audit-log query/export is part of the enterprise posture. |
| Retention controls | Available now | `docs/security-and-privacy.md`, `PRODUCT_GUIDE.md` | Retention controls are documented as product controls. |
| Procurement legal templates | External legal review required | `artifacts/legal/DPA_TEMPLATE.md`, `artifacts/legal/MSA_TEMPLATE.md` | Templates exist, but are not final signed legal documents. |
| SOC 2 certification | Not represented as completed | `docs/security/SOC2_CONTROLS.md`, `docs/security-and-privacy.md` | Controls mapping exists; certification is not claimed as complete. |
| HIPAA / BAA process | External legal and compliance work required | `docs/security-and-privacy.md` | No shipped claim that HIPAA or a BAA process is complete. |
| Penetration testing evidence | Not included in this packet | `artifacts/commercial-readiness-audit.md` | Remains an external evidence workstream. |

## Security Evidence Bundle

### Identity

- Admin API key authentication.
- SSO / JWT / OIDC admin authentication path.
- RBAC for protected admin capabilities.
- SCIM-style provisioning APIs for enterprise environments.

Primary evidence:

- `docs/security-and-privacy.md`
- `PRODUCT_GUIDE.md`
- `docs/security/SOC2_CONTROLS.md`

### Audit

- Tamper-evident audit logging is documented.
- Enterprise deployments can query and export audit logs.
- Audit evidence should be evaluated together with the partial-control notes in
  the SOC 2 mapping.

Primary evidence:

- `docs/audit-compliance.md`
- `docs/security-and-privacy.md`
- `docs/security/SOC2_CONTROLS.md`

### Retention

- Retention controls are part of the enterprise feature set.
- Production guidance explicitly calls for retention configuration before
  rollout.

Primary evidence:

- `docs/security-and-privacy.md`
- `PRODUCT_GUIDE.md`

### Deployment Posture

- Requests and responses are processed in memory by default.
- Local stores are customer-managed.
- Air-gapped operation is supported when dependencies are pre-staged.
- Upstream model calls still leave the environment during normal operation.

Primary evidence:

- `docs/security-and-privacy.md`
- `docs/air-gap-deployment.md`

## Not Claimed In This Packet

- Completed SOC 2 certification.
- Final legal approval of DPA or MSA templates.
- HIPAA, BAA, FedRAMP, or similar completed compliance programs.
- Third-party penetration-test completion.
- Hosted-SaaS prompt collection or centralized customer-data analytics.

## Reviewer Hand-off

Use this packet with:

- `docs/security-and-privacy.md`
- `docs/security/SOC2_CONTROLS.md`
- `docs/audit-compliance.md`
- `docs/air-gap-deployment.md`
- `artifacts/legal/DPA_TEMPLATE.md`
- `artifacts/legal/MSA_TEMPLATE.md`

If a reviewer asks whether a control is shipped now or still business-process
work, use the `Status` column in the fixed checklist as the source of truth.
