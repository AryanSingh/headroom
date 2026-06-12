# Headroom Feature Packaging Matrix

**Date:** June 13, 2026  
**Status:** v1.0 — Ready for review

---

## Summary

| Tier | Annual Price | Target Buyer | Key Value |
|------|-------------|--------------|-----------|
| **Builder (Free OSS)** | $0 | Individual engineers | Adoption, trust, GitHub growth |
| **Team** | $18k/yr ($1,500/mo) | Small engineering teams | Shared visibility, policy presets |
| **Business** | $42k/yr ($3,500/mo) | Platform teams, multi-project orgs | Cross-team analytics, workspace segmentation |
| **Enterprise** | $60k–$150k+/yr | Security-sensitive, compliance-heavy | SSO, RBAC, audit logs, air-gap |

---

## Feature Inventory by Tier

### Core Compression Engine

| Feature | OSS | Team | Business | Enterprise |
|---------|:---:|:----:|:--------:|:----------:|
| SmartCrusher (JSON compression) | ✅ | ✅ | ✅ | ✅ |
| CodeCompressor (AST-aware) | ✅ | ✅ | ✅ | ✅ |
| Kompress-base (ML text compression) | ✅ | ✅ | ✅ | ✅ |
| DiffCompressor (unified diffs) | ✅ | ✅ | ✅ | ✅ |
| LogCompressor (log files) | ✅ | ✅ | ✅ | ✅ |
| SearchCompressor (search results) | ✅ | ✅ | ✅ | ✅ |
| CacheAligner (KV cache stability) | ✅ | ✅ | ✅ | ✅ |
| ImageCompressor (multimodal) | ✅ | ✅ | ✅ | ✅ |
| AudioCompressor (multimodal) | ✅ | ✅ | ✅ | ✅ |
| ContentDetector (auto-routing) | ✅ | ✅ | ✅ | ✅ |
| AnchorSelector (density-based) | ✅ | ✅ | ✅ | ✅ |
| TagProtector (HTML/XML safety) | ✅ | ✅ | ✅ | ✅ |
| Safety guardrails | ✅ | ✅ | ✅ | ✅ |

### CCR (Reversible Compression)

| Feature | OSS | Team | Business | Enterprise |
|---------|:---:|:----:|:--------:|:----------:|
| CCR core (store + retrieve) | ✅ | ✅ | ✅ | ✅ |
| InMemoryCcrStore | ✅ | ✅ | ✅ | ✅ |
| SqliteCcrStore (persistent) | ✅ | ✅ | ✅ | ✅ |
| RedisCcrStore (multi-worker) | ✅ | ✅ | ✅ | ✅ |
| headroom_retrieve tool injection | ✅ | ✅ | ✅ | ✅ |
| CCR context tracking | ✅ | ✅ | ✅ | ✅ |
| CCR proactive expansion | ✅ | ✅ | ✅ | ✅ |

### Deployment Modes

| Feature | OSS | Team | Business | Enterprise |
|---------|:---:|:----:|:--------:|:----------:|
| Library mode (`compress()`) | ✅ | ✅ | ✅ | ✅ |
| CLI wrap (`headroom wrap`) | ✅ | ✅ | ✅ | ✅ |
| Proxy mode (`headroom proxy`) | ✅ | ✅ | ✅ | ✅ |
| MCP server | ✅ | ✅ | ✅ | ✅ |
| Docker deployment | ✅ | ✅ | ✅ | ✅ |
| docker-compose | ✅ | ✅ | ✅ | ✅ |
| Kubernetes manifests | ❌ | ✅ | ✅ | ✅ |
| Helm chart | ❌ | ❌ | ✅ | ✅ |
| Air-gapped deployment | ❌ | ❌ | ❌ | ✅ |

### Provider Support

| Feature | OSS | Team | Business | Enterprise |
|---------|:---:|:----:|:--------:|:----------:|
| Anthropic (Claude) | ✅ | ✅ | ✅ | ✅ |
| OpenAI (GPT) | ✅ | ✅ | ✅ | ✅ |
| Google (Gemini) | ✅ | ✅ | ✅ | ✅ |
| AWS Bedrock | ✅ | ✅ | ✅ | ✅ |
| Google Vertex AI | ✅ | ✅ | ✅ | ✅ |
| LiteLLM gateway | ✅ | ✅ | ✅ | ✅ |
| AnyLLM | ✅ | ✅ | ✅ | ✅ |

