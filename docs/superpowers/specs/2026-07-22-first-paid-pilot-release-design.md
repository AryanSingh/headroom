# First Paid Pilot Release Design

## Outcome

Cutctx v0.31.x must support one assisted paying customer on customer-managed
infrastructure and developer workstations. The customer will use OpenAI and
Anthropic through Codex, Claude Code or Desktop, and compatible SDK clients.
The release claim covers the matrix in this document. Other providers,
clients, and experimental capabilities remain outside the pilot commitment.

The pilot may launch when no Critical or High finding affects the supported
path, the customer can complete the acceptance test, and the operator can
restore service from a documented backup or rollback.

## Supported Matrix

### Clients

- Codex through the OpenAI-compatible proxy path.
- Claude Code through the Anthropic-compatible proxy path.
- Claude Desktop through Cutctx MCP registration and the MCP tool-output
  gateway. Claude Desktop hosted model traffic does not pass through the
  Cutctx proxy.
- OpenAI-compatible and Anthropic-compatible SDK clients that can set a base
  URL and the required Cutctx client credential.

### Providers

- OpenAI.
- Anthropic.

### Workstation platforms

- macOS.
- Linux.

Windows and other operating systems remain available without a pilot support
commitment unless the customer contract adds them.

### Deployment modes

- Local loopback proxy for one developer.
- Docker deployment as the reference customer-managed server installation.
- Kubernetes deployment for a customer that requires orchestration.

The pilot does not include a Cutctx-operated hosted service.

## Product Boundaries

### Workstation installation

The CLI must install, diagnose, upgrade, and remove the supported integrations.
Registration commands must distinguish Claude Code proxy routing from Claude
Desktop MCP coverage. The diagnostic output must identify missing provider
credentials, missing client credentials, unreachable proxy endpoints, stale MCP
registration, and a required application restart.

The installer must preserve existing client configuration through a backup or
an idempotent merge. Uninstall must remove Cutctx-owned entries without deleting
unrelated user configuration.

### Customer-managed deployment

Docker is the reference deployment. The release must provide a pinned image or
build artifact, an environment template, health and readiness checks, persistent
data paths, secrets guidance, TLS termination requirements, resource guidance,
and an upgrade and rollback procedure.

Kubernetes must expose equivalent configuration through manifests or Helm. The
deployment must define probes, resource requests and limits, persistent storage,
secret injection, disruption behavior, and a rollback command. The pilot
operator must be able to inspect health without exposing an administrative
surface to an unauthenticated network client.

### Runtime request path

The proxy must authenticate provider-route traffic on non-loopback bindings.
It must reject a network-exposed deployment that lacks a Cutctx client
credential. Operators must terminate TLS before traffic reaches a non-loopback
proxy.

The proxy must preserve provider semantics for streaming, tool calls, system
messages, multimodal content accepted by the provider, rate-limit responses,
and upstream errors. A compression or routing failure must use a documented
safe behavior: pass through the original request when preservation is possible,
or return a clear error before sending an altered request.

The model router may select a different model only when its capability,
transport, account, and policy checks prove the route safe. Claude Desktop
hosted model calls remain outside this router.

### Licensing and commercial access

The operator will issue the pilot license by hand after payment or contract
confirmation. A configured tier name does not grant commercial access. The
runtime must enable paid capabilities only after a trusted license authority or
a verified signed offline token returns an active or trial entitlement.

Invalid, expired, malformed, revoked, or unverifiable licenses must retain the
Builder entitlement. The operator needs documented procedures to issue,
activate, inspect, renew, revoke, and recover a license during an authority
outage. Logs and diagnostics must not print the full license key.

### Pilot operations

The repository must contain the materials required to run one paid pilot:

- an onboarding checklist;
- a customer environment worksheet;
- a customer acceptance test;
- a support and escalation runbook;
- an incident response checklist;
- backup, restore, upgrade, and rollback procedures;
- a manual license and billing handoff checklist;
- a known-limitations document tied to the supported matrix.

The customer must know the support channel, response expectations, maintenance
window policy, data locations, telemetry behavior, and steps for disabling or
removing Cutctx.

## Data and Control Flow

1. The operator confirms payment or contract approval and issues a license.
2. The customer deploys Cutctx on a workstation, Docker, or Kubernetes and
   supplies provider credentials through the documented secret path.
3. The customer configures a Cutctx provider-route credential for any
   non-loopback deployment.
4. Codex, Claude Code, or an SDK sends provider traffic to the proxy. Claude
   Desktop invokes registered MCP servers through the Cutctx gateway.
5. Cutctx authenticates the client, verifies entitlement, evaluates policy and
   routing constraints, applies safe compression, and forwards the request.
6. Cutctx returns the provider response while recording health, savings,
   routing, and error evidence without logging secrets or prompt bodies unless
   the operator enables a documented diagnostic mode.
