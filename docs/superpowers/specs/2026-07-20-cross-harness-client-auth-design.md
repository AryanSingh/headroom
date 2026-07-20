# Cross-Harness Client Authentication Design

**Date:** 2026-07-20
**Status:** Approved design; written specification pending user review

## 1. Problem

Cutctx currently uses its root administrative credential to protect
`/v1/compress` and CCR retrieval routes. Coding-harness integrations call
those routes through the Cutctx SDK, whose public client credential is
`CUTCTX_API_KEY`. The wrapper starts a proxy with
`CUTCTX_ADMIN_API_KEY`, but does not consistently give the SDK-facing
credential to the wrapped process.

The immediate symptom is an OpenCode plugin warning:

```text
cutctx: history compress failed, passing through Invalid or missing admin credentials.
```

This is not only an OpenCode environment bug. The current boundary makes an
administrative credential necessary for ordinary agent operations and leaves
each wrapper, plugin, SDK, and MCP registration to solve credential discovery
independently.

## 2. Goals

1. A user enters or provisions a Cutctx client credential once and can use it
   from every supported coding harness until it expires or is rotated.
2. Ordinary compression and CCR retrieval never require the root admin key.
3. Credentials are stored in the operating system's protected secret store,
   not in harness configuration, shell profiles, project files, command-line
   arguments, logs, or generated MCP configuration.
4. Every `cutctx wrap <harness>` command uses one shared credential-resolution
   and child-environment contract.
5. `cutctx mcp serve`, the Python SDK, the TypeScript SDK, and installed
   plugins use the same client-auth semantics.
6. CI, containers, and non-interactive environments remain supported through
   explicit environment-based secret injection.
7. Missing, invalid, expired, and rotated credentials produce one actionable
   failure rather than repeated per-message warnings.

## 3. Non-goals

- Replacing upstream provider credentials such as `OPENAI_API_KEY` or
  `ANTHROPIC_API_KEY`.
- Replacing the dedicated provider-route credential
  `CUTCTX_PROXY_API_KEY` / `X-Cutctx-Proxy-Key`.
- Giving client credentials access to dashboard, policy, secrets, audit,
  billing, cache-administration, or other administrative routes.
- Persisting secrets in OpenCode, Codex, Claude, Cursor, MCP, or editor
  configuration.
- Making arbitrary direct launches inherit a credential globally. The durable
  guarantee applies to Cutctx wrappers, Cutctx MCP processes, Cutctx SDK
  processes, and integrations launched through Cutctx's shared auth execution
  path.

## 4. Security Model

### 4.1 Credential classes

Cutctx will keep three credential classes distinct:

| Credential | Client-side name | Server-side name | Scope |
| --- | --- | --- | --- |
| Client API key | `CUTCTX_API_KEY` | `CUTCTX_CLIENT_API_KEY` | Compression and CCR agent operations |
| Proxy route key | Harness-specific header | `CUTCTX_PROXY_API_KEY` | Provider HTTP/WebSocket proxy routes |
| Admin key | Admin header or bearer token | `CUTCTX_ADMIN_API_KEY` | Administrative and operator operations |

The client key must not authorize any endpoint guarded by
`require_admin_auth`. The admin key remains accepted on administrative routes
and may be accepted as an explicit break-glass compatibility credential on
agent routes during a documented transition period, but wrappers must never
distribute it as a client key.

### 4.2 Agent route scope

The client-auth dependency protects only:

- `POST /v1/compress`
- `POST /v1/retrieve`
- `GET /v1/retrieve/{hash}`
- `GET /v1/retrieve/stats`
- `POST /v1/retrieve/tool_call`
- any future route explicitly classified as an agent-facing SDK or MCP
  operation

It does not authorize `/stats`, `/dashboard`, `/cache/clear`, `/v1/secrets/*`,
policy routes, audit routes, billing routes, or any other admin surface.

### 4.3 Secret handling invariants

- Keys are compared with constant-time comparison.
- Key values are never included in exceptions, structured logs, telemetry,
  command output, generated config, process arguments, or display lists.
- URL query-string credentials are not supported.
- Environment values are copied only into the proxy or harness child process
  that needs them.
- The parent process does not mutate global process or OS launch-service
  environments.
- Stored credentials are indexed by normalized proxy origin so credentials for
  different local, staging, and production proxies cannot be confused.
- File permissions and keyring backend failures are fail-closed.
- Automated tests use synthetic credentials and isolated fake stores.

## 5. Credential Store

### 5.1 Store interface

A new focused module owns client credential persistence:

```python
@dataclass(frozen=True)
class ClientCredential:
    proxy_origin: str
    value: str
    source: Literal["environment", "keyring", "legacy", "generated"]


class ClientCredentialStore(Protocol):
    def get(self, proxy_origin: str) -> str | None: ...
    def set(self, proxy_origin: str, value: str) -> None: ...
    def delete(self, proxy_origin: str) -> bool: ...
```

