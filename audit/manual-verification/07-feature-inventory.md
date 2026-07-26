# Complete Feature Inventory

This is the source-derived inventory used by the master gate. `Status` points to the manual cases that must be executed; it is not an assertion that the feature currently works. **Needs confirmation** identifies an inferred/optional capability whose deployment applicability must be established in the release record.

| Module/path | Feature or behavior | Audience | Evidence source | Manual-verification status |
|---|---|---|---|---|
| `pyproject.toml`, `cutctx/__init__.py`, `client.py`, `compress.py`, models/config | Python package distribution, facade, sync API/config/results/errors | Python developer | manifest, public modules, tests, README | CORE-001–006; SDK-005 |
| `cutctx/compression/`, `transforms/`, `tokenizers/`, `relevance/`, `image/` | text/code/diff/log/search/JSON/schema/image/audio compression and token/relevance choices | developer | maps, optional extras, docs/tests | CORE-003, NATIVE-004 |
| `cutctx/cache/`, `ccr/`, `savings/`, `pricing/`, `reporting/` | semantic/cache optimization, reversible storage, attribution/pricing/reporting | operator/developer | maps, routes, docs/tests | CORE-002, CORE-006, PX-021, CLI-004 |
| `cutctx/cli.py`, `cutctx/cli/` | all command groups and output/exit/interactive flows | user/operator | Click registry/help, command modules, docs/tests | CLI-001–006 |
| `cutctx/install/`, `providers/*`, `intercept/`, `rtk/` | install/wrap/intercept/global routing/agent host discovery | user | maps, install docs, tests | CLI-002, INT-007, OPS-001 |
| `cutctx/proxy/server.py`, handlers/openai, interceptors | FastAPI assembly, OpenAI/request lifecycle, streaming, metrics/session/CCR/dashboard static serving | API client/operator | route definitions/handler tests | PX-001–024 |
| `cutctx/proxy/routing/`, model router/config | model alias/preset/complexity route, cross-provider translation, retry/failover/circuit | API client/operator | routing code/tests, model-routing docs | PX-030–036 |
| proxy providers/adapters | OpenAI, Anthropic, Gemini, compatible/custom, media and other advertised data-plane protocols | API client | handler/provider code, API docs/tests | PX-010–014 |
| proxy policy/security/rate/budget/egress | request auth, validation, policy/firewall, structured output, budget, egress, rate controls | operator/security | middleware/routes/tests/docs | PX-002–005, PX-022, OPS-024 |
| proxy admin routes | configuration flags, health/stats, sessions/replay/traces, routing/orchestration/admin CRUD | operator | `routes/*.py`, dashboard API/tests | PX-024, PX-033–035, UI-003–008 |
| `cutctx/memory/` and backends/adapters/writers/sync | hierarchical memory extraction/storage/query/ranking/injection/export/sync | agent developer/operator | maps, APIs, CLI/tests/docs | MEM-001–004, MEM-009–012 |
| `cutctx/integrations/` | ASGI, LiteLLM, LangChain/LangGraph, LlamaIndex, Agno, Strands adapters | framework developer | integration maps/examples/tests | MEM-006–008 |
| MCP registry/server and retrieval | compression/retrieve/stats tools, MCP installer/gateway | MCP client/agent user | package/docs/tests | MEM-005, MEM-010, INT-003 |
| `dashboard/src/App.jsx`, pages, components, lib | operator SPA shell, auth, polling, health, savings, routing, governance, memory, replay, diagnostics, playground | operator | React routes, tests, maps | UI-001–016 |
| `crates/cutctx-core` | native compression, tokenizers, CCR, relevance, signals, stack graph, transforms/cache/license primitives | runtime/release engineer | Cargo maps/tests/benches | NATIVE-002–005 |
| `crates/cutctx-proxy` | Axum reverse proxy, HTTP/provider/cache/policy/observability/native route paths | operator | Cargo source/maps/tests | NATIVE-003–005 |
| `crates/cutctx-py`, `cutctx/_core` | PyO3 binding and Python artifact ABI | Python developer/release engineer | maturin/Cargo/binding tests | NATIVE-001–002 |
| `crates/cutctx-parity` | Rust/Python fixture parity and examples | release engineer | parity code/examples/tests | NATIVE-002 |
| `sdk/typescript` | typed client, retry/auth, compress/simulate/hosted, stream/hooks/shared context/path APIs | TS/JS developer | public index/types/examples/tests | SDK-001–002, SDK-008–010 |
| TS adapters | OpenAI/Anthropic/Gemini/Vercel AI wrappers and conversion | TS developer | adapters/maps/tests/docs | SDK-003 |
| `sdk/go`, `sdks/go-cutctx`, `sdk/python`, `sdks/java-cutctx` | language SDK/client/readme examples (Java applicability needs confirmation) | SDK developer | module manifests/readmes/source | SDK-004–007, SDK-010 |
| `plugins/claude-code`, `codex`, `cutctx-agent-hooks`, `cutctx-plugin` | host manifests, hooks, compression/retrieval lifecycle | coding-agent user | manifests/readmes/hooks/source | INT-001–003 |
| `plugins/cutctx-opencode` | OpenCode tool/history/chat/compaction compression | OpenCode user | package/source/map/tests | INT-004 |
| `plugins/openclaw` | context engine, proxy management, gateway routes, retrieval tool | OpenClaw user | manifest/source/map/tests | INT-005 |
| `plugins/hermes`, `cutctx-oauth2`, gateway/retrieval packages | optional retrieval/auth integration | agent operator | readmes/source/manifests | INT-006, MEM-010 |
| `extensions/vscode` | extension lifecycle, proxy manager/stats/status/configuration | VS Code/Cursor user | package/README/source/tests | INT-008–009, INT-011–014 |
| `extensions/jetbrains` | Kotlin application service/settings/actions/widget | JetBrains user | build/source/map | INT-010–014 |
| `cutctx_ee` identity/org/RBAC/SSO/SCIM/MFA | tenant identity, roles, provisioning, access boundaries | enterprise admin | EE maps/routes/tests | EE-001–003 |
| `cutctx_ee` policy/audit/ledger/billing/memory_service | policy signing/enforcement, audit/retention, usage/billing, tenant memory | enterprise admin/auditor | EE APIs/maps/tests | EE-004–007 |
| EE/licensing/secrets/residency/airgap/DSR/spend/failover routes | enterprise governance/security/operations controls | enterprise operator | proxy routes/tests/docs | EE-004–006, PX-035 |
| `docker-compose.yml`, Dockerfiles, devcontainer, packaging | local/container deployment, persistence/health, build/release assets | SRE/release engineering | manifests/docs | OPS-001–004, OPS-020–024 |
| docs, README, API/config/reference, examples, changelog/releases | every documented instruction/claim/config/endpoint/example | all audiences | documentation catalog/source | DOC-001–012 |
| tests, fixtures, benchmark/eval harnesses | executable behavior, regression/benchmark/quality claims | maintainers | test tree/docs | CLI-005, NATIVE-005, SDK-009, DOC-011 |

## Required generated inventories at release-candidate freeze

1. Export `cutctx --help` and every `cutctx <group> --help`, then map every displayed subcommand to CLI-001–006.
2. Enumerate all FastAPI/APIRouter methods/paths after the RC is installed, including optional routers; attach method/path/auth/applicability mapping to PX-035.
3. Enumerate `dashboard/src/App.jsx` routes, dashboard API helpers, shipped plugin manifests, IDE extension contributions, and public SDK export declarations; attach to UI-007/UI-015/INT-018/SDK-010.
4. Enumerate documentation code blocks, environment variables, configuration fields, endpoint claims and examples; attach a row per claim to DOC-001–012.

These generated inventories are the mechanism that makes the plan exhaustive even when a release introduces a new route, command, document, plugin, or config key after the initial source inspection.
