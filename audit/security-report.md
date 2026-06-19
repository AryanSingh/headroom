# Security Audit Report — CutCtx v0.26.0

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
