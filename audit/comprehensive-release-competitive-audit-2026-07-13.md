# Comprehensive Product, Competitive, and Release Audit — 2026-07-13

**Audit scope:** OSS and EE source, CLI, proxy/API, dashboard, agent/MCP integrations,
SDKs, packaging/deployment, tests, release automation, benchmarks, and commercial
claims. This is an evidence report for the current worktree, not a claim that all
staging, paid-provider, or third-party systems were exercised.

## Executive decision

**Decision: conditional go for a PR/CI release candidate; no external-release
approval yet.** The local product regression surface is unusually strong: the full
offline Python suite, dashboard build, Rust workspace gates, and formatter gate pass.
The outstanding release conditions are a publishable multi-tool benchmark protocol
and staging/live-provider evidence that necessarily requires managed credentials and
environments.

| Gate | Evidence | Status |
| --- | --- | --- |
| Offline Python product surface | `pytest -q tests scripts/tests`: **8,719 passed, 266 skipped** | Pass, with scoped skips |
| Rust workspace | `cargo test --workspace`, `cargo clippy --workspace -- -D warnings`, `cargo fmt --all -- --check` | Pass |
| Dashboard production build | `dashboard: npm run lint && npm run build` | Pass |
| Source formatting | `ruff check . && ruff format --check .` | Pass |
| Direct benchmark harness | Direct script and module invocation ran 5 fixtures | Pass, Cutctx and LLMLingua-2 arms |
| Fair competitor comparison | Same-fixture LLMLingua-2 cold run completed; protocol remains too small for marketing claims | **Release condition for comparative marketing claims** |
| Authenticated staging | Defined in `.github/workflows/product-release-evidence.yml`; not run locally | **Release condition** |

## Surface inventory

The authoritative inventory comes from the command tree, source routes, packaging
extras, dashboard pages, deployment assets, and test modules. A surface is
**visible** when documented or present in normal help/UI; **gated** when it needs an
extra, entitlement, environment switch, or explicit install; **hidden** when it is
intended for internal/backwards-compatible orchestration only.

| Area | Verified shipped surface | Maturity / exposure | Primary verification |
| --- | --- | --- | --- |
| Compression and CCR | Content-aware compressors, cache, CCR retrieval, tool/schema/code/log/image/audio paths | Visible; some ML/code paths require extras | compression, CCR, modality, and transform suites |
| Proxy/control plane | OpenAI, Anthropic, Gemini, Bedrock/Vertex-compatible paths; routing, fallback, budgets, cache, rate limits, firewall | Visible; provider integrations have credential-dependent skips | proxy, provider, routing, and security suites |
| Orchestration | Profiles, deterministic routing, policy bundles, workflow gates, outcomes, audit receipts, scheduler recommendations | Visible management API; direct execution opt-in | `test_orchestration_*` |
| Memory/context | Local, shared, episodic, project-scoped, graph/vector backends, retrieval/injection controls | Gated by backend/feature configuration | memory and graph suites |
| Governance/EE | RBAC, SSO, SCIM, audit, retention, organizations, entitlements, spend/quotas, residency | API/CLI first; several controls need EE/runtime configuration | enterprise, entitlement, RBAC, SSO, SCIM, audit suites |
| Clients/integrations | CLI wrap/init/install, MCP server/registry, Codex/Claude/OpenCode/OpenClaw and agent integrations, TypeScript/Go SDKs | Visible; harness/provider availability varies | CLI, MCP registry, integration suites |
| Operator UI | React dashboard: overview, savings, orchestration, capabilities, governance, firewall, memory, replay, playground, docs | Visible; production bundle succeeds | dashboard tests plus lint/build |
| Deployment/release | Docker, Compose, Kubernetes, Helm, OSS/EE package guards, signed artifacts, release-please, staging evidence | Visible pipeline; managed staging remains external | deployment, release, packaging tests/workflows |

### Hidden and gated controls that must be explicitly labeled

- `CUTCTX_MCP_READ=on` enables the MCP `cutctx_read` tool; it is intentionally off
  by default.
- Direct orchestration execution is opt-in through
  `CUTCTX_ORCHESTRATION_DIRECT_EXECUTION`; decision-only routing remains available.
- Hidden CLI aliases and internal setup flags exist for compatibility and installer
  orchestration (`memory-eval`, `memory-eval-v2`, `init hook`, and wrapper
  `--prepare-only`); they are not product promises.
- The `all` extra intentionally excludes experimental, heavy, and proprietary
  extensions (including memory-stack, LLMLingua, and EE). Packaging claims must
  name the required extra rather than imply one-command parity.
