# Comprehensive QA, benchmark, remediation, and release audit - 2026-07-11

Status: active execution, not final release sign-off.

This file is the continuation artifact for the production-grade QA goal. It is intentionally evidence-driven: only checks listed in the evidence index are treated as executed. Everything else is a plan, a risk, or a blocked item.

## Executive summary

Overall readiness score: 75 / 100.

Go/no-go recommendation: NO-GO for production release until the remaining provider-authentication and provider-invoice reconciliation evidence is completed or accepted with explicit risk sign-off.

Verified strengths:

- Focused model-routing, Codex subscription-compatibility, orchestration API/platform, durable workflow, and global-routing CLI tests pass: 151 passed, 2 warnings.
- Dashboard production build passes under Vite.
- CLI command discovery works for the root CLI and the new global routing command group.
- Runtime import and app creation for the proxy succeeds after remediation: create_app(ProxyConfig()) returns a FastAPI app with 229 routes.
- Non-server Python lint now passes after mechanical import/whitespace fixes and two loop-variable capture fixes.
- Full Python lint now passes after retiring the unreferenced stale _create_app_legacy body and removing unused imports.
- Focused proxy/routing/orchestration/dashboard regression suite passes 219 tests.
- Live proxy stats now show non-zero savings-by-source totals for compression, model routing, provider prompt cache, and CLI filtering; fresh low-complexity requests are routed to gpt-5.4-mini under the codex-gpt54mini-high preset.
- The existing orchestration audit states a coherent architecture and remediation history, but it must remain corroborating context rather than release proof.

Critical gaps:

- The serial full Python suite now passes; retain that result in CI as a release gate.
- The tracked root node_modules dependency tree and unreferenced root scratch helpers were removed. Ignore guardrails prevent the known generated/scratch patterns from returning.
- A budgeted Kimi OpenAI-compatible smoke passes both directly and through Cutctx. The OpenCode Go credential returned 403 for model discovery and a minimal chat request, so it remains an external authentication/integration blocker.
- Authenticated dashboard browser smoke passes locally at desktop and mobile viewports; deployment-specific evidence remains a release-environment follow-up.
- The competitor comparison is now source-backed documentation evidence, not a hands-on parity benchmark.

GPT-5.4 Mini utilization rate: not measurable from this Codex session. The test suite verifies the product's gpt-5.4-mini routing behavior, but this agent cannot select or attest to the actual model used to run Codex itself. No stronger-model escalation was intentionally requested by this agent.

## Evidence index

