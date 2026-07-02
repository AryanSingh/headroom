# Changelog

All notable changes to Cutctx will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.30.0](https://github.com/AryanSingh/headroom/compare/v0.29.0...v0.30.0) (2026-07-02)


### Features

* add differential network capture harness ([#761](https://github.com/AryanSingh/headroom/issues/761)) ([11ab5f8](https://github.com/AryanSingh/headroom/commit/11ab5f83a1ccd617a2608349a42feff7f7e72b98))
* add get_crl() to LicenseDB + full product audit report (7,767 tests, 8.5/10 score) ([ca05aed](https://github.com/AryanSingh/headroom/commit/ca05aed4f18c7a16e6fc1eec78c9a40b2d7eafe5))
* Add interactive controls to Orchestrator Insights page ([ce8b9bf](https://github.com/AryanSingh/headroom/commit/ce8b9bfdbb3b2c4cf797c2ca9831354cee7f6d2d))
* add light mode for dashboard ([#834](https://github.com/AryanSingh/headroom/issues/834)) ([c425893](https://github.com/AryanSingh/headroom/commit/c425893d123e67c62ee20ff64ae350eb4ea56477))
* Add light mode, fix UI layout bugs, handle memory 404 gracefully ([38b69e1](https://github.com/AryanSingh/headroom/commit/38b69e1895bff582c349062d16ae6124568b3c9a))
* add OAuth2 client-credentials upstream-auth proxy extension ([#778](https://github.com/AryanSingh/headroom/issues/778)) ([#784](https://github.com/AryanSingh/headroom/issues/784)) ([eb2e50f](https://github.com/AryanSingh/headroom/commit/eb2e50feb26bacadf8812d6e608a458a990096b9))
* Add proxy intercept functionality and savings by client dashboard view ([e591679](https://github.com/AryanSingh/headroom/commit/e591679d371953f4348d2e356e9a17f5cdd8406e))
* Add savings by model to dashboard and fix Governance/Docs pages ([b7f31e2](https://github.com/AryanSingh/headroom/commit/b7f31e26ca3b356e47fe63e989a518a9f4b7244b))
* add Vertex AI proxy routing ([#793](https://github.com/AryanSingh/headroom/issues/793)) ([3c77e52](https://github.com/AryanSingh/headroom/commit/3c77e52ce431210e6045671cf5f7c66c79f90a32))
* **audit-deep-2026-06-21:** persistent webhook subscriptions + DLQ ([811931e](https://github.com/AryanSingh/headroom/commit/811931e7c62421b3f667fcba16f2743366f0df75))
* **audit-deep-2026-06-21:** React dashboard real APIs + drawer Esc + firewall opt-in ([a3d2e7b](https://github.com/AryanSingh/headroom/commit/a3d2e7bc791133207a473825eb1957da9c2bc163))
* **audit-deep-2026-06-21:** savings --verify-integrity CLI flag ([ae10097](https://github.com/AryanSingh/headroom/commit/ae1009765f9a3924061432cee40af5ec8cd9d577))
* **audit-deep-2026-06-21:** streaming per-source fields + audit enum expansion ([34c936d](https://github.com/AryanSingh/headroom/commit/34c936d850edcfe1e567cfc9229442501ec35012))
* capability extensions — viral launch, benchmarks, ML firewall, Stripe billing, Go SDK, air-gap ([74a3439](https://github.com/AryanSingh/headroom/commit/74a34390616562019ad4226b030e5ca871828f0b))
* chat.messages.transform compresses long conversation history ([102b35e](https://github.com/AryanSingh/headroom/commit/102b35e5e45932c659815df0e9a553cf602f7a69))
* Claude Code + Codex plugins — install/uninstall, hooks, MCP integration ([8c31b18](https://github.com/AryanSingh/headroom/commit/8c31b1845ec5c70012ed2e8d7d1cf615393d2b89))
* **cli:** add `cutctx profile` and `cutctx stack-graph` commands ([a030496](https://github.com/AryanSingh/headroom/commit/a03049689f2d0e5ad89f9caad3114b80a13c6c58))
* **cli:** comprehensive help text, validation, and exception handling improvements ([#640](https://github.com/AryanSingh/headroom/issues/640)) ([028efab](https://github.com/AryanSingh/headroom/commit/028efabb4e611d77118baefb8ffdd13b0edc4fc5))
* close all PRODUCT_CAPABILITY_MATRIX gaps — enterprise admin UI, expanded MCP, CLI commands, rebrand to CutCtx ([0cc598e](https://github.com/AryanSingh/headroom/commit/0cc598e6967fa0784bcb7019f573d889f5cb0a1e))
* close all remaining product gaps — CLI bench/report, pricing page, enhanced dashboard, Go+Python SDKs ([494e75e](https://github.com/AryanSingh/headroom/commit/494e75ee5fcab66e17672801035ba93a66cd8e1d))
* close enterprise gaps — SSO, RBAC enforcement, CCR hash fix, license tier, Helm chart ([2b17d9c](https://github.com/AryanSingh/headroom/commit/2b17d9cfb4e41dd287ef7d9e0d2f090c218fa991))
* close feedback loop and add reachability + benchmark wiring ([248b371](https://github.com/AryanSingh/headroom/commit/248b3714cc3696197ffcfb62686a5cf8eebf2047))
* commercialization plan + entitlement system + documentation ([3f3b7ab](https://github.com/AryanSingh/headroom/commit/3f3b7ab09932f20a0879a5a9cb66f438ef432233))
* CompactTable, LLMLingua-2, query-aware compression + Langfuse/LlamaIndex/SelectiveFilter plan ([0bc68fc](https://github.com/AryanSingh/headroom/commit/0bc68fcd8d242885f7d6be63acabee3a2b47904a))
* complete all five savings sources — semantic, self-hosted prefix, model routing in hot path + durable history + buyer report ([dc7905d](https://github.com/AryanSingh/headroom/commit/dc7905d18b57d8a2a5d683580faf50afab5fcd66))
* complete dashboard UI/UX overhaul with dark/light mode ([727cf79](https://github.com/AryanSingh/headroom/commit/727cf79d62ee3f9c2f09261d61af0fb70e479fd4))
* complete remaining AGENT_TASKS (6-14) ([0114853](https://github.com/AryanSingh/headroom/commit/011485369368f84d1fa60ec9013f4d27b1c5066b))
* compression safety rails — error-output protection, pipeline circuit breaker, library inflation guard ([#851](https://github.com/AryanSingh/headroom/issues/851)) ([c0cadcc](https://github.com/AryanSingh/headroom/commit/c0cadccff98e572f126185f371e4de9e241b12e0))
* **copilot:** GitHub Copilot subscription mode through Headroom ([f4dff9b](https://github.com/AryanSingh/headroom/commit/f4dff9b4885b5c62d79396bbb0847ae3e39a9bd9))
* **core:** multimodal image+audio compression with CCR + live_zone integration ([9ce38bb](https://github.com/AryanSingh/headroom/commit/9ce38bb477ca29b8c3373362f36c203dc99a5676))
* CutCtx Claude.ai skill plugin — uploadable ZIP for web UI ([d23c252](https://github.com/AryanSingh/headroom/commit/d23c252bd8975b2dea2bfcd428f52fd097a893ab))
* **dashboard:** add react web dashboard and air-gap documentation ([e68a6be](https://github.com/AryanSingh/headroom/commit/e68a6be6af97fd7473a52c8a5344b4eaad739c66))
* **dashboard:** per-model savings breakdown and expected-vs-actual cost on historical charts ([#807](https://github.com/AryanSingh/headroom/issues/807)) ([34dafe6](https://github.com/AryanSingh/headroom/commit/34dafe69d907c9a2971abc0d801ff9bfa498b3a8))
* **dashboard:** release-ready polish — feature toggles, anti-RE, OSS scrub ([d35423c](https://github.com/AryanSingh/headroom/commit/d35423cd27af64ee4c2b54c90416d8ef843fb6c1))
* detect re-served tool results as over-compression waste signal ([#854](https://github.com/AryanSingh/headroom/issues/854)) ([5f1d88a](https://github.com/AryanSingh/headroom/commit/5f1d88ad2701ed186df93d8e2a3980f0329d9dbb))
* Dynamic capability toggling from dashboard ([a38800b](https://github.com/AryanSingh/headroom/commit/a38800b2f76b7dc64f2bf7efb3f8218a4b6f5881))
* episodic memory integration — cross-session memory with CCR compression ([2bc6052](https://github.com/AryanSingh/headroom/commit/2bc60525701fb64a83c603b6dda5509b2cf6cc84))
* **evals:** add zero-cost tool schema compaction integrity eval ([#817](https://github.com/AryanSingh/headroom/issues/817)) ([53a08c6](https://github.com/AryanSingh/headroom/commit/53a08c63bf56a76d4fb7b649e37c8e62b0b4cebf))
* finalize PitchToShip commercialization updates ([e9f9d6a](https://github.com/AryanSingh/headroom/commit/e9f9d6ac746c4f725d432ed4f6b6f55b3254c9a8))
* gated Markdown-KV compaction formatter (serialization-aware output) ([#859](https://github.com/AryanSingh/headroom/issues/859)) ([06b2625](https://github.com/AryanSingh/headroom/commit/06b2625b17b0b032f688d321c6aa30ae3f2b7d96))
* Implement priority token savings features ([c0604d8](https://github.com/AryanSingh/headroom/commit/c0604d81863a86c7a03840c3905894864735cb37))
* implement USearch vector backend + Stack Graphs cross-file code navigation ([2f0a525](https://github.com/AryanSingh/headroom/commit/2f0a525d403de663ee159d23a3b9d54e52262202))
* **infra:** final production readiness polish (rebranding, pinning, prestop, cronjob, alerts) ([69af0ff](https://github.com/AryanSingh/headroom/commit/69af0ff21ad95e118e8dd6d178717d802bde316c))
* intelligence layer — task-aware compression, semantic dedup, context budgeting, cross-session profiles, shared context, cost forecasting ([0ac2826](https://github.com/AryanSingh/headroom/commit/0ac282647142bea7787b10e1e95b188eabb8b0c9))
* JSON schema compression — 40% token savings on tool definitions ([3fb737f](https://github.com/AryanSingh/headroom/commit/3fb737fd566b7331a7ab459a447d93c6f62e14dd))
* **kompress:** warn on unrecognized HEADROOM_KOMPRESS_BACKEND + document backend selection ([#204](https://github.com/AryanSingh/headroom/issues/204)) ([6367d0b](https://github.com/AryanSingh/headroom/commit/6367d0b7228f53b29bbd20f55c1729476ba5ea68))
* LLM Firewall, Structured Output, Multi-Model Ensemble, Budget Cut-offs ([dff2cf8](https://github.com/AryanSingh/headroom/commit/dff2cf8ae69d81bfe3769040a7a07fea849aedcf))
* **memory:** add opt-in Apple-GPU (MPS) embedding runtime ([#766](https://github.com/AryanSingh/headroom/issues/766)) ([c71592d](https://github.com/AryanSingh/headroom/commit/c71592d4214adf1022e4c608518ae0c3ac4aa5e9))
* **memory:** team memory service Phase 3 B1 wiring ([bb21db8](https://github.com/AryanSingh/headroom/commit/bb21db8ea8832a9e7695c0a3df329b40bd16fb79))
* net-cost cache mutation formula on CompressionPolicy ([#856](https://github.com/AryanSingh/headroom/issues/856) P1) ([#857](https://github.com/AryanSingh/headroom/issues/857)) ([d5f5802](https://github.com/AryanSingh/headroom/commit/d5f58026e2a882bc508acfbddfc9d472100d6e16))
* **p6:** EE publish CI, learn share prompt, headroom branding ([9859087](https://github.com/AryanSingh/headroom/commit/9859087b7d49981e45f9c5a3bc2996cb17551563))
* **perf:** add --format {text,json,csv} to `headroom perf` ([#648](https://github.com/AryanSingh/headroom/issues/648)) ([9fe4886](https://github.com/AryanSingh/headroom/commit/9fe4886cf6b612452f7271d3204872f804074c1f))
* Phase 3 B2 memory provenance and value scoring, plus proxy budget enforcement ([6fa4888](https://github.com/AryanSingh/headroom/commit/6fa48882a528742b4f64d4a025b8a3251905b234))
* Phase 3 B3-B6 memory impact, curation, portability, dashboard ([5a06f93](https://github.com/AryanSingh/headroom/commit/5a06f93029c1b20a6185d3dbef0492f003981d30))
* pipeline wiring, openai split, integration tests, test fixes ([bcd67bb](https://github.com/AryanSingh/headroom/commit/bcd67bba492e58ccf9530fb38b770ce5c34441cb))
* PitchToShip integration — license validation, trial JWT, seat heartbeat ([55f5352](https://github.com/AryanSingh/headroom/commit/55f5352a5daba48ec297e1b8256f787f2278a2cb))
* **plugins:** Hermes agent headroom_retrieve plugin ([#824](https://github.com/AryanSingh/headroom/issues/824)) ([058bced](https://github.com/AryanSingh/headroom/commit/058bcedab838f3b34ac8e38853e1924329efd820))
* **privacy:** add GDPR/CCPA DSR endpoints /v1/me/{export,delete} (Blocker-2) ([0ea6dc9](https://github.com/AryanSingh/headroom/commit/0ea6dc9252eea05f6571eb169086252587e15314))
* probe-based retention scoring of recorded compression events ([#862](https://github.com/AryanSingh/headroom/issues/862)) ([c2106cb](https://github.com/AryanSingh/headroom/commit/c2106cbdabb905e1980c6694000c220a5042171c))
* **prod:** config-driven cost-based model router (Blocker-5 part 2) ([61b5196](https://github.com/AryanSingh/headroom/commit/61b5196a9be51ce7be8727fd048de45bf465c8a2))
* **prod:** production-grade webhook dispatcher with retry + signing + admin API (High-15) ([40ac6dc](https://github.com/AryanSingh/headroom/commit/40ac6dc0d78b3b5189a88a414356a7b223717c09))
* **proxy:** add --exclude-tools flag + HEADROOM_EXCLUDE_TOOLS env var ([1058043](https://github.com/AryanSingh/headroom/commit/10580439bb4227a3f6f375439b0baae60db2f288))
* **proxy:** add --exclude-tools flag + HEADROOM_EXCLUDE_TOOLS env var ([93cf8af](https://github.com/AryanSingh/headroom/commit/93cf8af0e0c6b6b7fee0bcfe5b57a514c294a898))
* **proxy:** add CLI opt-outs for CCR injection (compression-only mode) ([#823](https://github.com/AryanSingh/headroom/issues/823)) ([693d9d2](https://github.com/AryanSingh/headroom/commit/693d9d20e2b2d9bfce3a0c48314850ee77ff8af3))
* **proxy:** attribute savings history rollups per provider ([#791](https://github.com/AryanSingh/headroom/issues/791)) ([0b8b8d9](https://github.com/AryanSingh/headroom/commit/0b8b8d92de3bd5e0301eadedacfb4b1d20a8de7f))
* **proxy:** log compressed messages alongside original request ([#261](https://github.com/AryanSingh/headroom/issues/261)) ([2269e40](https://github.com/AryanSingh/headroom/commit/2269e40bde7e1b9fb0620bd2cec9e33a92834080))
* **proxy:** per-project savings breakdown on the dashboard (claude, codex, aider, copilot, cursor) ([#803](https://github.com/AryanSingh/headroom/issues/803)) ([914a60a](https://github.com/AryanSingh/headroom/commit/914a60a2b07caad8488c1e19a5465726b95f83d3))
* **proxy:** show resolved upstream API targets in startup banner ([#586](https://github.com/AryanSingh/headroom/issues/586)) ([8dbe7ad](https://github.com/AryanSingh/headroom/commit/8dbe7ad41b3a1d33c01874be5c1cbc68a5e68111)), closes [#583](https://github.com/AryanSingh/headroom/issues/583)
* **rebrand:** in-tree rebrand shell + Rust Ed25519 license verifier ([17cdc93](https://github.com/AryanSingh/headroom/commit/17cdc93bb4ea9127c7f18f35245151afbfd9c5a5))
* **release:** implement best-in-class release plan — capabilities, modality matrix, release gate ([20a44ed](https://github.com/AryanSingh/headroom/commit/20a44edc514ac8cadd69f73bc65ddb5c5b11fc5c))
* **relevance:** weight BM25 score_batch by corpus IDF ([#646](https://github.com/AryanSingh/headroom/issues/646)) ([88177bd](https://github.com/AryanSingh/headroom/commit/88177bd7a680490ac85d244c5fff90f21a3be27c))
* savings orchestration — unified ledger, provider parsers, policy engine, CLI breakdowns ([0ecf5ef](https://github.com/AryanSingh/headroom/commit/0ecf5ef3db2864994b2afcbca0d55ede487d7369))
* **security:** add /audit/verify endpoint with lightweight integrity check ([01ce9ef](https://github.com/AryanSingh/headroom/commit/01ce9efab5667c086a1734149d8683247b896a32))
* **security:** SQLite-backed RBAC persistence (Medium-29) ([ddef51a](https://github.com/AryanSingh/headroom/commit/ddef51a1e4956ab7356d6884785a631b6a86e10d))
* **security:** TOTP MFA for admin (High-12) ([58e5495](https://github.com/AryanSingh/headroom/commit/58e5495d2ea494bc1888968e7b596df513f32ca0))
* **security:** wire anti-debug at module init, JS obfuscation, Cython build ([d4fe0fd](https://github.com/AryanSingh/headroom/commit/d4fe0fda3f1ed70ccd8dcdbe5873d6d3d3876b76))
* session.compacting appends cutctx context to the compactor prompt ([f47b24c](https://github.com/AryanSingh/headroom/commit/f47b24c22ccd7a2ca98f5e14888f9188495007d2))
* SP-0 through SP-8 — complete software protection implementation ([9be1ae2](https://github.com/AryanSingh/headroom/commit/9be1ae270e2218d920d1dd285c8d5fa3b89d1c0f))
* Sprint 2 — retention controls, RBAC, license status, exportable reports ([2f1301a](https://github.com/AryanSingh/headroom/commit/2f1301aaaaadbf2ddc3f537a7c2a631175f7ea00))
* Sprint 4 — org-scoped analytics, entitlement boundary tests, enterprise smoke tests, admin dashboard UI ([535dabe](https://github.com/AryanSingh/headroom/commit/535dabe973b1f9dd1b986335b1de7d6194ef3459))
* stack-graph + usearch tests, plan tracker, changelog ([6c9d71d](https://github.com/AryanSingh/headroom/commit/6c9d71d7e70ad9de2e218f902c416c7957470869))
* **stack-graphs:** Python facade, proxy wiring, CLI flag, watcher integration ([2994769](https://github.com/AryanSingh/headroom/commit/2994769b25375d2976e09dd76c0295fd757f0d7f))
* support CLAUDE_CODE_USE_FOUNDRY and custom upstream gateways ([#726](https://github.com/AryanSingh/headroom/issues/726)) ([d90cdce](https://github.com/AryanSingh/headroom/commit/d90cdce3b69bbf27e0f5feea461766a9d797cf7e))
* support Python 3.14+ via pyo3 abi3 stable ABI ([#516](https://github.com/AryanSingh/headroom/issues/516)) ([19eac8e](https://github.com/AryanSingh/headroom/commit/19eac8e00dc9e3911f3afe8e8e5dcc9e00346baa))
* surface Langfuse + add LlamaIndex integration + selective context filter ([2d332f5](https://github.com/AryanSingh/headroom/commit/2d332f50207c5b6361f5c0335e34ee0abddbf6e0))
* switch Kompress default to kompress-v2-base with weight-only int8 ONNX ([#799](https://github.com/AryanSingh/headroom/issues/799)) ([74392b2](https://github.com/AryanSingh/headroom/commit/74392b238e4f76fa061e673d1415fc7fa2830011))
* **telemetry:** implement Phase 4 A1-A4 data flywheel ([518a9d2](https://github.com/AryanSingh/headroom/commit/518a9d257bf19d69015aed803282321f19bc102c))
* tool.execute.after compress hook with CUTCTX_DISABLED escape hatch ([8b9ecfc](https://github.com/AryanSingh/headroom/commit/8b9ecfcfa26c686fdb54d26d8e6ff54d52dd19c6))
* **transforms:** attribute read_lifecycle + smart_crush tags ([#249](https://github.com/AryanSingh/headroom/issues/249)) ([8f37426](https://github.com/AryanSingh/headroom/commit/8f374263d3971c072b5c977375c873864fb05763))
* wire intelligence layer into proxy pipeline — pre/post compression hooks ([2c9c78d](https://github.com/AryanSingh/headroom/commit/2c9c78deb4d7ad904deb7615c6463d155b3d445f))
* wire savings policy into handlers, dashboard by-source cards, buyer-grade report ([b47ccd8](https://github.com/AryanSingh/headroom/commit/b47ccd8e5e7463d1f41536657560c047858ce6a8))


### Bug Fixes

* add admin auth + RBAC to /admin dashboard route ([9e5b22b](https://github.com/AryanSingh/headroom/commit/9e5b22bdc62c37f22a90c59c0a97b53d57ada377))
* add entitlement_tier to CCR test fixtures blocked by TEAM+ gate ([a5bcfd4](https://github.com/AryanSingh/headroom/commit/a5bcfd4abbe4c8a7c548237df4bb7a7de0ff289f))
* additional headroom_ee + headroom module fixes for relicense split ([cace1de](https://github.com/AryanSingh/headroom/commit/cace1de4013eeb96236229d894c29a2ae65f8da5))
* **anthropic:** CCR exception must re-raise, not silently swallow ([#838](https://github.com/AryanSingh/headroom/issues/838)) ([8db5efc](https://github.com/AryanSingh/headroom/commit/8db5efc6f9f6de59e9d55cbcd63b75c37a81a26e))
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
* **ccr:** key Rust search/diff/log markers with explicit_hash ([#852](https://github.com/AryanSingh/headroom/issues/852)) ([bfcb07d](https://github.com/AryanSingh/headroom/commit/bfcb07d78ea7eba539a65b11e100ec23b336d8d1))
* **ccr:** make retrieval TTL configurable ([#715](https://github.com/AryanSingh/headroom/issues/715)) ([2533f77](https://github.com/AryanSingh/headroom/commit/2533f7703ee261dc35767b11e46b8eab6e0c454d))
* **ccr:** scope proactive expansion by workspace (cross-project leak) ([197601b](https://github.com/AryanSingh/headroom/commit/197601bc64ee72e786bf6b94cd90efcac4269bcf))
* **ccr:** scope proactive expansion by workspace (cross-project leak) ([1bc163f](https://github.com/AryanSingh/headroom/commit/1bc163f5bc1a8422f9ad659061e1fdd8cfeb077b))
* **ccr:** skip CCR when model calls headroom_retrieve alongside user tools ([#839](https://github.com/AryanSingh/headroom/issues/839)) ([30078f8](https://github.com/AryanSingh/headroom/commit/30078f8465fb6bb78a5a9c394b75e60cd3c4eeec))
* **ccr:** use shared compression store ([#875](https://github.com/AryanSingh/headroom/issues/875)) ([249af6c](https://github.com/AryanSingh/headroom/commit/249af6cc7b379678e60da3e98e552368632fd4f4))
* **ci:** correct comments, timeouts, and pip reliability in native e2e workflows ([#878](https://github.com/AryanSingh/headroom/issues/878)) ([b716c8c](https://github.com/AryanSingh/headroom/commit/b716c8c2ee7ccc68dd1b9294760db1af866843f2))
* **ci:** pin cosign-installer to v3 (v4 does not exist) ([#774](https://github.com/AryanSingh/headroom/issues/774)) ([199d693](https://github.com/AryanSingh/headroom/commit/199d693f98ecd72d80181c8fee8422b6b64651a2))
* **ci:** restore green lint gate on main ([fe50f9d](https://github.com/AryanSingh/headroom/commit/fe50f9daed35151134f79b767733d4be8093e325))
* Claude Code plugin — use claude mcp add for proper CLI registration ([6238a08](https://github.com/AryanSingh/headroom/commit/6238a086ce5f6a089da6c5adfc50ebee94ec8087))
* **cli:** G1 remediation — non-string clobber, per-model systemMessage, openhands gate ([ea1976e](https://github.com/AryanSingh/headroom/commit/ea1976e37a5147ecf37dbf5ffe4af5c2f2d1be6a))
* clippy cleanup, entitlement tier fixes, audit doc update ([b92e027](https://github.com/AryanSingh/headroom/commit/b92e0273354ca0cb61ff0557c5fb648b94ed087d))
* **cli:** wrap CLI breadth — cline, continue, goose, openhands ([8625f80](https://github.com/AryanSingh/headroom/commit/8625f8075ed75d2a002f6ba357697de0fa1ec434))
* **cli:** wrap subcommands for cline, continue, goose, openhands ([c375fa1](https://github.com/AryanSingh/headroom/commit/c375fa156dd0434256805f274c07be4f45db9814))
* **codex:** auto-enable fail-open on compression timeout in headroom wrap codex ([#531](https://github.com/AryanSingh/headroom/issues/531)) ([5f5f261](https://github.com/AryanSingh/headroom/commit/5f5f261a035d12d069eb212eb75c472e2c9edeff))
* **codex:** fail open for proxy compression timeout ([e8ecd08](https://github.com/AryanSingh/headroom/commit/e8ecd0882990e464f9b4a7d2041ce86863931e83))
* **codex:** keep init model_provider at config root ([#260](https://github.com/AryanSingh/headroom/issues/260)) ([304dcc7](https://github.com/AryanSingh/headroom/commit/304dcc78047bc744fc2f7656b484ec54dc271354))
* **codex:** keep init model_provider at config root ([#260](https://github.com/AryanSingh/headroom/issues/260)) ([849b46d](https://github.com/AryanSingh/headroom/commit/849b46de5934a88369af2fd7f7d52e9af0536a7e))
* **codex:** respect CODEX_HOME for wrap config ([#731](https://github.com/AryanSingh/headroom/issues/731)) ([96abf38](https://github.com/AryanSingh/headroom/commit/96abf38b0972adf5e5c66f9a49aa9d9f951b1aa0))
* commercial release audit gaps — rebranding, pricing, K8s probes, version bump, legal docs ([06ca87a](https://github.com/AryanSingh/headroom/commit/06ca87ac1e120cd9e7d76c0fbd0193434a82487a))
* commercialization sync — JSON always for savings --by-source, USD attribution fix in buyer report, 5-source model in docs ([454d85a](https://github.com/AryanSingh/headroom/commit/454d85aabb7746f9128a67edb40f086704511067))
* **content_router:** guard against empty compression output causing Anthropic 400 ([#771](https://github.com/AryanSingh/headroom/issues/771)) ([2f9ff07](https://github.com/AryanSingh/headroom/commit/2f9ff07e6caef0fe32d00ece6266a476eecff5a3))
* **copilot:** deterministic subscription token handoff to the proxy ([72da461](https://github.com/AryanSingh/headroom/commit/72da46121726074515e0c1eb9745498457a1a8d5))
* **copilot:** restore generic endpoint for non-subscription OAuth ([#610](https://github.com/AryanSingh/headroom/issues/610)) ([#612](https://github.com/AryanSingh/headroom/issues/612)) ([18925b8](https://github.com/AryanSingh/headroom/commit/18925b8c6e343c9d593891cd29ac27fee1cb9836))
* **copilot:** support subscription auth through Headroom ([ff4a0c6](https://github.com/AryanSingh/headroom/commit/ff4a0c6bc64e5e68ab76c38047a36a3c7a6aaacf))
* **copilot:** use responses API for subscription reasoning models ([#647](https://github.com/AryanSingh/headroom/issues/647)) ([84ac332](https://github.com/AryanSingh/headroom/commit/84ac332d14dafacedc2f0b46f5ac6b3977b098d0))
* correct preserved-entry index mapping in Gemini content round-trip ([#836](https://github.com/AryanSingh/headroom/issues/836)) ([0ffe2b6](https://github.com/AryanSingh/headroom/commit/0ffe2b6ea49e5c8d3bff5fe2c90873c71a95c457))
* correct tiktoken encoding for unknown gpt-4 model snapshots ([#552](https://github.com/AryanSingh/headroom/issues/552)) ([0e551de](https://github.com/AryanSingh/headroom/commit/0e551de9d81021bb7f0dde1857a2341408606969))
* cutctx plugin — rename headroom→cutctx CLI refs, add auto-start proxy, fix health endpoint ([6eeb468](https://github.com/AryanSingh/headroom/commit/6eeb4688aebbf952d71c8a30dbd49e79edcd9c8d))
* **cutctx-opencode:** realign types to real cutctx-ai API (reviewer findings) ([dece8c5](https://github.com/AryanSingh/headroom/commit/dece8c584502d529f5be21302a9502bf1268ceb9))
* **cutctx:** in-flight production-readiness fixes for v0.30.0 ([864c51e](https://github.com/AryanSingh/headroom/commit/864c51ef9f2c136f50bba91ea5b3d7850cd9dab7))
* **dashboard:** add missing JS bundle index-BAVvlhZA.js to tracked assets ([9bb8fc5](https://github.com/AryanSingh/headroom/commit/9bb8fc5b29b6bf01c2546ed414ca94f91bc22e55))
* **dashboard:** dynamic version + clean savings_by_source x-if guard ([87f03ca](https://github.com/AryanSingh/headroom/commit/87f03ca3b14ba581617d8b57881285af3c49dfb0))
* **dashboard:** rebind hero tile to file-backed savings, add cross-process lock ([a8b62a7](https://github.com/AryanSingh/headroom/commit/a8b62a77d9068372c55f70d74721f2a73774caf3))
* **dashboard:** stable 'Proxy $ Saved' hero tile under --workers &gt; 1 ([#481](https://github.com/AryanSingh/headroom/issues/481)) ([fd73b88](https://github.com/AryanSingh/headroom/commit/fd73b88368b22beeb586b8e1aa37fcd2afb12532))
* decode/encode owned config, state and template assets as UTF-8 ([2f1538a](https://github.com/AryanSingh/headroom/commit/2f1538a641dd0e60a7be3de85646a70c4bf7e287))
* decode/encode owned config, state and template assets as UTF-8 (fixes [#533](https://github.com/AryanSingh/headroom/issues/533)) ([92075b9](https://github.com/AryanSingh/headroom/commit/92075b95af799951c90a305a08ec4e958473967a))
* deprecated API usages + compress.py lazy import scoping bug ([b6e75c8](https://github.com/AryanSingh/headroom/commit/b6e75c87b07d61aa435c4c8e4524bd1905c7d1e3))
* **deps:** move gunicorn to [proxy-prod] extra, add Windows guard ([#537](https://github.com/AryanSingh/headroom/issues/537)) ([fa558c5](https://github.com/AryanSingh/headroom/commit/fa558c5647a91562f4a8fba0271d27b02c8ae01f))
* **docker:** upgrade base images to Python 3.13 / debian13 ([e6bf7a0](https://github.com/AryanSingh/headroom/commit/e6bf7a03fef8a9f2e4802d63afdafb40627c7ad9))
* **docker:** upgrade base images to Python 3.13 / debian13, drop digest pinning ([08a2197](https://github.com/AryanSingh/headroom/commit/08a219708c97dcdc678483a0e6891306624a1fad))
* **docs:** bump next.js to 16.2.6 for GHSA-h64f-5h5j-jqjh (CVE-2026-44577) ([a6a09e6](https://github.com/AryanSingh/headroom/commit/a6a09e6cfbe6962a70a6fb2e4bebeee80756e304))
* **docs:** mkdocs configuration to build with correct folder ([#543](https://github.com/AryanSingh/headroom/issues/543)) ([5557944](https://github.com/AryanSingh/headroom/commit/55579445f84c363219f45dc5358599a04d4263ed))
* **docs:** update brace-expansion to 5.0.6 to remediate GHSA-jxxr-4gwj-5jf2 (CVE-2026-45149) ([6eb6fb5](https://github.com/AryanSingh/headroom/commit/6eb6fb5941adfbd056daa1689c3fa0c3755fd298))
* **docs:** update bun.lock to next 16.2.6 for GHSA-h64f-5h5j-jqjh (CVE-2026-44577) ([91e0937](https://github.com/AryanSingh/headroom/commit/91e0937243c801fa5f1021b4c47debef2444650c))
* don't inject empty tools:[] when client omitted the tools field ([#772](https://github.com/AryanSingh/headroom/issues/772)) ([574bbae](https://github.com/AryanSingh/headroom/commit/574bbae2cbe2f20b3f0e12b421c25ac256712f0a))
* E2E test fixes — subscription NameError, admin dashboard path, firewall CLI wiring, learn_share branding ([0dab42d](https://github.com/AryanSingh/headroom/commit/0dab42d7e858cc5e492f3dbd684f90f120d0a5cc))
* hard license enforcement + secure-by-default admin auth ([488590a](https://github.com/AryanSingh/headroom/commit/488590aecccef197789c89803e0e8613d455e1b2))
* harden Copilot API auth token handling ([#557](https://github.com/AryanSingh/headroom/issues/557)) ([6b0c09f](https://github.com/AryanSingh/headroom/commit/6b0c09ffd5f2ce18c4d2cfa6233feaf37d487ead))
* headroom_ee module fixes — imports, APIs, compatibility ([873a717](https://github.com/AryanSingh/headroom/commit/873a7175e3184c988618252791c03ba565ab197f))
* **health:** readyz verifies upstream connectivity, not just process liveness ([#744](https://github.com/AryanSingh/headroom/issues/744)) ([5dfb446](https://github.com/AryanSingh/headroom/commit/5dfb446da1fb65002e0dea18a90210a2a026f0b3))
* ignore brackets inside JSON strings when splitting mixed content ([#553](https://github.com/AryanSingh/headroom/issues/553)) ([bdcfc32](https://github.com/AryanSingh/headroom/commit/bdcfc322da0c4cde69931d641cfa18c76ddb138b))
* Improve text legibility, clamp savings percentages, and optimize trend graph scaling ([1fc3fc3](https://github.com/AryanSingh/headroom/commit/1fc3fc3a10c5083352a7e4d4346b2ea64932fa08))
* **init:** guard persistent task startup ([#616](https://github.com/AryanSingh/headroom/issues/616)) ([9252d85](https://github.com/AryanSingh/headroom/commit/9252d852c5a4c716eb5438b8f438d50e59a55fef))
* **init:** normalize Windows hook paths to forward slashes ([#788](https://github.com/AryanSingh/headroom/issues/788)) ([6ea6e31](https://github.com/AryanSingh/headroom/commit/6ea6e31f09845b2ad5c8bae73bcf353f3b629188))
* **init:** suppress hook recovery output ([#760](https://github.com/AryanSingh/headroom/issues/760)) ([b439599](https://github.com/AryanSingh/headroom/commit/b4395993aecbb65b85a5b2479dfdb35ea243bf54))
* intelligence pipeline rewrite — 6 features fully integrated, 29 tests pass ([fa58f2a](https://github.com/AryanSingh/headroom/commit/fa58f2a8c425f4ee65d0fcf94be794012100d53b))
* **learn:** claude-cli streams output with idle timeout ([#373](https://github.com/AryanSingh/headroom/issues/373)) ([9bff575](https://github.com/AryanSingh/headroom/commit/9bff5752bbd769902f249cdfde42bc53539afd02))
* **learn:** decode Unix home dirs whose username contains '.', '-' or '_' ([211daae](https://github.com/AryanSingh/headroom/commit/211daae25687901d1f893714d877b25606d0ef69))
* **learn:** decode Unix home dirs whose username contains '.', '-' or '_' ([491a8b3](https://github.com/AryanSingh/headroom/commit/491a8b3a1b260f42f503b3553a04c578c18e1cc0))
* **learn:** finish gemini-flash-latest default model sweep ([982d01b](https://github.com/AryanSingh/headroom/commit/982d01b9c996fd5fe26154dc2f94d567192f6ff6))
* **learn:** finish gemini-flash-latest default model sweep ([#532](https://github.com/AryanSingh/headroom/issues/532)) ([d797366](https://github.com/AryanSingh/headroom/commit/d7973665f4e2f40f2b3acadd0ec584609fb33c6c))
* lint clean (memory/telemetry/D3), telemetry network egress opt-in (default off), commit D3 failover/residency ([241b436](https://github.com/AryanSingh/headroom/commit/241b4362cca0acc33db87395864f2acd59af931b))
* **lint:** ruff formatting and unused imports in resolver.py ([1d786ee](https://github.com/AryanSingh/headroom/commit/1d786eeec700566526405e7f5fc664f2e2b2307a))
* make headroom wrap readiness probe timeout configurable for slow ML imports ([#581](https://github.com/AryanSingh/headroom/issues/581)) ([163677b](https://github.com/AryanSingh/headroom/commit/163677b405d7ca8a54d6d7c798bf6ead90da7880))
* **mcp:** update test mocks and exports for mcp_server refactor ([bd9c022](https://github.com/AryanSingh/headroom/commit/bd9c022433691c17dc410231484e4f8b41779a5b))
* **memory:** expose memory IDs in auto-tail + memory_list tool + ID-usage guidance ([f844f64](https://github.com/AryanSingh/headroom/commit/f844f64840491d9a838be4b00a4ca6d9ff97adba))
* **memory:** expose memory IDs in auto-tail + memory_list tool + ID-usage guidance ([c62d45e](https://github.com/AryanSingh/headroom/commit/c62d45eea826c661aa8ebf1f2c8aba8408ea6109))
* **memory:** READ-ONLY framing + fail-closed unresolved-project fallback ([a178249](https://github.com/AryanSingh/headroom/commit/a178249fc0af4a1b6f212decb4f6d2793d57fae8))
* **memory:** READ-ONLY framing + fail-closed unresolved-project fallback ([482f80e](https://github.com/AryanSingh/headroom/commit/482f80e735f124ee6860f6854255c77170b862e7))
* **observability:** G3 remediation — bound cardinality + wire dead metrics ([2a717a9](https://github.com/AryanSingh/headroom/commit/2a717a993ee99f9401f5cdf78a23dcecd7cb1a51))
* **observability:** RTK metrics + Rust observability (Phase H blocker) ([b36ad9f](https://github.com/AryanSingh/headroom/commit/b36ad9fe1c6a488eb9ffbf0e8b38d989278cf8ef))
* **observability:** wire Phase G PR-G3 RTK + proxy metrics (H-blocker) ([5f264a5](https://github.com/AryanSingh/headroom/commit/5f264a53292e292c9c56b837c2750d1a415b1ea9))
* **ops:** align docker-compose.native.yml image to canonical owner (Medium-35) ([684a7e9](https://github.com/AryanSingh/headroom/commit/684a7e90d98f199446f46d9a0c5a702d680d5890))
* **parser:** detect waste signals in Anthropic tool_result content blocks ([#815](https://github.com/AryanSingh/headroom/issues/815)) ([929698a](https://github.com/AryanSingh/headroom/commit/929698af1030e5926f3766d7d6ac292d6e38437b))
* point Codex hooks to installed cutctx binary ([3e8d299](https://github.com/AryanSingh/headroom/commit/3e8d2994b7d35926c000eba953f8cae0e1b58b94))
* **policy:** enforce dynamic budgets and commit outstanding files ([834d79b](https://github.com/AryanSingh/headroom/commit/834d79bb1ca280386f49d1c9a6e6f648eb7f72c4))
* **policy:** implement proxy policy enforcement and stale-while-revalidate caching ([ef0d02e](https://github.com/AryanSingh/headroom/commit/ef0d02ec5659725d2eb461cbb716c4b03781992c))
* preserve Claude Code tool-search deferral through the proxy ([#746](https://github.com/AryanSingh/headroom/issues/746)) ([#753](https://github.com/AryanSingh/headroom/issues/753)) ([1c8c538](https://github.com/AryanSingh/headroom/commit/1c8c538780d5c9a43781f1fdd9eeda2657280446))
* **prod+security:** wire streaming PII redactor, from_stream per-source, audit events, k8s ([58c3226](https://github.com/AryanSingh/headroom/commit/58c3226e37ca602fe54228611cc0d87f4b2bab6a))
* **prod:** bind ModelRouter + WebhookDispatcher at server boot ([e57cf9a](https://github.com/AryanSingh/headroom/commit/e57cf9a0c626017d5458077eac2d8360a58730c3))
* production audit gaps — admin auth, CORS lockdown, body limit, K8s, versioning, docs ([0e44faf](https://github.com/AryanSingh/headroom/commit/0e44faff0c0d569a7a3802bfb91141d3f7fd3fe7))
* **proxy:** allow egress by default in connected mode ([b751cd0](https://github.com/AryanSingh/headroom/commit/b751cd025325117182094c855bd8f2567724284d))
* **proxy:** F4 — trust X-Forwarded-* only behind allow-listed gateway ([d10bd5f](https://github.com/AryanSingh/headroom/commit/d10bd5f59c5a36e14f6c5f0480b821532521b753))
* **proxy:** fail-open on corrupt golden bytes instead of RuntimeError ([#603](https://github.com/AryanSingh/headroom/issues/603)) ([2170a1b](https://github.com/AryanSingh/headroom/commit/2170a1b4a00e9c46e845993c9b0f6cb2ef0c0684))
* **proxy:** lazy-import server to avoid fastapi crash ([#442](https://github.com/AryanSingh/headroom/issues/442)) ([93c6937](https://github.com/AryanSingh/headroom/commit/93c69372e614f2b04873bed75602a88d2256a7fc))
* **proxy:** make CCR multi-worker warning conditional on backend ([#770](https://github.com/AryanSingh/headroom/issues/770)) ([d76a729](https://github.com/AryanSingh/headroom/commit/d76a7296df121365d74c415b8c702a3ad80abd30))
* **proxy:** make Kompress eager preload cache-only so a cold cache can't block startup ([#783](https://github.com/AryanSingh/headroom/issues/783)) ([841663d](https://github.com/AryanSingh/headroom/commit/841663da16971b1e0d8e204fdf18e4bafedaf9e0))
* **proxy:** MemoryDecision contract + 3 bypass bugs + drop 500-char query cap ([4e1b218](https://github.com/AryanSingh/headroom/commit/4e1b21854456431253952ec4d32b8464133cc667))
* **proxy:** MemoryDecision contract + 3 bypass bugs + drop 500-char query cap ([71d5a7b](https://github.com/AryanSingh/headroom/commit/71d5a7b5455f92bd07c1cfc95909738687672307))
* **proxy:** remove invalid savings tracker flock ([0d8de25](https://github.com/AryanSingh/headroom/commit/0d8de25bfc346da572fecabf86580415e3939341))
* **proxy:** restore Codex usage headers on WS and streaming SSE transports ([#577](https://github.com/AryanSingh/headroom/issues/577)) ([#794](https://github.com/AryanSingh/headroom/issues/794)) ([0ce68de](https://github.com/AryanSingh/headroom/commit/0ce68dedd770d5411d16abe30e5ea9dd0b7d8eee))
* **proxy:** route Claude Code model metadata to Anthropic ([#627](https://github.com/AryanSingh/headroom/issues/627)) ([30c1ac8](https://github.com/AryanSingh/headroom/commit/30c1ac8656bcc3d11755daef8d1d27cd8770ebc7))
* **proxy:** Strands MCP bundle + backend path fixes + Codex fail-closed protection ([20dc1f2](https://github.com/AryanSingh/headroom/commit/20dc1f28f3ccadbc2d1109d73b5bfe875eb81c47))
* **proxy:** thread tags into 13 outcome sites; synthesize /v1/models for ChatGPT auth ([6d62985](https://github.com/AryanSingh/headroom/commit/6d62985b73b4a9e50d13ee9fc3df4b62bcba1c14))
* **rebrand:** HeadroomProxy alias + streaming var name + 15 test imports ([7795ffb](https://github.com/AryanSingh/headroom/commit/7795ffb6d6f0d54d1a04dad0c943fd542b3fc2d5))
* **release:** content_router NameError, llmlingua tests, docs to v0.28.0 ([63896bb](https://github.com/AryanSingh/headroom/commit/63896bb2a3e16f0db8825e361e2c93005317352a))
* **release:** shipping-ready v0.26.0 — rebrand, Docker, Helm, legal, security config ([badc77c](https://github.com/AryanSingh/headroom/commit/badc77c96d5a0a325e38d083ee2a20a3cd1c246b))
* **release:** tag format vX.Y.Z (drop release-please component prefix) ([4a39ef5](https://github.com/AryanSingh/headroom/commit/4a39ef54ed6cdaa24d8f9fa49bbd3daf7100658e))
* **release:** tag format vX.Y.Z (drop release-please component prefix) ([0f3e3af](https://github.com/AryanSingh/headroom/commit/0f3e3af6b2a154c5ecaeda3f9770cec97e9a3ba0))
* **reliability+security:** per-identity rate limit + savings corruption recovery ([27320cd](https://github.com/AryanSingh/headroom/commit/27320cd8ae3ca7fb2bd4fda330ee478d0b9a2266))
* replace placeholder license key, lint new code, pin CI ruff ([84ac8f9](https://github.com/AryanSingh/headroom/commit/84ac8f951e8126793bed2c55db6667ac29ae47d1))
* resolve last 2 test failures — passthrough mixin import + WS timeout patch target ([8136435](https://github.com/AryanSingh/headroom/commit/81364355686f4baa0b6df2377c3b2c0d43065cd3))
* Resolve layout crash, add ErrorBoundary, and fix light theme mode ([77afd18](https://github.com/AryanSingh/headroom/commit/77afd18bbee21f04094275160f9f52c1a00c3c65))
* Resolve missing Savings panel and Orchestrator styles ([dfc5728](https://github.com/AryanSingh/headroom/commit/dfc57282ef811f60d76e6a5c18e43e4ac1a0cd3c))
* restore runtime app debug and admin surfaces ([f65514a](https://github.com/AryanSingh/headroom/commit/f65514aa8885be867de0aa145ea9660b1175c7ed))
* restore runtime surfaces and guardrail coverage ([765a77e](https://github.com/AryanSingh/headroom/commit/765a77e189576e588718b601bd11c03e6468b426))
* restore safe chatgpt responses request shape ([d852de6](https://github.com/AryanSingh/headroom/commit/d852de69ce44e9e2f86190e6edcc79a95a398173))
* **savings:** correct double-counting in funnel + add vLLM APC header aliases ([ef88bb6](https://github.com/AryanSingh/headroom/commit/ef88bb683b28c331ba0b152250e0e73656845618))
* **savings:** restore request history from JSONL on proxy restart ([a459f6c](https://github.com/AryanSingh/headroom/commit/a459f6c88d65f9afcff6f3342b72e396293cc1ba))
* schema compaction must not drop property names that match DROP_KEYS ([#785](https://github.com/AryanSingh/headroom/issues/785)) ([ae2122f](https://github.com/AryanSingh/headroom/commit/ae2122fda8ff0efc03d609d27270453fea3a8718))
* security hardening — auth on 12 unprotected routes, SSRF fix, codex runtime tests ([94075d5](https://github.com/AryanSingh/headroom/commit/94075d5f5d7aa627ad8a87afe1b4b7e16d9eeabb))
* security hardening — remove test mode bypass, decompression bomb protection, SQL defense-in-depth, expanded firewall tests ([4ffa2b3](https://github.com/AryanSingh/headroom/commit/4ffa2b3027e451e87975501bc3dc3d0d6ec0ee87))
* **security+code:** SSO requires PyJWT + /admin fallback + remove dead duplicate ([b5c221f](https://github.com/AryanSingh/headroom/commit/b5c221f2007190c698870c1b938aff6f8d4d7e00))
* **security:** block DNS-rebinding on /debug/* and /stats/reset via Host-header allowlist ([#605](https://github.com/AryanSingh/headroom/issues/605)) ([b4b5025](https://github.com/AryanSingh/headroom/commit/b4b50253f16d0a30f1d17a959753137e997efbac))
* **security:** block plaintext admin key log + require audit secret + auto-start retention ([fe32040](https://github.com/AryanSingh/headroom/commit/fe3204046d989bd5f7a83c1b22e63857ff25a31a))
* **security:** gate EE routes behind admin auth + RBAC (Blocker-1) ([2b49ee7](https://github.com/AryanSingh/headroom/commit/2b49ee7626b093d3220328f97d0b06b26e2d1bc3))
* **security:** GDPR DSR delete + export P0 bugs ([c556e5b](https://github.com/AryanSingh/headroom/commit/c556e5bb49e5f24d8504b5754ea5cb92af44a141))
* **security:** harden audit-actor source — SSO &gt; key fingerprint &gt; 'admin' ([54e6bb0](https://github.com/AryanSingh/headroom/commit/54e6bb03636d6b3db70763fd6cb07b6b9ce07e91))
* **security:** has_permission fail-closed for unknown SSO users ([7f6875c](https://github.com/AryanSingh/headroom/commit/7f6875c5153665b929ac0dcb15dd30b248d8f421))
* **security:** patch loopback guard, retry None raise, async subprocess, and cache race ([06d7cb9](https://github.com/AryanSingh/headroom/commit/06d7cb9e6c011711a478864a970f7c87ee853a97))
* **security:** patch loopback guard, retry None raise, blocking subprocess, and cache stats race ([78f3a4d](https://github.com/AryanSingh/headroom/commit/78f3a4dd3e8e26525822a3c830d576d702dfed8b))
* **security:** residency auth gate, Stripe tier validation, RBAC permission, test fixes ([7c2c6fe](https://github.com/AryanSingh/headroom/commit/7c2c6fec82df6af37cd6a444b929e50096b263c7))
* **security:** restore SSO class boundary + align docker-compose image ([fb73887](https://github.com/AryanSingh/headroom/commit/fb73887b4bb08a48244b2d8667ee83a0c9a74628))
* **security:** wire DSR cascade to real AuditLogger API (round-4 audit P0) ([f438a94](https://github.com/AryanSingh/headroom/commit/f438a9418ac8174350a94d520a0bcdcb7e7aeac8))
* ship-it audit improvements — 41 new tests, README rebrand, Helm version bump ([e4a1104](https://github.com/AryanSingh/headroom/commit/e4a110403879adbe7196ced5b7d2851cf170dd2d))
* sort anthropic handler imports ([8f6a9cf](https://github.com/AryanSingh/headroom/commit/8f6a9cfb26b480593a7e42e4ecd076fa74c4fc2a))
* **ssl:** upstream httpx client inherits SSL_CERT_FILE, REQUESTS_CA_BUNDLE, NODE_EXTRA_CA_CERTS ([#745](https://github.com/AryanSingh/headroom/issues/745)) ([e50fbb3](https://github.com/AryanSingh/headroom/commit/e50fbb3e0d61d561456d7b0ff9e0a8ee106a2f02))
* SSO timing-safe comparison + streaming decompression bomb protection ([cc3d6d3](https://github.com/AryanSingh/headroom/commit/cc3d6d3b22c88cacb8111c221efe1bc42d323904))
* **startup:** move HF/httpx log suppression before sentence_transformers init ([#622](https://github.com/AryanSingh/headroom/issues/622)) ([176d4c7](https://github.com/AryanSingh/headroom/commit/176d4c772a7ca8c9da58ca2403f890ba85e8bad8))
* **startup:** suppress proxy startup log noise ([#619](https://github.com/AryanSingh/headroom/issues/619)) ([4555901](https://github.com/AryanSingh/headroom/commit/45559011b16a2e084dda22c675c819a4789f961d))
* **stats:** remove legacy llmlingua and difftastic from stats payload ([eded7cf](https://github.com/AryanSingh/headroom/commit/eded7cfb70e62e3bb160ab8231991ce034359807))
* **subscription:** address G2 review findings — phantom delta, multi-worker race, silent fallbacks ([f68090c](https://github.com/AryanSingh/headroom/commit/f68090c5b4bd9670ee7fc9a0c71e57f05072c18c))
* **subscription:** wire tokens_saved_rtk data plane ([c7d1247](https://github.com/AryanSingh/headroom/commit/c7d1247a2bd06738c3b6c8e73e15902a7e428467))
* **subscription:** wire tokens_saved_rtk from RTK stats endpoint ([44c605f](https://github.com/AryanSingh/headroom/commit/44c605fbb0e3ae4e7a92d9693d0da8bc21115b81))
* suppress LiteLLM provider banner before import ([#874](https://github.com/AryanSingh/headroom/issues/874)) ([f9384ef](https://github.com/AryanSingh/headroom/commit/f9384ef4b780eaa1d8ca6dcc314ad430b87f524a))
* **tests:** close 6 round-4 P0 test regressions + 1 rebrand shell-leak ([fa310f1](https://github.com/AryanSingh/headroom/commit/fa310f17364c9f5d9f7fa1878bddb470e1675245))
* **tests:** drive RTK subprocess failure with real exec, not monkeypatched run ([9b6d637](https://github.com/AryanSingh/headroom/commit/9b6d6374f13a88842a1944688005649ad3680acd))
* **tests:** fix failing tests across sso, memory, auth and learn idempotency ([da8ca61](https://github.com/AryanSingh/headroom/commit/da8ca619ab7fca35a62b785518a599d8cf50ada8))
* **tests:** mock logger.warning directly instead of relying on caplog ([c38dac3](https://github.com/AryanSingh/headroom/commit/c38dac301e6bc702979ab11357a9c27a180ae060))
* **tests:** patch headroom.rtk.get_rtk_path, not the helpers alias ([317dffe](https://github.com/AryanSingh/headroom/commit/317dffe58fb0c6233210bbc9e42ebf16b9288391))
* **tests:** resolve remaining 7 test failures from proxy regressions ([ccb5a8d](https://github.com/AryanSingh/headroom/commit/ccb5a8df82cf7916e43843034b31365c3cac8b73))
* **tests:** tomllib fallback to tomli on python 3.10 ([74843d1](https://github.com/AryanSingh/headroom/commit/74843d1d626de70158a359661a540c615ef1a6c5))
* **transforms:** use thread-local tree-sitter parsers to prevent pyo3 Unsendable panic ([#604](https://github.com/AryanSingh/headroom/issues/604)) ([2ad300a](https://github.com/AryanSingh/headroom/commit/2ad300aff801838efe5649b00a0396523a401a2a))
* **types:** make headroom_ee shims transparent to mypy and ruff ([25fad54](https://github.com/AryanSingh/headroom/commit/25fad549dfe96246b2132f574031263013621547))
* update Claude Code + Codex plugins — consistent cutctx branding ([d61b134](https://github.com/AryanSingh/headroom/commit/d61b134d55a085c00fa40d493b54f79093846604))
* update dashboard doc link ([#544](https://github.com/AryanSingh/headroom/issues/544)) ([378d77e](https://github.com/AryanSingh/headroom/commit/378d77e79d0020ca7fba3de8df7aaf910056ad2a))
* Update Next.js to 16.2.4 in docs/bun.lock to address GHSA-gx5p-jg67-6x7h (CVE-2026-44580) ([0b9f11a](https://github.com/AryanSingh/headroom/commit/0b9f11a223bb6e6a6c1660ff1dfc1df6d67dfa84))
* Update Next.js to 16.2.6 in docs/package.json and package-lock.json to address GHSA-h64f-5h5j-jqjh (CVE-2026-44577) ([db5d15f](https://github.com/AryanSingh/headroom/commit/db5d15f99e71b69a369eb9c161e04dbffb9b5d4a))
* Upgrade litellm to 1.86.2 to remediate CVE-2026-42271 ([07581b9](https://github.com/AryanSingh/headroom/commit/07581b9e8075b833a6b543149008547260fe9dc0))
* use thread-local tree-sitter parsers to prevent unsendable panic ([38aefc1](https://github.com/AryanSingh/headroom/commit/38aefc1d34e65beec46f0b8cb0ff43028de38cbb))
* wire per-source savings signals end-to-end (hot path, status, dashboard, history) ([db7f7a4](https://github.com/AryanSingh/headroom/commit/db7f7a454bda501161e0af544c9175ff055bc01e))
* wire savings ledger into live traffic + durable history + runtime-backed integrations ([dca5b49](https://github.com/AryanSingh/headroom/commit/dca5b49da6e96f6754d81383967e06ff38248cc9))
* **wrap:** report unbindable proxy ports ([#602](https://github.com/AryanSingh/headroom/issues/602)) ([6dfcaa8](https://github.com/AryanSingh/headroom/commit/6dfcaa839f1175518e378963c79cc7bd3ceb7946))
* **wrap:** track shared proxy clients with markers ([#877](https://github.com/AryanSingh/headroom/issues/877)) ([05bd56b](https://github.com/AryanSingh/headroom/commit/05bd56bcb6b103fab5522da2b14295cf7bd8dbc1))


### Performance Improvements

* **core:** zero-copy anchor selection + SIMD line splitting ([b049b84](https://github.com/AryanSingh/headroom/commit/b049b8470902f923cdbd079c7a56d55a7d6de5b6))
* **core:** zero-copy SmartCrusher with Vec&lt;&Value&gt; borrows ([76df50d](https://github.com/AryanSingh/headroom/commit/76df50d69140fa479f6cca6877e43ea5f0800aa1))


### Code Refactoring

* **cli:** factor shared wrap-subcommand scaffolding ([8eeb926](https://github.com/AryanSingh/headroom/commit/8eeb9261680dd071654a87204521ccd3703ef77d))
* **cli:** factor shared wrap-subcommand scaffolding ([c74ad11](https://github.com/AryanSingh/headroom/commit/c74ad113a4ced9968e45cad1077e6a020dc6a401))
* extract admin routes + add rate limiting middleware + CCR store bridge ([26a46df](https://github.com/AryanSingh/headroom/commit/26a46df1229046c30fed0504c591e897e10e848e))
* extract litellm model resolution to shared utility ([ec7d006](https://github.com/AryanSingh/headroom/commit/ec7d0065cc5055e504e79cf24f3951e404fe4cb9))
* extract litellm model resolution to shared utility ([896a093](https://github.com/AryanSingh/headroom/commit/896a0933998c6dda4fcae44cc194ab2770e6f9d6))
* **proxy:** MemoryRanker + ImageCompressionDecision + branch-aware version-sync ([c79aa22](https://github.com/AryanSingh/headroom/commit/c79aa22be798a40e19c24cfc3e33427cdd84dc29))
* **proxy:** MemoryRanker + ImageCompressionDecision + branch-aware version-sync ([a7b197c](https://github.com/AryanSingh/headroom/commit/a7b197c6eca08e0080cb04bc19859026233c5603))

## [Unreleased]

### Strategy

- Public-facing copy now starts the context-control-plane repositioning from `artifacts/product-strategy-moat-analysis.md`: `README.md`, `PRODUCT_GUIDE.md`, `llms.txt`, and docs landing pages now lead with govern / attribute / remember, while token savings remain proof instead of the opening headline.

### Fixed

- CCR marker parsing and formatting now flow through shared `cutctx/ccr/markers.py` helpers, reducing duplicate marker logic across dedup and tool injection while keeping focused CCR regression coverage green.

- Tightened the live runtime admin surface in `cutctx/proxy/server.py`: wildcard CORS no longer advertises credential support, `/stats/reset` now logs audit failures instead of swallowing them silently, and the legacy earlier app builder is no longer exported as a second public `create_app` symbol.
- Split team-memory RBAC in `cutctx/proxy/routes/memory.py` so safe memory reads resolve `memory.read` while sync/review mutations still require `memory.write`, and preserved compatibility with existing zero-argument RBAC dependency callables via dedicated regression coverage.
- Dashboard operator stats now bypass browser cache for live admin fetches, expose proxy-sync freshness for history panels, and preserve lifetime totals in headline cards when the current session is smaller or tied.
- Dashboard recent-request docs and labels now clarify that the table shows the routed model observed by Cutctx, not necessarily the originally requested alias.
- Release metadata truthfulness improved across the dashboard and packaging surfaces: the sidebar version label now follows the live proxy or repo package version, `SECURITY.md` reflects the currently supported release line, and the README/Helm/Kubernetes defaults no longer point at stale pre-0.29 image versions or the old GitHub namespace.
- Go/no-go onboarding drift is reduced: the Docker-native install one-liners in `wiki/getting-started.md` and `wiki/quickstart.md` now point at the canonical `cutctx/cutctx` GitHub path instead of the stale `chopratejas/cutctx` repository.
- Release-manifest and active-doc drift are tightened further: `scripts/verify-versions.py` now passes with all tracked plugin/SDK manifests aligned at `0.29.0`, remaining active Docker-native docs now point at `cutctx/cutctx`, live troubleshooting/pricing/integration/OpenClaw docs now use canonical `cutctx/cutctx` links, the packaged EE commercial-license surface now consistently names `Cutctx Labs`, and the docs OG route no longer ships the `My App` placeholder brand.
- Restored the admin/runtime source tree to a bootable state after a corrupted `cutctx/proxy/routes/admin.py` edit, and re-verified live current-source endpoints for `/health`, `/config/flags`, `/policy/status`, `/stats`, and `/stats-history`.
- Hardened dashboard operator data loading so unsupported or absent config surfaces no longer present as broken stats in local dashboard flows.
- Dashboard Capabilities and Orchestrator toggles now surface a dismissible `alert-card` on config-update failure (previously only `console.error` was emitted — toggles snapped back silently). Both pages use the same `.alert-card` + `.ghost-button` pattern as `Overview.jsx` for visual consistency.

### Added

- Inline multimodal audio optimization for supported chat/compress flows, with targeted regression coverage in `tests/test_audio_compressor.py`, `tests/test_inline_audio_messages.py`, and `tests/test_proxy_compress_endpoint.py`.
- **Feedback Loop (Data Flywheel)** (`cutctx/ccr/response_handler.py`, `cutctx/proxy/intelligence_pipeline.py`, `cutctx/transforms/content_router.py`, `cutctx/proxy/server.py`, `cutctx/profiles.py`) — CCR response handler records retrievals as feedback → updates per-workspace `CompressionProfile` → `recommended_ratio` flows into `ContentRouterConfig.per_type_overrides` → adjusts `bias_multiplier` for affected content types. Enables adaptive compression based on retrieval patterns. Test coverage in `tests/test_feedback_loop.py` (11 tests).
- **Stack-graph reachability bridge** (`cutctx/graph/reachability.py`, `cutctx/transforms/code_compressor.py`) — symbol reachability analysis for Stack Graphs core, with `extract_symbol_names()`, `resolve_entry_points()`, and wiring into `CodeCompressor.set_protected_symbols()` for syntax-preserving code compression. Distinct from the Stack Graphs AST/TSG core released in [0.29.0]. Test coverage in `tests/test_stack_graph_reachability.py` (17 tests) and `tests/test_initiative2_e2e.py` (5 tests).
- **Benchmark CLI** (`cutctx evals benchmark`) — comprehensive compression evaluation harness with `BenchmarkRunner`, 10 guarded compressor adapters (smart_crusher, log, search, diff, code, kompress, llmlingua, drain3, content_router, all), ThreadPoolExecutor parallelism, JSON and markdown output (LLMLingua-paper-style comparable format). Supports `--dataset {tool_outputs,longbench,squad,hotpotqa}`, `--compressors`, and `--metrics {ratio,tokens_saved,f1,rouge_l,information_recall,exact_match}`. Zero-LLM by default. Test coverage in `tests/test_evals_benchmark.py` (6 tests).
- **Capabilities visibility for moat features** (`cutctx/cli/capabilities.py`) — `cutctx capabilities` now reports Feedback Loop, Stack Graphs, and Benchmark CLI availability alongside the existing optional-dependency checks. The `stack_graph` row uses a precise `stack_graph_available()` check (rather than a generic `_core` module-presence check).
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
  [#202](https://github.com/chopratejas/cutctx/issues/202), PR
  [#204](https://github.com/chopratejas/cutctx/pull/204)).
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
* **deps:** move `gunicorn` to `[proxy-prod]` extra with `sys_platform != 'win32'` guard; removed from `[proxy]` to avoid forcing a Unix-only package on dev, CI, and Windows users ([#537](https://github.com/chopratejas/cutctx/pull/537))
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
[0.2.0]: https://github.com/chopratejas/cutctx/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/chopratejas/cutctx/releases/tag/v0.1.0