- Dashboard feature controls include firewall, rate limiting, task-aware routing,
  deduplication, context budget, profiles, shared/episodic memory, cost forecast,
  autopilot, and routing presets. Their default state and restart requirement must
  be shown in operator documentation.

### CLI, SDK, and extension discovery record

`cutctx --help` exposes 29 top-level commands/groups across setup, install, wrap,
proxy, memory, capture, learning, reports/savings/performance, benchmarking/evals,
configuration/policies/profiles, agent savings, license/billing, organizations,
RBAC/audit, MCP, SSO testing, capabilities, and stack-graph navigation. The CLI
itself provides visible discovery for `setup`, `config doctor`, `benchmark`, and
`sso-test`, closing several gaps claimed by older internal inventories.

The source inventory also includes Python, TypeScript, Go, and Java SDK/package
surfaces; VS Code and JetBrains extensions; and Claude Code, Codex, OpenCode,
OpenClaw, Hermes, OAuth2, and agent-hook plugins. Every release should re-run the
CLI discovery command and package-specific test/build commands because artifacts in
these folders can drift independently of the proxy package.

## Validation evidence and coverage limits

### Completed local validation

1. Full Python test collection (`tests` and `scripts/tests`) passed with 8,719
   tests; 266 skips are environment/capability dependent. The release run emits
   JUnit XML and `scripts/summarize_pytest_skips.py` turns it into a test-by-test,
   reason-grouped manifest for owner review.
2. Rust test, clippy, and formatting gates passed for the workspace.
3. Dashboard lint and Vite production build passed.
4. The direct fixture benchmark now supports direct/module invocation, pinned
   cl100k token accounting, warm-ups/repetitions, F1/ROUGE-L retention, evidence
   metadata, and deterministic LLMLingua-2 window-safe chunking. The five-fixture
   smoke run yielded Cutctx **34.4% reduction**, **0.743** retention score, and
   **29.9 ms** median latency; LLMLingua-2 yielded **51.3% reduction**, **0.739**
   retention, and **1,591.6 ms** median latency. It remains too small and synthetic
   for a general marketing claim, but it is now valid regression evidence.

### Release test matrix to retain in CI/staging

| Layer | Required command or workflow | Acceptance condition |
| --- | --- | --- |
| Repository hygiene | `ruff check .`, `ruff format --check .`, `mypy cutctx --ignore-missing-imports`, `scripts/check_repo_hygiene.py` | Zero lint/format/type/hygiene failures |
| Python/Rust regression | `pytest -q tests scripts/tests`; Rust workspace gates | No unexpected failures; each skip is categorized |
| Product UI | Product-release-evidence fixture job and Playwright desktop/mobile projects | Dashboard and SDK contracts pass on built assets |
| Packages | Release dry run, OSS-wheel leak guard, SDK/package smoke imports | Installable signed artifacts contain no EE leakage |
| Deployments | Docker, Compose, Helm/Kubernetes config and smoke checks | Fresh install, upgrade, health, and rollback evidence |
| Managed integrations | Authenticated staging job | Provider auth, telemetry, dashboard, hosted compression, and gateway scenario artifacts are non-empty |
| Resilience/security | Provider outage/fallback, policy/rate/budget denial, restart and corrupted-store recovery | Fail closed where required; no credential/prompt leakage |

## Competitive benchmark assessment

### Current measured state

The repository contains a reproducible Cutctx-vs-LLMLingua fixture harness,
`benchmarks/run_comparison.py`, and a broader eval CLI. The documented direct
invocation (`python benchmarks/run_comparison.py`) fails because the repository
root is not on `sys.path`; `python -m benchmarks.run_comparison` succeeds. The
LLMLingua-2 was installed into the Python 3.11 test environment and the comparison
arm ran on the same five fixtures. The direct script invocation and module form now
both work. The runner records warm-ups, repetitions, cl100k token counts,
F1/ROUGE-L retention, and platform/interpreter metadata; LLMLingua inputs are
window-safe chunked rather than dropped. The measured micro-benchmark remains
regression evidence only because it lacks real corpora and downstream task quality.

### Why the previous score trailed LLMLingua-2

The old comparison did **not** show a product-quality loss. It compared a
structure-preserving Cutctx default against LLMLingua-2 configured with a blanket
`rate=0.5`, measured tokens as `len(text) // 4`, gave no quality score, did no
warm-up/repetition, and silently failed LLMLingua-2 on long model-window inputs.
That configuration will predictably reward higher deletion on prose and source,
even when the deleted content breaks a downstream task.

