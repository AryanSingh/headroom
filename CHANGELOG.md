# Changelog

## 2026-07-18 — Commercial hardening, attribution integrity, benchmarks

**Guided Safe Savings Mode** (feature-flagged, read-only): status model,
authenticated `GET /v1/orchestration/safe-savings/status`, `cutctx routing
status` CLI, and a dashboard panel with confirmed rollback to
`orchestrator_mode: off`. Discoverability via
`CUTCTX_SAFE_SAVINGS_EXPERIENCE`; the flag never enables routing.

**Savings attribution integrity (schema v7):** the lifetime
`model_routing_savings_usd` counter had drifted 4.1x below the canonical
by-source ledger (it re-estimated routing savings at the routed-to model's
flat input rate instead of the router's source−target delta). The typed
counter now adopts the by-source ledger, a one-time v7 migration reconciles
historical data (pre-migration values preserved under
`attribution_reconciliation`), and the Savings dashboard badges reconciled
ledgers.

**Entitlement enforcement on the request path:** episodic/cross-agent
memory (BUSINESS tier) is fail-closed gated at proxy init, on both
config-flags endpoints, and re-checked after startup license validation;
`UsageReporter.validate_license()` now runs at startup and a validated plan
overrides the declared tier (expired/invalid → free tier). CCR is
free-tier by prior product decision.

**Compression quality guarantees:** the content router never returns
output larger than its input (`expansion_guard`); Python code elision now
keeps `from __future__` imports first (reassembled output is
`compile()`-verified) and preserves numeric configuration constants in a
`values:` anchor line (code information recall 0.400 → 0.800 measured).

**Measured benchmarks (recorded in `benchmark_results.md` and the
2026-07-17 audit addendum):** per-request proxy overhead p50 2.5 ms / p95
3.1 ms (~443 req/s single-worker, 0 failures); routing quality 75/75 with
zero unsafe downgrades; four-corpus compression matrix with honest
kept-fraction framing.

**Commercial surface:** public plans/feature matrix
(`docs/content/docs/plans.mdx`) and published SLA (`docs/content/docs/sla.mdx`),
both test-pinned; PRODUCT_GUIDE enforcement claim corrected; dead doc links
repointed.

## Latest Verification Notes - 2026-07-03

- 2026-07-04 verification rerun: restored a corrupted uncommitted working-tree
  layer to committed source state, reran Python/Rust/dashboard gates, and
  recorded the remaining `ruff check .` release blocker in
  `artifacts/pending-items.md`.
- 2026-07-04 release-readiness follow-up: removed the dead duplicate legacy
  proxy app factory, restored live request-id/firewall middleware in
  `create_app()`, made CI-pinned Ruff check/format green, and reran full
  Python/Rust/dashboard release gates.
- WS1-WS3 release polish docs added: a quality-at-budget benchmark framing
  document and current outreach positioning templates now capture
  provider-native comparison caveats and design-partner messaging.
- Release QA planning added: `artifacts/end-to-end-bug-hunt-plan.md` defines
  the UI, API, feature, stub/fake-state, and release-claim audit workflow.
- WS7 Context Assurance completion gaps fixed: `cutctx report assurance`
  exists for JSON/markdown evidence export and `--verify` chain validation,
  matching the verification instructions embedded in exported bundles.
- WS8 replay extension discovery fixed: `ReplayPipelineExtension` is
  registered under the actual `cutctx.pipeline_extension` entry-point group
  and also loaded by an env-gated `CUTCTX_REPLAY=1` fallback for editable/local
  installs.
- Rust license verification test fixed to seed a fresh empty CRL cache in the
  debug/test path, preserving fail-closed revocation semantics while allowing a
  locally signed Ed25519 enterprise test token to verify as Enterprise.

All notable changes to Cutctx will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.31.0](https://github.com/AryanSingh/headroom/compare/v0.30.0...v0.31.0) (2026-07-14)


### Features

* add config doctor command ([362724f](https://github.com/AryanSingh/headroom/commit/362724f147cd342ae51fb375d3af24fe9c0e1d48))
* add environment client factory ([13f5943](https://github.com/AryanSingh/headroom/commit/13f594317516fcefcba75f721676f88a62f63f25))
* add first-run CLI guidance ([363a2e7](https://github.com/AryanSingh/headroom/commit/363a2e79861af886b4672e65818db9f126b359c2))
* add get_crl() to LicenseDB + full product audit report (7,767 tests, 8.5/10 score) ([ca05aed](https://github.com/AryanSingh/headroom/commit/ca05aed4f18c7a16e6fc1eec78c9a40b2d7eafe5))
* add Helm ServiceMonitor support ([37d331d](https://github.com/AryanSingh/headroom/commit/37d331d5f055fafcdfd7d664229e3b6ae82164bd))
* add install capability profiles ([0a65ed4](https://github.com/AryanSingh/headroom/commit/0a65ed40afb7865f96e9f9d67471ccfa1c11d431))
* Add interactive controls to Orchestrator Insights page ([ce8b9bf](https://github.com/AryanSingh/headroom/commit/ce8b9bfdbb3b2c4cf797c2ca9831354cee7f6d2d))
* Add light mode, fix UI layout bugs, handle memory 404 gracefully ([38b69e1](https://github.com/AryanSingh/headroom/commit/38b69e1895bff582c349062d16ae6124568b3c9a))
* Add proxy intercept functionality and savings by client dashboard view ([e591679](https://github.com/AryanSingh/headroom/commit/e591679d371953f4348d2e356e9a17f5cdd8406e))
* add proxy request path benchmark ([d6ad1ee](https://github.com/AryanSingh/headroom/commit/d6ad1ee39531f511459e416c839b833650c82a0e))
* Add savings by model to dashboard and fix Governance/Docs pages ([b7f31e2](https://github.com/AryanSingh/headroom/commit/b7f31e26ca3b356e47fe63e989a518a9f4b7244b))
* add strict compression failure mode ([16168dc](https://github.com/AryanSingh/headroom/commit/16168dca8682e7b1685480c159b294ad097d1517))
* add universal orchestration controls ([51b4b82](https://github.com/AryanSingh/headroom/commit/51b4b82f844aad359fd1709e73934646ce4c1058))
* **audit-deep-2026-06-21:** persistent webhook subscriptions + DLQ ([811931e](https://github.com/AryanSingh/headroom/commit/811931e7c62421b3f667fcba16f2743366f0df75))
* **audit-deep-2026-06-21:** React dashboard real APIs + drawer Esc + firewall opt-in ([a3d2e7b](https://github.com/AryanSingh/headroom/commit/a3d2e7bc791133207a473825eb1957da9c2bc163))
* **audit-deep-2026-06-21:** savings --verify-integrity CLI flag ([ae10097](https://github.com/AryanSingh/headroom/commit/ae1009765f9a3924061432cee40af5ec8cd9d577))
* **audit-deep-2026-06-21:** streaming per-source fields + audit enum expansion ([34c936d](https://github.com/AryanSingh/headroom/commit/34c936d850edcfe1e567cfc9229442501ec35012))
* **auth:** Validate OS credential manager (keyring) for API keys ([8106b21](https://github.com/AryanSingh/headroom/commit/8106b2186aa1e39021b2d92430c0f8c22fa49f64))
* bound semantic cache resident memory ([92f386c](https://github.com/AryanSingh/headroom/commit/92f386c76889811650d8850372bde5d8b581406b))
* capability extensions — viral launch, benchmarks, ML firewall, Stripe billing, Go SDK, air-gap ([74a3439](https://github.com/AryanSingh/headroom/commit/74a34390616562019ad4226b030e5ca871828f0b))
* chat.messages.transform compresses long conversation history ([102b35e](https://github.com/AryanSingh/headroom/commit/102b35e5e45932c659815df0e9a553cf602f7a69))
* Claude Code + Codex plugins — install/uninstall, hooks, MCP integration ([8c31b18](https://github.com/AryanSingh/headroom/commit/8c31b1845ec5c70012ed2e8d7d1cf615393d2b89))
* **cli:** add `cutctx profile` and `cutctx stack-graph` commands ([a030496](https://github.com/AryanSingh/headroom/commit/a03049689f2d0e5ad89f9caad3114b80a13c6c58))
* close all PRODUCT_CAPABILITY_MATRIX gaps — enterprise admin UI, expanded MCP, CLI commands, rebrand to CutCtx ([0cc598e](https://github.com/AryanSingh/headroom/commit/0cc598e6967fa0784bcb7019f573d889f5cb0a1e))
* close all remaining product gaps — CLI bench/report, pricing page, enhanced dashboard, Go+Python SDKs ([494e75e](https://github.com/AryanSingh/headroom/commit/494e75ee5fcab66e17672801035ba93a66cd8e1d))
* close feedback loop and add reachability + benchmark wiring ([248b371](https://github.com/AryanSingh/headroom/commit/248b3714cc3696197ffcfb62686a5cf8eebf2047))
* compact source code in Rust live zone ([6b3a28b](https://github.com/AryanSingh/headroom/commit/6b3a28badf78d259d2787a0f4575323a9c7dbb0f))
* CompactTable, LLMLingua-2, query-aware compression + Langfuse/LlamaIndex/SelectiveFilter plan ([0bc68fc](https://github.com/AryanSingh/headroom/commit/0bc68fcd8d242885f7d6be63acabee3a2b47904a))
* complete all five savings sources — semantic, self-hosted prefix, model routing in hot path + durable history + buyer report ([dc7905d](https://github.com/AryanSingh/headroom/commit/dc7905d18b57d8a2a5d683580faf50afab5fcd66))
* complete dashboard UI/UX overhaul with dark/light mode ([727cf79](https://github.com/AryanSingh/headroom/commit/727cf79d62ee3f9c2f09261d61af0fb70e479fd4))
* complete release readiness improvements ([4a768af](https://github.com/AryanSingh/headroom/commit/4a768af013b7fdf0c574d354fd28fc6bdf551b3b))
* complete remaining AGENT_TASKS (6-14) ([0114853](https://github.com/AryanSingh/headroom/commit/011485369368f84d1fa60ec9013f4d27b1c5066b))
* CutCtx Claude.ai skill plugin — uploadable ZIP for web UI ([d23c252](https://github.com/AryanSingh/headroom/commit/d23c252bd8975b2dea2bfcd428f52fd097a893ab))
* **dashboard:** add react web dashboard and air-gap documentation ([e68a6be](https://github.com/AryanSingh/headroom/commit/e68a6be6af97fd7473a52c8a5344b4eaad739c66))
* **dashboard:** release-ready polish — feature toggles, anti-RE, OSS scrub ([d35423c](https://github.com/AryanSingh/headroom/commit/d35423cd27af64ee4c2b54c90416d8ef843fb6c1))
* Dynamic capability toggling from dashboard ([a38800b](https://github.com/AryanSingh/headroom/commit/a38800b2f76b7dc64f2bf7efb3f8218a4b6f5881))
* expose routing scorer readiness ([90084a0](https://github.com/AryanSingh/headroom/commit/90084a0f7aa28bd6f41dddfc35f8bfc83b432b79))
* finalize PitchToShip commercialization updates ([e9f9d6a](https://github.com/AryanSingh/headroom/commit/e9f9d6ac746c4f725d432ed4f6b6f55b3254c9a8))
* group CLI help by operator workflow ([8f91803](https://github.com/AryanSingh/headroom/commit/8f91803f65bc6d3742497dd4e5265b1f2917506e))
* harden adaptive model routing ([5a81a53](https://github.com/AryanSingh/headroom/commit/5a81a53ff0f9262d707fd26d1c10c8766af3bf78))
* harden model routing control plane ([e49ff7b](https://github.com/AryanSingh/headroom/commit/e49ff7b6f8fd4e3aad69929a0a69e76591c28c4e))
* harden network deployment security ([a60f156](https://github.com/AryanSingh/headroom/commit/a60f15662587fec47009335ea09a2d855e0ac293))
* harden routing and operational readiness ([bca86de](https://github.com/AryanSingh/headroom/commit/bca86dedcae8780021bf69617b593ffb67fb2b50))
* Implement priority token savings features ([c0604d8](https://github.com/AryanSingh/headroom/commit/c0604d81863a86c7a03840c3905894864735cb37))
* implement USearch vector backend + Stack Graphs cross-file code navigation ([2f0a525](https://github.com/AryanSingh/headroom/commit/2f0a525d403de663ee159d23a3b9d54e52262202))
* **infra:** final production readiness polish (rebranding, pinning, prestop, cronjob, alerts) ([69af0ff](https://github.com/AryanSingh/headroom/commit/69af0ff21ad95e118e8dd6d178717d802bde316c))
* intelligence layer — task-aware compression, semantic dedup, context budgeting, cross-session profiles, shared context, cost forecasting ([0ac2826](https://github.com/AryanSingh/headroom/commit/0ac282647142bea7787b10e1e95b188eabb8b0c9))
* JSON schema compression — 40% token savings on tool definitions ([3fb737f](https://github.com/AryanSingh/headroom/commit/3fb737fd566b7331a7ab459a447d93c6f62e14dd))
* log Rust proxy panics structurally ([7bd12a1](https://github.com/AryanSingh/headroom/commit/7bd12a1a1f3d117cc15626ee89c7569985ee71e6))
* measure Rust proxy streaming TTFB ([86d2ae4](https://github.com/AryanSingh/headroom/commit/86d2ae45ded9e2a1d0997d23e6f0c8e29aaf7972))
* **memory:** team memory service Phase 3 B1 wiring ([bb21db8](https://github.com/AryanSingh/headroom/commit/bb21db8ea8832a9e7695c0a3df329b40bd16fb79))
* **p6:** EE publish CI, learn share prompt, headroom branding ([9859087](https://github.com/AryanSingh/headroom/commit/9859087b7d49981e45f9c5a3bc2996cb17551563))
* Phase 3 B2 memory provenance and value scoring, plus proxy budget enforcement ([6fa4888](https://github.com/AryanSingh/headroom/commit/6fa48882a528742b4f64d4a025b8a3251905b234))
* Phase 3 B3-B6 memory impact, curation, portability, dashboard ([5a06f93](https://github.com/AryanSingh/headroom/commit/5a06f93029c1b20a6185d3dbef0492f003981d30))
* PitchToShip integration — license validation, trial JWT, seat heartbeat ([55f5352](https://github.com/AryanSingh/headroom/commit/55f5352a5daba48ec297e1b8256f787f2278a2cb))
* **privacy:** add GDPR/CCPA DSR endpoints /v1/me/{export,delete} (Blocker-2) ([0ea6dc9](https://github.com/AryanSingh/headroom/commit/0ea6dc9252eea05f6571eb169086252587e15314))
* **prod:** config-driven cost-based model router (Blocker-5 part 2) ([61b5196](https://github.com/AryanSingh/headroom/commit/61b5196a9be51ce7be8727fd048de45bf465c8a2))
* **prod:** production-grade webhook dispatcher with retry + signing + admin API (High-15) ([40ac6dc](https://github.com/AryanSingh/headroom/commit/40ac6dc0d78b3b5189a88a414356a7b223717c09))
* **proxy:** add savings tracking, improved request logging, and cross-process savings tracker tests ([7d3d9fe](https://github.com/AryanSingh/headroom/commit/7d3d9fe3bd79acc5a3388ed2d96e30c31e11d501))
* **rebrand:** in-tree rebrand shell + Rust Ed25519 license verifier ([17cdc93](https://github.com/AryanSingh/headroom/commit/17cdc93bb4ea9127c7f18f35245151afbfd9c5a5))
* record backend OpenAI streaming TTFB ([b66bae0](https://github.com/AryanSingh/headroom/commit/b66bae0d8b7cdb0ac8cc534a366afe0cd6538379))
* **release:** implement best-in-class release plan — capabilities, modality matrix, release gate ([20a44ed](https://github.com/AryanSingh/headroom/commit/20a44edc514ac8cadd69f73bc65ddb5c5b11fc5c))
* route simple terra requests to gpt-5.4 mini ([b228fc1](https://github.com/AryanSingh/headroom/commit/b228fc1d3c4416bdbbef8b564f718acb7133698d))
* savings orchestration — unified ledger, provider parsers, policy engine, CLI breakdowns ([0ecf5ef](https://github.com/AryanSingh/headroom/commit/0ecf5ef3db2864994b2afcbca0d55ede487d7369))
* **security:** add /audit/verify endpoint with lightweight integrity check ([01ce9ef](https://github.com/AryanSingh/headroom/commit/01ce9efab5667c086a1734149d8683247b896a32))
* **security:** SQLite-backed RBAC persistence (Medium-29) ([ddef51a](https://github.com/AryanSingh/headroom/commit/ddef51a1e4956ab7356d6884785a631b6a86e10d))
* **security:** TOTP MFA for admin (High-12) ([58e5495](https://github.com/AryanSingh/headroom/commit/58e5495d2ea494bc1888968e7b596df513f32ca0))
* **security:** wire anti-debug at module init, JS obfuscation, Cython build ([d4fe0fd](https://github.com/AryanSingh/headroom/commit/d4fe0fda3f1ed70ccd8dcdbe5873d6d3d3876b76))
* session.compacting appends cutctx context to the compactor prompt ([f47b24c](https://github.com/AryanSingh/headroom/commit/f47b24c22ccd7a2ca98f5e14888f9188495007d2))
* share orchestration state through redis ([a0bd945](https://github.com/AryanSingh/headroom/commit/a0bd945a362cc61ebe67a8bb9d2d09fc0ea808cd))
* ship audited orchestration and release evidence ([74dd4e6](https://github.com/AryanSingh/headroom/commit/74dd4e6f4611037a8d09dc911b0030b3895ea7ae))
* SP-0 through SP-8 — complete software protection implementation ([9be1ae2](https://github.com/AryanSingh/headroom/commit/9be1ae270e2218d920d1dd285c8d5fa3b89d1c0f))
* stack-graph + usearch tests, plan tracker, changelog ([6c9d71d](https://github.com/AryanSingh/headroom/commit/6c9d71d7e70ad9de2e218f902c416c7957470869))
* **stack-graphs:** Python facade, proxy wiring, CLI flag, watcher integration ([2994769](https://github.com/AryanSingh/headroom/commit/2994769b25375d2976e09dd76c0295fd757f0d7f))
* support network proxy benchmarking ([dbd7f88](https://github.com/AryanSingh/headroom/commit/dbd7f883eae62843da04db99efa7212f2e75aa20))
* surface Langfuse + add LlamaIndex integration + selective context filter ([2d332f5](https://github.com/AryanSingh/headroom/commit/2d332f50207c5b6361f5c0335e34ee0abddbf6e0))
* **telemetry:** implement Phase 4 A1-A4 data flywheel ([518a9d2](https://github.com/AryanSingh/headroom/commit/518a9d257bf19d69015aed803282321f19bc102c))
* tool.execute.after compress hook with CUTCTX_DISABLED escape hatch ([8b9ecfc](https://github.com/AryanSingh/headroom/commit/8b9ecfcfa26c686fdb54d26d8e6ff54d52dd19c6))
* version compliance SQLite schemas ([ae49a0c](https://github.com/AryanSingh/headroom/commit/ae49a0ce2f5273bc15a6011c0bfad180481eabf5))
* version critical SQLite schemas ([de96311](https://github.com/AryanSingh/headroom/commit/de96311e10150db9d6c281e0b26c74e8d45fcd0a))
* version operational SQLite schemas ([70c2d4b](https://github.com/AryanSingh/headroom/commit/70c2d4b012a68b1faba8a5f3f4e9a6e85d313b92))
* version proxy state SQLite schemas ([8aa5be0](https://github.com/AryanSingh/headroom/commit/8aa5be07ba9f3cd01898b1fe9fc1de0c49af1ea6))
* **vscode:** Add native workspace config proxying for Cursor and Copilot ([b4f6e66](https://github.com/AryanSingh/headroom/commit/b4f6e66ab7cb629dd794ca88431494d4d49b08cb))
* wire intelligence layer into proxy pipeline — pre/post compression hooks ([2c9c78d](https://github.com/AryanSingh/headroom/commit/2c9c78deb4d7ad904deb7615c6463d155b3d445f))
* wire savings policy into handlers, dashboard by-source cards, buyer-grade report ([b47ccd8](https://github.com/AryanSingh/headroom/commit/b47ccd8e5e7463d1f41536657560c047858ce6a8))
* **WS10:** output-side optimization (3 levers + safety rail) ([2a199b0](https://github.com/AryanSingh/headroom/commit/2a199b015f0df39378d1697349dc0e514850d2d1))
* **WS11:** tool-result memoization pre-pass ([18537fe](https://github.com/AryanSingh/headroom/commit/18537fe3e38e140cb38f93126e8c3268c1fa59f7))
* **WS13:** batch-API arbitrage (eligibility gate + queue) ([f18a3ce](https://github.com/AryanSingh/headroom/commit/f18a3cebe6d14489e0eafed4d1153c21bf3c7b8a))
* **WS16:** tokenizer-aware normalization pre-pass ([4ed4237](https://github.com/AryanSingh/headroom/commit/4ed4237b515cd60556b920b84abcbd914a880278))
* **WS19:** compression autopilot (closed feedback loop) ([50d483e](https://github.com/AryanSingh/headroom/commit/50d483e789d8007efdf17e5ac03cd4ec760cdb29))


### Bug Fixes

* add admin auth + RBAC to /admin dashboard route ([9e5b22b](https://github.com/AryanSingh/headroom/commit/9e5b22bdc62c37f22a90c59c0a97b53d57ada377))
* additional headroom_ee + headroom module fixes for relicense split ([cace1de](https://github.com/AryanSingh/headroom/commit/cace1de4013eeb96236229d894c29a2ae65f8da5))
* align fallback dashboard savings headline ([6d7e1d3](https://github.com/AryanSingh/headroom/commit/6d7e1d30f257843133a4ef743b4ff005fb1f6723))
* align Kubernetes metrics port ([1af266e](https://github.com/AryanSingh/headroom/commit/1af266ec5bacd4e9e6984f715166f5e2d7869667))
* align Rust diff compression with Python fallback ([9276b29](https://github.com/AryanSingh/headroom/commit/9276b290975c3be40979480d224ade19af98f61f))
* allow easy codex followups to route to mini ([e0df3e3](https://github.com/AryanSingh/headroom/commit/e0df3e3e253599c1016b560598aaa254bd30b9dd))
* **audit-deep-2026-06-21:** CLI commands + audit actor + K8s/deploy polish ([53413fa](https://github.com/AryanSingh/headroom/commit/53413fa151187b6b2d54e27cf3fc7d3392781419))
* **audit-deep-2026-06-21:** dashboard search/filter/sort + loading/error (Blocker 4) ([e0bdd00](https://github.com/AryanSingh/headroom/commit/e0bdd0099678fcbec4194d4b01fe1515aff29937))
* **audit-deep-2026-06-21:** EE memory review RBAC+audit (Blocker 3c) ([7297b18](https://github.com/AryanSingh/headroom/commit/7297b186afa3af5eaa3c3aec6f3f0f51ada69742))
* **audit-deep-2026-06-21:** real egress policy + airgap status (Blocker 3a) ([173c39a](https://github.com/AryanSingh/headroom/commit/173c39a4f1154548084ea64a91795bb4d90aaf6b))
* **audit-deep-2026-06-21:** real secrets backend (Blocker 3b) ([aefcdb8](https://github.com/AryanSingh/headroom/commit/aefcdb8d8efd64536a05fff56e79792aa80e2526))
* **audit-deep-2026-06-21:** residency verify + rebrand backward-compat ([04267cb](https://github.com/AryanSingh/headroom/commit/04267cba9aa462895dd91d820d13acb7fa47cade))
* **audit-deep-2026-06-21:** spend ledger tenant scoping default ([544b730](https://github.com/AryanSingh/headroom/commit/544b73064669ebe4b20a59cc7ea4cafcb91ff0b2))
* **audit-deep-2026-06-21:** Stripe webhook secret + CRL fail-closed ([cc1d0f5](https://github.com/AryanSingh/headroom/commit/cc1d0f5dbbe0bbab33ae35cb2ce2adf2725bcf0e))
* **audit-deep-2026-06-21:** wire ModelRouter into request path (Blocker 1) ([962854b](https://github.com/AryanSingh/headroom/commit/962854b6dabbca07d8c3114eac5081b90ef81c41))
* **audit:** fold flat audit.py into package __init__ (fixes import shadowing) ([d5adb4d](https://github.com/AryanSingh/headroom/commit/d5adb4d982b95b6279b27b0a1464f00f4590fd3d))
* balance routing and timeout fallbacks ([8a98d05](https://github.com/AryanSingh/headroom/commit/8a98d056d16ff6b35d8cceb46d5dcaaec7fa90d1))
* Claude Code plugin — use claude mcp add for proper CLI registration ([6238a08](https://github.com/AryanSingh/headroom/commit/6238a086ce5f6a089da6c5adfc50ebee94ec8087))
* **codex:** route via native openai provider to stop session-history fragmentation ([45b3c2f](https://github.com/AryanSingh/headroom/commit/45b3c2f7f5fda86878458c49f2563230b0537099))
* commercial release audit gaps — rebranding, pricing, K8s probes, version bump, legal docs ([06ca87a](https://github.com/AryanSingh/headroom/commit/06ca87ac1e120cd9e7d76c0fbd0193434a82487a))
* commercialization sync — JSON always for savings --by-source, USD attribution fix in buyer report, 5-source model in docs ([454d85a](https://github.com/AryanSingh/headroom/commit/454d85aabb7746f9128a67edb40f086704511067))
* complete production readiness remediation ([6042e94](https://github.com/AryanSingh/headroom/commit/6042e941eb773ffbb7919bae2e4c7a802da67c18))
* compress latest openai responses user tail ([cbd2691](https://github.com/AryanSingh/headroom/commit/cbd26916b7a30c70cb0d571e63d30741367bd083))
* cutctx plugin — rename headroom→cutctx CLI refs, add auto-start proxy, fix health endpoint ([6eeb468](https://github.com/AryanSingh/headroom/commit/6eeb4688aebbf952d71c8a30dbd49e79edcd9c8d))
* **cutctx-opencode:** realign types to real cutctx-ai API (reviewer findings) ([dece8c5](https://github.com/AryanSingh/headroom/commit/dece8c584502d529f5be21302a9502bf1268ceb9))
* **cutctx:** in-flight production-readiness fixes for v0.30.0 ([864c51e](https://github.com/AryanSingh/headroom/commit/864c51ef9f2c136f50bba91ea5b3d7850cd9dab7))
* **cutctx:** README hero, PitchToShip CTA, audit chain HMAC contract ([f38ca11](https://github.com/AryanSingh/headroom/commit/f38ca11512a747d9961a1308c6a8b27f9d0802d0))
* dashboard current session shows $0 for money saved ([c6bdbf8](https://github.com/AryanSingh/headroom/commit/c6bdbf859a83ab19f88f6c58ce5b42d1e7d9dba1))
* dashboard money saved shows $0 for current session ([6d30932](https://github.com/AryanSingh/headroom/commit/6d309325f2477c12bb5333868ea8ccbee11a2211))
* **dashboard:** add missing JS bundle index-BAVvlhZA.js to tracked assets ([9bb8fc5](https://github.com/AryanSingh/headroom/commit/9bb8fc5b29b6bf01c2546ed414ca94f91bc22e55))
* **dashboard:** dynamic version + clean savings_by_source x-if guard ([87f03ca](https://github.com/AryanSingh/headroom/commit/87f03ca3b14ba581617d8b57881285af3c49dfb0))
* **dashboard:** resolve missing css, refresh 404, and &gt;100% active compression bugs with regression tests ([4318a11](https://github.com/AryanSingh/headroom/commit/4318a118891da931ce40409072d0d1e9bf56f173))
* deprecated API usages + compress.py lazy import scoping bug ([b6e75c8](https://github.com/AryanSingh/headroom/commit/b6e75c87b07d61aa435c4c8e4524bd1905c7d1e3))
* E2E test fixes — subscription NameError, admin dashboard path, firewall CLI wiring, learn_share branding ([0dab42d](https://github.com/AryanSingh/headroom/commit/0dab42d7e858cc5e492f3dbd684f90f120d0a5cc))
* enforce billing subscription lifecycle ([067176a](https://github.com/AryanSingh/headroom/commit/067176aa53005a37d3aedfac85fe9f52afa91309))
* enforce spend and audit retention ([28661a9](https://github.com/AryanSingh/headroom/commit/28661a90f7f27610d1fc26f3666ab58819b3a4fa))
* expire idle Rust websocket sessions ([2b1203c](https://github.com/AryanSingh/headroom/commit/2b1203c65f5326d542d15eda8c497c9d689cee3b))
* gate routing savings on actual model match ([e732d2b](https://github.com/AryanSingh/headroom/commit/e732d2b981236ec41a60ad664230f56e8e6a4201))
* guard responses context overflow after restart ([71ab948](https://github.com/AryanSingh/headroom/commit/71ab948417aeb40d773dfb380a00e7cc80848326))
* harden dashboard governance controls ([b47add7](https://github.com/AryanSingh/headroom/commit/b47add750a107400edb19cc432b090ac69638d13))
* harden orchestration persistence and telemetry ([b5e2230](https://github.com/AryanSingh/headroom/commit/b5e22305258a5711b0b38bdc302257afb70dab5c))
* harden release validation and dependencies ([9f84b4b](https://github.com/AryanSingh/headroom/commit/9f84b4b5adaf0adb15dc565b950764e0430d85c8))
* headroom_ee module fixes — imports, APIs, compatibility ([873a717](https://github.com/AryanSingh/headroom/commit/873a7175e3184c988618252791c03ba565ab197f))
* improve dashboard keyboard navigation ([295cb13](https://github.com/AryanSingh/headroom/commit/295cb13f223f6237275b6a52583fe8ebb0f79893))
* improve dashboard trend accessibility ([f02118a](https://github.com/AryanSingh/headroom/commit/f02118a6c7d1ce538a52f76159ea87c2f1448dbf))
* Improve text legibility, clamp savings percentages, and optimize trend graph scaling ([1fc3fc3](https://github.com/AryanSingh/headroom/commit/1fc3fc3a10c5083352a7e4d4346b2ea64932fa08))
* include test helpers and enterprise test dependency ([bd0ce01](https://github.com/AryanSingh/headroom/commit/bd0ce01e8f613316f7a5292fa7239e333ea39ed6))
* include tree-sitter in dev test environment ([191076f](https://github.com/AryanSingh/headroom/commit/191076ffb634285785c2cba2a1c72d1ab42159de))
* intelligence pipeline rewrite — 6 features fully integrated, 29 tests pass ([fa58f2a](https://github.com/AryanSingh/headroom/commit/fa58f2a8c425f4ee65d0fcf94be794012100d53b))
* keep empty websocket completions off hot path ([6b0fe5f](https://github.com/AryanSingh/headroom/commit/6b0fe5ff4e46609d57a7964d9acd4e7b148e7e96))
* lint clean (memory/telemetry/D3), telemetry network egress opt-in (default off), commit D3 failover/residency ([241b436](https://github.com/AryanSingh/headroom/commit/241b4362cca0acc33db87395864f2acd59af931b))
* **lint:** ruff formatting and unused imports in resolver.py ([1d786ee](https://github.com/AryanSingh/headroom/commit/1d786eeec700566526405e7f5fc664f2e2b2307a))
* make max savings use aggressive fallback ([a60224b](https://github.com/AryanSingh/headroom/commit/a60224ba6a34cc4dfe4135a75749e5f483b75046))
* maturity score improvements — litellm noise, --json, test ordering ([418ae99](https://github.com/AryanSingh/headroom/commit/418ae99aa1f09277491f6b4ea6104942184f0638))
* **mcp:** update test mocks and exports for mcp_server refactor ([bd9c022](https://github.com/AryanSingh/headroom/commit/bd9c022433691c17dc410231484e4f8b41779a5b))
* move savings persistence off request path ([d41aec2](https://github.com/AryanSingh/headroom/commit/d41aec2d0a9d1cd51b332c7b35aecd0c99e549aa))
* **ops:** align docker-compose.native.yml image to canonical owner (Medium-35) ([684a7e9](https://github.com/AryanSingh/headroom/commit/684a7e90d98f199446f46d9a0c5a702d680d5890))
* persist global routing preset ([49831e1](https://github.com/AryanSingh/headroom/commit/49831e153f3a9b35f77c0930ea4e5f47c586afbe))
* point Codex hooks to installed cutctx binary ([3e8d299](https://github.com/AryanSingh/headroom/commit/3e8d2994b7d35926c000eba953f8cae0e1b58b94))
* **policy:** enforce dynamic budgets and commit outstanding files ([834d79b](https://github.com/AryanSingh/headroom/commit/834d79bb1ca280386f49d1c9a6e6f648eb7f72c4))
* **policy:** implement proxy policy enforcement and stale-while-revalidate caching ([ef0d02e](https://github.com/AryanSingh/headroom/commit/ef0d02ec5659725d2eb461cbb716c4b03781992c))
* preserve capabilities JSON contract ([9736f71](https://github.com/AryanSingh/headroom/commit/9736f719be5985a1601a7c9447aac5ecfc0e5b83))
* preserve Codex websocket wrap contract ([fb08ca1](https://github.com/AryanSingh/headroom/commit/fb08ca1c4814b899b3890cac239e04534415cd2e))
* preserve launchagent during rollback ([9175af0](https://github.com/AryanSingh/headroom/commit/9175af019ac3d9fcd9550adcf4ed9d7c5183b56a))
* prevent hidden dashboard controls intercepting taps ([2d33215](https://github.com/AryanSingh/headroom/commit/2d33215ad4793e5696ca626acac008b7bd4ba9b2))
* **prod+security:** wire streaming PII redactor, from_stream per-source, audit events, k8s ([58c3226](https://github.com/AryanSingh/headroom/commit/58c3226e37ca602fe54228611cc0d87f4b2bab6a))
* **prod:** bind ModelRouter + WebhookDispatcher at server boot ([e57cf9a](https://github.com/AryanSingh/headroom/commit/e57cf9a0c626017d5458077eac2d8360a58730c3))
* **proxy:** allow egress by default in connected mode ([b751cd0](https://github.com/AryanSingh/headroom/commit/b751cd025325117182094c855bd8f2567724284d))
* **rebrand:** HeadroomProxy alias + streaming var name + 15 test imports ([7795ffb](https://github.com/AryanSingh/headroom/commit/7795ffb6d6f0d54d1a04dad0c943fd542b3fc2d5))
* redact sensitive tags from stats ([1ed9933](https://github.com/AryanSingh/headroom/commit/1ed9933334130585db3580ed081c7d401f07292b))
* refuse codex overflow after compression failures ([be2e674](https://github.com/AryanSingh/headroom/commit/be2e6745b28d459855dceb502f50ec8c7e8a9774))
* refuse overflow after compression failure ([a572088](https://github.com/AryanSingh/headroom/commit/a5720882fbd9c28b1c4edd55736c6192e0192107))
* **release:** content_router NameError, llmlingua tests, docs to v0.28.0 ([63896bb](https://github.com/AryanSingh/headroom/commit/63896bb2a3e16f0db8825e361e2c93005317352a))
* **release:** shipping-ready v0.26.0 — rebrand, Docker, Helm, legal, security config ([badc77c](https://github.com/AryanSingh/headroom/commit/badc77c96d5a0a325e38d083ee2a20a3cd1c246b))
* **reliability+security:** per-identity rate limit + savings corruption recovery ([27320cd](https://github.com/AryanSingh/headroom/commit/27320cd8ae3ca7fb2bd4fda330ee478d0b9a2266))
* remediate all critical/high issues from QA and Product Audits ([c4953df](https://github.com/AryanSingh/headroom/commit/c4953df35c5fe2e9773e0e7f9905a73bfa71c6d5))
* replace placeholder license key, lint new code, pin CI ruff ([84ac8f9](https://github.com/AryanSingh/headroom/commit/84ac8f951e8126793bed2c55db6667ac29ae47d1))
* report incomplete setup honestly ([94eb91e](https://github.com/AryanSingh/headroom/commit/94eb91eb7ce9cc461aec43c765331f0b127325ef))
* require robust scorer promotion evidence ([100f062](https://github.com/AryanSingh/headroom/commit/100f062acc344c14a0700409ac04426364c7be6e))
* Resolve layout crash, add ErrorBoundary, and fix light theme mode ([77afd18](https://github.com/AryanSingh/headroom/commit/77afd18bbee21f04094275160f9f52c1a00c3c65))
* Resolve missing Savings panel and Orchestrator styles ([dfc5728](https://github.com/AryanSingh/headroom/commit/dfc57282ef811f60d76e6a5c18e43e4ac1a0cd3c))
* resolve optional ML deps on Python 3.14 ([18ae913](https://github.com/AryanSingh/headroom/commit/18ae91361ec3dba739df800ef9fea78ea3b4b7dd))
* restore enterprise release workflows ([92f629e](https://github.com/AryanSingh/headroom/commit/92f629eb2ccacb2198bab9a87a6014942153c8d9))
* restore model routing savings attribution ([06b02e3](https://github.com/AryanSingh/headroom/commit/06b02e38ec0c2ecac611ec242a6c460f0a033c2c))
* restore runtime app debug and admin surfaces ([f65514a](https://github.com/AryanSingh/headroom/commit/f65514aa8885be867de0aa145ea9660b1175c7ed))
* restore runtime surfaces and guardrail coverage ([765a77e](https://github.com/AryanSingh/headroom/commit/765a77e189576e588718b601bd11c03e6468b426))
* restore safe chatgpt responses request shape ([d852de6](https://github.com/AryanSingh/headroom/commit/d852de69ce44e9e2f86190e6edcc79a95a398173))
* route easy follow-ups to mini ([9d6c230](https://github.com/AryanSingh/headroom/commit/9d6c2304324a240011986cac08def573f3f95203))
* route more easy followups to mini ([92d8929](https://github.com/AryanSingh/headroom/commit/92d8929778f08fea295aaafd857a7dc161cddace))
* **savings:** correct double-counting in funnel + add vLLM APC header aliases ([ef88bb6](https://github.com/AryanSingh/headroom/commit/ef88bb683b28c331ba0b152250e0e73656845618))
* **savings:** restore request history from JSONL on proxy restart ([a459f6c](https://github.com/AryanSingh/headroom/commit/a459f6c88d65f9afcff6f3342b72e396293cc1ba))
* **security+code:** SSO requires PyJWT + /admin fallback + remove dead duplicate ([b5c221f](https://github.com/AryanSingh/headroom/commit/b5c221f2007190c698870c1b938aff6f8d4d7e00))
* **security:** block plaintext admin key log + require audit secret + auto-start retention ([fe32040](https://github.com/AryanSingh/headroom/commit/fe3204046d989bd5f7a83c1b22e63857ff25a31a))
* **security:** gate EE routes behind admin auth + RBAC (Blocker-1) ([2b49ee7](https://github.com/AryanSingh/headroom/commit/2b49ee7626b093d3220328f97d0b06b26e2d1bc3))
* **security:** GDPR DSR delete + export P0 bugs ([c556e5b](https://github.com/AryanSingh/headroom/commit/c556e5bb49e5f24d8504b5754ea5cb92af44a141))
* **security:** harden audit-actor source — SSO &gt; key fingerprint &gt; 'admin' ([54e6bb0](https://github.com/AryanSingh/headroom/commit/54e6bb03636d6b3db70763fd6cb07b6b9ce07e91))
* **security:** has_permission fail-closed for unknown SSO users ([7f6875c](https://github.com/AryanSingh/headroom/commit/7f6875c5153665b929ac0dcb15dd30b248d8f421))
* **security:** residency auth gate, Stripe tier validation, RBAC permission, test fixes ([7c2c6fe](https://github.com/AryanSingh/headroom/commit/7c2c6fec82df6af37cd6a444b929e50096b263c7))
* **security:** restore SSO class boundary + align docker-compose image ([fb73887](https://github.com/AryanSingh/headroom/commit/fb73887b4bb08a48244b2d8667ee83a0c9a74628))
* **security:** wire DSR cascade to real AuditLogger API (round-4 audit P0) ([f438a94](https://github.com/AryanSingh/headroom/commit/f438a9418ac8174350a94d520a0bcdcb7e7aeac8))
* ship-it audit improvements — 41 new tests, README rebrand, Helm version bump ([e4a1104](https://github.com/AryanSingh/headroom/commit/e4a110403879adbe7196ced5b7d2851cf170dd2d))
* stabilize savings pricing lookup ([b41d674](https://github.com/AryanSingh/headroom/commit/b41d6746073016587f0462cb65f8ca81e68e3fac))
* stabilize stack graph symbol selection ([3ee363d](https://github.com/AryanSingh/headroom/commit/3ee363daed80fef8f4aed7299f66a809faa27604))
* start retention cleanup with proxy lifecycle ([be13c37](https://github.com/AryanSingh/headroom/commit/be13c374a35fee60f08fe1bb3f022ddf1e5bcd22))
* **stats:** remove legacy llmlingua and difftastic from stats payload ([eded7cf](https://github.com/AryanSingh/headroom/commit/eded7cfb70e62e3bb160ab8231991ce034359807))
* surface enterprise startup degradation ([f9c4385](https://github.com/AryanSingh/headroom/commit/f9c43852a3d0072debcb0791cb42b1facb9d70fd))
* sync embedded dashboard docs assets ([2413d2b](https://github.com/AryanSingh/headroom/commit/2413d2bd5af2d5f974ffe1941e719af80ff279c7))
* synchronize dashboard runtime defaults ([89a511a](https://github.com/AryanSingh/headroom/commit/89a511abbdb9d84265f1a80e2d8807b05486d8d8))
* synchronize Rust extension release version ([a80d7ec](https://github.com/AryanSingh/headroom/commit/a80d7ec60b31a04859079feae8844123e16db5b0))
* **tests:** close 6 round-4 P0 test regressions + 1 rebrand shell-leak ([fa310f1](https://github.com/AryanSingh/headroom/commit/fa310f17364c9f5d9f7fa1878bddb470e1675245))
* **tests:** fix failing tests across sso, memory, auth and learn idempotency ([da8ca61](https://github.com/AryanSingh/headroom/commit/da8ca619ab7fca35a62b785518a599d8cf50ada8))
* **tests:** relax each branch's own-source guard test post-merge ([f9c4c9d](https://github.com/AryanSingh/headroom/commit/f9c4c9d3d79b94adaafcda4c675780e0f0f67db4))
* **tests:** resolve remaining 7 test failures from proxy regressions ([ccb5a8d](https://github.com/AryanSingh/headroom/commit/ccb5a8df82cf7916e43843034b31365c3cac8b73))
* truncate function call outputs in chatgpt fallback ([2b1ff87](https://github.com/AryanSingh/headroom/commit/2b1ff87d5f549ed69dac5811f2498e39370b5af7))
* **types:** make headroom_ee shims transparent to mypy and ruff ([25fad54](https://github.com/AryanSingh/headroom/commit/25fad549dfe96246b2132f574031263013621547))
* unblock release validation workflows ([de0e904](https://github.com/AryanSingh/headroom/commit/de0e90417b35aba3141ce0e553ddaade8f3dcbde))
* update Claude Code + Codex plugins — consistent cutctx branding ([d61b134](https://github.com/AryanSingh/headroom/commit/d61b134d55a085c00fa40d493b54f79093846604))
* **V-10:** replace hardcoded True stub with actual SQLite query against license DB ([2da88a4](https://github.com/AryanSingh/headroom/commit/2da88a436562459ed58f51cdef39fedf5854ca65))
* wire per-source savings signals end-to-end (hot path, status, dashboard, history) ([db7f7a4](https://github.com/AryanSingh/headroom/commit/db7f7a454bda501161e0af544c9175ff055bc01e))
* wire savings ledger into live traffic + durable history + runtime-backed integrations ([dca5b49](https://github.com/AryanSingh/headroom/commit/dca5b49da6e96f6754d81383967e06ff38248cc9))


### Performance Improvements

* avoid detector-only cache aligner copy ([0fefd98](https://github.com/AryanSingh/headroom/commit/0fefd9864f6a9e816b71b529cf716a063040ed4b))
* bound optional SSE stream mirrors ([f7f6b12](https://github.com/AryanSingh/headroom/commit/f7f6b1202f4eb55d388f96c4fea1cd2185e1ad8c))
* enable WAL across memory SQLite stores ([3c6983b](https://github.com/AryanSingh/headroom/commit/3c6983beb92134ea3cb862afc2ead380247b5109))
* enable WAL for CCR SQLite cache ([cd0bfc6](https://github.com/AryanSingh/headroom/commit/cd0bfc6dde3c0adb3efd2ec40f70d6cea3f581e2))
* make semantic cache stats constant time ([f6380f1](https://github.com/AryanSingh/headroom/commit/f6380f179c5759f6bfd76918735c1adad3013974))
* offload Codex wire debug writes ([b7dc00b](https://github.com/AryanSingh/headroom/commit/b7dc00bb07bc44bf80f14c1647b2a9bfcd370252))
* render Prometheus metrics outside request lock ([c1552db](https://github.com/AryanSingh/headroom/commit/c1552dbd1b46a5882a716fbcd674e346943fa292))
* reuse SQLite CCR connections per thread ([8f0283f](https://github.com/AryanSingh/headroom/commit/8f0283ff247fb5927fc4bba352fec94646ae4114))


### Code Refactoring

* centralize unknown model warnings ([79489e3](https://github.com/AryanSingh/headroom/commit/79489e3775dd6cbc89d532f5587b185290b96456))
* extract admin routes + add rate limiting middleware + CCR store bridge ([26a46df](https://github.com/AryanSingh/headroom/commit/26a46df1229046c30fed0504c591e897e10e848e))

## [Unreleased]

### Added

- Added a provider-neutral orchestration control plane with encrypted provider accounts, dynamic capability-aware model discovery, custom role and selector bindings, deterministic strict/relaxed routing, bounded fallback chains, execution telemetry, and dashboard configuration surfaces.
- Integrated LiteLLM's open-source core as the default orchestration execution substrate while retaining Cutctx-owned routing and account policy. OpenAI-compatible sidecars such as Bifrost, Portkey, and Envoy can be registered without replacing Cutctx's control plane.
- Hardened orchestration configuration updates with merged-candidate validation, atomic in-process routing swaps, removal of stale configured models, and rejection of plaintext authentication headers outside the encrypted credential store.
- Added exact deployment keys (`provider:account:model`) for multi-account assignments and an explicit, default-off `CUTCTX_ORCHESTRATION_DIRECT_EXECUTION` development switch.
- Added Claude Desktop app support to `cutctx mcp install` (new `claude-desktop` registrar), and a transparent MCP compression gateway (`cutctx mcp gateway`) with `cutctx mcp install --gateway` to auto-compress Desktop MCP tool outputs; compression stays on-machine by default; config wrapping backs up and is reversible.

### Security

- Orchestration callers can no longer relax configured strict mode, override account credentials/cloud deployment fields, inject LiteLLM retry or fallback controls, or silently inherit process-global provider keys without account-level opt-in.
- Management APIs redact custom-header values while preserving them across configuration round trips, and compatibility routes fail closed when they cannot prove the exact assigned provider account.

### Strategy

- Public-facing copy now starts the context-control-plane repositioning from `artifacts/product-strategy-moat-analysis.md`: `README.md`, `PRODUCT_GUIDE.md`, `llms.txt`, and docs landing pages now lead with govern / attribute / remember, while token savings remain proof instead of the opening headline.

### Fixed

- Added a documented model-routing preset path for agent-facing setups: `codex-gpt54mini-high` now routes low-complexity GPT tasks to `gpt-5.4-mini` with `reasoning.effort = high`, while heavy work keeps the requested model; compatibility aliases `codex-opencode-slim` and `oh-my-opencode-slim` are documented in project guidance and docs.
- EE audit-chain source and operator-facing docs now match the intended cryptographic contract again: `cutctx_ee/audit/store.py` now uses HMAC-SHA256 over canonical length-prefixed fields, residency/compliance/SOC2 docs were updated to the same framing, and the regression suite now guards the fixed contract instead of the old truthfulness workaround.
- Development hygiene now catches accidental line-collapsed source/docs earlier: pre-commit wiring was normalized and a dependency-free `scripts/check_text_hygiene.py` hook guards editable Python, Markdown, YAML, TOML, and JSON files before heavier lint lanes run.
- Dashboard packaged-asset sync now copies Vite hashed JS/CSS into the directory actually mounted by the proxy (`cutctx/dashboard/assets/assets`), preventing stale bundled dashboard assets after `make build-dashboard`.
- Public marketing surfaces are a bit more truthful and consistent: blog CTAs no longer point readers at the dead `cutctx.sh` domain, `marketing/roi-calculator/index.html` now uses visible `Cutctx` branding, and the regression suite guards both the live-domain links and public-surface casing.
- CLI discoverability is tighter again: `cutctx evals -?` now describes the group as both memory evaluations and compressor benchmarks, with benchmark usage shown as a first-class example and guarded by a help-output test.
- Shared docs entry copy now matches the control-plane repositioning again: `docs/components/stats.tsx` and `docs/app/layout.tsx` no longer lead with the old “context optimization / fraction of the tokens” wedge, and instead describe Cutctx as a local-first context control plane for AI agents.
- Audit/compliance documentation is more truthful: the tamper-evident EE audit store is described as a HMAC-SHA256 hash chain, and the SOC 2 availability mapping now reflects the current backup scope (memory, spend ledger, and audit DBs only).
- Customer-facing fallback paths are safer: the public pricing pages no longer route Team-tier users to the dead PitchToShip self-serve checkout, and the CLI invalid-license hint now points operators back to their administrator instead of a broken external billing URL.
- Windows install docs no longer point at a non-existent `scripts/install.ps1`, and the SOC 2 roadmap now matches the verified audit-chain wording and current backup scope.
- Billing documentation is more truthful about the current codebase: it no longer claims a Razorpay-based production flow and instead describes the actual hybrid state of hosted PitchToShip helpers, Stripe webhook handling, and offline-license verification.
- Air-gap and operator-runbook docs now describe offline and commercial licensing as operator-managed workflows instead of assuming a verified PitchToShip customer portal.
- Licensing-migration guidance is less brittle: it now points at the configured hosted license-service URL instead of hardcoding one public domain as the only valid validation path.
- The commercial license branding is now internally consistent (`Cutctx`, not `CutCtx`), and a new docs/commercial-surface truthfulness test guards the corrected billing, installer, and SOC2 wording against drift.
- Commercial artifacts are less misleading: the implementation checklist, management OpenAPI spec, and license-portal artifact no longer present the dead PitchToShip checkout path as a verified live customer flow.
- Security/customer docs are more careful about scope: they no longer assume a universal live customer portal for licensing, billing MFA, or seat management when the current repo state only proves operator-led or API-driven workflows.
- The missing on-disk EE audit-chain regression file now exists as a source-contract test: it guards the current HMAC-SHA256 chain wording and keeps the docs aligned with the rebuilt runtime contract.
- Active public HTML surfaces now use consistent `Cutctx` product branding instead of mixed `CutCtx` casing across pricing, enterprise, and license-portal artifacts.
- Licensing migration copy is narrower again: server-side trials are described as part of the hosted licensing workflow rather than implying a universal portal surface.
- Security questionnaire/policy language is more precise about evidence: DR exercises, incident-response exercises, and third-party pentest summaries are no longer phrased as guaranteed fresh annual artifacts in every release state.
- Dashboard development hygiene is tighter: `dashboard/eslint.config.js` now rejects line-collapsed multi-statement code, dashboard lint runs with `--max-warnings=0`, pre-commit adds a dashboard ESLint hook, and `make ci-precheck` now includes a dashboard lint lane. Existing flattened dashboard conditionals and audit helper snippets were expanded to comply.
- Savings-moat tracking is now more honest after a branch audit: `artifacts/savings-moat-priority-todo.md` no longer marks WS19 fully done on the strength of controller-only work; pipeline wiring and Overview surfacing remain pending.
- Savings-moat handoff docs now match verified code state: `artifacts/pending-items.md`, `artifacts/release-checklist.md`, and `artifacts/design-partner-demo-script.md` no longer claim proxy-side context-policy enforcement, WS7 assurance, or WS8 replay are complete; the long todo now has a dated current-status override.
- WS4 context policy enforcement now works in proxy routes when `CUTCTX_CONTEXT_POLICY` is set: `/v1/messages`, `/v1/chat/completions`, and `/v1/responses` apply block/redact policy before upstream forwarding while default-off behavior preserves existing requests.
- WS5 org-scoped memory export/import now has CLI regression coverage proving `workspace_id` and `project_id` survive export/import round trips.
- WS6 local-only learn telemetry aggregation shipped as `cutctx learn --aggregate`, producing anonymized JSON summaries without model analysis or network egress; `CUTCTX_LEARN_SHARE=1` now fails explicitly until sharing is product/security approved.
- Dashboard Playwright fixtures now mock `/stats`, `/stats-history`, and `/health` separately so E2E tests verify loaded dashboard states instead of accidentally feeding history payloads into stats loaders.
- WS8 session replay alpha now ships behind `CUTCTX_REPLAY=1`: context-policy block/redaction decisions are recorded to a bounded in-memory per-session event store, `GET /v1/sessions/{session_id}/replay` returns authenticated replay timelines, and the dashboard has a Replay screen with success/empty/error E2E coverage.
- WS2 Agent Context Report v1 now exists as `cutctx report agent-context`, with markdown/html/json output aggregating savings attribution, governance posture, assurance status, and replay readiness from existing telemetry.
- Context-policy team budgets are now enforced and recorded in addition to per-agent budgets, closing the prior `team_id` no-op gap in `ContextPolicyEngine`.
- Dashboard release-readiness fixes now cover unknown-route fallback, mobile drawer Escape/focus behavior, Replay navigation, and feature-specific accessible labels for ambiguous switches/copy buttons.
- Proxy rate-limiter token buckets now clean up stale token-only keys and expose token-bucket cardinality in `stats()`, preventing invisible long-running bucket growth.
- SSO token validation now accepts safer JSON-body tokens on `POST /v1/sso/validate` while preserving the legacy query-token path for compatibility.
- Codex websocket sessions now override uvicorn's 20-second default ping/pong timeout with 10-minute `ws_ping_interval` / `ws_ping_timeout` settings, preventing long local tool calls from being severed mid-turn and regressing into non-resumable "Bad Request" reconnects.
- Packaged dashboard HTML loading now prefers the fresh `cutctx/dashboard/index.html` produced by `make build-dashboard` before falling back to the legacy `cutctx/dashboard/assets/index.html`, so Python Playwright/package tests no longer serve stale deleted hashed assets.
- Savings tracker litellm token-estimation failures now fail soft beyond `ImportError`, with regression coverage preventing the narrow exception handler from being reintroduced; buyer-report history rows also keep lifetime ghost/scaffolding totals separate from per-request deltas.

- CCR marker parsing and formatting now flow through shared `cutctx/ccr/markers.py` helpers, reducing duplicate marker logic across dedup and tool injection while keeping focused CCR regression coverage green.

- Tightened the live runtime admin surface in `cutctx/proxy/server.py`: wildcard CORS no longer advertises credential support, `/stats/reset` now logs audit failures instead of swallowing them silently, and the legacy earlier app builder is no longer exported as a second public `create_app` symbol.
- Split team-memory RBAC in `cutctx/proxy/routes/memory.py` so safe memory reads resolve `memory.read` while sync/review mutations still require `memory.write`, and preserved compatibility with existing zero-argument RBAC dependency callables via dedicated regression coverage.
- Dashboard operator stats now bypass browser cache for live admin fetches, expose proxy-sync freshness for history panels, and preserve lifetime totals in headline cards when the current session is smaller or tied.
- Dashboard recent-request docs and labels now clarify that the table shows the routed model observed by Cutctx, not necessarily the originally requested alias.
- Release metadata truthfulness improved across the dashboard and packaging surfaces: the sidebar version label now follows the live proxy or repo package version, `SECURITY.md` reflects the currently supported release line, and the README/Helm/Kubernetes defaults no longer point at stale pre-0.29 image versions or the old GitHub namespace.
- Go/no-go onboarding drift is reduced: the Docker-native install one-liners in `wiki/getting-started.md` and `wiki/quickstart.md` now point at the canonical `cutctx/cutctx` GitHub path instead of the stale `cutctx/cutctx` repository.
- Release-manifest and active-doc drift are tightened further: `scripts/verify-versions.py` now passes with all tracked plugin/SDK manifests aligned at `0.29.0`, remaining active Docker-native docs now point at `cutctx/cutctx`, live troubleshooting/pricing/integration/OpenClaw docs now use canonical `cutctx/cutctx` links, the packaged EE commercial-license surface now consistently names `Cutctx Labs`, and the docs OG route no longer ships the `My App` placeholder brand.
- Restored the admin/runtime source tree to a bootable state after a corrupted `cutctx/proxy/routes/admin.py` edit, and re-verified live current-source endpoints for `/health`, `/config/flags`, `/policy/status`, `/stats`, and `/stats-history`.
- Hardened dashboard operator data loading so unsupported or absent config surfaces no longer present as broken stats in local dashboard flows.
- Dashboard Capabilities and Orchestrator toggles now surface a dismissible `alert-card` on config-update failure (previously only `console.error` was emitted — toggles snapped back silently). Both pages use the same `.alert-card` + `.ghost-button` pattern as `Overview.jsx` for visual consistency.

### Added

- WS18 Phase A learned policy-table foundation: `cutctx policies train/show/reset` now stores local SQLite policy rows at `~/.cutctx/policies.db` (or `--db`), aggregates JSONL outcome events by tool/content/repo into conservative/balanced/aggressive rows, exposes bounded runtime bias application through `LearnedPolicyHooks`, adds unsafe-row eviction via `cutctx policies evict-unsafe`, and can be enabled for the proxy with `--enable-learned-policies` / `CUTCTX_LEARNED_POLICIES=1`.
- WS18 Phase A now has `--watch` ergonomics: `cutctx policies train --watch` monitors a directory for new/modified JSONL event files and auto-trains on them via polling (`--poll-interval`, default 30s). Test coverage in `tests/test_policy_learning.py` (10 tests).
- WS18 Phase A dashboard surfacing: `/stats` now exposes `intelligence.policies` with policy count, total samples, and aggressiveness/algorithm-hint distribution; the Overview dashboard renders a `PoliciesPanel` showing learned policy visibility.
- WS19 compression autopilot wiring is now live in the current worktree: `CUTCTX_AUTOPILOT` is threaded through proxy config/CLI/runtime toggles, the intelligence pipeline is kept stateful across requests so task-level setpoints persist, `/stats` exposes autopilot levels/history, and the Overview dashboard now renders a compression-autopilot panel with a level sparkline.
- Governance and manual-testing docs now surface the WS19 control path (`CUTCTX_AUTOPILOT=1` and `/intelligence/autopilot/status`) so the new loop can be enabled and verified without hunting through code.
- Inline multimodal audio optimization for supported chat/compress flows, with targeted regression coverage in `tests/test_audio_compressor.py`, `tests/test_inline_audio_messages.py`, and `tests/test_proxy_compress_endpoint.py`.
- **Feedback Loop (Data Flywheel)** (`cutctx/ccr/response_handler.py`, `cutctx/proxy/intelligence_pipeline.py`, `cutctx/transforms/content_router.py`, `cutctx/proxy/server.py`, `cutctx/profiles.py`) — CCR response handler records retrievals as feedback → updates per-workspace `CompressionProfile` → `recommended_ratio` flows into `ContentRouterConfig.per_type_overrides` → adjusts `bias_multiplier` for affected content types. Enables adaptive compression based on retrieval patterns. Test coverage in `tests/test_feedback_loop.py` (11 tests).
- **Stack-graph reachability bridge** (`cutctx/graph/reachability.py`, `cutctx/transforms/code_compressor.py`) — symbol reachability analysis for Stack Graphs core, with `extract_symbol_names()`, `resolve_entry_points()`, and wiring into `CodeCompressor.set_protected_symbols()` for syntax-preserving code compression. Distinct from the Stack Graphs AST/TSG core released in [0.29.0]. Test coverage in `tests/test_stack_graph_reachability.py` (17 tests) and `tests/test_initiative2_e2e.py` (5 tests).
- **Benchmark CLI** (`cutctx evals benchmark`) — comprehensive compression evaluation harness with `BenchmarkRunner`, 10 guarded compressor adapters (smart_crusher, log, search, diff, code, kompress, llmlingua, drain3, content_router, all), ThreadPoolExecutor parallelism, JSON and markdown output (LLMLingua-paper-style comparable format). Supports `--dataset {tool_outputs,longbench,squad,hotpotqa}`, `--compressors`, and `--metrics {ratio,tokens_saved,f1,rouge_l,information_recall,exact_match}`. Zero-LLM by default. Test coverage in `tests/test_evals_benchmark.py` (6 tests).
- **Capabilities visibility for moat features** (`cutctx/cli/capabilities.py`) — `cutctx capabilities` now reports Feedback Loop, Stack Graphs, and Benchmark CLI availability alongside the existing optional-dependency checks. The `stack_graph` row uses a precise `stack_graph_available()` check (rather than a generic `_core` module-presence check).
- **WS4 context policy engine MVP** (`cutctx/context_policy.py`) — declarative redaction/block/allow rules compiled from regex patterns, per-agent cumulative budget tracking with time-window expiry, and YAML/JSON config loading. `ContextPolicyEngine` evaluates rules in priority order (block → budget → redact/allow) and returns typed `EvaluationResult`. Composes with existing RBAC, firewall, and proxy policy scaffolding. Test coverage in `tests/test_context_policy.py` (16 tests).
- **WS5 org-scope memory export/import** — `SQLiteMemoryStore` schema now stores `workspace_id`/`project_id` with zero-data-loss migration for existing databases. `cutctx memory export --workspace-id` / `--project-id` filters memories by org scope.
- **WS18 learned policies --watch ergonomics** — `cutctx policies train --watch` monitors a directory for new/modified JSONL event files and auto-trains via polling (`--poll-interval`, default 30s). All 10 WS18 tests pass.
- **WS18 learned policies dashboard surfacing** — `/stats` exposes `intelligence.policies` with count, total samples, aggressiveness/algorithm-hint distribution. Overview dashboard renders a `PoliciesPanel` showing learned policy visibility.
- **WS9 design-partner readiness** — demo script (`artifacts/design-partner-demo-script.md`) and release checklist (`artifacts/release-checklist.md`) created for partner walkthroughs.
- **Dashboard Feedback Loop panel** (`cutctx/dashboard/templates/dashboard.html`) — the fallback dashboard now surfaces per-workspace `CompressionProfile` stats (compressions, retrievals, retrieval rate, per-content-type recommended ratios, router-override count) via the existing `/stats` `profile` and `content_router_overrides_count` fields. Renders a friendly empty-state block when the profile has not loaded yet.
- **Benchmark result publication** (`cutctx evals benchmark --publish`) — appends a dated results section to `docs/benchmarks.md`, idempotent per calendar day (re-running replaces that day's section instead of duplicating it). Uses a `\n## \`cutctx evals benchmark\` — ` boundary marker so nested H2 headings from `_build_markdown_report` (e.g. `## Compression Ratio by Dataset × Compressor`) do not cause premature truncation.
- **Bounded reachability cache** (`cutctx/graph/reachability.py`, `cutctx/graph/resolver.py`) — mitigates the synchronous per-request BFS cost on the `pre_compress_hook` hot path by caching per-symbol stack-graph lookups in a process-local 512-entry LRU. Invalidated automatically on re-index via a new monotonic `StackGraphResolver.generation` counter (no explicit cache-clearing needed). New tests in `tests/test_stack_graph_reachability.py` cover both the cache-hit and the reindex-invalidation paths.
- **Top-level `cutctx benchmark` alias** — `cutctx evals benchmark` is now also reachable as `cutctx benchmark` for top-level discoverability; both forms are equivalent. The lazy-loader knows the `evals` module registers a top-level `benchmark` command (`"benchmark": "evals"` in `_SIDE_EFFECT_COMMAND_MODULES`).

## [0.29.0] - 2026-06-30

### Added
- **USearch vector backend** (`cutctx/memory/backends/usearch_store.py`) — new optional vector index backend using Unum's USearch library for ~10× faster vector search with f16 quantization and zero-copy memory-mapped index loading. Added `VectorBackend.USEARCH` enum; wired into factory with `AUTO` fallback chain (USEARCH → SQLITE_VEC → HNSW). Requires `pip install usearch>=2.10.0`.
- **Stack Graphs Rust module** (`crates/cutctx-core/src/stack_graph/`) — GitHub-style stack-graph implementation for deterministic, file-incremental cross-file code navigation. `StackGraphManager` with language registration (Python + JS/TS), tree-sitter AST parsing, TSG rule loading for scoped symbol resolution, and BFS-based `resolve_reference()` for go-to-definition across files.
- **PyO3 binding** (`crates/cutctx-py/src/lib.rs`) — `StackGraphManager` exposed to Python as `cutctx._core.StackGraphManager` with thread-safe mutex wrapping.
- **Python facade** (`cutctx/graph/resolver.py`) — `StackGraphResolver` with `index_project()`, `index_file()`, `resolve()`, file/node count properties.
- **Proxy integration** (`cutctx/cli/proxy.py`, `cutctx/proxy/models.py`, `cutctx/proxy/server.py`) — `--stack-graph` CLI flag (`CUTCTX_STACK_GRAPH=1` env var), background indexing, `/stats` exposure.
- **CodeGraphWatcher integration** (`cutctx/graph/watcher.py`) — incremental stack graph re-indexing on file change.
- **Documentation** — `wiki/stack-graphs.md` (full feature docs), `wiki/memory.md` (USearch section), `wiki/index.md` (feature entries), `wiki/plans/2026-06-30-usearch-stack-graphs-integration-plan.md` (integration plan with ADRs).

### Changed
- **`pyproject.toml`** — added `usearch>=2.10.0` to `[memory]` optional-dependency group
- **`crates/cutctx-core/Cargo.toml`** — added `stack-graphs`, `tree-sitter`, `tree-sitter-stack-graphs`, `tree-sitter-python`, `tree-sitter-javascript`, `lsp-positions`, `streaming-iterator` dependencies
- **`crates/cutctx-core/src/lib.rs`** — added `pub mod stack_graph;`
- **`cutctx/memory/config.py`** — added `VectorBackend.USEARCH = "usearch"` enum member
- **`cutctx/memory/factory.py`** — added `USEARCH` routing with availability check and fallback
- **`cutctx/memory/backends/__init__.py`** — added lazy import for `UsearchMemoryBackend`
- **`cutctx/graph/__init__.py`** — added `StackGraphResolver` and `stack_graph_available()` to re-exports

### New Files
- `cutctx/memory/backends/usearch_store.py` — `UsearchMemoryBackend` class (thread-safe, persistent, f16 quantization)
- `crates/cutctx-core/src/stack_graph/mod.rs` — `StackGraphManager` with TSG rule loading and `resolve_reference()`
- `crates/cutctx-core/src/stack_graph/tsg_rules/python.tsg` — Python TSG definitions
- `crates/cutctx-core/src/stack_graph/tsg_rules/javascript.tsg` — JavaScript/TypeScript TSG definitions
- `crates/cutctx-py/src/py_stack_graph.rs` — PyO3 `PyStackGraphManager` wrapper
- `cutctx/graph/resolver.py` — `StackGraphResolver` Python facade
- `tests/test_usearch_backend.py` — 11 tests for USearch backend (skipif guard)
- `tests/test_stack_graph_resolver.py` — 12 Python-level stack graph tests
- `crates/cutctx-core/tests/test_stack_graphs.rs` — 6 Rust integration tests
- `wiki/stack-graphs.md` — Stack Graphs documentation page
- `wiki/plans/2026-06-30-usearch-stack-graphs-integration-plan.md` — full integration plan

### Documentation
- `wiki/memory.md` — Added USearch backend section with config options, auto-preference chain, and architecture diagram update
- `wiki/index.md` — Added Stack Graphs feature card, updated memory entry to mention USearch, added usearch to installation extras

### Security
- **CRITICAL**: Stripped `/dashboard`, `/api/savings`, `/api/models` from loopback auth bypass path (server.py:213) — localhost no longer skips auth for these endpoints
- **CRITICAL**: LIKE wildcard injection fix — added `_escape_like()` helper and `ESCAPE "\\"` clause for entity_ref LIKE queries in sqlite.py
- **HIGH**: Kompress max-input DoS guard — added `CUTCTX_KOMPRESS_MAX_WORDS` env var (default 80,000 words) limiting per-call text input
- **MEDIUM**: Added startup-time `logger.warning` when `CUTCTX_ALLOW_DEBUG` is set

### Fixed
- 56 ruff auto-fixable lint errors resolved (F401 unused imports, trailing whitespace, etc.)

## [0.28.0] - 2026-06-29

### Added
- **`cutctx capabilities` command** — new CLI command to display all available compression capabilities, formats, algorithms, and configuration options
- **Pass-through audio routing** — audio requests pass through unmodified when compression is not applicable
- **Documentation improvements** — expanded README guidance on install extras and CLI commands

### Fixed
- **README install guidance** — clarified distinction between recommended/full install (`pip install "cutctx-ai[all]"`) and granular extras
- **Audio compression documentation** — documented pass-through behavior for non-compression scenarios


## [0.26.1] - 2026-06-23

### Security
* **Hardware fingerprint hardening**: replaced `uuid.getnode()` (MAC address, trivially spoofed) with OS-native machine IDs — `/etc/machine-id` on Linux, `IOPlatformUUID` via `ioreg` on macOS, `HKLM\MachineGuid` on Windows. Three-factor binding: machine ID + hostname + username.
* **HMAC signature expanded 64-bit → 128-bit**: `licensing.rs` truncation changed from 16 → 32 hex chars with constant-time XOR fold comparison and up-front length rejection. `generate_license.py` updated to emit 32-char signatures.
* **Anti-debug guard**: Rust module `antidebug.rs` — macOS `ptrace(PT_DENY_ATTACH)`, Linux `TracerPid` parse, Windows `IsDebuggerPresent`. Python fallback in `cutctx/security/antidebug.py`. `CUTCTX_ALLOW_DEBUG=1` escape hatch. Called automatically at EE import time.
* **EE binary integrity manifest**: `cutctx_ee/MANIFEST.sha256.json` — SHA-256 hashes of all `.so` files, HMAC-signed with `CUTCTX_LICENSE_HMAC_SECRET`. Verified by `cutctx/security/integrity.py` before any EE code executes. `CUTCTX_SKIP_INTEGRITY_CHECK=1` escape hatch for debugging.

### Fixed
* **Stateless mode** (`--stateless` / `CUTCTX_STATELESS=true`): 14 files updated to use `:memory:` SQLite; beacon lock files, file logging, and subscription file persistence all guarded. Zero files written in stateless mode (was 20+).
* **Docker**: `COPY cutctx_ee/` was missing from `Dockerfile`, causing `ImportError` at container start. Fixed with correct COPY directives, extras (`proxy,code,ee`), `--no-editable` install, and EE manifest rebuild for Linux platform.
* **Proxy routes**: `/audit/stats` returned 404 (now 403 for non-enterprise); `/v1/spend/query` returned 500 (now 200 with NullStore fallback); `/v1/dsr/export` and `/v1/dsr/delete` had wrong prefix (`/v1/me` → `/v1/dsr`).
* **CLI** (from manual testing pass): `bench --algorithm` six implementations replacing broken `_get_algorithms()`; `agent-savings` duplicate `--format` option removed; `audit` broken import removed; `learn --dry-run` flag added; `evals probes` empty-directory guard.
* **Compression**: `compact_table.py` `compress()` was returning `None`; `diff_compressor.py` Python fallback added for when Rust produces no compression; `log_compressor.py` missing `tokens_saved_estimate` field; `selective_filter.py` wrong return type.
* **LlamaIndex Pydantic v2 compatibility**: `CutctxNodePostprocessor` fields now use class-level annotations and `PrivateAttr`.
* **Air-gap mode**: `is_offline()` now checks both `CUTCTX_AIR_GAP=1` and `CUTCTX_OFFLINE_MODE=1`; proxy refuses to start without `CUTCTX_LICENSE_HMAC_SECRET` in air-gap mode.
* **EE integrity check on source installs**: `verify_ee_manifest` now detects when zero `.so` files are present (fresh clone / uncompiled dev install) and skips gracefully instead of raising `IntegrityError`.

### Added
* **JetBrains plugin CI verification**: `pluginVerification.ides` block added to `build.gradle.kts` — verifies against IntelliJ IDEA Community 2024.1, 2024.3, and 2025.1 (the full declared `sinceBuild=241` / `untilBuild=251.*` range).
* **`CCRStore`**: backward-compatible wrapper (`cutctx/ccr/store.py`) exposing legacy `put()`/`get()` API over `BatchContextStore`.
* **Missing package inits**: `cutctx_ee/memory_service/__init__.py` and `cutctx_ee/tests/__init__.py` added (were causing `ImportError` in Docker).

### Fixed
* **pyproject.toml URLs**: corrected typo `AryanSingh/cutcxt` → `cutctx/cutctx` in Repository, Issues, and Changelog URLs
* **README badge URLs**: all 5 `AryanSingh/cutcxt` badge and star-history URLs corrected to `cutctx/cutctx`

### Added
* **PRIVACY.md**: new document covering local-first architecture, CCR store location, `--stateless` / `--no-telemetry` modes, API key pass-through, enterprise VPC deployment, and explicit "what Cutctx does NOT do" list
* **Image optimization documented**: README and proxy `--help` now surface the `image_optimize` capability (40–90% reduction, zero config, on-by-default)
* **Accuracy guard documented**: `CUTCTX_ACCURACY_GUARD=strict|balanced|off` surfaces in README near proxy configuration
* **LLMLingua-2 integration** (`pip install cutctx-ai[llmlingua]`): Microsoft's BERT-level ML token-classification compressor now available as an optional algorithm. Use `cutctx proxy --llmlingua` or `CUTCTX_USE_LLMLINGUA=1`. Falls through to Kompress gracefully when not installed. Provides a second ML compression path independent of the Kompress/ModernBERT stack.
* **CompactTableCompressor**: new pure-Python transform that serializes JSON arrays of homogeneous objects into a compact pipe-delimited table format (30–60% smaller than JSON for file listings, DB rows, search results, API list responses). Auto-activates for arrays of ≥5 dicts before SmartCrusher; constant columns collapsed to header annotations.
* **Query-aware compression** (`--query-aware` / `CUTCTX_QUERY_AWARE=1`): detects the user's task type from the last message (CODE, DEBUG, SEARCH, LIST, SUMMARIZE, etc.) and automatically adjusts `protect_recent` and `min_tokens_to_crush` per compression pass. CODE/DEBUG: conservative (protect last 6 turns). SEARCH/LIST/SUMMARIZE: aggressive (protect last 2 turns). Uses existing `TaskType` feature extractor infrastructure.
* **JetBrains plugin**: raised `pluginUntilBuild` from `243.*` to `251.*` so the plugin is compatible with IntelliJ 2025.1+ (build 251)
* **Langfuse integration surfaced** (`pip install cutctx-ai[langfuse]`): `cutctx proxy --langfuse` (or `CUTCTX_LANGFUSE_ENABLED=1`) now activates the built-in Langfuse OTEL tracing with visible CLI flag, startup banner line, and `[langfuse]` installable extra. Added `wiki/langfuse.md`.
* **LlamaIndex integration** (`pip install cutctx-ai[llamaindex]`): `CutctxNodePostprocessor` — drop-in LlamaIndex `NodePostprocessor` that filters retrieved nodes by BM25/hybrid relevance score and optionally compresses surviving node text via Cutctx ContentRouter. Added `wiki/llamaindex.md`.
* **Selective Context Filter** (`--selective-filter` / `CUTCTX_SELECTIVE_FILTER=1`): new pre-compression transform that scores each conversation turn against the current user query and drops turns below `--selective-filter-threshold` (default 0.15). Uses existing BM25/hybrid relevance infrastructure. Wired into `ContentRouterConfig` and runs before all compression logic.

### Added
* **`cutctx init windsurf`**: now performs real durable install — writes `openai.baseUrl` to the platform-correct Windsurf `settings.json` (macOS/Linux/Windows paths resolved automatically); merges non-destructively with existing settings
* **`cutctx init zed`**: now performs real durable install — writes `language_models.openai.api_url` and `language_models.anthropic.api_url` into `~/.config/zed/settings.json` via deep-merge
* **`cutctx init opencode`**: now performs real durable install — injects `OPENAI_BASE_URL` into the user's shell profile using the existing marker-block mechanism (same pattern as Copilot/Gemini)
* **`cutctx proxy --ccr-ttl-seconds`**: configurable CCR store TTL (default 1800s / 30 min; `0` = never expire). Also controllable via `CUTCTX_CCR_TTL_SECONDS` env var. Removes the silent-data-loss risk on long agent runs and enables persistent/daemon deployments with no expiry
* **e2e wrap smoke tests**: added `verify_windsurf_wrap`, `verify_zed_wrap`, `verify_opencode_wrap` to `e2e/wrap/run.py` following the `--prepare-only` pattern used by cline/continue/goose/openhands

### Added

* **harnesses — Windsurf:** `cutctx wrap windsurf` starts the proxy and prints OpenAI and Anthropic base URL configuration instructions for Windsurf's Settings UI and `settings.json`. Provider module at `cutctx/providers/windsurf/`. `cutctx init windsurf` prints manual shell-profile setup instructions.
* **harnesses — Zed:** `cutctx wrap zed` starts the proxy and prints the exact `language_models.openai.api_url` / `language_models.anthropic.api_url` JSON snippet for `~/.config/zed/settings.json`. Provider module at `cutctx/providers/zed/`. `cutctx init zed` prints manual setup instructions.
* **harnesses — opencode:** `cutctx wrap opencode` starts the proxy and launches opencode with `OPENAI_BASE_URL` pointed at the local proxy — same Pattern A as `cutctx wrap codex`. `cutctx init opencode` prints manual shell-profile instructions. Added `opencode` and `windsurf` to `_AGENT_SAVINGS_WRAP_AGENTS` for per-session savings attribution.
* **VS Code extension:** full TypeScript extension at `extensions/vscode/` — auto-starts the `cutctx proxy` process, polls `/stats` every 30 s, shows tokens saved in the status bar, and configures Cline / Continue via command. Published as `cutctx-ai` on the VS Code Marketplace.
* **JetBrains plugin:** full Kotlin/Gradle plugin at `extensions/jetbrains/` for IntelliJ IDEA, PyCharm, and all JetBrains IDEs — `ProxyService` manages the proxy process lifetime, status bar widget shows live savings, settings configurable, Tools > Cutctx menu. Uses IntelliJ Platform Gradle Plugin v2.
* **distribution protection:** `scripts/strip_wheel.py` strips proprietary `.py` sources from built wheels (algorithms stay in compiled Rust `.so`). `scripts/build_protected_wheel.sh` runs the full maturin + strip pipeline in one command. `make dist-protected` target added. `PROTECTION.md` documents the protection architecture.
* **compress SKILL.md:** adversarially tested all five claims against live `cutctx-ai` v0.27.0 install; corrected binary name, removed non-existent CLI commands (`compress`, `stats`, `retrieve`), added proxy dependency note, fixed compression ratio claims, documented 30-minute CCR TTL.

* **kompress:** warn when `CUTCTX_KOMPRESS_BACKEND` is set to an unrecognized
  value instead of silently falling back to `auto`, and document the backend
  selection env var (`auto` / `onnx` / `onnx_cpu` / `onnx_coreml` / `pytorch` /
  `pytorch_mps` plus shorthand aliases) in `wiki/configuration.md` (issue
  [#202](https://github.com/cutctx/cutctx/issues/202), PR
  [#204](https://github.com/cutctx/cutctx/pull/204)).
* **proxy:** per-provider attribution in the savings history rollups. Each `/stats-history` bucket (hourly/daily/weekly/monthly) now carries a `by_provider` map breaking down `tokens_saved`, `compression_savings_usd_delta`, `total_input_tokens_delta`, and `total_input_cost_usd_delta` per provider, so consumers can show how savings and spend are distributed across providers within a time period. Providers only appear in a bucket where they moved a counter; legacy history checkpoints with no provider collapse into `"unknown"`. Affected files: `cutctx/proxy/savings_tracker.py`, `cutctx/proxy/prometheus_metrics.py`.
* **cli:** startup banner now includes a `Performance Tuning` section that surfaces active `CUTCTX_COMPRESSION_STABLE_AFTER_TURN`, `CUTCTX_STALE_READ_COMPRESS_AFTER_TURNS`, and embedding-server socket values when set; shows a hint to set them when all defaults are in use.

### Changed

* **deps:** loosen over-pinned constraints and add upper bounds
  - `litellm==1.82.3` -> `>=1.86.2,<2.0` (exact pin blocked security patches; floor stays above the CVE-2026-42271 fix)
  - `transformers>=4.30.0` -> `>=4.30.0,<6.0` (add upper bound; library already crossed a major version silently)
  - `sentence-transformers>=2.2.0` -> `>=2.2.0,<6.0` (same; applied in `memory`, `evals`, and `dev` extras)
  - `neo4j>=5.20.0` -> `>=5.20.0,<7.0` (client had already crossed the 5.x/6.x boundary)
  - `mem0ai>=0.1.100` -> `>=1.0.0,<2.0` (floor was pre-1.0; locked package is already 1.0.11)
  - `langchain-core>=0.2.0` -> `>=1.3.3,<4.0` (floor stays above current high-severity advisory fixes)
  - `langchain-openai>=0.1.0` -> `>=1.1.14,<2.0` (floor stays above current advisory fixes)
  - `qdrant-client>=1.9.0` -> `>=1.9.0,<2.0`
  - `uvicorn>=0.23.0` -> `>=0.23.0,<1.0` (applied in `proxy` and `dev` extras)
  - Same `transformers` and `litellm` bounds applied consistently across `ml`, `voice`, and `dev` extras
* **docker:** bump `neo4j` image in `docker-compose.yml` from `5.15.0` to `5.26` (latest 5.x LTS)
* **docker:** bump `UV_VERSION` in `Dockerfile` from `0.11.16` to `0.11.18`

### Bug Fixes

* **codex:** respect `CODEX_HOME` when `cutctx wrap codex` writes provider, MCP, memory, backup, and global `AGENTS.md` config, and warn when `unwrap codex` may be looking at the default Codex home because `CODEX_HOME` is unset.
* **proxy:** multi-worker CCR warning is now conditional on backend — when `CUTCTX_CCR_BACKEND` is unset (default `InMemoryBackend`, per-process), the startup warning includes CCR retrieval failures and suggests `CUTCTX_CCR_BACKEND=sqlite`; when a cross-worker backend is already configured, the warning covers only the remaining per-worker stores (compression cache, prefix tracker, TOIN, CostTracker). Updated `RUST_DEV.md` to accurately document Python `CompressionStore` as per-process by default.
* **deps:** move `gunicorn` to `[proxy-prod]` extra with `sys_platform != 'win32'` guard; removed from `[proxy]` to avoid forcing a Unix-only package on dev, CI, and Windows users ([#537](https://github.com/cutctx/cutctx/pull/537))
* **startup:** suppress proxy startup log noise -- litellm banner, trafilatura parse errors, HuggingFace Hub unauthenticated warnings, tiktoken fallback warning, and httpx INFO lines from sentence_transformers HEAD checks. Affected files: `cutctx/providers/litellm.py`, `cutctx/transforms/html_extractor.py`, `cutctx/memory/adapters/embedders.py`, `cutctx/providers/anthropic.py`, `cutctx/providers/registry.py`, `cutctx/image/onnx_router.py`, `cutctx/transforms/kompress_compressor.py`.

### Security
- **`/debug/memory` loopback guard.** The endpoint was missing the
  `Depends(_require_loopback)` guard that all other `/debug/*` endpoints carry.
  External callers can no longer reach it.
- **`retry_max_attempts` zero guard.** When `retry_enabled=True` and
  `retry_max_attempts=0` the retry loop exited without setting `last_error`,
  causing `raise last_error` to raise `TypeError: exceptions must derive from
  BaseException`. A `RuntimeError` with an actionable message is now raised
  instead, and `ProxyConfig.__post_init__` rejects `retry_max_attempts < 1`
  at construction time.
- **Blocking subprocess on async event loop.** `_read_rtk_lifetime_stats` and
  `_read_lean_ctx_lifetime_stats` called `subprocess.run` directly on the
  asyncio thread. The `initialize_context_tool_session_baseline` function is
  now `async` and offloads the subprocess via `asyncio.to_thread`; the stats
  endpoint uses `await asyncio.to_thread(_get_context_tool_stats)`.
- **Hardcoded Neo4j credential in `docker-compose.yml`.** `NEO4J_AUTH` now
  defaults to `${NEO4J_AUTH:-neo4j/REPLACE_WITH_STRONG_PASSWORD}` and is documented in
  `.env.example` (excluded from `.gitignore` via `!.env.example`).
- **`SemanticCache.get_memory_stats()` concurrent iteration.** The method
  iterates `self._cache.values()` without holding the async lock. A snapshot
  is now taken via `list(self._cache.values())` before iterating to avoid
  `RuntimeError: dictionary changed size during iteration` under async load.
- **Default Neo4j password in `ProxyConfig`.** `memory_neo4j_password` default
  changed from `"password"` to `""`. The proxy startup path now emits a
  `logger.warning` when `memory_backend == "qdrant-neo4j"` and the password
  is empty, prompting operators to set a real credential.

### Fixed
- **PyPI install clarity and release gating.** Documented `pipx --python python3.13`
  for environments where unsupported Python wheel tags cause older-version
  resolution, made PyPI publish failures block GitHub Releases unless
  `PYPI_SKIP=true`, and added an sdist `LICENSE` invariant.

- **`cutctx learn` with claude-cli no longer fails silently on slow
  networks or large digests.** The CLI backend timeout was a hard 120s
  wall-clock cap with no liveness signal: a successful long analysis and
  a hung connection looked identical, and exit 0 with "no recommendations"
  was the only user-visible signal. Two changes:
  (1) **Streaming + idle timeout for claude-cli**: the command now uses
  `--output-format stream-json --verbose` and a watchdog thread reads
  events as they arrive. The process is killed only after
  `CUTCTX_LEARN_CLI_IDLE_TIMEOUT_SECS` (default 60s) of zero output, or
  after `CUTCTX_LEARN_CLI_TIMEOUT_SECS` (default 300s, was 120s) total.
  Long-but-active analyses run to completion; genuine hangs are caught
  fast. The final `type:"result"` event carries the assistant response.
  Drains stdout/stderr via reader threads so the watchdog works on
  Windows too. (2) **Env-var overrides for all CLI backends**:
  `CUTCTX_LEARN_CLI_TIMEOUT_SECS` is honored by gemini-cli and
  codex-cli as the wall-clock timeout; idle override applies only to the
  streaming claude-cli path.
- **`Learned: error recovery` section in MEMORY.md no longer bloats with
  stale, one-shot, or contradictory entries.** The matchers paired up
  unrelated tool calls (e.g. `state.rs` and `lib.rs` in the same dir
  becoming `File state.rs does not exist. The correct path is lib.rs.`),
  the dedup key was the literal rendered bullet text so near-duplicates
  each created their own row, the shutdown flush dropped the evidence
  gate to 1 so every singleton landed at session end, and there was no
  TTL or re-validation. Fixed at every layer:
  (1) **Emission**: Read recoveries require the failed/successful
  basenames to be identical or close in edit distance; Bash recoveries
  require a shared binary (allowing `python`↔`python3` and
  `ruff`↔`.venv/bin/ruff` variants) plus low-edit-distance OR a shared
  substantive non-flag token. Unrelated pairs are rejected at the source.
  (2) **Dedup**: error-recovery rows are hashed on recovery intent —
  Read on `(basename(error_path), basename(success_path))`, Bash on the
  primary command stripped of volatile suffixes (`| tail -N`, `2>&1`,
  etc.). Near-duplicates collapse into one row.
  (3) **Evidence gating**: default `min_evidence` raised from 2 to 5;
  shutdown-relaxation removed; new `--min-evidence` flag and
  `CUTCTX_MIN_EVIDENCE` envvar so embedded clients can tighten the
  threshold further.
  (4) **Render-time refinement**: drop rows not re-observed in 21 days,
  re-validate Read success paths against the filesystem, collapse
  same-error_path-with-multiple-targets into one "use Glob/Grep first"
  bullet, rank by `evidence_count * 0.5 ** (days/5)`, cap the section
  at 15. A→B / B→A contradiction pairs are also dropped at flush time.
  Patterns now stamp `first_seen_at` / `last_seen_at` on every save;
  `_bump_persisted_evidence` updates them via `json_set`. Other
  `Learned: …` categories (environment, preference, architecture) are
  untouched.
- **`cutctx unwrap codex` now actually undoes `cutctx wrap codex`** —
  previously there was no `unwrap codex` subcommand at all, so the injected
  `model_provider = "cutctx"` / `[model_providers.cutctx]` block stayed
  in `~/.codex/config.toml` forever and Codex continued routing through the
  (potentially stopped) proxy, surfacing as `Missing environment variable:
  OPENAI_API_KEY`. `wrap codex` now snapshots the pre-wrap
  `config.toml` to `config.toml.cutctx-backup` before its first injection,
  and `unwrap codex` restores that snapshot byte-for-byte (or, if the
  backup is missing, strips only the Cutctx-managed block and leaves
  surrounding user content intact). Safe no-op when run without a prior
  wrap. Reported by @raenaryl in Discord.
- **Image compressors now release shared router models after use and proxy shutdown** —
  the proxy/image compression path no longer keeps global `technique-router`
  and `SigLIP` model instances pinned in memory after one-off image
  optimization work. The `get_compressor()` helper now returns a fresh,
  caller-owned compressor instead of a process-lifetime singleton.
- **`cutctx learn` no longer clobbers prior recommendations on re-run** —
  the marker block in `CLAUDE.md` / `MEMORY.md` is now merged with the
  prior block instead of wholesale-replaced. Sections re-surfaced by the
  new run win; sections not re-surfaced are carried forward so learnings
  accumulate across runs instead of disappearing. To fully rebuild the
  block, delete it manually and re-run. (#231)
- **`cutctx learn` no longer emits dangling cross-references when a
  section is re-surfaced** — the analyzer now includes the project's
  current `<!-- cutctx:learn -->` block (from `CLAUDE.md` and
  `MEMORY.md`) in the LLM digest as a "Prior Learned Patterns" section,
  and the system prompt instructs the LLM that re-emitting a section
  replaces the prior one wholesale. Prevents bullets like "`X` is *also*
  large — same rule as `Y`, `Z`" from appearing after `Y` and `Z` got
  dropped during per-section replacement. The writer's section-level
  carry-forward from #231 remains in place as a safety net for sections
  the LLM omits entirely. New helper `extract_marker_block` added to
  `cutctx.learn.writer`.

### Added
- **`turn_id` linking agent-loop API calls to a single user prompt** — a new
  `compute_turn_id(model, system, messages)` helper in
  `cutctx/proxy/helpers.py` hashes the message prefix up to and including
  the last user-text message, yielding an id that is stable across every
  agent-loop iteration of one prompt but rolls over when the user sends a
  new prompt (or runs `/compact`, `/clear`). `RequestLog` gained a
  `turn_id: str | None` field, which is stamped at every log site
  (anthropic handler bedrock + direct branches, and the streaming handler)
  and surfaced as `turn_id` in `/transformations/feed`. Lets downstream
  consumers (e.g. the Cutctx Desktop Activity tab) aggregate savings per
  user prompt rather than per API call.
- **Live flush of traffic-learned patterns to CLAUDE.md / MEMORY.md** — the
  `TrafficLearner` now writes to agent-native context files continuously
  during proxy operation, not just at shutdown. A new dirty-flag debounced
  `_flush_worker` (10s window, `FLUSH_DEBOUNCE_SECONDS`) calls
  `flush_to_file()` whenever `_accumulate()` marks the learner dirty, so
  patterns surface in `CLAUDE.md` / `MEMORY.md` near real-time. Flushes
  read both persisted rows (via `_load_persisted_patterns_from_sqlite`)
  and the in-memory accumulator, bucket patterns by project via the learn
  plugin registry (`plugin.discover_projects()` + longest-path anchoring
  in `_project_for_pattern`), and route by `PatternCategory` to the
  correct file (`_patterns_to_recommendations` +
  `_CATEGORY_TO_TARGET`). Live flushes require `evidence_count >= 2`;
  the shutdown flush accepts single-evidence rows.

### Fixed
- **Traffic-learner evidence count stuck at 1; duplicate DB rows across
  restarts.** `_accumulate` queued patterns with the default
  `ExtractedPattern.evidence_count = 1` regardless of how many times the
  pattern was actually seen, so every persisted row landed at `1` and
  never crossed the live-flush gate (`evidence_count >= 2`). Worse, once
  a pattern was in `_saved_hashes` it was early-returned on every
  re-sighting, and `_saved_hashes` reset on process restart — so a second
  sighting in a later session inserted a duplicate row rather than
  bumping the existing one. Now: `_accumulate` writes the real
  accumulated count at save time, `start()` hydrates `_saved_hashes` +
  a new `_persisted_ids` map from the DB, and re-sightings bump the
  persisted row's `metadata.evidence_count` via an atomic `json_set`
  `UPDATE` (`_bump_persisted_evidence`). `_load_persisted_patterns_from_sqlite`
  now filters via `json_extract(metadata, '$.source')` instead of a
  LIKE on the raw JSON string, so rows survive metadata rewrites.

### Added
- **`CUTCTX_QDRANT_*` environment variables for memory Qdrant configuration**
  (#31) — `Memory(backend="qdrant-neo4j")`, `Mem0Config`, `MemoryConfig`, and
  `ProxyConfig` now resolve their Qdrant connection from
  `CUTCTX_QDRANT_URL`, `CUTCTX_QDRANT_HOST`, `CUTCTX_QDRANT_PORT`,
  `CUTCTX_QDRANT_API_KEY`, `CUTCTX_QDRANT_HTTPS`,
  `CUTCTX_QDRANT_PREFER_GRPC`, and `CUTCTX_QDRANT_GRPC_PORT`. Explicit
  constructor arguments still win; unset env keeps the existing
  `localhost:6333` defaults. Adds matching `--memory-qdrant-{url,host,port,api-key}`
  CLI flags. Enables hosted Qdrant (Qdrant Cloud) and shared/remote Qdrant
  stacks without code changes. New helper:
  [`cutctx/memory/qdrant_env.py`](cutctx/memory/qdrant_env.py).
- **Telemetry stack & install-mode identity fields** — anonymous beacon now
  reports `cutctx_stack` (how Cutctx is invoked: `proxy`, `wrap_claude`,
  `adapter_ts_openai`, ...) and `install_mode` (`wrapped` / `persistent` /
  `on_demand`), plus `requests_by_stack` for proxies that serve multiple
  integrations. Proxy exposes a `by_stack` bucket alongside `by_provider` /
  `by_model` on `/stats`, a matching `cutctx_requests_by_stack` Prometheus
  counter, and an `X-Cutctx-Stack` header honored by the FastAPI middleware.
  `cutctx wrap <tool>` sets `CUTCTX_STACK=wrap_<agent>`; the TS SDK and
  all four adapters (`openai`, `anthropic`, `gemini`, `vercel-ai`) tag their
  compress calls. Schema migration:
  [`sql/upgrade_telemetry_stack_context.sql`](sql/upgrade_telemetry_stack_context.sql).
- **Canonical filesystem contract** (issue #175) — new `CUTCTX_CONFIG_DIR`
  (default `~/.cutctx/config`, read-mostly) and `CUTCTX_WORKSPACE_DIR`
  (default `~/.cutctx`, read-write state) env vars recognized by the Python
  proxy/CLI and the npm SDK. Additive; all existing per-resource env vars
  (`CUTCTX_SAVINGS_PATH`, `CUTCTX_TOIN_PATH`,
  `CUTCTX_SUBSCRIPTION_STATE_PATH`, `CUTCTX_MODEL_LIMITS`) continue to
  work with identical semantics. Docker install scripts and
  `docker-compose.native.yml` forward the new vars into containers so
  savings, logs, and telemetry resolve to the bind-mounted `.cutctx` path.
  See [`wiki/filesystem-contract.md`](wiki/filesystem-contract.md).

### Changed
- **`/stats-history` now returns compact checkpoint history by default** — the
  JSON response keeps recent checkpoints dense while evenly sampling older
  checkpoints so long-running installs do not return ever-growing payloads.
  Add `history_mode=full` to fetch the full retained checkpoint list, or
  `history_mode=none` to skip it entirely while still receiving the derived
  hourly/daily/weekly/monthly rollups. Responses now include a
  `history_summary` block describing stored versus returned points.

### Fixed
- **Streaming Anthropic requests are now visible to `/stats.recent_requests`
  and `/transformations/feed`** — `_finalize_stream_response` did not call
  `self.logger.log(...)`, so the entire streaming Anthropic code path (the
  one Claude Code uses) silently bypassed the request logger. Only the
  non-streaming Anthropic path and the Bedrock streaming path were logged.
  As a consequence, `--log-messages` had no observable effect on the live
  transformations feed for typical traffic. The streaming finalizer now
  emits the same `RequestLog` shape the other paths do, including
  `request_messages` when `log_full_messages` is enabled.

### Added
- **Codex-proxy resilience hardening** — reduces event-loop starvation under cold-start reconnect storms
  - **Stage-timing instrumentation** — per-stage durations for both Codex WS accept and Anthropic `/v1/messages` pre-upstream phases emitted as a single `STAGE_TIMINGS` structured log line per request plus Prometheus histograms
  - **Per-pipeline shared warmup** — Anthropic + OpenAI pipelines eagerly load compressors/parsers once at startup; status merged into `WarmupRegistry` for `/debug/warmup` and `/readyz`
  - **WS session registry** — first-class tracking of active Codex WS sessions with deterministic relay-task cancellation and termination-cause classification (`client_disconnect`, `upstream_error`, `client_timeout`, etc.)
  - **Bounded pre-upstream Anthropic concurrency** — `--anthropic-pre-upstream-concurrency` / `CUTCTX_ANTHROPIC_PRE_UPSTREAM_CONCURRENCY` caps simultaneous `/v1/messages` pre-upstream work (body read, deep copy, first compression stage, memory-context lookup, upstream connect) so replay storms cannot starve `/livez`, `/readyz`, and new Codex WS opens. Default: auto `max(2, min(8, cpu_count))`; `0` or negative disables (unbounded)
  - **Loopback-only debug endpoints** — `/debug/tasks`, `/debug/ws-sessions`, `/debug/warmup` return `404` (not `403`) to non-loopback callers so external scanners cannot enumerate them
  - **Reconnect-storm repro harness** — `scripts/repro_codex_replay.py` drives concurrent WS + HTTP replay traffic against a local proxy and asserts `/livez` p99 under threshold; `--json` output routes JSON to stdout and the human summary to stderr
- **Proxy liveness and readiness health checks**
  - Adds `GET /livez` for process liveness and `GET /readyz` for traffic readiness
  - Keeps `GET /health` backward compatible while expanding it with readiness details and subsystem checks
  - Eagerly initializes configured memory backends during proxy startup so readiness reflects real serving capability
  - Wires `/readyz` into the Docker image `HEALTHCHECK` and the example `docker-compose.yml`
- **Durable proxy savings history**
  - Persists proxy compression savings history locally at `~/.cutctx/proxy_savings.json`
  - Supports `CUTCTX_SAVINGS_PATH` to override the storage location
  - Adds `/stats-history` with lifetime totals plus hourly/daily/weekly/monthly rollups
  - Supports JSON and CSV export from `/stats-history`
  - Extends `/stats` with a `persistent_savings` block while keeping `savings_history` backward compatible
  - Adds a historical mode to `/dashboard` backed by `/stats-history`, including export actions
- **Proxy telemetry SDK override** via `CUTCTX_SDK`
  - Downstream apps can override the anonymous telemetry `sdk` field without patching installed files
  - Blank values fall back to the default `proxy` label
- **`cutctx learn`** — Offline failure learning for coding agents
  - Analyzes past conversation history (Claude Code, extensible to Cursor/Codex)
  - **Success correlation**: for each failure, finds what succeeded after and extracts the specific correction
  - 5 analyzers: Environment, Structure, Command Patterns, Retry Prevention, Cross-Session
  - Writes specific learnings to CLAUDE.md (stable project facts) and MEMORY.md (session patterns)
  - Generic architecture: tool-agnostic `ToolCall` model, pluggable Scanner/Writer adapters
  - Dry-run by default, `--apply` to write, `--all` for all projects
  - Example output: "FirstClassEntity.java is not at axion-formats/ — actually at axion-scala-common/"
- **Read Lifecycle Management** — Event-driven compression of stale/superseded Read outputs
  - Detects when a Read output becomes stale (file was edited after) or superseded (file was re-read)
  - Replaces stale/superseded content with compact CCR markers, stores originals for retrieval
  - 75% of Read output bytes are provably stale or redundant (from real-world analysis of 66K tool calls)
  - Fresh Reads (latest read, no subsequent edit) are never touched — Edit safety preserved
  - Opt-in via `ReadLifecycleConfig(enabled=True)`, disabled by default
  - Handles both OpenAI and Anthropic message formats
- **any-llm backend** - Route requests through 38+ LLM providers (OpenAI, Mistral, Groq, Ollama, etc.) via [any-llm](https://mozilla-ai.github.io/any-llm/providers/)
  - Enable with `--backend anyllm --anyllm-provider <provider>`
  - Install with: `pip install 'cutctx-ai[anyllm]'`
- Production-ready proxy server with caching, rate limiting, and metrics
- CLI command `cutctx proxy` to start the proxy server

- **LLMLingua-2 Integration** (opt-in ML-based compression)
  - `LLMLinguaCompressor` transform using Microsoft's LLMLingua-2 model
  - Content-aware compression rates (code: 0.4, JSON: 0.35, text: 0.3)
  - Memory management utilities: `unload_llmlingua_model()`, `is_llmlingua_model_loaded()`
  - Proxy integration via `--llmlingua` flag
  - Device selection: `--llmlingua-device` (auto/cuda/cpu/mps)
  - Custom compression rate: `--llmlingua-rate`
  - Helpful startup hints when llmlingua is available but not enabled
  - ~~Install with: `pip install cutctx-ai[llmlingua]`~~ (the `[llmlingua]` extra was removed in 0.9.x)
- **Code-Aware Compression** (AST-based, syntax-preserving)
  - `CodeAwareCompressor` transform using tree-sitter for AST parsing
  - Supports Python, JavaScript, TypeScript, Go, Rust, Java, C, C++
  - Preserves imports, function signatures, type annotations, error handlers
  - Compresses function bodies while maintaining structural integrity
  - Guarantees syntactically valid output (no broken code)
  - Automatic language detection from code patterns
  - Memory management: `is_tree_sitter_available()`, `unload_tree_sitter()`
  - Uses `tree-sitter-language-pack` for broad language support
  - Install with: `pip install cutctx-ai[code]`
- **ContentRouter** (intelligent compression orchestrator)
  - Auto-routes content to optimal compressor based on type detection
  - Source hint support for high-confidence routing (file paths, tool names)
  - Handles mixed content (e.g., markdown with code blocks)
  - Strategies: CODE_AWARE, SMART_CRUSHER, SEARCH, LOG, TEXT, LLMLINGUA
  - Configurable strategy preferences and fallbacks
  - Routing decision log for transparency and debugging
- **Custom Model Configuration**
  - Support for new models: Claude 4.5 (Opus), Claude 4 (Sonnet, Haiku), o3, o3-mini
  - Pattern-based inference for unknown models (opus/sonnet/haiku tiers)
  - Custom model config via `CUTCTX_MODEL_LIMITS` environment variable
  - Config file support: `~/.cutctx/models.json`
  - Graceful fallback for unknown models (no crashes)
  - Updated pricing data for all current models

### Fixed
- **Event.wait task leak in subscription trackers** — `asyncio.shield` pattern prevents cancellation of the outer `wait_for` from leaking the inner `Event.wait` task
- **Python 3.10 compatibility for memory-context fail-open** — catches `asyncio.TimeoutError` (the 3.10-compatible alias) rather than `TimeoutError` to preserve behaviour on older runtimes
- **uvicorn `proxy_headers=False`** — refuses `Forwarded` / `X-Forwarded-For` rewrites so the loopback guard on `/debug/*` cannot be spoofed by a misconfigured reverse proxy
- **First-frame timeout for Codex WS accepts** — guards against a client that opens a handshake and never sends the first frame; relays cancel deterministically with `client_timeout`
- **Semaphore leak on unexpected exception in Anthropic pre-upstream path** — the finalizer now releases the pre-upstream semaphore on every exit path (early 4xx, cache hit, upstream error, streaming handoff)
- **`active_relay_tasks` gauge double-decrement** — `deregister_and_count` returns `(handle, released_task_count)` atomically so the handler decrements the Prometheus gauge by the exact number it registered, eliminating drift

### Internal
- **IPv6-mapped loopback recognition** — the loopback guard parses `::ffff:127.0.0.1` and other dual-stack literals through `ipaddress.ip_address(...).is_loopback`
- **Lock-free stage-timing accumulators** — `record_stage_timings` writes to per-path counters that do not contend with `/metrics` export or `record_request`
- **Narrow `contextlib.suppress` in relay classification** — only `CancelledError` is suppressed where we reclassify it; other exceptions propagate so termination cause stays truthful
- **`jitter_delay_ms` helper** — shared exponential-backoff + 50-150% jitter formula in `cutctx/proxy/helpers.py`; used by three proxy retry sites and mirrored inline in the repro harness

## [0.2.0] - 2025-01-07

### Added
- **SmartCrusher**: Statistical compression for tool outputs
  - Keeps first/last K items, errors, anomalies, and relevance matches
  - Variance-based change point detection
  - Pattern detection (time series, logs, search results)
- **Relevance Scoring Engine**: ML-powered item relevance
  - `BM25Scorer`: Fast keyword matching (zero dependencies)
  - `EmbeddingScorer`: Semantic similarity with sentence-transformers
  - `HybridScorer`: Adaptive combination of both methods
- **CacheAligner**: Prefix stabilization for better cache hits
  - Dynamic date extraction
  - Whitespace normalization
  - Stable prefix hashing
- **RollingWindow**: Context management within token limits
  - Drops oldest tool units first
  - Never orphans tool results
  - Preserves recent turns
- **Multi-Provider Support**:
  - Anthropic with official `count_tokens` API
  - Google with official `countTokens` API
  - Cohere with official `tokenize` API
  - Mistral with official tokenizer
  - LiteLLM for unified interface
- **Integrations**:
  - LangChain callback handler (`CutctxOptimizer`)
  - MCP (Model Context Protocol) utilities
- **Proxy Server** (`cutctx.proxy`):
  - Semantic caching with LRU eviction
  - Token bucket rate limiting
  - Retry with exponential backoff
  - Cost tracking with budget enforcement
  - Prometheus metrics endpoint
  - Request logging (JSONL)
- **Pricing Registry**: Centralized model pricing with staleness tracking
- **Benchmarks**: Performance benchmarks for transforms and relevance scoring

### Changed
- Improved token counting accuracy across all providers
- Enhanced tool output compression with relevance-aware selection

### Fixed
- Mistral tokenizer API compatibility
- Google token counting for multi-turn conversations

## [0.1.0] - 2025-01-05

### Added
- Initial release
- `CutctxClient`: OpenAI-compatible client wrapper
- `ToolCrusher`: Basic tool output compression
- Audit mode for observation without modification
- Optimize mode for applying transforms
- Simulate mode for previewing changes
- SQLite and JSONL storage backends
- HTML report generation
- Streaming support

### Safety Guarantees
- Never removes human content
- Never breaks tool ordering
- Parse failures are no-ops
- Preserves recency (last N turns)

---

## Migration Guide

### From 0.1.x to 0.2.x

The 0.2.0 release is backward compatible. New features are opt-in:

```python
# Old code still works
from cutctx import CutctxClient, OpenAIProvider

# New SmartCrusher (replaces ToolCrusher for better compression)
from cutctx import SmartCrusher, SmartCrusherConfig

config = SmartCrusherConfig(
    min_tokens_to_crush=200,
    max_items_after_crush=50,
)
crusher = SmartCrusher(config)

# New relevance scoring
from cutctx import create_scorer

scorer = create_scorer("hybrid")  # or "bm25" for zero deps
```

### Using the Proxy

New in 0.2.0 - run Cutctx as a proxy server:

```bash
# Start the proxy
cutctx proxy --port 8787

# Use with Claude Code
ANTHROPIC_BASE_URL=http://localhost:8787 claude
```

[Unreleased]: https://github.com/cutctx/cutctx/compare/v0.29.0...HEAD
[0.29.0]: https://github.com/cutctx/cutctx/compare/v0.28.0...v0.29.0
[0.28.0]: https://github.com/cutctx/cutctx/compare/v0.26.1...v0.28.0
[0.26.1]: https://github.com/cutctx/cutctx/compare/v0.26.0...v0.26.1
[0.2.0]: https://github.com/cutctx/cutctx/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/cutctx/cutctx/releases/tag/v0.1.0