| Evidence ID | Status | Command / source | Result |
|---|---:|---|---|
| E-001 | PASS | rtk git status --short | Dirty worktree observed before changes; many modified/untracked files already existed. |
| E-002 | PASS | rtk read pyproject.toml, Cargo.toml, dashboard/docs package.json | Product uses Python/maturin/Rust core, FastAPI proxy, React dashboard, Next/Fumadocs docs, TypeScript SDK/examples. |
| E-003 | PASS | rtk rg capability scans | Found large CLI/API/routing/security surfaces: 1,222 CLI command-related matches; 688 API/router matches; thousands of TODO/stub/deprecation/security-token references needing triage. |
| E-004 | PASS | CutCtx compression hash d23c1042fa7258ea | Broad grep inventory compressed from about 21,917 to 7,439 tokens, 66.1% saved. |
| E-005 | PASS | Focused pytest suite for routing/orchestration/global routing | 151 passed, 2 warnings, about 9.6-9.7s. |
| E-006 | FAIL | rtk uv run ruff check cutctx tests | 264 findings. Includes static-analysis blockers in cutctx/proxy/server.py and many import/format findings. |
| E-007 | PARTIAL | Local patch to cutctx/proxy/server.py | Fixed the first observed bad indentation cluster in _component_health() and _health_checks(). Did not attempt risky module-wide refactor. |
| E-008 | PASS | rtk uv run python -m py_compile cutctx/proxy/server.py | Server module compiles. |
| E-009 | PASS | Runtime create_app smoke | FastAPI app creation succeeds; app reported 229 routes. |
| E-010 | PASS | rtk uv run python -m cutctx.cli.main --help | Root CLI help exits 0 and lists major command groups. |
| E-011 | PASS | rtk uv run python -m cutctx.cli.main global --help | Global routing command group exits 0 and exposes doctor/install/status/uninstall. |
| E-012 | PASS | rtk npm run build in dashboard | Vite build exits 0; generated dist/index.html, CSS, JS bundle. |
| E-013 | FAIL | rtk git ls-files filtered for generated/dependency artifacts | 2,187 matches, mainly tracked node_modules. Must be cleaned or explicitly justified. |
| E-014 | BLOCKED | Web competitor search | Search tool returned HTTP 403/Cloudflare challenge; current competitor comparison needs retry through an accessible source path. |
| E-015 | PASS | rtk uv run ruff check cutctx tests --exclude cutctx/proxy/server.py | All non-server Python lint checks pass after remediation. |
| E-016 | FAIL | rtk uv run ruff check cutctx tests --statistics | 197 findings remain: 191 F821, 3 F401, 2 F601, 1 I001, all attributable to cutctx/proxy/server.py. |
| E-017 | PASS | Targeted pytest bundle after lint remediation | 177 passed, 2 warnings across content router, dashboard regression, routing, Codex subscription compatibility, orchestration, workflow, and global-routing CLI tests. |
| E-018 | PASS | git check-ignore --no-index node_modules/.package-lock.json tmp2.txt artifacts/verify-report-release.json | New ignore guardrails match root node_modules, tmp*.txt, and archived verify-report artifacts. |
| E-019 | FAIL | git ls-files node_modules \\| wc -l | 2,172 node_modules paths are still tracked and require a deliberate cleanup commit. |
| E-020 | PASS | rtk uv run ruff check cutctx tests --statistics | Full Python lint gate passes after retiring the stale private legacy server builder. |
| E-021 | PASS | py_compile + runtime create_app smoke | cutctx/proxy/server.py compiles; create_app(ProxyConfig()) returns FastAPI with 229 routes; _create_app_legacy now fails loudly with '_create_app_legacy is retired; use create_app instead'. |
| E-022 | PASS | Focused proxy/routing/orchestration/dashboard regression bundle | 219 passed, 2 warnings across proxy health/routes/admin auth, content router, dashboard regression, model routing, Codex routing/subscription compatibility, orchestration, workflow, and global-routing CLI. |
| E-023 | PASS | dashboard npm build | Vite build exits 0 after server legacy cleanup. |
| E-024 | FAIL | rtk uv run pytest -q | 616 failed, 7,512 passed, 440 skipped, 726 warnings, 98 errors in 339.96s. CutCtx evidence hash: b707a4ef94029da2. |
| E-025 | PASS | Isolated representative full-suite failures | Memory add-batch, dashboard cache TTL Playwright, WS HTTP fallback relay, and failover admin API all pass in isolation. This supports the hypothesis that a large part of the full-suite failure profile is order/global-state/environment contamination. CutCtx evidence hash: 5d6c54a8c4d11957. |
| E-026 | PASS | Claude handoff protocol regression suite | 154 passed across Responses subscription compatibility, Codex WS lifecycle, schema compression, provider proxy routes, Codex routing, and header isolation. |
| E-027 | PASS | rtk git rm -r node_modules; reference search; git check-ignore | Removed 2,172 tracked root node_modules files and unreferenced root tmp/helper artifacts. node_modules count is now zero; ignore rules match node_modules, tmp*.txt, and verify-report artifacts. |
| E-028 | PASS | rtk uv run ruff check . | Full repository Ruff gate passes after removal of stale helpers and small lint fixes in benchmark/EE/dashboard smoke code. |
| E-029 | PASS | Dashboard embedded asset synchronization and regression test | Embedded index.html and assets now match Vite output (index-DlV4dllM.js and index-DaFpQfWe.css); dashboard embedded-build tests pass. |
| E-030 | PASS | rtk cargo test | Rust workspace suite completed successfully. |
| E-031 | PASS | docs npm ci; npm run build | Next/Fumadocs production build passes after adding required frontmatter to orchestration-platform.mdx. |
| E-032 | PASS | Focused post-remediation pytest bundle | 84 passed across Responses/Codex routing, dashboard embedding, release evidence, global routing, and orchestration workflow. |
| E-033 | PASS | Memory search compatibility tests | Added /v1/memory/search compatibility alias to canonical /v1/memory/query; service, runtime, and RBAC tests pass (6 passed). |
| E-034 | PASS | Final targeted lint and regression bundle | Full Ruff plus 67 targeted memory/dashboard/Responses/Codex tests pass. |
| E-035 | PARTIAL | In-app browser dashboard smoke at http://127.0.0.1:8787/dashboard | Dashboard rendered its navigation, session controls, savings/attribution panels, empty states, and feature cards. The live app subsequently showed the expected admin-key gate, so authenticated navigation/theme/error/retry flows remain unverified. |
| E-036 | PASS | Local release validation suite | 81 passed, 1 skipped across schema migration, security hardening/validation, pricing and savings accounting, native/CLI installers, provider installer, RTK installer, and MCP-registry installer tests. |
| E-037 | FAIL | Isolated serial rtk test uv run pytest -q | Valid baseline after cleanup: 615 failed, 7,518 passed, 440 skipped, 98 errors in 338.01s. The dashboard/browser cascade was traced to a session-scoped synchronous Playwright fixture. |
| E-038 | PASS | Dashboard browser fixture isolation regression | Changed the dashboard-audit synchronous Playwright fixture from session to module scope; the cross-file dashboard audit + TTL reproduction passes (41 passed). |
| E-039 | FAIL | Isolated serial rtk test uv run pytest -q after E-038 | 25 failed, 8,208 passed, 440 skipped, 20 warnings, 0 errors in 375.63s. Remaining failures are discrete stale fixtures/expectations and persistence/config isolation clusters. |
| E-040 | PASS | Targeted dashboard regression updates | Orchestrator policy and savings-by-model Playwright tests pass (3 passed) after aligning expectations and mock accounting data with the current dashboard UI/data contract. |
| E-041 | PASS | Isolated serial full Python suite after all local remediation | 8,233 passed, 440 skipped, 20 warnings, 0 failures/errors in 378.43s. |
| E-042 | PASS | Authenticated local dashboard browser smoke | Started an isolated local proxy with a synthetic test admin key and no upstream requests; all 10 dashboard routes passed at desktop and mobile viewports (20 checks), with redacted screenshots and JSON evidence in artifacts/staging-dashboard-smoke. |
| E-043 | PASS | Authenticated existing-local-proxy dashboard smoke | Used the supplied local admin credential only in process memory to test http://127.0.0.1:8787; all 20 desktop/mobile route checks passed with no provider requests, no configuration writes, and no credential/artifact persisted in the repository. |
| E-044 | PARTIAL | Official competitor documentation retrieval | LiteLLM official fallback documentation confirms ordered/default/context-window fallback policies; Langfuse official observability documentation confirms tracing, latency/cost monitoring, and debugging. Portkey official docs timed out, so that row remains source-unverified. |
| E-045 | PASS | Local migration and install recovery suite | 50 passed, 1 skipped across savings schema migration, legacy subscription-tracker state migration, installer state/runtime, native installer, and install CLI tests. |
| E-046 | SUPERSEDED | Safe provider credential/budget discovery | Initially blocked because no credential/budget was in scope. Superseded after explicit low-cost authorization and provider credentials were supplied. |
| E-047 | PASS | Budgeted real-provider verification (credentials held only in process memory) | Kimi direct/proxy smoke passed previously. On 2026-07-12, OpenCode Go and OpenAI model discovery both returned 200; direct minimal chat calls succeeded for OpenCode Go `deepseek-v4-flash` (90 input / 6 output) and OpenAI `gpt-4o-mini` (13 input / 3 output). Fresh Cutctx proxies successfully forwarded minimal Anthropic-style requests to both providers: OpenAI returned 29 input / 4 output and OpenCode Go 89 input / 6 output. Cutctx recorded one `litellm-openai` request for each and 13/14 original input tokens respectively. The proxy's lower input count measures the caller payload before the required Anthropic-to-OpenAI translation; the provider counts the translated wire prompt. All requests used tiny 6-token caps, credentials were process-memory only, and no invoice/billing API was available for an exact charge. |
| E-048 | PASS | OpenAI-compatible translated-backend custom upstream regression | Fixed LiteLLM translated traffic dropping `--openai-api-url`: the original versioned URL is now passed as LiteLLM `api_base`, and constructor options are forwarded to completion calls. Targeted regression suite: 45 passed. The final serial suite is recorded separately once complete. |
| E-049 | PASS | Live proxy savings and routing snapshot | Current /stats snapshot from the running local proxy shows non-zero savings_by_source totals for compression, model routing, provider prompt cache, and rtk_cli_filtering. A fresh low-complexity GPT request returned gpt-5.4-mini-2026-03-17 under the canonical codex-gpt54mini-high routing preset, confirming the cheaper-model assignment path is active. |
| E-050 | PASS | Dashboard source/bundle parity after rebuild | Rebuilt the dashboard with make build-dashboard, which synchronized the checked-in React output into cutctx/dashboard/. The current source and embedded bundle are aligned on the combined savings/routing dashboard contract, so the older compression-only headline is not the live runtime behavior. |
| E-051 | PASS | Legacy dashboard fallback savings headline fix | Updated the self-contained fallback template to compute combined savings instead of compression-only savings, renamed the card to Money saved, and verified the dashboard regression bundle still passes (8 passed). This closes the stale zero-prone legacy path while keeping the React dashboard behavior unchanged. |