The corrected five-fixture smoke run gives both arms the same fixtures and pinned
tokenizer. It reports nearly equal lexical retention (**0.743** vs **0.739**) while
LLMLingua-2 deletes more tokens (**51.3%** vs Cutctx **34.4%**) at a much higher
median latency (**1,591.6 ms** vs **29.9 ms**). This is not a winner claim:
token/ROUGE retention
is a proxy, not task success. We should only say Cutctx is faster on this named
local smoke workload until a preregistered public-corpus evaluation completes.

### Public-corpus extension (not yet marketing evidence)

The eval loaders now run reproducible public tracks rather than only synthetic
fixtures. On 50 examples each, LLMLingua-2 reduced prose more on SQuAD
(**54.52%** vs **35.25%**) and LongBench/Qasper (**57.02%** vs **38.62%**) and
also had higher lexical retention on Qasper (**0.655** vs **0.536**). Cutctx
reduced structured/function-call context more on HumanEval (**85.08%** vs
**47.61%**) and BFCL (**68.91%** vs **47.76%**). These results explain the
apparent score gap: a conservative mixed-content router is not optimized for
LLMLingua's prose-deletion objective. They are diagnostic only: the HumanEval
and BFCL arms measure context retention, not code execution or valid function
calls, and no downstream answering model has yet been run.

The LongBench loader now pins the upstream revision and archive SHA-256 because
the official dataset uses a legacy loading script that modern `datasets` cannot
execute. This makes the Qasper artifact reproducible, but downstream task scoring
and multi-machine confidence intervals remain release conditions.

### Compression policy calibration

The router now exposes `off`, `safe`, and `aggressive` policies through both
proxy CLIs and `CUTCTX_COMPRESSION_MODE`. `off` is byte-preserving; `safe` is
the backwards-compatible default; `aggressive` applies a 40% ML target to
plain prose and has a deterministic sentence-selection fallback when the ML
runtime is unavailable. The selected policy is also reported by authenticated
`/health/config` and described in the dashboard capability and environment
reference surfaces; it is therefore not a hidden-only configuration. On the
first ten cached SQuAD examples, aggressive
reduced the word-count proxy by **54.29%** (1,341 → 613), compared with
**44.30%** at the earlier 50% target and the previously recorded LLMLingua-2
SQuAD reduction of **54.52%** on 50 examples. This is calibration evidence,
not a published comparative claim: it uses a word proxy and a 10-example slice,
so it must be repeated with pinned token counts, task scoring, and confidence
intervals before publication.

The tiered evaluation suite now accepts `--compression-mode off|safe|aggressive`
and threads the choice into its auto-started proxy. Its Tier 1–2 zero-cost slice
was executed under `aggressive` with all four checks passing (CCR round-trip,
information retention, verbatim compaction, and tool-schema integrity). The
tool-schema evaluator was decoupled from the HTTP provider handler so this
advertised no-API track no longer requires `httpx` in a minimal evaluation
environment.

### Exact skip accountability

The 266 number is **skipped tests**, not skipped customer tasks or missing product
jobs. They are primarily capability guards: credentials/live-provider scenarios,
optional integration dependencies, model/GPU/platform conditions, and network or
external-service tests. A release now needs the JUnit-derived manifest to identify
each test and its exact reason. A release owner must classify each as one of
`external-credential`, `optional-extra`, `platform-or-hardware`, `network-service`,
or `intentional-deprecation`, and must reject any uncategorized skip in a
release-critical suite.

### Competitor matrix and fair comparison requirements

| Segment | Comparison set | Required proof before a claim | Current audit finding |
| --- | --- | --- | --- |
| Prompt/context compression | LLMLingua/LLMLingua-2, Morph, Compresr, The Token Company, provider-native compaction/cache | Same fixed inputs, tokenizer, model, warm/cold cache state, token reduction, latency, fidelity, downstream task score | LLMLingua-2 smoke arm ran; no quality-scored or external-vendor comparison |
| AI gateway/control plane | LiteLLM, Portkey, Helicone, provider gateways | Provider breadth, routing/fallback, virtual keys/budgets, request trace, cost/latency, governance UX | Strong code breadth; independently verified feature parity and workflow ergonomics are incomplete |
| Memory/agent context | Mem0, LangGraph/LangChain, LlamaIndex, provider-native memory | Retrieval accuracy, multi-turn continuity, isolation, latency/cost, operator controls | Extensive unit/integration coverage; no head-to-head workload result |
| Enterprise control plane | Gateway/observability and identity vendors | RBAC, audit, SSO/SCIM, residency, retention, reporting, procurement artifacts | APIs/tests are strong; UI and external assurance/procurement evidence remain the risk |

**Benchmark protocol:** pin versions and configuration; publish raw JSON, fixture
hashes, machine details, repetitions and dispersion; separate code/tool-output,
prose/RAG, and mixed agent traces; include exact/verbatim fidelity, structured
output validity, retrieval/task quality, reduction, latency, throughput, cache
state, and cost. Treat a non-installed comparator or unavailable provider as
`not measured`, never as a loss or win.

