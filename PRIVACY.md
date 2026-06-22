# Privacy — CutCtx

_Last updated: June 2026_

CutCtx is designed from the ground up to keep your data on your machine. This document explains exactly what CutCtx does and does not do with your data.

---

## Local-first architecture

The CutCtx proxy binds exclusively to `127.0.0.1` (loopback). It never listens on an external interface unless you explicitly configure it to do so. All compression logic runs in-process inside the Rust core — no data leaves your machine as part of compression itself.

The only network traffic CutCtx generates is the already-compressed request forwarded to whatever LLM API endpoint you configured (Anthropic, OpenAI, AWS Bedrock, a self-hosted model, etc.) — the same destination your application was already calling, just with fewer tokens.

---

## CCR store (reversible compression)

CutCtx's reversible compression feature (CCR) caches original content locally so the LLM can retrieve it on demand via the `cutctx_retrieve` MCP tool.

| Setting | Behaviour |
|---|---|
| Default | Originals stored in `~/.headroom/ccr_store.db` (SQLite, local disk) |
| `--ccr-ttl-seconds N` | Originals expire and are deleted after `N` seconds |
| `--ccr-ttl-seconds 0` | In-memory only — nothing written to disk, originals lost when the process exits |
| `--stateless` | Disables all writes to disk entirely; CCR runs in-memory for the session only |

The CCR store is a plain SQLite file on your local filesystem. It is never synced, uploaded, or shared by CutCtx.

---

## No telemetry by default

CutCtx does not collect usage statistics or telemetry unless you explicitly opt in.

- `--no-telemetry` — explicitly disables any usage stats collection, in case a future release adds an opt-in telemetry path.
- `--stateless` — writes nothing to disk at all. No CCR store, no audit log, no session data. Useful for air-gapped environments, compliance-sensitive deployments, or ephemeral containers where you need a clean slate after every run.

---

## What data goes to the LLM API

CutCtx forwards the **compressed** version of what your application was already sending to the LLM provider. Specifically:

- The content is smaller (fewer tokens) than what you originally sent.
- CutCtx does not add, append, or inject any of your data into any external service other than your configured LLM provider.
- CutCtx does not send your prompts, tool outputs, or conversation history anywhere except your configured LLM endpoint.

If you use `--stateless`, even the local CCR store is disabled, so no record of the original content is kept anywhere after the request completes.

---

## API keys and credentials

CutCtx does **not** store your API keys. Keys (e.g., `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) are read from environment variables and passed through directly to the upstream provider in the request headers. CutCtx never writes API keys to disk, logs them, or transmits them to any service other than the provider they belong to.

---

## Enterprise and VPC deployments

For enterprise and compliance deployments:

- The proxy can run entirely within a private network (VPC, on-premises, air-gapped). No outbound calls are required for compression itself — only the forwarded LLM request leaves the network boundary, and only to your configured endpoint.
- `--stateless` mode is recommended for shared-infrastructure or multi-tenant deployments where per-session isolation is required.
- Self-hosted LLM backends (vLLM, Ollama, private Bedrock endpoints) are supported. In a fully self-hosted configuration, no traffic ever leaves your private network.
- Audit logging (`cutctx audit`) is SQLite WAL-backed and stored locally. It is never exported automatically.

---

## What CutCtx does NOT do

- **No prompt collection.** CutCtx does not collect, store, or transmit your prompts to Anthropic, any CutCtx-operated service, or any third party.
- **No training on your data.** CutCtx does not use your conversations, tool outputs, or any data passing through the proxy to train or fine-tune any model.
- **No external calls except to your LLM provider.** The only outbound network call CutCtx makes at runtime is forwarding the compressed request to the LLM endpoint you configured. There are no "phone home" calls, no analytics beacons, and no background sync processes.
- **No API key storage.** Keys pass through to the upstream provider and are never written to disk by CutCtx.
- **No cloud dependency for compression.** Compression runs entirely in the local Rust core. No cloud API is called to perform compression.

---

## Data flow summary

```
Your application
    │
    │  original request (prompts, tool outputs, etc.)
    ▼
CutCtx proxy  ──── CCR store (local SQLite, optional, TTL-controlled)
    │
    │  compressed request (fewer tokens, same destination)
    ▼
Your configured LLM provider
(Anthropic · OpenAI · Bedrock · self-hosted · …)
```

Nothing in this flow touches any CutCtx-operated server. The proxy is a local process. The CCR store is a local file. The only external party that sees any of your data is the LLM provider you configured — and they see less of it than they would without CutCtx.

---

## Contact

For privacy questions or enterprise data-handling requirements, contact **privacy@cutctx.dev** or open an issue in the repository.