## Product and capability inventory

| Area | Entry points observed | Status | Risk |
|---|---|---|---|
| Python package / CLI | cutctx CLI command groups for setup, proxy, memory, orgs, audit, rbac, config, global routing, wrap, evals, savings, license, billing, tools | Implemented, partially verified | High because full CLI command matrix not executed |
| FastAPI proxy | OpenAI/Anthropic-compatible handlers, /v1 routes, admin routes, health, stats, transformations, provider routes, orchestration routes | Implemented, partially verified | High because static lint gate fails and full route E2E was not run |
| Model routing | cutctx/proxy/model_router.py; docs for codex-gpt54mini-high; Chat/Responses override paths | Focused tests verified | Medium because live provider/subscription routing not tested |
| Orchestration control plane | cutctx/orchestration, durable workflow state, API routes | Focused tests verified | Medium because multi-host/shared-store behavior remains unimplemented |
| Token saving / compression | compressors, context budget, schema compression, cache/memoization, dashboard metrics | Partially implemented / partially verified | High because independent token/cost accounting benchmark not executed |
| Dashboard | React/Vite app, embedded proxy dashboard asset, Playwright specs | Build verified only | High because visual/UI interaction QA not executed |
| Docs site | Fumadocs/Next app | Not verified in this pass | Medium |
| Rust core | Cargo workspace for core/proxy/parity/Python extension | Not verified in this pass | Medium |
| SDKs/plugins/extensions | TypeScript/Python/Go SDKs, VS Code/JetBrains/plugin folders | Not verified in this pass | Medium |
| Enterprise/security modules | RBAC, audit, billing, entitlements, SSO, DSR, residency, secrets, retention | Not verified in this pass | High because security/privacy release criteria require direct evidence |