The canonical keyring service name is `cutctx`. The account name is a stable,
non-secret digest of the normalized proxy origin prefixed with
`client-api-key:`. Normalization lowercases the host, removes default ports and
trailing slashes, and rejects URLs containing user information, query strings,
or fragments.

### 5.2 Platform backends

The default backend is Python `keyring`, which maps to:

- macOS Keychain
- Windows Credential Manager
- Linux Secret Service

If no secure keyring backend is available:

- interactive desktop setup fails with installation guidance;
- CI and containers use `CUTCTX_API_KEY` and do not persist it;
- an encrypted or mode-`0600` file fallback is not selected silently;
- an explicit future `--credential-store=file` compatibility mode may be
  added separately, but is outside this fix.

This avoids presenting plaintext filesystem storage as equivalent to an OS
credential facility.

### 5.3 Resolution precedence

For client processes:

1. non-empty `CUTCTX_API_KEY` from the current environment;
2. OS credential store entry for the normalized proxy origin;
3. no credential.

For proxy server verification:

1. explicit server configuration / `CUTCTX_CLIENT_API_KEY`;
2. OS credential store entry for the proxy's normalized public origin when
   running as the same interactive user;
3. no configured client authentication for loopback-only development
   instances;
4. startup failure for a non-loopback proxy without client authentication.

An environment override is never written back to the credential store.

## 6. CLI Experience

### 6.1 Commands

The CLI adds:

```text
cutctx auth login [--proxy-url URL]
cutctx auth status [--proxy-url URL]
cutctx auth rotate [--proxy-url URL]
cutctx auth logout [--proxy-url URL]
cutctx auth exec [--proxy-url URL] -- COMMAND [ARGS...]
```

`login` and `rotate` prompt with hidden input and confirmation where
appropriate. Secret-bearing command-line flags are intentionally unsupported.

`status` reports only:

- normalized proxy origin;
- whether a credential exists;
- credential source;
- validation state (`valid`, `invalid`, `expired`, `unreachable`, or
  `not_configured`);
- non-secret expiry metadata when the proxy exposes it.

`logout` removes only the selected origin's client credential.

`exec` resolves the credential and launches a child command with
`CUTCTX_API_KEY` set. It is the generic auth boundary used by wrappers and is
also available for third-party harnesses not yet known to Cutctx.

### 6.2 One-time local bootstrap

For a new loopback-only installation:

1. setup generates a cryptographically random client key with at least 256
   bits of entropy;
2. setup stores it in the OS credential store;
3. the local proxy reads the same origin-scoped credential;
4. the user is not asked to invent or copy a local key;
5. setup reports that client authentication was configured without printing
   the value.

For a remote proxy, the user enters the provisioned client key once through
`cutctx auth login`.

### 6.3 Validation and expiry

Before persisting a remote credential, `login` validates it against a
lightweight authenticated endpoint that exposes no administrative data.
`rotate` validates the replacement before overwriting the previous value.

If a stored key later receives an authentication response indicating expiry
or revocation, the wrapper stops before launching the harness and prints:

```text
Cutctx client authentication expired for https://proxy.example.com.
Run: cutctx auth login --proxy-url https://proxy.example.com
```

The key is not automatically deleted, allowing operators to distinguish
temporary server failures from confirmed revocation.

## 7. Shared Harness Launch Contract

All wrapper commands delegate to one helper before starting a proxy or harness:

```python
def apply_client_auth(
    env: dict[str, str],
    *,
    proxy_url: str,
    required: bool,
) -> ClientAuthResult:
    ...
```

The helper:

1. normalizes the proxy origin;
2. resolves the environment or keyring credential;
3. sets `env["CUTCTX_API_KEY"]` only in the returned child environment;
4. returns redaction-safe source and status metadata;
5. raises an actionable configuration error when authentication is required
   but unavailable.

This helper is called from the common `_launch_tool` boundary so existing and
future wrappers inherit the behavior without duplicating logic. Provider
runtime builders may continue constructing provider-specific base URLs; the
common launch boundary adds Cutctx client authentication afterward.

The covered wrappers include:

- Claude Code
- Codex CLI and Codex app launch helpers
- OpenCode
- Aider
- Gemini CLI
- GitHub Copilot CLI
- Cursor
- Windsurf
- Zed
- Antigravity
- Goose
- OpenHands
- OpenClaw
- any future wrapper using `_launch_tool` or `cutctx auth exec`

Wrappers that only print manual editor setup instructions must not print a
credential. Their instructions direct users to the authenticated Cutctx
launcher or MCP integration instead.

## 8. SDK, Plugin, and MCP Contract

### 8.1 Python and TypeScript SDKs

Both SDKs continue accepting:

```text
CUTCTX_API_KEY
Authorization: Bearer <client-key>
X-Cutctx-Api-Key: <client-key>
```

The SDK error type distinguishes:

- missing credential;
- invalid credential;
- expired credential;
- insufficient scope.

SDK fallback may preserve the original content, but it must rate-limit repeated
authentication warnings to one per client/session.

### 8.2 OpenCode and other plugins

