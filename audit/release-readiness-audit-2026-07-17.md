# Release-readiness audit — 2026-07-17

## Verdict

**Local implementation gaps remediated; external release evidence pending.**

The exercised core build, test, type-check, lint, CLI, and proxy-health paths
are strong. The two originally blocking functional gaps and the strict Clippy
failure were remediated after this audit. A public-release decision still
requires the external staging and host evidence listed below.

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

### Resolved — OpenClaw `compact()` no longer reports a no-op as successful

- **Affected:** `plugins/openclaw/src/engine.ts`
- **Remediation:** standalone compaction now returns `{ ok: false, compacted:
  false }` with an explicit deferred reason and does not increment compaction
  statistics. Context compression remains available through `assemble()`.
- **Regression coverage:** `plugins/openclaw/test/engine.test.ts` verifies that
  no successful session mutation is claimed.

### Resolved — Rust parity no longer advertises unimplemented comparators

- **Affected:** `crates/cutctx-parity/src/lib.rs`
- **Remediation:** `cache_aligner` and `ccr` stubs were removed from the
  built-in comparator catalog. `parity-run list` now exposes only implemented
  transforms, and the supported fixture suite reports 153 matches, zero diffs,
  and zero skips.

### Resolved — Strict Rust lint gate passes

- **Affected:** `crates/cutctx-core/tests/test_stack_graphs.rs` and
  `crates/cutctx-py/src/lib.rs`
- **Remediation:** the stack-graph test uses `if let Err(error)` rather than an
  unnecessary unwrap; PyO3 binding calls now use the current `new` and
  `IntoPyObject`-compatible dict construction APIs. `cargo clippy --workspace
  --all-targets -- -D warnings` passes.

### Medium — Some major paths have only mocked/unit coverage in this audit

- **Affected:** provider egress, external authentication, live LLM/provider interactions, optional ML/embedding extras, Docker/Kubernetes deployment, JetBrains runtime.
- **Evidence:** the suite passes broadly, but many provider tests use mocks and the local audit did not provision external credentials, cloud services, Docker, a JetBrains host, or browser-driven production topology.
- **Impact:** the audit cannot certify production behavior for provider-specific auth/streaming or optional deployment surfaces.
- **Required remediation:** require staging evidence for each supported provider/auth mode, Docker-native compose smoke, Helm deployment with `/readyz`, and IDE-host smoke tests before a public release.

### Resolved — Dashboard main bundle is within the advisory threshold

- **Affected:** `dashboard/src/App.jsx`
- **Remediation:** route pages are lazy-loaded behind a `Suspense` fallback.
  The entry chunk is now 255.55 kB minified, and an automated dashboard test
  enforces Vite's 500 kB per-JavaScript-chunk threshold.

## Intentional/non-blocking items

- `cutctx/learn/aggregate.py:97-104` deliberately refuses telemetry sharing pending product/security approval. Treat it as a disabled feature, not a defect, if it is absent from the release scope.
- Tokenizer/backend base-class `NotImplementedError` paths are capability guards for unsupported implementations, not confirmed stubs.
- JetBrains filename TODOs are naming debt, not evidence of an unimplemented behavior.

## Release gate

The local functional and quality gates above are closed. Do not make a public
release certification until staging evidence exists for each supported
provider/auth mode, Docker Compose, Helm `/readyz`, and supported IDE hosts.
Retain a parity-run report with zero skips for the transforms it lists and run
the full serial Python/Rust suites before release.
