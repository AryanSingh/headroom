# Security Audit Report — Cutctx v0.26.0

## 2026-07-22 assisted-pilot addendum

**Pilot security score: 94/100.** No Critical or High security finding remains
on the supported path. Non-loopback HTTP and WebSocket provider traffic now
requires `CUTCTX_PROXY_API_KEY`. Customer-managed deployments require distinct
admin, provider-route, and agent-client credentials. Helm fails during render
when the required credentials are missing or reused.

The root Docker Compose deployment now keeps Qdrant and Neo4j off host ports,
requires an explicit Neo4j credential, and persists Cutctx state in a named
volume. The commercial-header scan passes for every Python file in `cutctx_ee`.
Focused authentication and deployment tests pass 40 cases; the Helm and Docker
configuration checks pass from candidate
`b88669e3a19db4b42b2a71a15edf91c3725f67d5`.

The pilot still requires TLS termination, customer secret-manager controls,
legal approval of data terms, and customer acceptance of telemetry. No external
penetration test was performed in this release pass.

**Date:** 2026-06-19

## Summary
No critical vulnerabilities found. Enterprise-grade security controls in place.

## Findings

| # | Finding | Severity | File |
|---|---------|----------|------|
| 1 | Hardcoded Neo4j default password "password" | Medium | memory/backends/direct_mem0.py:102 |
| 2 | CORS `*` + credentials combo when opted in | Medium | server.py:2014-2025 |
| 3 | Version header leaked in every response | Low | server.py:2044-2046 |
| 4 | Admin key logged in plaintext on auto-gen | Low | server.py:2255-2259 |

## Positive Controls
- Admin auth: Auto-generated + timing-safe (hmac.compare_digest)
- RBAC: All admin endpoints have require_admin_auth + require_rbac_permission
- Rate limiting: Token bucket with RPM/TPM, per-IP
- Body limits: 50 MB with decompression bomb protection (zstd, gzip, deflate, brotli)
- CORS: Default-closed (empty origins)
- LLM Firewall: 27 regex patterns (injection, PII, jailbreak, exfil)
- SSRF: Allowlist-based base_url validation
- SQL: Column name allowlist validation
- Audit: Structured events with actor, IP, user-agent

## Score: 8.5/10
# 2026-07-19 merged-main security addendum

The replay journal remains default-off, metadata-only, local-admin protected,
and bounded. No fresh Critical or High finding was identified in the merged
event-journal diff. Full CI security-audit should be rerun on `main` before GA.