Wrapped plugins receive `CUTCTX_API_KEY` through the shared child environment.
Plugin configuration files contain only proxy URLs and non-secret behavior
settings.

The OpenCode regression is fixed at the shared boundary, not with an
OpenCode-specific key reader.

### 8.3 MCP

`cutctx mcp serve` resolves the credential directly from the same
origin-scoped store. MCP registrar specifications contain `CUTCTX_PROXY_URL`
when required, but never contain `CUTCTX_API_KEY`.

The MCP server uses the client key only for agent routes. Administrative stats
remain unavailable; any model-facing statistics tool uses a narrowly scoped
agent stats endpoint or local session counters.

## 9. Migration and Compatibility

### 9.1 Existing admin-key installations

The current `~/.cutctx/admin_key.txt` remains an admin credential and is not
copied into the client store.

During the compatibility window:

1. an existing loopback proxy may accept the admin credential on agent routes
   for old SDKs;
2. setup generates and stores a separate client key;
3. new wrappers and MCP processes use only the client key;
4. a deprecation warning is emitted once when an admin credential authenticates
   an agent route;
5. a later major release removes this compatibility acceptance.

### 9.2 Existing environment users

Existing `CUTCTX_API_KEY` users continue working. Existing
`CUTCTX_ADMIN_API_KEY` users retain admin access but wrappers no longer
reinterpret that variable as the SDK client credential.

### 9.3 Existing harness config

No harness config receives a secret during migration. Existing Cutctx MCP
registrations may be updated to remove legacy secret-bearing environment
entries while preserving their proxy URL and command.

## 10. Error Handling

| Condition | Behavior |
| --- | --- |
| Secure keyring unavailable interactively | Stop setup with platform-specific remediation |
| Credential absent and remote auth required | Stop before harness launch |
| Credential invalid during login | Do not store it |
| Replacement invalid during rotation | Keep the existing credential |
| Credential expired at launch | Stop once with `cutctx auth login` remediation |
| Proxy unreachable during status | Report `unreachable`; do not mutate storage |
| Keyring read fails | Fail closed; do not fall back to admin or plaintext storage |
| SDK receives 401 mid-session | Preserve original content and warn once per session |
| Client key used on admin route | Return 401/403 without revealing route internals |
| Admin key used on agent route during transition | Accept, audit, and warn once |

## 11. Verification Strategy

The primary evidence path is an isolated end-to-end launch:

1. use a fake keyring backend and a synthetic client key;
2. start a loopback proxy configured with that client key;
3. launch a child probe through the common wrapper boundary;
4. assert the child sees `CUTCTX_API_KEY`;
5. call `/v1/compress` successfully with the client key;
6. assert the same key cannot access an admin route;
7. launch `cutctx mcp serve` against the same proxy and exercise compress and
   retrieve;
8. remove or expire the key and assert the wrapper refuses to launch;
9. inspect captured output and generated configs for the synthetic secret.

Supporting test layers:

- unit tests for URL normalization, store addressing, precedence, redaction,
  rotation atomicity, and failure modes;
- parameterized wrapper tests proving every wrapper using the shared launcher
  receives the common contract;
- proxy authorization tests proving client/admin/proxy credential separation;
- SDK contract tests for bearer and `X-Cutctx-Api-Key`;
- MCP registrar tests proving credentials are absent from persisted specs;
- OpenCode regression test reproducing the original history-compression 401;
- platform-adapter tests with mocked macOS, Windows, and Linux keyring backends;
- full targeted Python and TypeScript test suites;
- a secret scan over diffs, logs, generated configs, and subprocess display
  output.

## 12. Expected Code Boundaries

The implementation plan may refine exact names after repository inspection,
but the responsibilities remain:

- `cutctx/auth/client_credentials.py`: normalization, keyring store, resolution,
  and redaction-safe result types.
- `cutctx/cli/auth.py`: login, status, rotate, logout, and exec commands.
- `cutctx/proxy/client_auth.py`: least-privilege request dependency and
  constant-time verification.
- `cutctx/cli/wrap.py`: one shared child-environment integration point.
- `cutctx/integrations/mcp/`: client credential resolution at MCP runtime.
- `cutctx/mcp_registry/`: proxy URL only; never persisted credentials.
- `sdk/typescript/` and the Python SDK: consistent client-auth errors and
  headers.
- wrapper, proxy, SDK, MCP, and OpenCode regression tests.

## 13. Acceptance Criteria

The feature is complete when:

1. a new local user can set up Cutctx once and run every supported wrapper
   without re-entering a credential;
2. a remote user can run `cutctx auth login` once and reuse the key until
   expiry or rotation;
3. the OpenCode history-compression regression succeeds without an admin key;
4. the same client key succeeds on agent routes and fails on admin routes;
5. no generated harness or MCP config contains the client key;
6. `CUTCTX_API_KEY` still supports non-interactive CI/container use without
   persistence;
7. rotation never destroys a previously valid key when replacement validation
   fails;
8. all supported wrapper tests, proxy auth tests, SDK tests, MCP tests, and
   secret-redaction checks pass.