## Scored gaps and release actions

Scores are `impact / effort / confidence` on a 1–5 scale. “Release” means a
customer-visible external release; a PR/CI release candidate can proceed with the
conditions listed above.

| Priority | Gap | Score | Required action / exit evidence |
| --- | --- | --- | --- |
| Closed | Python formatting gate | 4 / 2 / 5 | Repository formatted; Ruff check and format check pass |
| P0 | Comparative benchmark lacks downstream task scoring and confidence intervals | 5 / 3 / 5 | Public SQuAD, HotpotQA, HumanEval, BFCL, and LongBench/Qasper reduction tracks now run; add task execution/answer scoring, multiple machines/configurations, and publish raw evidence/version pins |
| P0 | Authenticated staging/managed-provider proof is absent from this audit | 5 / 3 / 5 | Run the required staging release workflow with release credentials; attach generated evidence artifacts |
| P1 | 266 skipped tests are not classified in release evidence | 4 / 2 / 4 | Emit a skip manifest grouped by reason/environment and require owner approval for release-critical skips |
| P1 | Broad product surface is unevenly discoverable: hidden/gated features can be mistaken for standard availability | 4 / 2 / 4 | Generate a capability manifest from CLI/routes/config and render it in docs/dashboard with tier/extra/flag status |
| P1 | Enterprise/operator capabilities are richer in APIs than UI/procurement workflow | 4 / 4 / 4 | Prioritize audit/RBAC/org/retention/report views and a truthful procurement packet; validate with a security-admin persona |
| Partial | Warning hygiene | 3 / 2 / 5 | Evaluation/relevance/dev extras now cap NumPy at `<2.3` for the SciPy stack; remaining unawaited-coroutine warnings still need a warning-budget gate and individual remediation |
| P2 | No complete cross-product benchmark for memory, gateways, and provider-native controls | 4 / 4 / 3 | Add representative scenario fixtures and adapters; start with decision-grade workflows rather than synthetic score chasing |
| P2 | Hosted-first onboarding and ROI proof compete poorly with simple API products | 4 / 4 / 3 | Package hosted/local parity smoke tests, SDK quickstart, and a seven-day savings-report path |

## Release recommendation and ownership checklist

**Conditional PR/CI go:** code regression, dashboard production build, and Rust
quality gates are green. **External release no-go until P0 conditions close.**

1. Release engineering: close Ruff formatting baseline, package/OSS-wheel/SDK dry
   runs, version/changelog validation, and artifact signing/provenance.
2. Platform/SRE: run authenticated staging evidence and deployment/upgrade/rollback
   checks against supported targets.
3. Product/engineering: repair and execute the competitor benchmark protocol; add a
   capability manifest plus a skip-evidence report.
4. Security/commercial: verify every public claim against the manifest and benchmark
   artifact; mark unavailable or entitlement-only functionality precisely.

## Reproduction log

```text
pytest -q tests scripts/tests
# 8719 passed, 266 skipped, 21 warnings in 445.73s

# A later JUnit evidence run on the same host reported 264 skips: two previously
# optional test paths ran after LLMLingua installation; the sole Playwright
# screenshot timeout passed when rerun in isolation.

pytest -q tests scripts/tests --junitxml=artifacts/pytest.xml
python scripts/summarize_pytest_skips.py artifacts/pytest.xml \\
  --output artifacts/pytest-skips.json
# Required release artifact: exact skipped test names and grouped reasons.

cargo test --workspace
cargo clippy --workspace -- -D warnings
cargo fmt --all -- --check
# passed

cd dashboard && npm run lint && npm run build
# passed

/opt/homebrew/bin/python3.11 -m benchmarks.run_comparison \\
  --output /tmp/cutctx-audit-llmlingua-benchmark.json
# 5-fixture smoke: Cutctx 34.4% reduction, 0.743 retention, p50 29.9 ms;
# LLMLingua-2 51.3% reduction, 0.739 retention, p50 1591.6 ms.
# Versioned JSON includes fixture SHA-256, tokenizer, platform, repetitions,
# and comparator versions. This remains regression evidence, not a marketing claim.

ruff check .
# passed
ruff format --check .
# passed
```

## Audit limitations

- No customer data, paid-provider credentials, production/staging secrets, or
  competitor services were used locally.
- Competitive product claims in prior repository material require fresh validation
  against primary vendor documentation and current product versions before external
  publication.
- The evidence is pinned to this worktree and should be regenerated for every
  release candidate, not copied forward as a standing certification.
