# Product-Managed Proxy Runtime

## Goal

Make the CutCtx proxy a managed product dependency so Codex and ChatGPT routing never silently loses compression because a user did not manually start a PATH-installed process.

## Decision

Use the existing persistent-service installer as the single supervisor.  On macOS it creates a per-user LaunchAgent with `RunAtLoad` and `KeepAlive`; equivalent user services are used on Linux and Windows.  The product control application invokes an idempotent ensure command during startup, but it first attaches to an already healthy proxy and never replaces or stops it.

The manifest preserves the proxy's existing `anthropic` default backend, records `CUTCTX_REVERSIBLE_CODE=1`, and explicitly includes `--enable-reversible-code`.  This makes the release behavior independent of whether a previously installed package had the new default.

## Safety contracts

- An already healthy listener is preserved without restart, including live WebSocket sessions.
- Service installation is performed only when the managed manifest is absent or differs from the desired product profile.
- A failed fresh installation removes only the newly-created product manifest/artifacts; an existing healthy deployment is not replaced.
- The Control app reports a managed-runtime failure instead of silently falling back to PATH or an unsupervised child.
- No credentials are stored in manifests or emitted in status output.

## Verification

- Unit-test manifest construction for the explicit reversible-code contract.
- Unit-test the idempotent ensure decision: attach to healthy, install when absent, and reject a mismatched active deployment rather than interrupting it.
- Unit-test the Control startup path uses the managed runtime before attempting a local child process.
- Run the relevant Python and Rust suites, Rust formatting/lint checks, and a package build.
