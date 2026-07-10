# Security and Privacy

## Data Flow

```text
AI Agent -> Cutctx Proxy -> Upstream LLM Provider
               |
               +-> Local CCR store
               +-> Local memory store
               +-> Local audit and org stores when enabled
```

## What Stays Local

| Data | Default Location | Notes |
|------|------------------|-------|
| Request and response content | Process memory | Not persisted by default |
| CCR data | Local SQLite | Customer-managed |
| Memory data | Local SQLite | Customer-managed |
| Audit log data | Local SQLite | Enterprise only |
| Org, workspace, and project metadata | Local SQLite | Business and Enterprise |
| Fleet inventory | Local SQLite | Enterprise only |
| SCIM provisioning records | Local SQLite | Enterprise only |

## What Leaves The Environment

| Data | When | Required |
|------|------|----------|
| Upstream provider request | On every model call | Yes |
| Optional license validation and aggregate usage | When a license key is configured | No |
| Initial runtime and model downloads | First-time setup unless pre-staged | No |

## What Cutctx Does Not Claim To Collect

- Prompt content for SaaS analytics
- Tool results for hosted analysis
- API keys as a product dataset
- Customer codebases as a central corpus

## Security Controls Available Now

- Admin API key auth
- SSO or JWT/OIDC admin authentication
- RBAC
- Audit logging
- Retention controls
- Fleet inventory APIs
- SCIM-style provisioning APIs
- Kubernetes and Helm deployment paths
- Air-gap compatible deployment path

## Operational Guidance

### Recommended production stance
- Run behind a private network boundary
- Set an admin API key even if SSO is enabled
- Route dashboard and admin paths through authenticated ingress
- Enable audit storage for enterprise deployments
- Configure retention settings before production rollout

### Air-gapped deployments
- Pre-stage model/runtime dependencies
- Set `HF_HUB_OFFLINE=1`
- Set `ORT_STRATEGY=system`

## Compliance Status

The repo now includes the technical controls needed for enterprise review.
Formal certifications and legal/compliance paperwork remain separate business
workstreams.

| Workstream | Status |
|------------|--------|
| Security review packet | Can be assembled from existing docs |
| DPA and procurement docs | External legal work required |
| SOC 2 program | Not represented as completed in code |
| HIPAA or BAA process | External legal and compliance work required |

## Procurement Review Split

### Available now in product

- Local-first deployment posture
- Admin authentication and protected admin routes
- SSO / JWT / OIDC admin auth path
- RBAC
- Audit-log query and export path for enterprise deployments
- Retention controls
- Air-gap deployment guidance

### External or planned workstreams

- Final DPA / MSA legal approval
- SOC 2 certification or audit completion
- HIPAA / BAA process completion
- Third-party penetration-test evidence

For a reviewer-ready summary with evidence links, use
`artifacts/enterprise-procurement-packet.md`.

## Buyer FAQ

**Does Cutctx store prompts by default?**
No. Content is processed in memory. Local stores are customer-managed.

**Can Cutctx run without outbound network dependencies after setup?**
Yes, with pre-staged dependencies and offline flags.

**Can admins audit changes?**
Yes. Enterprise deployments can query and export audit logs.

**Can identity be centralized?**
Yes. Enterprise deployments can use SSO-aware admin auth, RBAC, and SCIM-style provisioning APIs.

## Orchestration state and key custody

`CUTCTX_ORCHESTRATION_DIR` contains `credentials.enc`, the discovered-model cache, and execution telemetry. Back up the directory with the same access controls as other proxy state, but manage `CUTCTX_ORCHESTRATION_MASTER_KEY` separately in a secret manager. The value must be a valid Fernet key. If no external key is set, Cutctx creates `credentials.key` with mode `0600`; that file must be backed up separately from `credentials.enc`. Losing the key makes stored credentials intentionally unrecoverable.

Restore the key before restoring `credentials.enc`, restrict the state directory to the proxy identity, and restart the proxy after restoration. For key rotation, decrypt credentials with the old key, write them through the credential API under the new key, verify provider authentication, and only then retire the old key. Sensitive request headers belong in the encrypted credential payload under `headers`; plaintext orchestration configuration rejects common authentication header names.
