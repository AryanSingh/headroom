# Core Python Package and CLI Checklist

## Python SDK and compression

### CORE-001 — Basic compression and token accounting

**Priority:** P0. **Feature:** `cutctx.compress`/public Python API. **Purpose:** prove a typical developer call returns usable compressed content and truthful accounting. **Preconditions:** clean environment with the core package; deterministic long-text fixture. **Actions:** (1) run `python -c 'from cutctx import compress; ...'` using the fixture and an explicitly supported model; save the original and result. (2) Repeat with messages containing system, user, assistant, tool, and tool-result content. **Expected evidence:** successful typed result; output preserves message order/roles and `ORDER-ALPHA-93817`; token metrics are non-negative and output is not falsely reported as smaller when it is not. **Negative:** unsupported model, empty message list, invalid message type, `None`, oversize input, and unavailable optional compressor each produce documented error/fallback without process crash or silent content loss. **Cleanup:** delete generated CCR/test state. **Pass:** all valid calls preserve required identifiers and all invalid calls have deterministic documented outcomes.

### CORE-002 — Reversible CCR and expiry

**Priority:** P0. **Feature:** CCR markers/store. **Preconditions:** CCR enabled with short test TTL. **Actions:** (1) compress fixture until a `<<ccr:...>>` marker is produced. (2) retrieve through the supported API/tool using its 24-character hash. (3) wait beyond TTL and repeat. **Expected:** first retrieve returns exact original bytes/metadata; expired key is a clear miss/error, never another tenant/session’s content. **Negative:** malformed hash, unknown hash, path traversal-shaped value, and duplicate requests are rejected/safe. **Cleanup:** remove CCR backend. **Pass:** reversibility and expiry are both evidenced.

### CORE-003 — Transform/content matrix

**Priority:** P1. **Feature:** SmartCrusher, code/diff/log/search/JSON-schema/image/audio pass-through routes where installed. **Preconditions:** install each advertised extra in a separate environment. **Actions:** run the same preservation fixture type through its documented mode/profile and compare critical fields, code symbols, JSON parseability, diff headers, log error lines, and binary/media validity. **Expected:** only documented optional modes appear; unavailable extra gives an actionable install message. **Negative:** malformed JSON, invalid UTF-8/binary, deeply nested objects, image/audio too large, unsupported language, and empty content. **Cleanup:** clear cached models/assets if the environment is disposable. **Pass:** each advertised transform has a valid and invalid evidence row, or is marked blocked with missing extra.

### CORE-004 — Configuration, telemetry, hooks, and lifecycle

**Priority:** P1. **Feature:** config precedence, hooks/events/telemetry. **Actions:** set the same option in defaults, config file, environment, and explicit API argument; invoke compression while a test hook records lifecycle events. **Expected:** documented precedence wins; hook order is stable; telemetry has request correlation but no raw secret. **Negative:** malformed config, unknown key, unwritable telemetry target, hook exception. **Cleanup:** unset variables/remove config. **Pass:** effective configuration and fail-open/fail-closed behavior match docs/code.

### CORE-005 — Streaming/non-streaming preservation

**Priority:** P0. **Feature:** SDK/proxy client request handling. **Actions:** send the same provider-compatible request with and without stream enabled; collect all frames. **Expected:** non-stream response has complete usage/content; stream has valid ordering, terminates once, and reconstructs an equivalent response with tool/function fields retained. **Negative:** client disconnect, upstream mid-stream error, malformed SSE/JSON, timeout. **Cleanup:** close clients. **Pass:** no duplicate/missing terminal frames and clear error propagation.

### CORE-006 — Shared context/cache/budget boundaries

**Priority:** P1. **Feature:** shared context, semantic/cache/budget behavior. **Actions:** put/get/remove named context; submit duplicate and near-duplicate prompts; cross configured budget zones. **Expected:** scoped records are visible only to intended namespace; cache response/metrics and budget decisions are explicit. **Negative:** zero/negative/huge TTL, cache unavailable, quota exhausted, concurrent writers. **Pass:** no cross-session leak, stale response, or unbounded growth.

## CLI command-family coverage

### CLI-001 — Root help, version, and global failures

**Priority:** P0. **Actions:** run `cutctx --help`, `cutctx --version`, unknown command, `cutctx <group> --help`, and malformed flags for every listed top-level group. **Expected:** help names the current commands; version equals artifact metadata; errors go to stderr with non-zero exit and no traceback at normal verbosity. **Pass:** command registry and help are internally consistent.

### CLI-002 — Setup, init, install, unwrap, wrap, and global routing

**Priority:** P0. **Actions:** in disposable home/workspaces, execute documented noninteractive and interactive setup/install/init flows for detected and unsupported hosts; wrap then unwrap each supported agent/provider from the compatibility matrix; test `global` enable/status/disable. **Expected:** only intended config files are changed, a backup/diff is offered where documented, status recognizes the result, and uninstall restores prior values. **Negative:** absent binary, denied write, invalid target, interrupted install, duplicate install. **Cleanup:** use supported uninstall/unwrap and compare original tree. **Pass:** no unrelated user config is altered and failures are reversible.

### CLI-003 — Proxy/config/auth and safety commands

**Priority:** P0. **Actions:** execute `proxy --help`, start/stop on free and occupied ports, `config doctor`, `config-check`, `auth login/status/rotate/logout/run`, and `capabilities`. **Expected:** valid config starts; doctor reports exact remediation; authentication token is not echoed; occupied port exits non-zero. **Negative:** bad URL/key/config permission, missing optional runtime, expired token. **Pass:** exit codes/output formats are script-safe and secrets are redacted.

### CLI-004 — Memory/capture/learn/report/savings/perf

**Priority:** P1. **Actions:** exercise every subcommand shown by `cutctx memory --help` (list/show/stats/edit/delete/prune/purge/export/import) using `RUN_ID`; run capture compare, learn dry-run/write path, report/savings/perf formats. **Expected:** list/filter/pagination/export/import preserve intended records; destructive operations require documented confirmation/force semantics; JSON is parseable. **Negative:** missing ID/file, corrupt import, empty store, permission denial, invalid date/filter. **Cleanup:** delete `RUN_ID` records and generated reports. **Pass:** all help-advertised commands receive a valid/invalid row.

### CLI-005 — Evaluation, evidence, benchmark, tools, stack graph

**Priority:** P1. **Actions:** execute `verify`, `evidence`, `benchmark`, `bench`, `evals`, `tools list/doctor/difft-check/install`, and `stack-graph explain` with local fixtures, then invalid dataset/tool/path values. **Expected:** reproducibility settings/seeds are recorded; unavailable model/dataset is explicit rather than fabricated; tool install is reversible. **Pass:** outputs agree with documentation and exit status reflects failure.

### CLI-006 — Enterprise/admin families

**Priority:** P1 (EE only). **Actions:** run help plus allowed/denied operation for `license`, `billing`, `orgs`, `rbac`, `audit`, `mcp`, `policies`, `profile`, `agent-savings`, and `sso-test`. **Expected:** OSS build declares unavailable enterprise capability; EE build enforces role/tenant boundaries. **Pass:** every command is either verified or explicitly tagged EE-only/blocked.
