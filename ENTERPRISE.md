# CutCtx Enterprise

> **The context, cost, and governance layer for AI agents.**

CutCtx is a self-hosted, local-first proxy that reduces waste in agent traffic while giving teams a governed admin plane for analytics, policy, identity, and auditability.

## Why Teams Buy CutCtx

### Local-first deployment
- Runs in customer infrastructure
- No prompt content leaves the environment except the upstream provider request
- Docker, Kubernetes, and Helm deployment paths are available

### Cross-provider optimization
- One layer across Anthropic, OpenAI, Google, Bedrock, and Vertex
- Preserves developer workflows across Claude Code, Codex, Cursor, Aider, Copilot, and OpenAI-compatible clients

### Reversible compression
- CCR keeps originals locally and lets the model recover fidelity on demand
- Avoids the quality tradeoffs of blind lossy compression

### Governance for shared deployments
- Team and business reporting
- Enterprise admin controls
- Identity, audit, retention, and fleet operations

## Commercial Tiers

| Tier | Best For | Key Commercial Features |
|------|----------|-------------------------|
| **Builder** | Individual engineers | Core compression, proxy, SDK, CLI, local dashboard |
| **Team** | One engineering team | Team analytics, usage reports, savings profiles, policy presets |
| **Business** | Platform teams | Workspace and project model, historical and exportable reporting, K8s and Helm |
| **Enterprise** | Security-sensitive orgs | SSO, RBAC, audit logs, retention, fleet management, SCIM, air-gap support |

## Available Now

| Capability | Status |
|-----------|--------|
| Core proxy and compression pipeline | Available |
| CCR reversible retrieval | Available |
| Multi-provider support | Available |
| Team analytics and usage reports | Available |
| Workspace and project management | Available |
| Historical and exportable reports | Available |
| Kubernetes manifests | Available |
| Helm chart | Available |
| SSO-aware admin authentication | Available |
| RBAC | Available |
| Audit log query and export | Available |
| Retention controls | Available |
| Fleet management APIs | Available |
| SCIM-style provisioning APIs | Available |

## Deployment Options

### Local
```bash
pip install cutctx-ai
cutctx proxy --port 8787
```

### Docker
```bash
docker compose up -d
```

### Kubernetes
```bash
kubectl apply -f k8s/
```

### Helm
```bash
helm install cutctx ./helm/cutctx
```

### Air-gapped
- Pre-stage model/runtime dependencies
- Run with `HF_HUB_OFFLINE=1`
- Use `ORT_STRATEGY=system`
- See [docs/air-gap-deployment.md](docs/air-gap-deployment.md) for full runbook

## Security and Trust

### Enterprise controls
- Ed25519 Token Licensing (Seat Leases, Server-Side Trials, Offline Tolerance)
- SSO or JWT/OIDC admin authentication
- Role-based access control
- Audit logging
- Retention controls
- Fleet visibility across deployments
- SCIM-style user and group provisioning APIs

### Data handling
- Request content is processed in memory
- Local stores remain customer-managed
- Aggregate telemetry is optional and license-gated

### Review materials
- [SECURITY.md](/Users/aryansingh/Documents/Claude/Projects/headroom/SECURITY.md)
- [docs/security-and-privacy.md](/Users/aryansingh/Documents/Claude/Projects/headroom/docs/security-and-privacy.md)
- [artifacts/security-one-pager.md](/Users/aryansingh/Documents/Claude/Projects/headroom/artifacts/security-one-pager.md)

## Pricing

| Tier | Price |
|------|-------|
| Builder | Free |
| Team | $18,000/year |
| Business | $42,000/year |
| Enterprise | $60,000-$150,000+/year |

Detailed pricing: [artifacts/pricing-sheet.md](/Users/aryansingh/Documents/Claude/Projects/headroom/artifacts/pricing-sheet.md)

## What Still Requires External Work

These are not code gaps, but business workstreams:
- Legal contracting and procurement redlines
- Billing and collections operations
- Formal certification programs such as SOC 2
- Design partner acquisition and case-study generation

## Capability Extensions

| Feature | Status |
|---------|--------|
| Intelligence layer (6 features: task-aware, dedup, budget, profiles, shared-state, cost-forecast) | Available |
| LLM Firewall (27 regex patterns + ML classifier) | Available |
| Structured output validation with auto-retry | Available |
| Multi-model ensemble routing | Available |
| Budget cut-offs with progressive compression | Available |
| Episodic memory (cross-session learning) | Available |
| Multimodal compression (image + audio) | Available |
| Stripe billing integration | Available |
| Go SDK (full: Client, Memory, Proxy, SharedContext) | Available |
| Python SDK (CutCtxClient + SharedContext) | Available |
| Benchmark suite (vs LLMLingua-2) | Available |

## Plugins

| Agent | Plugin | Install |
|-------|--------|---------|
| Claude Code | `plugins/claude-code/` | `cutctx setup` or `bash plugins/claude-code/install.sh` |
| Codex | `plugins/codex/` | `cutctx setup` or `bash plugins/codex/install.sh` |
| Claude.ai (web) | `plugins/cutctx-plugin/` | Upload ZIP to Plugins → Personal → Local uploads |
| Hermes | `plugins/hermes/` | `pip install headroom-hermes` |
| OpenClaw | `plugins/openclaw/` | `npm install @cutctx/openclaw` |

## Contact

- `hello@cutctx.dev`
- `security@cutctx.dev`
