# Team vs Enterprise

## Quick Comparison

| | Team | Enterprise |
|---|------|-----------|
| **Price** | $18,000/yr | $60k–$150k+/yr |
| **Target** | Small engineering teams (5–50 seats) | Security-sensitive orgs, compliance-heavy |
| **SSO / SAML** | ✗ | ✓ |
| **RBAC** | ✗ | ✓ |
| **Audit logs** | ✗ | ✓ |
| **Retention controls** | ✗ | ✓ |
| **Air-gap deployment** | ✗ | ✓ |
| **Kubernetes / Helm** | ✗ | ✓ |
| **Compliance (SOC 2, HIPAA)** | ✗ | ✓ |
| **Dedicated support engineer** | ✗ | ✓ |
| **Premium SLA (24/7)** | ✗ | ✓ |
| **Onboarding sessions** | ✗ | ✓ (unlimited) |
| **Quarterly business reviews** | ✗ | ✓ |

## What's in Both Tiers

- All core compression (SmartCrusher, CodeCompressor, LogCompressor, DiffCompressor, SearchCompressor, Kompress)
- CCR reversible retrieval
- Proxy, SDK, CLI, MCP modes
- Local dashboard
- Cross-agent memory
- Episodic memory
- All providers (Anthropic, OpenAI, Google, Bedrock, Vertex)
- Agent compatibility (Claude Code, Codex, Cursor, Copilot, Aider)
- Docker deployment

## Team Tier — What You Get

### Org-Level Analytics
See compression metrics across your engineering team. Who's saving the most? Which agents are the most token-heavy? Exportable CSV reports for ROI reviews.

### Policy Presets
Configure compression behavior per team or project. Set different savings targets for different agent classes. Control which compressors are active.

### Usage Reports
Weekly email digests with team usage summaries. Token savings, cost reduction, and optimization trends.

### Savings Profiles
Pre-configured compression profiles: `conservative` (quality-first), `balanced`, `aggressive` (max savings). Apply per project or per agent.

### Budget Controls
Set USD limits per hour, day, or month. Alert thresholds. Hard stops when budgets are exceeded.

## Enterprise Tier — What You Get

### SSO / SAML
Single sign-on integration for the admin dashboard and proxy access. Works with Okta, Azure AD, Google Workspace, and any SAML 2.0 provider.

### RBAC
Role-based access control with three roles:
- **Admin**: Full access to all settings, user management, and billing
- **Operator**: Can manage proxy configuration, policies, and view analytics
- **Viewer**: Read-only access to dashboard and reports

### Audit Logs
Comprehensive audit trail for all administrative actions:
- Configuration changes (who changed what, when)
- User access (who logged in, from where)
- Proxy restarts and deployments
- Entitlement changes
- Exportable in JSON/CSV for compliance

### Retention Controls
Control how long request logs, compression metrics, and audit data are retained. Set per-data-type retention periods. Automatic cleanup. Export before deletion.

### Air-Gap Deployment
Run Headroom entirely offline. Pre-download ONNX Runtime and Kompress model. No external network access required. Documented air-gap installation guide.

### Kubernetes / Helm
Production-ready Kubernetes manifests and Helm chart for deploying Headroom in your cluster. Includes:
- Deployment, Service, Ingress resources
- ConfigMap and Secret management
- Horizontal pod autoscaling
- Health checks and readiness probes
- Network policies

### Compliance Documentation
- SOC 2 Type II readiness documentation
- HIPAA readiness assessment
- Architecture diagrams for security review
- Data flow documentation
- Third-party security audit reports

### Dedicated Support Engineer
A named support engineer who knows your deployment. Direct Slack channel. Architecture reviews. Deployment hardening.

### Premium SLA
- 1-hour response time for critical issues
- 24/7 on-call support
- 99.9% uptime guarantee
- Escalation path to engineering leadership

## Choosing Between Them

**Choose Team if:**
- You have 5–50 engineers using AI agents
- You need shared visibility across your team
- Policy presets and budget controls are sufficient
- Your security requirements are met by self-hosted deployment

**Choose Enterprise if:**
- You need SSO/SAML for compliance
- You require RBAC for multi-team deployments
- Audit logs are a regulatory requirement
- You need air-gap or Kubernetes deployment
- SOC 2 or HIPAA compliance is required
- You need dedicated support and SLA guarantees

## Getting Started

### Team
```bash
# Deploy the proxy
pip install "headroom-ai[all]"
headroom proxy --port 8787

# Enable team analytics
export HEADROOM_LICENSE_KEY=hlk_your_team_key
headroom proxy --port 8787
```

### Enterprise
1. Contact hello@headroomlabs.ai
2. Security review and architecture assessment
3. Custom deployment plan
4. Pilot with measurable success criteria
5. Contract and onboarding