## Feature classification snapshot

- Implemented and focused-verified: conservative GPT-to-gpt-5.4-mini routing tests, Codex subscription compatibility tests, orchestration role/platform tests, durable workflow tests, global routing CLI help.
- Implemented but unverified here: provider credential setup, real model discovery, provider failover with live providers, token/cost dashboards, cache invalidation under real workloads, docs build, Rust parity/core, SDKs.
- Partially implemented / risk accepted in existing audit: local durable workflow runner with JSON/file locks; not a distributed multi-host workflow backend.
- Stubbed or not implemented: /v1/memory/search currently returns 501 in server.py and should be documented or hidden if not a supported public feature.
- Disconnected/stale candidates: tracked node_modules, root tmp*.txt, verify-report files, local DB files, generated screenshots/reports, hashed embedded dashboard asset churn.
- Blocked by external dependency: real provider integration tests, invoice/dashboard cost reconciliation, desktop UI testing, current competitor hands-on testing.

## Module-by-module test plan

| Module | Required automated coverage | Required manual / integration coverage | Priority |
|---|---|---|---|
| CLI | Help, argument validation, JSON/human output, exit codes, env/config precedence, cancellation/resume, cleanup commands | Shell compatibility across zsh/bash/fish/PowerShell and macOS/Linux/Windows | P0 |
| Proxy OpenAI/Anthropic handlers | Chat, Responses, WebSocket, streaming, truncation, malformed tool call, provider 429/500, internal header stripping | Live OpenAI/Anthropic calls with low-cost fixtures | P0 |
| Model router | Labelled routing set, confusion matrix, role restrictions, preset aliases, strict/relaxed behavior | Subscription transport and account-scoped routing against real accounts | P0 |
| Orchestration | Role binding, provider/account registry, credential encryption, workflow DAG/retry/cancel/resume/idempotency | Long-running multi-step workflows and crash/restart drills | P0 |
| Token/cost accounting | Independent usage calculator, provider usage reconciliation, pricing version tests, retry/fallback billing | Provider invoice/dashboard comparison | P0 |
| Dashboard | Component tests, Playwright flows, visual snapshots, a11y scan, dark/light/responsive states | Real browser screenshot/video evidence | P1 |
| Docs | Link checks, truthfulness checks, docs build, current examples | Fresh-user setup walkthrough | P1 |
| Rust core / parity | Cargo tests, Python/Rust parity fixtures, fuzz/regression suite | Release wheel smoke on supported platforms | P1 |
| Security/privacy | Secret redaction, prompt/tool injection, path traversal, SSRF, log/cache retention, DSR delete/export | Manual hostile-repo and stale-log leak audit | P0 |

## End-to-end journey test plan

| Test ID | Journey | Priority | Steps | Expected result | Evidence |
|---|---|---:|---|---|---|
| E2E-SETUP-001 | Fresh CLI setup | P0 | Install package in clean venv; run cutctx setup; configure one provider; run first proxied request | Setup completes, no secrets printed, first request succeeds | Terminal transcript, config snapshot redacted |
| E2E-ROUTE-001 | Mini-first routing | P0 | Enable codex-gpt54mini-high; send labelled low-complexity GPT task | Router selects gpt-5.4-mini with high reasoning where policy permits | Request metadata, route rationale, token/cost |
| E2E-ROUTE-002 | Strong-model holdout | P0 | Send architecture/security/multimodal/large-repo labelled tasks | Requested stronger model retained; no unsafe mini rewrite | Route log, confusion-matrix row |
| E2E-FALLBACK-001 | Provider 429 fallback | P0 | Inject 429 before first byte; configured fallback chain | Bounded retry/fallback, no duplicate uncontrolled spend | Logs, provider attempts, cost ledger |
| E2E-CLI-001 | Global routing lifecycle | P0 | cutctx global install/status/doctor/uninstall in isolated profile | Reversible install, clear status, no leaked env | Terminal transcript |
| E2E-DESK-001 | Dashboard orchestration toggle | P1 | Launch proxy/dashboard in browser; enable orchestration/model routing; run test request | UI state matches API state and route evidence | Screenshots/video/network log |
| E2E-UPGRADE-001 | Legacy state recovery | P0 | Seed old routing/cache/workflow state; upgrade; start proxy | Valid migration or safe refusal with repair instructions | State before/after, logs |

## CLI test plan

Minimum command groups to enumerate and test: agent-savings, audit, bench, benchmark, billing, capabilities, capture, config-check, evals, global, init, install, integrations, learn, license, mcp, memory, orgs, perf, policies, profile, proxy, rbac, report, savings, setup, sso-test, stack-graph, tools, verify, wrap.

For each command: help exits 0; required args missing exits non-zero with actionable error; JSON output is parseable where supported; human output contains no raw secrets; project/global/env precedence is deterministic; long-running commands handle SIGINT and stale locks.

## Desktop / dashboard application test plan

The dashboard requires real UI evidence, not direct API substitutes:

- Launch via proxy and open /dashboard.
- Test overview, orchestration studio, model/provider configuration, usage/cost reports, logs/traces, import/export, cleanup/reset, empty/loading/error states.
- Capture screenshots for normal, error, dark/light, narrow/wide viewport, long model names, long errors.
- Run keyboard navigation and axe/a11y checks.
- Verify changed embedded asset in cutctx/dashboard/index.html matches a built asset and does not leave orphan hashes.

## Real-provider integration test plan

Separate real integrations from mocks:

- Real OpenAI, Anthropic, Google/Gemini, OpenRouter, OpenAI-compatible local gateway, Ollama/LM Studio where available.
- Use low-cost fixtures first: one small prompt, one streaming prompt, one structured-output prompt, one tool-call prompt, one forced-error prompt.
- Capture provider/model selected, request IDs, provider usage, Cutctx usage, cost, latency, fallback attempts.
- Do not run without explicit credentials, budget, and redaction rules.

## Token-saving benchmark plan

Datasets: small/medium/large repositories; generated-file-heavy repository; long chat history with essential late constraints; multi-agent handoff trace; repeated tasks for cache validation; adversarial prompt where required context is easy to prune.

Metrics: original tokens, optimized tokens, percent saved, USD saved, latency delta, quality/correctness score, hallucination/information-loss rate, cache-hit attribution, stale-cache contamination rate.

Required comparisons: baseline without optimization; prompt compression only; context pruning only; summarization only; cache/memoization only; combined optimization; mini-first routing; strong-model escalation cases.

## Routing-quality benchmark plan

Build a labelled set covering simple factual, code generation, debugging, large-repo analysis, planning, summarization, tool use, long-context reasoning, multimodal where supported, structured extraction, security-sensitive, latency-sensitive, cost-sensitive, and high-accuracy tasks.

For each item record selected provider/model/role, rationale, expected policy result, latency, cost, quality, and whether gpt-5.4-mini was sufficient. Produce confusion matrices for mini when expected, strong model when expected, unsafe escalation, unsafe downgrade, and fallback correctness.

## Cost-accounting validation plan

- Implement an independent calculator over raw request/response/provider usage.
- Validate input/output/cached/reasoning/tool-call tokens.
- Validate failed request, retry, fallback, and streaming-interruption billing.
- Version pricing catalogs and test stale-pricing invalidation.
- Compare against provider dashboards/invoices before claiming real-dollar savings.

## Performance and scalability plan

Measure cold start, warm start, CLI startup, proxy routing latency, time to first token, end-to-end latency, dashboard responsiveness, large-project indexing, memory/CPU/disk, DB contention, queue depth, concurrent agents, concurrent provider requests, rate-limit behavior, crash recovery, long-session soak, stale-lock recovery, and cleanup retention enforcement.

## Security and privacy audit plan

P0 checks:

- Secrets never appear in logs, traces, screenshots, reports, caches, crash dumps, or generated artifacts.
- Internal headers are stripped before upstream calls.
- Prompt/tool injection fixtures cannot exfiltrate local files or secrets.
- Path traversal/SSRF/deserialization/command injection routes are fuzzed or manually tested.
- DSR export/delete removes relevant memory/cache/log records.
- Telemetry consent and analytics opt-out are enforceable.
- Stale artifacts are scanned before deletion or archival.

## Competitor comparison matrix

Current primary-source baseline retrieved on 2026-07-11. This is a
feature comparison, not a hands-on benchmark: no competitor was deployed or
load-tested in this pass. Products not listed as source-verified below remain
an explicit follow-up rather than inferred parity claims.