### Agent Support

| Feature | OSS | Team | Business | Enterprise |
|---------|:---:|:----:|:--------:|:----------:|
| Claude Code wrap | ✅ | ✅ | ✅ | ✅ |
| Codex wrap | ✅ | ✅ | ✅ | ✅ |
| Cursor wrap | ✅ | ✅ | ✅ | ✅ |
| Aider wrap | ✅ | ✅ | ✅ | ✅ |
| Copilot CLI wrap | ✅ | ✅ | ✅ | ✅ |
| OpenClaw wrap | ✅ | ✅ | ✅ | ✅ |
| Any OpenAI-compatible client | ✅ | ✅ | ✅ | ✅ |

### Memory & Context

| Feature | OSS | Team | Business | Enterprise |
|---------|:---:|:----:|:--------:|:----------:|
| Cross-agent memory (local) | ✅ | ✅ | ✅ | ✅ |
| Memory search & retrieval | ✅ | ✅ | ✅ | ✅ |
| Memory injection (auto_tail) | ✅ | ✅ | ✅ | ✅ |
| Episodic memory (cross-session) | ✅ | ✅ | ✅ | ✅ |
| Traffic learning | ✅ | ✅ | ✅ | ✅ |
| headroom learn (failure mining) | ✅ | ✅ | ✅ | ✅ |
| SharedContext (multi-agent) | ✅ | ✅ | ✅ | ✅ |
| Memory bridge (Markdown import) | ✅ | ✅ | ✅ | ✅ |
| Qdrant + Neo4j backend | ✅ | ✅ | ✅ | ✅ |
| Project-scoped memory isolation | ✅ | ✅ | ✅ | ✅ |

### SDKs & Integrations

| Feature | OSS | Team | Business | Enterprise |
|---------|:---:|:----:|:--------:|:----------:|
| Python SDK | ✅ | ✅ | ✅ | ✅ |
| TypeScript SDK | ✅ | ✅ | ✅ | ✅ |
| Vercel AI SDK middleware | ✅ | ✅ | ✅ | ✅ |
| LangChain integration | ✅ | ✅ | ✅ | ✅ |
| Agno integration | ✅ | ✅ | ✅ | ✅ |
| Strands integration | ✅ | ✅ | ✅ | ✅ |
| LiteLLM callback | ✅ | ✅ | ✅ | ✅ |
| ASGI middleware | ✅ | ✅ | ✅ | ✅ |

### Observability & Dashboard

| Feature | OSS | Team | Business | Enterprise |
|---------|:---:|:----:|:--------:|:----------:|
| Local dashboard | ✅ | ✅ | ✅ | ✅ |
| /stats endpoint | ✅ | ✅ | ✅ | ✅ |
| /healthz + /readyz endpoints | ✅ | ✅ | ✅ | ✅ |
| Request logging (JSONL) | ✅ | ✅ | ✅ | ✅ |
| Cost tracking per request | ✅ | ✅ | ✅ | ✅ |
| Compression ratio tracking | ✅ | ✅ | ✅ | ✅ |
| Waste signal detection | ✅ | ✅ | ✅ | ✅ |
| **Org-level analytics** | ❌ | ✅ | ✅ | ✅ |
| **Historical reporting** | ❌ | ✅ | ✅ | ✅ |
| **Multi-project rollups** | ❌ | ❌ | ✅ | ✅ |
| **Exportable reports (CSV/PDF)** | ❌ | ❌ | ✅ | ✅ |
| **Trend views for ROI reviews** | ❌ | ❌ | ✅ | ✅ |
| **Prometheus metrics** | ✅ | ✅ | ✅ | ✅ |

### Administration & Governance

