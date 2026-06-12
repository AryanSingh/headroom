# Headroom Enterprise

> **The context, cost, and governance layer for AI agents.**

Headroom is a self-hosted, local-first proxy that compresses AI agent context by 60–95% while giving teams visibility, policy control, and enterprise-grade security. Your prompts never leave your infrastructure.

---

## Why Enterprise Teams Choose Headroom

### Cross-Provider Context Optimization
A single proxy layer for Anthropic, OpenAI, Google, Bedrock, and Vertex AI. No vendor lock-in, no per-provider optimization, one governance surface.

### Reversible Compression (CCR)
Unlike lossy compression, Headroom stores originals locally and provides retrieval markers. The LLM gets compressed context on the wire — and full fidelity on demand via `headroom_retrieve`.

### Local-First, Self-Hosted
Runs in your infrastructure, behind your firewall. Docker, docker-compose, or Kubernetes. No external API calls for compression. No data retention on external servers.

### Team Governance & Analytics
See where AI spend goes across teams, projects, and agents. Policy presets by team or agent class. Exportable reports for ROI reviews.

---

## Enterprise Features

### Available Now

| Feature | Description |
|---------|-------------|
| **Core proxy** | `headroom proxy --port 8787`, zero code changes |
| **6 compression algorithms** | SmartCrusher (JSON), CodeCompressor (AST), LogCompressor, DiffCompressor, SearchCompressor, Kompress-base (ML) |
| **Multimodal compression** | Image and audio compression with CCR storage |
| **CCR reversible retrieval** | Originals stored locally, retrievable on demand |
| **Multi-provider support** | Anthropic, OpenAI, Google, Bedrock, Vertex AI |
| **Agent compatibility** | Claude Code, Codex, Cursor, Aider, Copilot, any OpenAI-compatible client |
| **Cross-agent memory** | Shared context across agents, episodic memory |
| **Local dashboard** | Real-time compression metrics and cost tracking |
| **Rate limiting** | Token bucket rate limiter per client |
| **Budget controls** | USD budget limits (hourly/daily/monthly) |
| **Internal header stripping** | Drops x-headroom-* headers to prevent fingerprinting |
| **Docker deployment** | Production Dockerfile and docker-compose |

### Coming Soon

| Feature | Tier | Target |
|---------|------|--------|
| **SSO / SAML** | Enterprise | Q3 2026 |
| **RBAC** | Enterprise | Q3 2026 |
| **Audit logs** | Enterprise | Q3 2026 |
| **Retention controls** | Enterprise | Q4 2026 |
| **Org/project/workspace model** | Business | Q3 2026 |
| **Team analytics** | Business | Q3 2026 |
| **Exportable reports (CSV/PDF)** | Business | Q3 2026 |
| **Policy presets** | Business | Q3 2026 |
| **Kubernetes manifests** | Team | Q3 2026 |
| **Helm chart** | Business | Q4 2026 |
| **Air-gap deployment guide** | Enterprise | Q4 2026 |
| **SOC 2 readiness** | Enterprise | Q4 2026 |

---

## Deployment Options

### Local (Fastest)
```bash
pip install "headroom-ai[all]"
headroom proxy --port 8787
```

### Docker
```bash
docker pull ghcr.io/chopratejas/headroom:latest
docker run -p 8787:8787 -e ANTHROPIC_API_KEY=$KEY ghcr.io/chopratejas/headroom:latest
```

### docker-compose
```bash
docker compose up -d
```

### Kubernetes
Kubernetes manifests and Helm chart coming soon.

### Air-Gapped
Pre-download ONNX Runtime and Kompress model, then run with:
```bash
HF_HUB_OFFLINE=1 ORT_STRATEGY=system headroom proxy --port 8787
```

---

## Security & Privacy

### Data Residency
- **Prompts:** Processed in memory, never persisted
- **CCR originals:** SQLite DB in workspace directory (customer-managed)
- **Memory store:** SQLite DB in workspace directory (customer-managed)
- **Request logs:** Local JSONL file (if enabled, customer-managed)

