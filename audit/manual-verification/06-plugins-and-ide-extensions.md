# Plugin and IDE Extension Checklist

For each integration use a fresh host profile/workspace and log exact host/plugin version. Test process ownership: a plugin may stop only the proxy it started, never an already-running shared proxy.

### INT-001 — Manifest/package install sweep

**Priority:** P0. **Actions:** enumerate every plugin directory and manifest (`claude-code`, `codex`, `cutctx-agent-hooks`, `cutctx-plugin`, `cutctx-oauth2`, `cutctx-opencode`, `hermes`, `openclaw`, plus any release package); install/package/load each in its host. **Expected:** valid metadata, declared entrypoint/assets present, version matches release, clean uninstall. **Negative:** duplicate/older plugin, missing binary/dependency, invalid manifest. **Pass:** every shipped plugin has install/load/uninstall evidence.

### INT-002 — Claude Code, Codex, generic agent hooks

**Priority:** P0. **Actions:** enable each hook/plugin, run tool output above compression threshold, invoke CCR retrieval, restart host, disable/uninstall. **Expected:** hook registration occurs once; tool/history content compacts under configured policy; retrieval succeeds; host remains usable if proxy fails. **Negative:** malformed hook output, proxy timeout, invalid marker, disabled feature. **Pass:** no host configuration or conversation corruption.

### INT-003 — Claude Desktop MCP and gateway

**Priority:** P0 where supported. **Actions:** run `cutctx mcp install` and `--gateway` in disposable Desktop config; verify server registration; call tool through Desktop; pass a large result from another MCP server; stop/restart gateway. **Expected:** gateway interposes only documented MCP traffic; direct model endpoint limitation is accurately stated; errors are actionable. **Cleanup:** uninstall and restore config. **Pass:** observed behavior agrees with docs.

### INT-004 — OpenCode plugin

**Priority:** P1. **Actions:** install `cutctx-opencode`; trigger `chat.params`, large `tool.execute.after`, history transform, and compaction hook; toggle threshold/model/disable environment variables. **Expected:** recent turns preserved, old history compacted with CCR guidance, last-seen model attribution correct, compression fails open. **Negative:** malformed tool output, unsupported model, proxy/SDK failure. **Pass:** host message shape remains valid and savings evidence appears.

### INT-005 — OpenClaw context engine

**Priority:** P1. **Actions:** install/load manifest; configure local auto-start, existing local proxy, remote proxy (connect-only), selected provider reroute, retrieval tool; assemble multi-turn agent context and dispose. **Expected:** proxy URL validation/probe, only owned process stops, selected in-memory gateway routes update, conversions preserve content. **Negative:** invalid/non-local proxy URL, proxy unavailable, invalid hash, gateway update failure. **Pass:** context engine and tool complete without host crash or unsafe remote launch.

### INT-006 — Hermes, OAuth2, and retrieval/gateway packages

**Priority:** P1 when shipped. **Actions:** follow each README’s install/config/sample request; authenticate via sandbox OAuth provider; retrieve CCR record; inject token failure/expiry. **Expected:** credentials are handled/redacted per docs, failure is fail-safe. **Pass:** all advertised package paths have evidence or a clear blocked prerequisite.

### INT-007 — Provider/agent wrapper matrix

**Priority:** P1. **Actions:** execute `cutctx wrap` and relevant plugins for Claude, Codex, Copilot subscription mode, Cursor, Aider, Gemini, Windsurf, Zed, Antigravity, OpenClaw/OpenCode; use at least one real/sandbox request per supported host. **Expected:** proxy target/config is applied precisely; original configuration backups/undo work; provider-specific auth discovery obeys platform claim. **Negative:** absent host, invalid credential, non-writable config, process interruption. **Pass:** compatibility matrix is validated row by row.

### INT-008 — VS Code/Cursor lifecycle

**Priority:** P0. **Actions:** package/install extension; test auto-start off/on, start/stop/show stats/configure commands, status bar states, configured port/binary path, deactivate/reload. **Expected:** extension waits for `/livez`, polls `/stats`, displays active/off/savings, stops only owned proxy. **Negative:** port busy, missing binary, malformed stats, proxy crash. **Cleanup:** remove extension/config. **Pass:** no orphan process and status accurately reflects runtime.

### INT-009 — VS Code AI configurator

**Priority:** P1. **Actions:** configure VS Code/Cursor HTTP proxy, Copilot, Cline and Continue target options in disposable settings; inspect changes; restore. **Expected:** host-specific settings/clipboard guidance match installed extensions and do not overwrite unrelated settings. **Negative:** target absent, read-only config, invalid JSON. **Pass:** supported provider actually uses test proxy and undo restores baseline.

### INT-010 — JetBrains plugin

**Priority:** P1. **Actions:** build/install plugin into supported JetBrains IDE; open settings, configure proxy/binary/port, use start/stop/status actions/widget, restart IDE. **Expected:** persistent settings and application service honor ownership; polling/errors visible; shutdown cleans resources. **Negative:** absent binary, occupied port, malformed config, proxy unavailable. **Pass:** current IDE compatibility and all action states are evidenced.

### INT-011 — Cross-platform host smoke

**Priority:** P1. **Actions:** repeat applicable plugin/extension P0/P1 flows on macOS, Windows, Linux; especially Copilot/keychain/secret-service and path/quoting. **Expected:** platform-specific limitation is explicit. **Pass:** unsupported platform is documented, not silently broken.

### INT-012 — Host security, privacy, and recovery

**Priority:** P0. **Actions:** inspect host config/log files/network for provider/admin token; kill proxy while host active; reconnect/restart host; submit sensitive marker content. **Expected:** no secret leakage, safe fallback/degraded UX, no unbounded restart loop. **Pass:** extension/plugin recovery retains user work and access boundary.

### INT-013 — Plugin documentation/examples sweep

**Priority:** P1. **Actions:** execute every README command/example/manifests’ declared setting for each plugin/IDE package. **Expected:** command/config matches current artifact. **Pass:** discrepancies are entered under DOC-008.

### INT-014 — Packaging/update/uninstall

**Priority:** P1. **Actions:** install prior plugin/extension then update RC; verify migrations/settings, activation and rollback/uninstall. **Expected:** no duplicate registrations or orphan configuration/process. **Pass:** update path is release-ready.

### INT-015 — Disabled/optional feature behavior

**Priority:** P2. **Actions:** turn off compression/retrieval/routing flags; install host without optional SDK; use experimental config. **Expected:** clear disabled status and original host behavior. **Pass:** plugin never claims an unavailable capability.

### INT-016 — Error-message and supportability review

**Priority:** P2. **Actions:** force failures from INT-001–015; read UI/log/error text as a new user. **Expected:** next action, affected component and safe redaction. **Pass:** support can diagnose without secret/source access.

### INT-017 — Concurrency and multi-workspace behavior

**Priority:** P1. **Actions:** activate same plugin in two workspaces/hosts sharing a proxy and different sessions. **Expected:** isolation, no process race, correctly aggregated stats. **Pass:** ownership and context scope hold.

### INT-018 — Final host artifact inventory

**Priority:** P1. **Actions:** attach matrix with host, version, package SHA, command/config, result, error scenario, cleanup. **Pass:** no plugin/IDE artifact is omitted.