| Feature | OSS | Team | Business | Enterprise |
|---------|:---:|:----:|:--------:|:----------:|
| Proxy config (CLI/env) | ✅ | ✅ | ✅ | ✅ |
| Rate limiting | ✅ | ✅ | ✅ | ✅ |
| Budget limits (USD) | ✅ | ✅ | ✅ | ✅ |
| Request timeout controls | ✅ | ✅ | ✅ | ✅ |
| Compression profiles | ✅ | ✅ | ✅ | ✅ |
| **Org/project/workspace model** | ❌ | ✅ | ✅ | ✅ |
| **Team-level admin controls** | ❌ | ✅ | ✅ | ✅ |
| **Policy presets by team** | ❌ | ✅ | ✅ | ✅ |
| **Usage exports** | ❌ | ✅ | ✅ | ✅ |
| **Workspace segmentation** | ❌ | ❌ | ✅ | ✅ |
| **Role-aware admin actions** | ❌ | ❌ | ✅ | ✅ |
| **SSO / SAML** | ❌ | ❌ | ❌ | ✅ |
| **RBAC** | ❌ | ❌ | ❌ | ✅ |
| **Audit logs** | ❌ | ❌ | ❌ | ✅ |
| **Retention controls** | ❌ | ❌ | ❌ | ✅ |
| **Policy engine** | ❌ | ❌ | ❌ | ✅ |
| **Fleet management** | ❌ | ❌ | ❌ | ✅ |

### Security & Compliance

| Feature | OSS | Team | Business | Enterprise |
|---------|:---:|:----:|:--------:|:----------:|
| Local-first (data stays on device) | ✅ | ✅ | ✅ | ✅ |
| No prompt content in telemetry | ✅ | ✅ | ✅ | ✅ |
| Internal header stripping | ✅ | ✅ | ✅ | ✅ |
| HTTPS-only telemetry | ✅ | ✅ | ✅ | ✅ |
| 7-day grace period (offline) | ✅ | ✅ | ✅ | ✅ |
| **Security review packet** | ❌ | ❌ | ❌ | ✅ |
| **Compliance documentation** | ❌ | ❌ | ❌ | ✅ |
| **SOC2 readiness** | ❌ | ❌ | ❌ | ❌ (planned) |
| **HIPAA BAA** | ❌ | ❌ | ❌ | ❌ (planned) |

### Support

| Feature | OSS | Team | Business | Enterprise |
|---------|:---:|:----:|:--------:|:----------:|
| Community Discord | ✅ | ✅ | ✅ | ✅ |
| Documentation | ✅ | ✅ | ✅ | ✅ |
| **Email support (business hours)** | ❌ | ✅ | ✅ | ✅ |
| **Deployment assistance** | ❌ | ✅ | ✅ | ✅ |
| **Support SLA** | ❌ | ❌ | ✅ | ✅ |
| **Dedicated support engineer** | ❌ | ❌ | ❌ | ✅ |
| **Onboarding package** | ❌ | ❌ | ✅ | ✅ |
| **Architecture review** | ❌ | ❌ | ❌ | ✅ |
| **Premium support SLA** | ❌ | ❌ | ❌ | ✅ |

---

## Upgrade Triggers

### Builder → Team
- More than 1 team member using agents
- Need for shared compression policy
- Repeated request for reporting
- Want to govern how agents use context

### Team → Business
- Multiple teams or projects
- Need cross-team analytics
- Platform owner or AI lead exists
- Want workspace segmentation

### Business → Enterprise
- Security review required
- SSO/SAML mandate
- Compliance requirements (SOC2, HIPAA)
- Multi-business-unit rollout
- Air-gapped deployment needed
- Procurement/legal review

---

## "Why Pay" Summary

### Builder (Free)
> "Install Headroom, compress your agent context, save tokens. No strings attached."

### Team ($18k/yr)
> "Your whole team shares compression policies, sees unified analytics, and gets deployment support. Stop managing Headroom per-engineer."

### Business ($42k/yr)
> "Cross-team analytics, workspace segmentation, and policy governance. See where your AI spend goes across the entire org."

### Enterprise ($60k–$150k+/yr)
> "SSO, RBAC, audit logs, air-gap support, and a dedicated success team. Headroom meets your security and procurement requirements."

---

## Ambiguous Features (Needs Decision)

| Feature | Current State | Question |
|---------|--------------|----------|
| Prometheus metrics | OSS | Should advanced dashboards be Team+? |
| RedisCcrStore | OSS (cfg-gated) | Keep OSS or Team+ for multi-worker? |
| Traffic learning | OSS | Team+ for aggregate insights? |
| Episodic memory | OSS | Team+ for cross-session? |
| Code graph watcher | OSS | Team+ for enterprise code intelligence? |
| Subscription tracking | OSS | Internal; keep hidden |
| Provider fallback | OSS | Enterprise for multi-region failover? |

**Recommendation:** Keep all compression and CCR features in OSS to maximize adoption. Gate analytics, admin, and governance features behind paid tiers. Enterprise gates should be security/compliance features that procurement requires.