### Telemetry (Optional)
- Only active when `HEADROOM_LICENSE_KEY` is set
- Sends only aggregate counts: request count, tokens saved, model distribution
- Never sends: message content, API keys, prompts, tool results, user data
- HTTPS only

### Air-Gap Support
- Pre-download ONNX Runtime from `cdn.pyke.io`
- Pre-download Kompress model from `huggingface.co`
- Run with `HF_HUB_OFFLINE=1` and `ORT_STRATEGY=system`
- No external network access required after initial setup

### Network Requirements
| Connection | Required | Purpose |
|------------|:--------:|---------|
| LLM provider API | Yes | Forward compressed requests |
| `cdn.pyke.io` | First run | ONNX Runtime (can be pre-provided) |
| `huggingface.co` | First run | Kompress model (can be pre-provided) |
| `app.headroomlabs.ai` | No | License validation (optional) |

---

## Pricing

| Tier | Price | Target |
|------|-------|--------|
| **Builder** | Free | Individual engineers |
| **Team** | $18,000/year | Small engineering teams |
| **Business** | $42,000/year | Platform teams, multi-project orgs |
| **Enterprise** | $60k–$150k+/year | Security-sensitive, compliance-heavy |

→ [Full pricing details](artifacts/pricing-sheet.md)

---

## Enterprise Support

### Contact
- **Email:** hello@headroomlabs.ai
- **GitHub:** github.com/chopratejas/headroom
- **Discord:** discord.gg/yRmaUNpsPJ

### Support Tiers

| Tier | Response Time | Coverage |
|------|--------------|----------|
| Community | Best effort | Discord |
| Team | Business hours | Email |
| Business | 4-hour SLA | Business hours |
| Enterprise | 1-hour critical SLA | 24/7 |

### What's Included in Enterprise
- Dedicated support engineer
- Architecture review and deployment hardening
- Security review packet
- Compliance documentation (SOC 2, HIPAA readiness)
- Onboarding package (unlimited sessions)
- Custom enterprise integrations
- Quarterly business reviews
- Air-gap deployment support

---

## ROI

Teams running Headroom typically see:

- **60–95%** token savings on tool outputs, logs, and search results
- **4.4 month** payback period
- **$50k–$140k/year** in combined token savings and engineering time savings
- **No quality degradation** — reversible compression preserves fidelity

→ [ROI Calculator](artifacts/roi-calculator.md)

---

## Getting Started

### For Individual Engineers
```bash
pip install "headroom-ai[all]"
headroom wrap claude
```

### For Teams
1. Deploy Headroom proxy in your infrastructure
2. Point your agents at the proxy
3. Capture baseline metrics
4. Measure savings over 14 days
5. Decide on paid tier

### For Enterprise
1. Contact hello@headroomlabs.ai
2. Security review and architecture assessment
3. Custom deployment plan
4. Pilot with measurable success criteria
5. Contract and onboarding

---

## Frequently Asked Questions

**Q: Does Headroom store our prompts?**
A: No. Message content is processed in memory and never written to disk. CCR stores compressed originals locally — they never leave your infrastructure.

**Q: Can we run Headroom in an air-gapped environment?**
A: Yes. Pre-download the ONNX Runtime and Kompress model, then run with `HF_HUB_OFFLINE=1` and `ORT_STRATEGY=system`.

**Q: What data is in the telemetry?**
A: Only aggregate counts: total requests, tokens saved, and model distribution. No message content is ever transmitted.

**Q: Is there a security review packet available?**
A: Yes. Contact hello@headroomlabs.ai for architecture diagrams, data flow documentation, and compliance documentation.

**Q: How does Headroom handle API keys?**
A: Keys are passed through to the upstream provider. Headroom does not store or log them.

**Q: Can we audit what Headroom does?**
A: Yes. JSONL request logs (optional), Prometheus metrics, and local dashboard. Enterprise tier adds comprehensive audit logs.
