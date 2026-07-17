# Release-readiness audit — 2026-07-17

## Verdict

**Not ready to ship** (production-readiness score: **58/100**).

The exercised core build, test, type-check, lint, CLI, and proxy-health paths are strong. However, the release requirement that every shipped module be functional and contain no stubs is not met: the Rust parity module contains two deliberate non-functional comparators, and the published OpenClaw plugin reports a compaction as successful without performing it.

## Verified checks

| Surface | Evidence | Result |
|---|---|---|
| Python test suite | `CI=true uv run --no-sync python -m pytest tests -q --tb=short` | Passed (9,176 collected; expected optional integration skips are reported by the suite). |
| Python targeted route/security-store tests | `pytest tests/test_route_modules.py tests/test_secrets_store.py -q` | 40 passed. |
| Rust workspace | `cargo test --workspace --no-fail-fast` | Passed; includes core, proxy, bindings, and parity tests. |
| Dashboard | `npm --prefix dashboard run lint`, `npm --prefix dashboard test -- --run`, `npm --prefix dashboard run build` | Passed: 11 tests; production build succeeded. Build warns of a 504 kB minified JS chunk. |
| OpenClaw plugin | `npm --prefix plugins/openclaw test -- --run`, `typecheck` | Passed: 54 tests; type-check passed. |
| TypeScript SDK | `npm --prefix sdk/typescript test -- --run`, `typecheck` | Passed: 306 tests; 33 skipped; type-check passed. |
| VS Code extension | `npm --prefix extensions/vscode run compile` | Passed. |
| Python lint | `uv run --no-sync ruff check .` | Passed. |
| Runtime smoke | `cutctx --help`; `TestClient(create_app()).get('/livez')` | Passed; `/livez` returned 200. |
| Release/deployment wiring | CI/release workflows, Docker/Kubernetes and Helm manifests inspected | Build, wheel smoke, SBOM/signing, health probes, release evidence, and publish gates are present. |

## Findings

### High — OpenClaw `compact()` is a no-op that returns success

- **Affected:** `plugins/openclaw/src/engine.ts:156-193`
- **Evidence:** the method's own TODO says it must read the session file, extract messages, call compression, and write compacted messages. Instead it increments a counter and returns `{ ok: true, compacted: true }`.
- **Impact:** callers can discard or defer a real compaction operation believing it completed. This violates the advertised compact-context workflow and creates a data/UX correctness risk.
- **Required remediation:** either implement the read/compress/write transaction (including atomic persistence and error propagation) or expose the action as deferred/no-op and remove the successful `compacted: true` result. Add an integration test that verifies persisted session content and token reduction.

### High — Rust parity module deliberately skips two advertised comparators

- **Affected:** `crates/cutctx-parity/src/lib.rs:148-173`
- **Evidence:** `CacheAlignerComparator` and `CcrComparator` are generated from `stub_comparator`; their `run()` always returns `not implemented (Phase 0)`. The harness turns this into `Skipped`, so the existing parity test pass does not prove those transforms are equivalent across Python and Rust.
- **Impact:** the parity binary is shipped/buildable but cannot validate two named transform paths. If parity is a release claim or customer-facing module, this is a direct functional gap.
- **Required remediation:** implement both comparators and add fixtures with zero skipped outcomes; otherwise remove/feature-gate the incomplete commands and document them as unavailable.

### Medium — Strict Rust lint gate fails

- **Affected:** `crates/cutctx-core/tests/test_stack_graphs.rs:39`
- **Evidence:** `cargo clippy --workspace --all-targets -- -D warnings` fails on `clippy::unnecessary_unwrap`: `result.unwrap_err()` is guarded by `result.is_err()`.
- **Impact:** the repository does not satisfy a strict all-targets Clippy release gate. This is test code, so it is not a runtime blocker, but it prevents a clean quality gate.
- **Required remediation:** use `if let Err(error) = result { ... }` (or equivalent) and add strict Clippy to CI if it is intended as a release criterion.

### Medium — Some major paths have only mocked/unit coverage in this audit

- **Affected:** provider egress, external authentication, live LLM/provider interactions, optional ML/embedding extras, Docker/Kubernetes deployment, JetBrains runtime.
- **Evidence:** the suite passes broadly, but many provider tests use mocks and the local audit did not provision external credentials, cloud services, Docker, a JetBrains host, or browser-driven production topology.
- **Impact:** the audit cannot certify production behavior for provider-specific auth/streaming or optional deployment surfaces.
- **Required remediation:** require staging evidence for each supported provider/auth mode, Docker-native compose smoke, Helm deployment with `/readyz`, and IDE-host smoke tests before a public release.

### Low — Dashboard main bundle exceeds the configured advisory threshold

- **Affected:** dashboard production build
- **Evidence:** Vite reports `dist/assets/index-*.js` at 504.18 kB minified (144.23 kB gzip), above its 500 kB advisory threshold.
- **Impact:** potential first-load cost; not a functional blocker.
- **Required remediation:** code-split large route modules and retain a bundle budget.

## Intentional/non-blocking items

- `cutctx/learn/aggregate.py:97-104` deliberately refuses telemetry sharing pending product/security approval. Treat it as a disabled feature, not a defect, if it is absent from the release scope.
- Tokenizer/backend base-class `NotImplementedError` paths are capability guards for unsupported implementations, not confirmed stubs.
- JetBrains filename TODOs are naming debt, not evidence of an unimplemented behavior.

## Release gate

Do not approve this release as “all modules functional; no stubs.” Clear the two High findings first, fix the strict lint failure, then collect the staging/host evidence listed above. Re-run the commands in **Verified checks** and require a parity run with zero skips for supported transforms.
