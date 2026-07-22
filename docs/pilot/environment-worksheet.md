# Pilot Environment Worksheet

Complete this worksheet before installation. Store the completed copy in the
customer record. Do not put secret values in this document.

## Customer and owners

- Customer organization:
- Technical owner:
- Cutctx support owner:
- Change window:
- Rollback owner:
- Support channel:
- Agreed response target:

## Supported workload

- OpenAI models in use:
- Anthropic models in use:
- Codex users and operating systems:
- Claude Code users and operating systems:
- Claude Desktop MCP servers to wrap:
- SDK languages and versions:

## Deployment

- Mode: workstation, Docker, or Kubernetes
- Cutctx version or image digest:
- Public hostname or private service name:
- TLS termination point:
- Persistent data location:
- Backup destination:
- Restore-test date:

## Secrets

Generate distinct random values for these boundaries:

- `CUTCTX_ADMIN_API_KEY`: operator access
- `CUTCTX_PROXY_API_KEY`: provider HTTP and WebSocket traffic
- `CUTCTX_CLIENT_API_KEY`: SDK, MCP, compression, and CCR clients
- `CUTCTX_LICENSE_KEY`: paid entitlement
- OpenAI provider credential
- Anthropic provider credential

Record the secret-manager path for each value. Do not reuse a provider key as a
Cutctx credential.

## Data handling

- Telemetry enabled or disabled:
- Request-body logging enabled: must be `no` for the pilot
- Retention settings:
- Customer-approved data regions:
- Support-bundle transfer method:

