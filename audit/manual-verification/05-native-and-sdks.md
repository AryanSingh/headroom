# Rust/Native Components and SDK Checklists

### NATIVE-001 — Build/install artifact matrix

**Priority:** P0. **Actions:** build release artifacts on each supported OS/arch/Python combination; install wheel into fresh venv; run Python import and `cutctx --version`; build Rust workspace/native proxy. **Expected:** PyO3 extension loads, version/ABI match, no runtime compiler requirement for wheel path. **Negative:** unsupported Python/arch, missing Rust for sdist, corrupt wheel. **Pass:** clean install works or supported limitation is documented.

### NATIVE-002 — Rust/Python parity

**Priority:** P0. **Actions:** run parity fixtures and manually compare token counts, CCR marker/key, transforms/manifests for text/code/log/diff/JSON fixtures. **Expected:** deterministic values per documented parity contract. **Negative:** unicode, empty input, long input, unsupported tokenizer. **Pass:** no unreviewed behavioral divergence.

### NATIVE-003 — Native proxy data plane

**Priority:** P1. **Actions:** start `crates/cutctx-proxy`; execute health, OpenAI/Anthropic/Gemini-compatible request, streaming, compression, CCR and configured cache backend paths. **Expected:** Axum proxy obeys protocol, metrics and errors; behavior aligns with declared Python/native scope. **Pass:** compatibility differences are explicit and tested.

### NATIVE-004 — Core algorithms and storage backends

**Priority:** P1. **Actions:** manually exercise tokenizers (tiktoken/HF/estimator), relevance (BM25/embedding/hybrid), signal detectors, stack graph, CCR in-memory/SQLite/Redis, cache stabilization, transforms/pipelines. **Expected:** factory chooses requested backend; TTL/persistence/concurrency and fallback are visible. **Negative:** missing model/backend, corrupt SQLite/Redis down, unsupported language. **Pass:** every configured native feature has a row.

### NATIVE-005 — Build, feature, benchmark, and packaging claims

**Priority:** P1. **Actions:** build with default/advertised Cargo features, run selected Criterion/parity examples, inspect binary help/version/licenses/SBOM packaging. **Expected:** optional features are gated cleanly and performance claims have reproducible command/config. **Pass:** build documentation is accurate.

### SDK-001 — TypeScript public facade and direct compression

**Priority:** P0. **Actions:** clean `npm` install of `cutctx-ai`; import every documented top-level export; call `compress`, client, hosted/simulate helpers and error/fallback paths. **Expected:** ESM/CJS/types work as advertised; snake/camel conversion and auth/timeout/retry match proxy. **Negative:** bad URL/key, invalid message, unavailable proxy. **Pass:** README examples compile/run unchanged.

### SDK-002 — TypeScript streaming, hooks, shared context, paths

**Priority:** P1. **Actions:** consume SSE async iterator, collect stream, register success/error hooks, exercise bounded TTL shared context and filesystem path helper. **Expected:** event ordering/cancellation/error types are stable; no unhandled promise. **Pass:** output and type declarations match docs.

### SDK-003 — TypeScript provider adapters

**Priority:** P0. **Actions:** wrap OpenAI, Anthropic, Gemini and Vercel AI client/model with fixtures including tools/stream/schema. **Expected:** original options/results retain provider type/semantics except documented compression. **Negative:** adapter conversion error, proxy unavailable, unsupported content. **Pass:** each wrapper has non-stream/stream/error evidence.

### SDK-004 — Go SDK(s)

**Priority:** P1. **Actions:** from clean module, run every README example for `sdk/go` and `sdks/go-cutctx`: client/compression, transport/middleware, memory/options/shared context as exposed. **Expected:** `go vet/test` and example compile; context cancellation/timeout and typed errors work. **Negative:** invalid URL/key, cancelled context, bad JSON. **Pass:** module versions and imports resolve from release artifact.

### SDK-005 — Python SDK distribution

**Priority:** P0. **Actions:** install published/wheel package and execute `sdk/python` README/public client flows separately from source checkout. **Expected:** imports/metadata/extras and sync client match supported Python range. **Pass:** no undeclared source dependency.

### SDK-006 — SDK backward compatibility and upgrade

**Priority:** P1. **Actions:** install previous supported SDK then upgrade to RC against current proxy, and current SDK against previous supported proxy where claimed. **Expected:** deprecation/error/capability behavior is explicit; no silent incompatibility. **Cleanup:** remove test venv/modules. **Pass:** release notes/documentation reflect findings.

### SDK-007 — Examples and package security

**Priority:** P1. **Actions:** execute all example directories/readmes with test credentials; inspect package tarball for secrets, source maps, license and unintended EE code. **Expected:** examples only call declared endpoints; package has intended files/licenses. **Pass:** every example is verified or blocked with exact prerequisite.

### SDK-008 — API schema and error contract sweep

**Priority:** P1. **Actions:** derive endpoint/client method inventory; validate valid response, 4xx, 5xx, timeout, malformed JSON, retry/fallback for each. **Expected:** language-native error classes/codes preserve request ID. **Pass:** no client masks security/error condition as success.

### SDK-009 — Performance and resource guardrails

**Priority:** P2. **Actions:** run documented benchmark/load examples with fixed corpus; observe memory/CPU/FD behavior and cancellation. **Expected:** no unbounded growth; published benchmark caveats are visible. **Pass:** no regression beyond approved threshold.

### SDK-010 — Documentation parity

**Priority:** P1. **Actions:** map each public export/example/config option to code/type/test and `DOC-*`. **Pass:** missing/stale API is entered in gap ledger before release.
