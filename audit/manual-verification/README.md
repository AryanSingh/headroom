# Cutctx Release Manual Verification Master Checklist

**Status:** Release gate template — execute against the release candidate, not a developer workstation with untracked changes.

## Release scope and risk

Cutctx is a Python/Rust context-efficiency platform with SDK, CLI, provider-compatible proxy, memory and routing services, operator UI, SDKs, host plugins, IDE extensions, and optional enterprise services. The highest release risks are: accidental alteration of provider requests or streamed responses; unauthorized access to operator/tenant data; loss or misattribution of context/savings; unsafe configuration or routing changes; and a released artifact whose documented installation/configuration does not work on a clean machine.

This pack is deliberately split by ownership. A case is **not passed** until its required evidence is attached to the release record. `Needs confirmation` means the repository indicates capability but the test environment must confirm the deployed configuration or external-provider behavior.

## How to run this pack

1. Create an isolated, named test run: `RC_VERSION`, `RUN_ID`, and UTC start time.
2. Complete [00-prerequisites-and-evidence.md](00-prerequisites-and-evidence.md); never use production keys, tenant data, or a production dashboard.
3. Execute P0 cases in the order below. Stop promotion on any P0 failure, data-isolation failure, credential disclosure, request corruption, or unrecoverable startup/recovery failure.
4. Run every applicable P1 case. Execute P2 cases unless explicitly waived by a named release owner; record a rationale and residual risk for every waiver.
5. Complete [08-operations-documentation-and-gaps.md](08-operations-documentation-and-gaps.md), including the documentation matrix and gap ledger.

## P0 release gate

| Gate | Cases | Owner | Required evidence |
|---|---|---|---|
| Clean artifact/install | OPS-001–004 | Release engineering | install transcript, package metadata, version output |
| Proxy availability and auth | PX-001–005 | Proxy owner | `/livez`, `/readyz`, `/health`, auth denial/allow logs |
| Provider data plane | PX-010–018 | Provider owner | sanitized OpenAI, Anthropic, Gemini request/response captures including one stream each |
| Compression safety and CCR | CORE-001–006, PX-020–024 | Core owner | before/after token counts, preservation fixture, CCR retrieval/expiry evidence |
| Routing and failures | PX-030–036 | Routing owner | selected route, alias/preset evidence, fallback/retry/circuit evidence |
| Dashboard correctness | UI-001–006 | UI owner | screenshots at desktop/mobile width and matching API payloads |
| Tenant/admin boundaries (when EE enabled) | EE-001–007 | Security/EE owner | role matrix and cross-tenant denial evidence |
| Recovery and observability | OPS-020–024 | SRE | restart record, metrics/log/trace samples, data persistence proof |

## Feature inventory and traceability

| Module/path | Feature or behavior | Audience | Evidence source | Manual-verification status |
|---|---|---|---|---|
| `cutctx/client.py`, `cutctx/compress.py`, transforms/tokenizers | Python compression APIs, configuration, token accounting, errors | Python developer | code, tests, `README.md`, docs | CORE-001–012 |
| `cutctx/cli.py`, `cutctx/cli/` | setup/auth/init/install/wrap/proxy/memory/capture/learn/reports/savings/evals/admin commands | CLI operator | command registry/help, docs, tests | CLI-001–018 |
| `cutctx/proxy/server.py`, `handlers/`, `routes/`, `routing/` | HTTP data/control plane, auth, streaming, metrics, CCR, provider translation, routing | API client/operator | FastAPI routes, handler tests, API docs | PX-001–042 |
| `cutctx/memory/`, integrations, MCP | memory lifecycle, retrieval/injection, framework and MCP integration | agent/application developer | maps, public modules, tests/docs | MEM-001–012 |
| `dashboard/src/` | SPA routes, polling, auth, mutations, loading/error/accessibility | operator | React routes/components, Playwright/tests | UI-001–016 |
| `crates/` and `cutctx/_core` | native core/proxy/PyO3/parity/storage/tokenization | release engineer/developer | Cargo manifests, parity tests, maps | NATIVE-001–012 |
| `sdk/`, `sdks/` | TypeScript, Go, Python clients/adapters/examples | SDK user | public facades, package manifests/readmes/tests | SDK-001–016 |
| `plugins/`, `extensions/` | OpenCode/OpenClaw/Codex/Claude/agent/Hermes/OAuth hooks and IDE lifecycle/config | agent/IDE user | manifests/readmes/source/tests | INT-001–018 |
| `cutctx_ee/`, EE route modules | identity, RBAC/SSO, billing, policy, ledger, audit, retention, residency | enterprise admin/auditor | EE code/maps/routes/tests | EE-001–020 |
| packaging, Docker, docs, release material | installs, upgrades, deployment, security claims, documentation accuracy | release/SRE | manifests, Compose, docs | OPS-001–032, DOC-001–012 |

## Detailed checklists

- [Prerequisites, environment and evidence](00-prerequisites-and-evidence.md)
- [Complete feature inventory](07-feature-inventory.md)
- [Core Python package and CLI](01-core-python-and-cli.md)
- [Proxy, protocols, routing and control plane](02-proxy-and-provider-compatibility.md)
- [Memory, retrieval and framework integrations](03-memory-retrieval-and-integrations.md)
- [Dashboard operator UI](04-dashboard.md)
- [Rust/native components and SDKs](05-native-and-sdks.md)
- [Plugins and IDE extensions](06-plugins-and-ide-extensions.md)
- [Enterprise, operations, documentation and gaps](08-operations-documentation-and-gaps.md)

## End-to-end release journeys

| Journey | Required cases | Completion evidence |
|---|---|---|
| New user | OPS-001–004, CLI-001–004, PX-001 | clean VM/container log; successful `cutctx --version`, proxy and dashboard |
| SDK client through proxy | CORE-001, PX-001–024, SDK-001–006 | original/optimized request pair, correct response, savings and retrieval evidence |
| OpenAI / Anthropic / Gemini | PX-010–018 | one non-stream and one stream transcript per protocol, plus malformed/auth/error case |
| Savings and routing | PX-020–036, UI-003–005 | exact request ID visible in `/stats` and dashboard; configured alias/preset route selection |
| Memory/context | MEM-001–009 | write/query/injection/isolation/expiry record |
| Operator monitoring | UI-001–016 | health/savings/routing/governance/memory/replay/diagnostics pages and API reconciliation |
| Plugin/IDE workflow | INT-001–018 | installation, host activation, proxy ownership, compression/retrieval, graceful failure |
| Enterprise governance | EE-001–020 | tenant and role matrix, audit/ledger/retention/policy proof; N/A only if EE artifact absent |
| Failure and recovery | PX-033–036, OPS-020–024 | fault injection, retry/fallback, restart, preserved state and alerts/telemetry |

## Exit criteria

Release is eligible only when every applicable P0/P1 case passes, all provider/enterprise credentials used are test-only and revoked or rotated, documentation claims have a recorded result, and the gap ledger has no unaccepted Critical/High item. A test blocked by credentials, a missing service, a platform, or an unavailable external provider is **unverified**, not passed.
