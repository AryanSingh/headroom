# QA Verification Report — CutCtx v0.26.0

**Date:** 2026-06-19

## Test Results

| Suite | Passed | Failed | Skipped | Ignored | Duration |
|-------|--------|--------|---------|---------|----------|
| Python (pytest) | 6,991 | 0 | 243 | — | 3m 58s |
| Rust core | 863 | 0 | — | 1 | 0.51s |
| Rust proxy | 260 | 0 | — | 0 | 0.19s |
| Go SDK | 19 | 0 | — | — | cached |
| **Total** | **8,133** | **0** | **243** | **1** | — |

## Import Verification
All critical module imports succeeded:
- `cutctx.proxy.server.create_app`
- `cutctx.proxy.schema_compress.compress_tool_schemas`
- `cutctx.security.firewall.FirewallScanner`
- `cutctx.entitlements.EntitlementChecker`

## Warnings (non-blocking)
- 22 Python warnings (deprecation notices for Python 3.14 tar filter, swigvarlink)
- 243 Python skips (platform/provider-dependent tests)
- 1 Rust test ignored in core suite

## Score: 9.5/10
