# Repository Atlas: Cutctx / Headroom

## Project Responsibility

Cutctx is a protocol-aware context-efficiency layer for LLM and coding-agent
workloads. It combines a Python SDK/CLI, an OpenAI/Anthropic/Gemini-compatible
proxy, native Rust compression and transport components, memory and routing
services, an operator dashboard, enterprise governance, SDKs, and host plugins.

## System Entry Points

- `cutctx/cli.py` and `cutctx/cli/`: the `cutctx` command and operational workflows.
- `cutctx/proxy/server.py`: FastAPI proxy assembly, lifecycle, provider routes, and admin APIs.
- `cutctx/client.py` and `cutctx/compress.py`: application-facing Python SDK surfaces.
- `dashboard/src/main.jsx`: React operator console bootstrap.
- `crates/cutctx-proxy/src/main.rs`: native Axum proxy binary.
- `crates/cutctx-py/src/lib.rs`: PyO3 bindings for native compression primitives.
- `pyproject.toml` / `Cargo.toml`: Python distribution and Rust workspace manifests.
- `docker-compose.yml`: optional memory-service dependencies for local operation.

## End-to-End Flow

1. An SDK, CLI wrapper, IDE/plugin, or compatible HTTP client sends a request.
2. The proxy authenticates the client, classifies provider/protocol content, and
   applies cache-safe compression, memory, policy, routing, and egress controls.
3. A provider adapter forwards the preserved/transformed request and streams the
   upstream response back to the client.
4. Savings, latency, routing, audit, budget, and memory outcomes are persisted or
   emitted to the dashboard/telemetry surfaces.
5. Enterprise extensions add tenant identity, entitlements, billing, retention,
   policy, and tamper-evident audit/usage services when installed.

## Repository Directory Map

| Directory | Responsibility | Detailed map |
|---|---|---|
| `cutctx/` | Python SDK, CLI, proxy runtime, transforms, memory, providers, security, telemetry, and operations. | [Map](cutctx/codemap.md) |
| `cutctx_ee/` | Optional commercial multi-tenant governance, identity, billing, policy, audit, and retention services. | [Map](cutctx_ee/codemap.md) |
| `dashboard/` | Vite/React operator console for health, savings, routing, governance, memory, replay, and diagnostics. | [Map](dashboard/codemap.md) |
| `crates/` | Rust compression core, native proxy, Python bindings, and parity tooling. | [Map](crates/codemap.md) |
| `sdk/` | TypeScript, Go, and Python client libraries and provider adapters. | [Map](sdk/codemap.md) |
| `plugins/` | Coding-agent, gateway, MCP, retrieval, and authentication integrations. | [Map](plugins/codemap.md) |
| `extensions/` | VS Code and JetBrains proxy-management integrations. | [Map](extensions/codemap.md) |

Each mapped child directory contains its own `codemap.md` with responsibility,
design, control flow, and integration details derived from production source.