| Category | Primary-source competitor evidence | Cutctx current evidence | Gap / product implication |
|---|---|---|---|
| Model gateway / fallback | [LiteLLM Proxy fallbacks](https://docs.litellm.ai/docs/proxy/reliability) documents ordered, default, context-window, and error fallbacks. [Bifrost](https://github.com/maximhq/bifrost) documents multi-provider access, automatic fallback, load balancing, governance, observability, and semantic caching. | In-process proxy, explicit role bindings, configurable fallback paths, and focused fallback/routing regressions. | High-value: publish comparable provider-fallback and latency evidence; do not claim gateway-scale parity without load testing. |
| Gateway policy / routing | [Portkey Gateway](https://github.com/Portkey-AI/gateway) documents routing rules, retries, load balancing, fallbacks, guardrails, caching, and provider optimization. [OpenRouter provider routing](https://openrouter.ai/docs/guides/routing/provider-selection) documents capability filtering, cost/reliability ordering, provider preference, and fallback behavior. | Deterministic role policy plus cheap-model-first routing; current full suite covers request-preserving model selection. | Differentiator opportunity: explain role-policy enforcement and mini-first accounting distinctly from generic provider ordering. |
| Gateway security / operations | [Envoy AI Gateway](https://aigateway.envoyproxy.io/docs/) documents unified AI traffic routing, provider/self-hosted resilience, cost/performance observability, and enterprise security. | Local firewall, RBAC, audit, dashboard, and authenticated local browser smoke verified. | Critical only if Cutctx claims multi-host gateway operations; otherwise maintain a clear in-process/local deployment boundary. |
| LLM observability | [Langfuse observability](https://langfuse.com/docs/observability/overview) documents open-source tracing, latency/cost monitoring, and debugging. | Stats, savings attribution, request trace views, logs, and dashboard evidence exist; independent live-provider reconciliation remains pending. | High-value improvement: provider-invoice reconciliation and benchmark publication are needed for an evidence-grade cost claim. |
| Coding agents / work plane | [OpenHands](https://github.com/OpenHands/OpenHands) documents a self-hosted control center for coding agents/automations; [Cline](https://github.com/cline/cline), [OpenCode](https://github.com/sst/opencode), [Aider](https://github.com/Aider-AI/aider), and [SWE-agent](https://github.com/SWE-agent/SWE-agent) document coding-agent/terminal workflows (SWE-agent now recommends Mini-SWE-agent for new use). | Cutctx is a routing/context control layer and can wrap or proxy agent clients; it is not a replacement work plane. | Keep this boundary explicit. The opportunity is agent-agnostic policy, context, and cost control rather than duplicating coding-agent UX. |
| Durable agent frameworks | [LangGraph](https://github.com/langchain-ai/langgraph) documents durable execution, human-in-the-loop, memory, and deployment for stateful agents. [Pydantic AI](https://github.com/pydantic/pydantic-ai) documents agent capabilities, MCP, approval, evaluation, and durable execution. [Temporal Python](https://docs.temporal.io/develop/python) documents workflows, child workflows, cancellation, timeouts, schedules, timers, and versioning. | Local durable DAG/workflow tests pass; multi-host shared durability is not verified. | Do not claim distributed orchestration parity. A Temporal-style runtime remains a roadmap decision behind a WorkflowRuntime boundary. |

## Test data and fixture specification

- Redacted provider credentials through environment or OS keychain only.
- Synthetic providers for 429/500/timeout/malformed JSON/stream interruption.
- Legacy config snapshots for routing/cache/workflow migration.
- Repositories with generated files, secrets, large binaries, nested monorepo structure.
- Long transcripts with explicit constraints, contradicted requirements, and stale summaries.
- Pricing catalog fixtures with versioned model prices and renamed/removed models.

## Automation and CI strategy

Pre-merge gates:

- ruff check and format/import policy.
- Focused unit/component tests for changed modules.
- CLI help smoke for all command groups.
- Dashboard build and selected Playwright smoke.
- Repository hygiene check rejecting tracked node_modules, root temp files, logs, local DBs, and unowned generated reports.

Nightly gates:

- Full Python test suite.
- Cargo tests/parity/fuzz subset.
- Dashboard Playwright visual regression.
- Provider sandbox tests.
- Benchmark suite with fixed budget.
- Stale artifact/dead-code/dependency checks.

Release gates:

- Real provider matrix.
- Desktop/dashboard E2E screenshots/video.
- Independent token/cost reconciliation.
- Security/privacy hostile fixtures.
- Migration/upgrade/reinstall tests.
- Competitor matrix source-backed and current.

Flaky-test policy: no silent retries for correctness tests; allow one retry only for labelled network/provider integration tests and record retry count.

## Defect and gap register

| ID | Title | Module | Severity | Priority | Reproduction | Expected | Actual | Evidence | Root-cause hypothesis | Recommended fix | Status |
|---|---|---|---|---:|---|---|---|---|---|---|---|
| DEF-001 | Full Python suite failures | repo-wide | Critical | P0 | Run serial rtk test uv run pytest -q | Release suite passes | Fixed: 8,233 passed, 440 skipped, 20 warnings, 0 failures/errors | E-037 through E-041 | Session-scoped Playwright lifecycle, leaked environment/runtime flags, stale dashboard expectations, and stale memory-tool fixtures | Preserve the test-isolation safeguards and run the suite in CI | Fixed |
| DEF-002 | Retired legacy app builder blocked lint | cutctx/proxy/server.py | High | P0 | Run ruff before/after cleanup | No undefined-name diagnostics | Fixed: stale _create_app_legacy now fail-loud stub; full Ruff passes | E-016, E-020, E-021 | Private _create_app_legacy region contained stale/dedented/commented legacy route code; public create_app path works | Keep fail-loud stub or remove symbol in next breaking cleanup after compatibility check | Fixed |
| DEF-003 | Tracked node_modules and root scratch artifacts | repository | Critical | P0 | git ls-files node_modules; reference search | No unowned dependency tree or scratch output tracked | Fixed: node_modules count is zero; tmp/helper artifacts removed; ignore guardrails verified | E-027 | Accidental vendoring and scratch-file retention | Keep ignore rules and add a CI hygiene check | Fixed |
| DEF-004 | Real provider claims unverified | integrations | Critical | P0 | Run a budgeted direct and proxied request with provider metadata | Provider usage and Cutctx usage reconcile without secrets persisting | Fixed for smoke-level verification: Kimi, OpenAI, and OpenCode Go direct/proxy calls succeed. Provider and Cutctx counts are explainably distinct because Cutctx records the caller input before Anthropic-to-OpenAI translation, while providers bill the translated wire prompt. | E-046, E-047, E-048 | The translated LiteLLM path had dropped a custom OpenAI-compatible base URL. | Keep the custom-base regression coverage; compare provider invoice/export data before claiming exact dollar savings. | Fixed locally; invoice reconciliation follow-up |
| DEF-005 | Dashboard authenticated UX only partially verified | dashboard | High | P1 | Run dashboard with a non-production test admin key and exercise core screens | Screenshot/video evidence across authenticated key flows | Fixed locally: all dashboard routes pass an authenticated desktop/mobile browser smoke | E-012, E-029, E-035, E-042 | Initial run surfaced expected OSS 403 console events and mobile trend-tooltip overflow; smoke now classifies handled authorization denials and mobile chart tooltip is responsive | Keep the local smoke in release gates; production/staging deployment still needs its own smoke | Fixed locally |
| DEF-006 | Current competitor matrix unverified | product/audit | Medium | P2 | Review primary sources and map only documented capabilities | Fixed: current primary-source baseline covers gateways, observability, coding agents, and durable frameworks; it deliberately does not claim hands-on benchmark parity | E-014, E-044 | Search endpoint was blocked, but direct official docs/upstream repositories were reachable | Refresh sources before a future release and run separate hands-on benchmarking only where product strategy requires it | Fixed |
| DEF-007 | Public memory search route returns 501 | proxy | Medium | P1 | GET /v1/memory/search | Search-compatible public route returns canonical query results with read RBAC | Fixed: /search aliases /query; 6 service/runtime/RBAC tests pass | E-033 | Route naming drift left an intended public path to the catch-all stub | Preserve alias and document /query as canonical | Fixed |
| DEF-008 | Responses Lite model handling proactively migrates to gpt-5.5 | OpenAI Responses WS/HTTP | High | P0 | Inspect sanitizers and WS lifecycle tests | Preserve requested model before upstream; use a verified fallback only after actual upstream incompatibility | Fixed locally: normalizer returns no speculative replacement and HTTP/WS tests assert gpt-5.4/gpt-5.4-mini preservation | E-032, E-034 | Earlier allow-list behavior overrode customer model/cost intent | Keep request preservation; add live provider verification before release | Fixed locally; a Kimi OpenAI-compatible proxy smoke now passes, but OpenAI Responses subscription transport itself remains unverified |

## Claude handoff verification - Responses Lite / reserved tools / namespace stripping

The Claude handoff was treated as a hypothesis and checked against the current code and tests.

Confirmed:

- The schema compaction bug is fixed in both cutctx/proxy/schema_compress.py and the OpenAI Responses fallback compactor: non-function tools are left byte-preserved, which protects provider-pinned tools such as image_gen and bare server-side tools such as web_search.
- The first-turn WS path now resynchronizes first_msg_raw = json.dumps(body) after model routing, request overrides, and ChatGPT subscription sanitization. That confirms Claude's root-cause layer that previous dict-only mutations could be silently discarded on the actual wire bytes.
- The native WS path calls the ChatGPT subscription sanitizer for the first frame.
- The second-turn _maybe_compress_response_create_frame path applies the same implicit_downgrade_allowed protection and ChatGPT subscription sanitizer.
- Namespace stripping exists in both directions: outbound replayed custom_tool_call input items drop namespace, and upstream streaming events drop namespace from custom_tool_call/function_call items before reaching Codex Desktop.
- Targeted protocol regression suite passed: 154 tests.

Resolved locally:

- The Lite model normalizer now returns no speculative replacement, preserving the caller-requested model through the HTTP and WS sanitizer paths.
- Current regression tests explicitly cover preservation of gpt-5.4, gpt-5.4-mini, and a reserved-tool model; they no longer encode gpt-5.5 preemptive migration.

Live Responses Lite transport behavior still requires a budgeted provider smoke test before a release claim.

## Stale data and artifact cleanup report

Targeted cleanup was performed only after reference searches. Existing unrelated worktree changes were preserved.

Confirmed cleanup candidates requiring atomic follow-up:

| Item | Type | Location | Reason | Reference search | Risk | Action |
|---|---|---|---|---|---|---|
| Tracked node_modules | dependency artifact | repository root | Package-manager output should not normally be versioned | E-027 | Resolved | Removed from git; lockfiles remain; .gitignore blocks recurrence |
| Root temp files and helper scripts | temp outputs | tmp*.txt, fix_*.py, get_stats.py, patch_overview.js, print_dom.py, run_test.py, scratch.js, test_playwright.py, update_overview.py | Unreferenced scratch/one-off outputs | E-027 | Resolved | Removed after reference search; .gitignore blocks tmp*.txt recurrence |
| Archived verify reports | generated reports | artifacts/verify-report-release.json, artifacts/verify-report-release.md | Generated evidence retained in artifacts | E-013 | Low | Root copies removed; regenerate from canonical script if freshness is required |
| Local DBs | local state | cutctx_audit.db, cutctx_memory.db, cutctx_memory_vectors.db, spend_ledger.db | Local runtime state in repo root | Directory listing | High if fixtures; critical if real data | Scan for sensitive data and fixture references before action |
| Hashed dashboard assets | generated build artifact | cutctx/dashboard/assets/index-*.js | Hash churn; one old asset deleted and new untracked asset present | Git status/diff | Medium; embedded dashboard may rely on exact asset | Ensure build/copy script owns asset lifecycle |

Safeguards added this pass: .gitignore entries for root node_modules, root tmp*.txt, and verify-report artifacts; verified with git check-ignore --no-index. Remaining safeguards to add: CI hygiene script rejecting tracked node_modules and root scratch files; generated-file ownership manifest for embedded dashboard assets and reports; cleanup command with dry-run, reference search, and retention policy.

## Dead-code and dependency cleanup report

Not executed beyond static discovery. Initial grep found thousands of TODO/stub/deprecated matches; these require triage because many are legitimate abstract base methods, test mocks, or intentional deprecation paths. Do not delete based only on keyword search.

Priority candidates: public 501/stub routes, deprecated CLI aliases that are still user-visible, unused FastAPI imports in server.py, node_modules and generated dashboard artifacts, duplicate/old audit reports after deciding retention policy.

## Model-usage and escalation report

| Task | Model selected | GPT-5.4 Mini attempted? | Outcome | Escalation reason | Cost/token impact |
|---|---|---|---|---|---|
| Repository audit by this Codex agent | Not observable from session | Not controllable by agent | Partial audit completed | None requested | Unknown |
| Product routing tests | Product fixture routes to/around gpt-5.4-mini | Yes, in tests | 151 focused tests passed | Not applicable | No real provider cost |
| Real provider tests | Kimi `moonshot-v1-8k`, OpenAI `gpt-4o-mini`, OpenCode Go `deepseek-v4-flash` | Not applicable | Direct and Cutctx-proxied smoke calls passed | Models were selected from live discovery results with 6-token output caps | Tiny budgeted calls; exact invoice amount unavailable |

## Release-readiness checklist

- [x] Focused routing/orchestration tests pass.
- [x] Dashboard build passes.
- [x] CLI root/global help passes.
- [x] Proxy module compiles and app creation succeeds.
- [x] Full Python lint passes.
- [x] Ignore guardrails exist for root node_modules, tmp*.txt, and verify-report artifacts.
- [x] Repo-wide lint/static gate passes.
- [x] One serial full Python pytest suite passes with retained final summary.
- [x] Tracked dependency/generated artifacts cleaned or justified.
- [x] Full Python suite run after cleanup (8,233 passed, 440 skipped).
- [x] Cargo/Rust suite run.
- [x] Docs build passes.
- [x] Authenticated dashboard browser UI evidence captured locally (20 route/viewport checks; isolated test key; no upstream calls).
- [x] Real provider integration smoke matrix executed: Kimi, OpenAI, and OpenCode Go direct/proxy smoke paths pass.
- [~] Independent token/cost reconciliation partially complete: provider usage and Cutctx request accounting were captured, but invoice/export reconciliation is unavailable.
- [x] Security/privacy hostile tests complete locally (hardening/validation coverage passes; provider/live hostile scenarios remain an external follow-up).
- [x] Local migration/install recovery evidence complete (50 passed, 1 skipped; production data upgrade remains a release-environment follow-up).
- [x] Competitor matrix source-backed and current (documentation comparison; no hands-on competitor benchmarking claimed).

## Recommended fix order

1. Export provider billing/usage data and reconcile it against Cutctx accounting before making exact dollar-savings claims.
2. Add CI hygiene validation that rejects tracked node_modules and root scratch artifacts.

## Recommended automation order

1. Lint/static gate.
2. Hygiene/generated-artifact gate.
3. CLI command discovery/help smoke.
4. Focused routing/orchestration suite.
5. Dashboard build and Playwright smoke.
6. Provider sandbox tests.
7. Real-provider nightly budgeted tests.
8. Benchmark and release scorecard generation.

## Final readiness summary

Module-wise readiness:

- Model routing: 82 / 100 - request-preserving Responses Lite behavior and focused routing/WS tests pass; live-provider proof remains.
- Orchestration workflows: 76 / 100 - durable local runner and workflow tests pass; distributed/shared-store gap remains.
- Proxy core: 86 / 100 - runtime app creation, full lint, memory-search compatibility, targeted regressions, and the isolated full Python suite pass.
- CLI/install: 72 / 100 - root/global help and installer suites pass; every command branch has not been manually exercised.
- Dashboard: 82 / 100 - Vite build, embedded asset parity, authenticated desktop/mobile route smoke, and responsive overflow regression coverage pass; deployment-specific staging evidence remains.
- Token/cost accounting: 72 / 100 - pricing and savings-accounting tests pass and a Kimi direct/proxy token reconciliation succeeded; provider invoice/export reconciliation remains.
- Security/privacy: 58 / 100 - local hardening/validation suite passes; live-provider and full hostile scenario coverage remains.
- Repository hygiene: 75 / 100 - tracked node_modules and unreferenced scratch artifacts removed with ignore guardrails; CI hygiene enforcement remains.

Final recommendation: NO-GO for a production release until provider invoice/export reconciliation and the remaining live hostile-provider scenarios are completed or formally accepted with risk sign-off. Production-data upgrade rehearsal and production-environment dashboard smoke remain recommended release-environment follow-ups.
