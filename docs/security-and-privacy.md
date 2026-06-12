# Security & Privacy

## Data Flow Architecture

```
AI Agent → Headroom Proxy → LLM Provider
              ↓
         [Compression]
              ↓
         [CCR Storage] (local SQLite)
              ↓
         [Memory Store] (local SQLite)
```

## What Stays Local

| Data | Storage | Retention |
|------|---------|-----------|
| Request/response payloads | In-memory only | Request duration |
| CCR compressed originals | SQLite (`~/.headroom/ccr.db`) | Until TTL expiry (default 24h) |
| Episodic memories | SQLite (`~/.headroom/memories/`) | Until manual deletion |
| Request logs (if enabled) | Local JSONL file | Until rotation/deletion |
| License cache | `~/.headroom/license_cache.json` | 7 days |

## What Leaves the Machine

| Data | Destination | When | Required? |
|------|------------|------|-----------|
| LLM API requests | Anthropic/OpenAI/Google | Every request | Yes |
| Aggregate usage stats | Headroom cloud | Every 5 minutes | Only with license key |
| ONNX Runtime download | cdn.pyke.io | First run only | Can be pre-provided |
| Kompress model download | huggingface.co | First run only | Can be pre-provided |

## What We Never Collect

- Message content (prompts, tool outputs, responses)
- API keys or authentication tokens
- User data or personally identifiable information
- File contents or code
- Conversation history
- Tool call parameters or results

## Privacy Guarantees

### 1. Local-First by Default
Headroom runs in your infrastructure. No external API calls for compression. No data retention on external servers.

### 2. No Prompt Content in Telemetry
Optional telemetry sends only aggregate counts: request count, tokens saved, model distribution. Never message content.

### 3. Air-Gap Support
Pre-download models and run fully offline. No external network access required after initial setup.

### 4. Internal Header Stripping
All `x-headroom-*` headers are dropped before forwarding to prevent proxy fingerprinting.

### 5. 7-Day Offline Grace Period
If the license server is unreachable, cached license data is used for up to 7 days. Proxy continues normally.

### 6. No Content Logging by Default
Request logs contain metadata only (timestamps, token counts, models used). Full message logging is opt-in via `--log-full-messages`.

## Deployment Security

### Self-Hosted
Runs on your infrastructure, behind your firewall. No external dependencies for core functionality.

### Docker
Production Dockerfile with minimal attack surface. Non-root user. No shell in production image.

### docker-compose
Includes health checks, resource limits, and network isolation.

### Kubernetes
Production-ready manifests with:
- Network policies
- Pod security policies
- Secret management via Kubernetes Secrets
- Resource quotas
- Readiness/liveness probes

### Air-Gapped
No external network access required. Pre-download all dependencies. Run with `HF_HUB_OFFLINE=1` and `ORT_STRATEGY=system`.

## Network Requirements

| Connection | Required | Purpose |
|------------|:--------:|---------|
| LLM provider API | Yes | Forward compressed requests |
| `cdn.pyke.io` | First run | ONNX Runtime (can be pre-provided) |
| `huggingface.co` | First run | Kompress model (can be pre-provided) |
| `app.headroomlabs.ai` | No | License validation (optional) |

## Access Control

### Current
- Local proxy access (localhost only by default)
- Optional license key authentication
- No user management

### Coming (Enterprise Tier)
- SSO / SAML integration
- Role-based access control (Admin, Operator, Viewer)
- Audit logs for all administrative actions
- Retention controls for data lifecycle

## Compliance Roadmap

| Target | Timeline | Status |
|--------|----------|--------|
| SOC 2 Type II readiness | Q4 2026 | Planning |
| HIPAA readiness | Q4 2026 | Planning |
| GDPR data processing agreement | Q3 2026 | In progress |
| Security audit (third-party) | Q3 2026 | Scheduled |

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

**Q: What happens if the license server is unreachable?**
A: Headroom uses cached license data for up to 7 days (grace period). The proxy continues operating normally.
