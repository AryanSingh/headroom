# Security Audit Report — Private EE Release Candidate

**Date:** 2026-08-02
**Candidate source:** `a33f67831a2e17f8fa229a5e08909a742c3dbe7d`

## Verdict

**Security score: 94/100.** No verified Critical or High engineering finding remains on the supported private-release path.

## Closed release findings

| Finding | Resolution |
| --- | --- |
| EE source/binary drift | Release build compiles all modules, fails closed on partial compilation, stages the exact wheel contents, then signs that staged package. |
| Unsigned or tampered EE artifact | Archive verifier validates HMAC signature, native membership, hashes, duplicates, and source leakage before publication. |
| Misleading pure-Python wheel tag | Native wheels are retagged to the exact CPython ABI and platform. |
| CCR credential retrieval risk | Credential-like values are redacted before reversible originals are stored. |
| Anonymous MCP proxy fallback | MCP resolves protected origin-scoped credentials and preserves actionable 401/403 responses. |
| Ambiguous public-key type | PitchToShip token verification rejects non-EC public keys before ECDSA verification. |
| Stale “missing Sentry” audit claim | Optional Sentry-compatible tracking exists and is initialized when configured. |
| Stale unbounded WebSocket claim | Pre-upstream admission is bounded, reserved atomically, and rejects at capacity. |
| Stale cache-memory claim | Compression cache has total and per-entry byte budgets, eviction, and telemetry. |

## Fresh security evidence

- Secret-pattern scan passed.
- Auth/security and full regression suites passed.
- Dashboard dependency audit found zero vulnerabilities.
- Signed archive verification passed for 33 native modules.
- Isolated installed-wheel billing replay smoke passed.

## Remaining non-blocking risk

| Severity | Risk | Release control |
| --- | --- | --- |
| Medium | No independent penetration test in this pass | Keep distribution private, require authenticated ingress, and schedule external testing before broad GA. |
| Medium | Production signing/index secrets were not available locally | GitHub workflow fails closed when required secrets are absent; configure secrets before tagging. |
| Medium | Customer network policy and TLS termination are deployment-owned | Require the documented customer acceptance and deployment-security checks. |
| Low | Dependency deprecation warnings for the WebSocket stack | Track upgrades; no functional failure was observed. |
