# Prerequisites, Test Environments, and Evidence

## Environment matrix

| Environment | Purpose | Required components | Safety boundary |
|---|---|---|---|
| Local clean | installation, SDK/CLI/native smoke | Python 3.10–3.14, current Rust toolchain, Node/npm, Go, Docker if selected | no real customer data; provider calls disabled or sandboxed |
| Staging integration | proxy/provider/dashboard/memory E2E | HTTPS test deployment, dashboard, configured test upstreams, persistent test database/cache | use provider project with spend cap and synthetic prompts |
| Enterprise staging | EE governance | two tenants; viewer/operator/admin identities; SSO/OIDC test IdP; billing webhook sandbox | no production tenant or Stripe live endpoint |
| Host matrix | IDE/plugin/agent flows | VS Code/Cursor, a supported JetBrains IDE, Claude Code/Desktop, Codex, OpenCode, OpenClaw as applicable | disposable profiles/workspaces only |

Required release-record fields: release artifact SHA/version; commit SHA; OS/arch; Python/Node/Rust/Go/IDE/browser versions; Docker image digest; configuration file checksum; environment name; executor; UTC timestamps; all test IDs; sanitized request IDs; screenshots/log attachments.

## Accounts, seed data, and cleanup

Create `tenant-a` and `tenant-b`, each with `viewer-a`, `operator-a`, `admin-a`, and equivalent B identities. Give each test provider a unique model alias. Seed: a 10–20 KB deterministic text fixture containing `ORDER-ALPHA-93817`, a code fixture with function `critical_payment_path`, a tool schema, one image/audio sample where extras are installed, and two semantically similar prompt pairs. Use `RUN_ID` in session IDs, memory keys, route contracts, provider credentials, audit events, and filenames.

After execution: delete test provider keys and dashboard storage; revoke client/admin tokens; remove test secrets/contracts/memories/organizations only through supported APIs; export and retain sanitized evidence; verify no test records remain in shared/staging UI. Do not run `/stats/reset`, destructive memory/DSR operations, webhook replay, or credential mutations outside an isolated environment.

## Standard evidence capture

For HTTP cases save redacted command, status, headers excluding secrets, body, SSE frames, proxy log lines, request/session ID, and relevant metric delta. For CLI cases save stdout, stderr, exit code, effective config, and created files. For UI cases save screenshot, viewport, browser console/network errors, and corresponding API response. Secrets must appear as `<redacted>`; evidence containing a secret is a test failure and must be removed from the record.

## Shared commands and fixtures

Use a dedicated shell with variables exported only for the test process:

```bash
export BASE_URL=http://127.0.0.1:8787
export RUN_ID=rc-$(date -u +%Y%m%dT%H%M%SZ)
export CUTCTX_ADMIN_KEY='<test-only-admin-key>'
export CUTCTX_CLIENT_API_KEY='<test-only-client-key>'
cutctx proxy --host 127.0.0.1 --port 8787
curl -fsS "$BASE_URL/livez"
```

Expected: the process remains running; `/livez` returns HTTP 200; all subsequent authenticated calls use the documented header/key mechanism for this build. If the configured auth mode differs, record it and mark any assumption **Needs confirmation**.

## Universal test-case contract

Every case below has the same evidence rules. Execute all numbered actions in order; the final `Pass` statement is the pass/fail criterion. Where a case says “repeat per item,” create a separate row in the release record per item, retain the exact request/command, and attach result evidence. A missing prerequisite means **Blocked**, never Pass.