7. The operator uses health checks, logs, metrics, and the dashboard to diagnose
   failures. The operator restores data or rolls back the release when recovery
   cannot complete within the pilot support target.

## Failure Handling

### Provider and network failures

Cutctx must preserve upstream status codes and actionable error context. The
runtime must bound retries, apply timeouts, and avoid retrying requests that may
duplicate non-idempotent provider actions. Streaming disconnects must release
resources and leave the proxy ready for the next request.

### Compression and routing failures

Cutctx must not send a partially transformed request. The runtime may forward
the original request when policy permits and byte-preserving recovery remains
possible. Logs and metrics must record the fallback reason. Capability or
policy uncertainty must keep the requested model.

### State and storage failures

SQLite-backed state must handle expected contention with bounded retry or a
clear failure. The operator must know which state requires backup and which
state Cutctx can rebuild. Restore verification must prove that licensing,
configuration, and required operational history survive the documented process.

### License authority failures

A prior signed, unexpired entitlement may use the documented cache grace
period. A missing, corrupt, expired, or unverified cache cannot grant paid
access. Diagnostics must distinguish authority unavailability from an invalid
license without exposing the key.

## Security Requirements

- Non-loopback provider traffic requires a Cutctx client credential.
- Administrative routes require their existing admin or RBAC controls.
- Deployment guidance requires TLS termination for network access.
- Logs, traces, support bundles, and error responses redact provider keys,
  license keys, authorization headers, cookies, and configured secrets.
- Default deployment examples bind to loopback or a private service boundary.
- The proxy enforces request size, decompression, compression, rate, and timeout
  limits on the supported path.
- Release artifacts preserve the OSS and commercial package boundary.
- Dependency, secret, and artifact scans run through the release evidence path.

## Verification Design

### Automated gates

The release evidence must include:

- Python tests for supported OpenAI and Anthropic HTTP and streaming paths;
- client-auth, admin-auth, license enforcement, redaction, and limit tests;
- Claude Desktop registrar and MCP gateway tests;
- model-routing safety and benchmark tests for the supported clients;
- Docker build and smoke tests;
- Kubernetes or Helm render and policy checks;
- dashboard unit, build, and supported operator-flow tests;
- Rust format, lint, unit, parity, and Python-extension checks;
- package build, install, import, metadata, version, license-boundary, and
  artifact inspection checks;
- dependency, secret, and static security scans available in the repository.

### Customer acceptance test

The acceptance test starts from a documented clean state and proves:

1. The customer installs or deploys Cutctx with the supplied instructions.
2. Health and readiness checks pass.
3. An OpenAI request through Codex or a compatible client succeeds.
4. An Anthropic request through Claude Code or a compatible client succeeds.
5. Claude Desktop detects the Cutctx MCP registration and a large MCP tool
   result follows the documented gateway path.
6. The dashboard or metrics surface records truthful request, routing, savings,
   and error information.
7. Invalid client and license credentials fail without leaking secrets.
8. The customer upgrades or rolls back using the runbook.
9. The operator restores required state from backup and repeats a health check.
10. The customer disables and removes Cutctx without losing unrelated client
    configuration.

### Manual gates

The release owner must record evidence for UI behavior, installation on the
supported workstation platforms, container startup, Kubernetes operation,
backup and restore, rollback, and support-bundle redaction. Live provider tests
require customer-safe test accounts and bounded spend.

## Release Artifacts

The pilot handoff must include:

- versioned Python and container artifacts for the chosen pilot version;
- checksums and available signatures or provenance;
- release notes and known limitations;
- the supported matrix and environment worksheet;
- onboarding, acceptance, operations, recovery, and removal runbooks;
- audit reports for QA, security, production readiness, and product readiness;
- `audit/final-verdict.md` with the launch recommendation and unresolved risks.

## External Sign-offs

Repository work cannot supply legal advice, create a contracting entity,
collect payment, or promise a support response on behalf of a person. Before the
customer receives paid access, the release owner must record:

- the contracting entity and approved order form or pilot agreement;
- legal review of terms, privacy terms, and any required DPA;
- payment or invoice status;
- the named support owner and response target;
- customer approval of data handling and telemetry settings;
- the production change window and rollback owner.

These sign-offs block a paid launch even when the software gate passes.

## Completion Criteria

The pilot release is ready when:

1. The audit finds no open Critical or High issue on the supported path.
2. Automated release gates pass from the candidate commit.
3. The customer acceptance test passes on one workstation path and the selected
   customer-managed deployment path.
4. Backup restore and rollback evidence exists for the release candidate.
5. The release owner records each external sign-off or marks the launch blocked.
6. `audit/final-verdict.md` states the supported matrix, evidence, scores,
   residual Medium and Low risks, and a Go, Conditional Go, or No-Go decision.
