# Headroom Security One-Pager

**Date:** June 13, 2026  
**Audience:** Enterprise security reviewers, procurement teams, CISOs

---

## Overview

Headroom is a self-hosted, local-first context optimization layer for AI agents. It compresses payloads between your agent workflows and LLM providers — without sending prompts, tool outputs, or conversation content to external services by default.

---

## Data Flow Architecture

```
┌─────────────────┐     ┌──────────────────────────────────┐     ┌──────────────┐
│  AI Agent       │────▶│  Headroom Proxy (self-hosted)    │────▶│  LLM Provider│
│  (Claude Code,  │     │                                  │     │  (Anthropic, │
│   Cursor, etc.) │     │  ┌─────────┐  ┌──────────────┐  │     │   OpenAI,    │
│                 │◀────│  │Compress │  │ CCR Store    │  │◀────│   Google,    │
│                 │     │  │ Engine  │  │ (local DB)   │  │     │   Bedrock)   │
└─────────────────┘     │  └─────────┘  └──────────────┘  │     └──────────────┘
                        │                                  │
                        │  ┌─────────┐  ┌──────────────┐  │
                        │  │Dashboard│  │ Memory Store │  │
                        │  │(local)  │  │ (local DB)   │  │
                        │  └─────────┘  └──────────────┘  │
                        └──────────────────────────────────┘
                              ▲                    ▲
                              │                    │
                        All data stays       Optional: aggregate
                        on customer infra    usage stats only
```

---

## What Stays Local (Always)

| Data Type | Location | Encrypted at Rest |
|-----------|----------|:-----------------:|
| Prompts and messages | Proxy memory (process-local) | N/A (not persisted) |
| Tool outputs | Proxy memory (process-local) | N/A (not persisted) |
| CCR originals | SQLite DB in workspace dir | Optional (SQLite encryption) |
| Memory store | SQLite DB in workspace dir | Optional |
| Episodic memories | `~/.headroom/memories/` | Filesystem permissions |
| Request logs | Local JSONL file (if enabled) | Filesystem permissions |
| Dashboard data | In-memory or local SQLite | Optional |

---

## What Leaves the Machine (Optional, Opt-In)

| Data | When | What | Frequency |
|------|------|------|-----------|
| License validation | Only when `HEADROOM_LICENSE_KEY` is set | License key, org ID | On startup + every 5 min |
| Aggregate usage stats | Only when `HEADROOM_LICENSE_KEY` is set | Request count, tokens saved, model distribution | Every 5 minutes |
| ONNX Runtime download | First run only (ML compression) | Binary from `cdn.pyke.io` | Once |
| Kompress model download | First run only (ML compression) | Model from `huggingface.co` | Once |

**Critical:** Headroom works fully offline after initial model download. Set `HF_HUB_OFFLINE=1` and `ORT_STRATEGY=system` for fully air-gapped operation.

---

## What We Never Collect

- ❌ Message content, prompts, or conversation history
- ❌ API keys, tokens, or credentials
- ❌ Tool outputs or function results
- ❌ File contents or code
- ❌ User identifiers or PII
- ❌ Model responses
- ❌ Any personally identifiable information

---

## Privacy Guarantees

1. **No prompt retention:** Message content is processed in memory and never written to disk by Headroom. CCR stores compressed originals locally — they never leave your infrastructure.

2. **No outbound calls for compression:** All compression happens locally in the Rust core. No external API calls are made for the compression pipeline.

3. **Optional telemetry:** License validation and usage reporting are only active when you set a license key. The proxy works normally without a license key — all compression features are available.

4. **Aggregate only:** Telemetry sends only aggregate counts (request count, tokens saved, model distribution). No individual request data is ever transmitted.

5. **HTTPS only:** All outbound communication (license validation, model downloads) uses HTTPS with certificate verification.

6. **Grace period:** If the license server is unreachable, cached license data is used for up to 7 days. The proxy continues working normally.

---

## Deployment Security

### Self-Hosted (Default)
- Runs in your infrastructure, behind your firewall
- No external network access required (after initial model download)
- Docker images available: `ghcr.io/chopratejas/headroom:latest`
- docker-compose for easy deployment

### Air-Gapped
- Pre-download ONNX Runtime and Kompress model
- Set `HF_HUB_OFFLINE=1` and `ORT_STRATEGY=system`
- No external network access required at any point
- Supports corporate SSL inspection environments

### Kubernetes
- Deployment manifests available
- Helm chart planned (Business tier)

### Authentication
- Proxy authentication via existing API keys (passthrough to provider)
- OAuth2 plugin available for managed deployments
- SSO/SAML coming in Enterprise tier

---

## Network Requirements

| Connection | Required | Purpose |
|------------|:--------:|---------|
| LLM provider API | Yes | Forward compressed requests to provider |
| `cdn.pyke.io` | First run | Download ONNX Runtime (can be pre-provided) |
| `huggingface.co` | First run | Download Kompress model (can be pre-provided) |
| `app.headroomlabs.ai` | No | License validation (optional, only with license key) |

**For air-gapped:** Pre-download ONNX Runtime and Kompress model, then run with `HF_HUB_OFFLINE=1` and `ORT_STRATEGY=system`. No external connections needed.

---

## Access Control

### Current (OSS)
- Proxy access via network binding (default: `127.0.0.1:8787`)
- API key passthrough to upstream provider
- Rate limiting per client
- Budget limits (USD) per deployment

### Coming (Enterprise)
- SSO / SAML integration
- Role-based access control (RBAC)
- Audit logging for all admin actions
- Retention controls for logs and data
- API key rotation and management

---

## Compliance Roadmap

| Certification | Status | Target Date |
|--------------|--------|-------------|
| SOC 2 Type II | Planned | Q4 2026 |
| HIPAA BAA | Planned | Q1 2027 |
| GDPR compliance review | Planned | Q3 2026 |
| ISO 27001 | Under evaluation | TBD |

---

## Frequently Asked Questions

### Does Headroom store our prompts?
No. Message content is processed in memory and never written to disk. CCR stores compressed originals locally in a SQLite database — these never leave your infrastructure.

### Does Headroom make external API calls?
Only for license validation (optional, only with a license key) and initial model download. All compression happens locally. The proxy works fully offline after initial setup.

### Can we run Headroom in an air-gapped environment?
Yes. Pre-download the ONNX Runtime and Kompress model, then run with `HF_HUB_OFFLINE=1` and `ORT_STRATEGY=system`. No external network access is required.

### What data is in the telemetry?
Only aggregate counts: total requests, tokens saved, and model distribution. No message content, API keys, or user data is ever transmitted.

### Is there a security review packet available?
Yes. Contact hello@headroomlabs.ai for a detailed security review packet including architecture diagrams, data flow documentation, penetration test reports (when available), and compliance documentation.

### How does Headroom handle API keys?
Headroom does not store or log API keys. Keys are passed through to the upstream provider. The proxy authenticates with the provider using the same credentials your agent provides.

### Can we audit what Headroom does?
Yes. Headroom provides JSONL request logs (optional), Prometheus metrics, and a local dashboard. Enterprise tier adds comprehensive audit logs for all admin actions.

---

## Contact

For security questions, compliance documentation, or a detailed security review packet:

**Email:** hello@headroomlabs.ai  
**GitHub:** github.com/chopratejas/headroom  
**Docs:** headroom-docs.vercel.app/docs
