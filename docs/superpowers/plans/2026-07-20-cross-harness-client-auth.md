# Cross-Harness Client Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a least-privilege, OS-keyring-backed Cutctx client credential that is configured once and reused safely by every supported wrapper, SDK plugin, and MCP process.

**Architecture:** A new `cutctx.auth.client_credentials` module owns proxy-origin normalization, keyring persistence, environment precedence, local key generation, and child-environment injection. A separate `cutctx.proxy.agent_auth` dependency protects compression and CCR routes without granting admin access. The CLI, setup flow, wrapper launcher, persistent runtime, MCP server, and TypeScript plugin all consume that shared contract.

**Tech Stack:** Python 3.11+, Click, keyring, FastAPI, httpx, pytest, TypeScript, Vitest, esbuild.

## Global Constraints

- `CUTCTX_API_KEY` is the client-side environment contract; `CUTCTX_CLIENT_API_KEY` is the proxy-side verifier contract.
- Do not reuse or distribute `CUTCTX_ADMIN_API_KEY`.
- Do not alter the existing `CUTCTX_PROXY_API_KEY` / `X-Cutctx-Proxy-Key` provider-route contract.
- Never persist credentials in harness configs, MCP configs, shell profiles, project files, command arguments, logs, telemetry, or display lists.
- Environment credentials override keyring credentials and are never written back.
- Keyring entries are scoped by normalized proxy origin.
- Non-loopback proxies fail startup without client authentication.
- Loopback setup generates at least 256 bits of entropy and stores it in the OS keyring.
- Interactive setup fails closed if no secure keyring backend is available.
- CI and containers use explicit `CUTCTX_API_KEY` / `CUTCTX_CLIENT_API_KEY` environment injection.
- All production changes follow red-green-refactor and preserve existing unrelated workspace changes.

---

## File Structure

| Path | Responsibility |
| --- | --- |
| `cutctx/auth/__init__.py` | Public client-credential exports |
| `cutctx/auth/client_credentials.py` | Origin normalization, keyring adapter, resolution, generation, child-env injection |
| `cutctx/proxy/agent_auth.py` | Least-privilege FastAPI authentication for SDK/MCP routes |
| `cutctx/cli/auth.py` | `login`, `status`, `rotate`, `logout`, and `exec` commands |
| `cutctx/cli/main.py` | Lazy registration and help grouping for `auth` |
| `cutctx/cli/setup.py` | One-time local client credential bootstrap |
| `cutctx/cli/proxy.py` | Resolve the stored verifier for manually launched proxies |
| `cutctx/cli/wrap.py` | Shared wrapper launch and proxy-process injection |
| `cutctx/install/runtime.py` | Persistent Python/container proxy credential injection |
| `cutctx/proxy/models.py` | `client_api_key` configuration field |
| `cutctx/proxy/server.py` | Agent auth dependency wiring and client status endpoint |
| `cutctx/proxy/deployment_security.py` | Non-loopback client-auth startup requirement |
| `cutctx/cli/mcp.py` | Keyring resolution before MCP server construction |
| `cutctx/mcp_server.py` | Client-authenticated retrieve/stats HTTP calls |
| `plugins/cutctx-opencode/cutctx.ts` | Rate-limited authentication warning behavior |
| `plugins/cutctx-opencode/dist/cutctx.js` | Rebuilt distributable plugin |
| `cutctx/providers/opencode/plugin/cutctx.js` | Packaged rebuilt plugin |
| `sdk/typescript/src/errors.ts` | Structured client-auth error metadata |
| `sdk/typescript/src/client.ts` | Preserve proxy auth error code/details |
| `tests/auth/test_client_credentials.py` | Credential-store and resolution unit tests |
| `tests/test_agent_client_auth.py` | Agent/admin endpoint privilege-separation tests |
| `tests/test_cli/test_auth.py` | Auth CLI tests |
| `tests/test_cli/test_setup.py` | One-time setup bootstrap tests |
| `tests/test_cli/test_wrap_client_auth.py` | Shared and direct wrapper launch tests |
| `tests/test_install_runtime.py` | Persistent runtime injection tests |
| `tests/test_cli/test_mcp.py` | MCP startup resolution tests |
| `tests/test_ccr_mcp_server.py` | MCP client header and no-admin regression tests |
| `plugins/cutctx-opencode/test/compress.test.ts` | OpenCode repeated-401 warning regression |
| `sdk/typescript/test/client.test.ts` | SDK client-auth error contract tests |
| `tests/test_cross_harness_client_auth_e2e.py` | End-to-end wrapper/proxy privilege and redaction evidence |
| `docs/content/docs/authentication.mdx` | User setup, rotation, CI, and troubleshooting documentation |

---

### Task 1: Origin-Scoped OS Credential Store

**Files:**
- Create: `cutctx/auth/__init__.py`
- Create: `cutctx/auth/client_credentials.py`
- Create: `tests/auth/test_client_credentials.py`

**Interfaces:**
- Produces `normalize_proxy_origin(proxy_url: str) -> str`.
- Produces `KeyringClientCredentialStore.get/set/delete`.
- Produces `resolve_client_credential(proxy_url, environ=None, store=None) -> ClientCredential | None`.
- Produces `ensure_local_client_credential(proxy_url, store=None) -> ClientCredential`.
- Produces `apply_client_auth(env, proxy_url, required, store=None) -> ClientAuthResult`.
- Produces `validate_client_credential(proxy_url, credential) -> ClientCredentialStatus`.

- [ ] **Step 1: Write failing normalization and storage-address tests**

```python
def test_normalize_proxy_origin_is_stable_and_rejects_secret_bearing_urls():
    assert normalize_proxy_origin("HTTP://LOCALHOST:80/v1/") == "http://localhost"
    assert normalize_proxy_origin("https://Proxy.Example:443/api") == "https://proxy.example"
    with pytest.raises(ClientCredentialConfigError):
        normalize_proxy_origin("https://user:secret@proxy.example")
    with pytest.raises(ClientCredentialConfigError):
        normalize_proxy_origin("https://proxy.example?key=secret")


def test_keyring_account_uses_non_secret_origin_digest(fake_keyring):
    store = KeyringClientCredentialStore(keyring_backend=fake_keyring)
    store.set("https://proxy.example", "client-secret")
    service, account, value = fake_keyring.saved
    assert service == "cutctx"
    assert account.startswith("client-api-key:")
    assert "proxy.example" not in account
    assert value == "client-secret"
```

- [ ] **Step 2: Run the tests and confirm RED**

Run: `rtk pytest tests/auth/test_client_credentials.py -q`

Expected: import failure because `cutctx.auth.client_credentials` does not exist.

- [ ] **Step 3: Implement the credential types, normalization, and keyring adapter**

```python
@dataclass(frozen=True)
class ClientCredential:
    proxy_origin: str
    value: str = field(repr=False)
    source: Literal["environment", "keyring", "generated"]


@dataclass(frozen=True)
class ClientAuthResult:
    proxy_origin: str
    configured: bool
    source: str | None


def normalize_proxy_origin(proxy_url: str) -> str:
    parsed = urlsplit(proxy_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ClientCredentialConfigError("Proxy URL must be an absolute HTTP(S) URL.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ClientCredentialConfigError(
            "Proxy URL must not contain user info, query credentials, or fragments."
        )
    port = parsed.port
    default_port = 80 if parsed.scheme == "http" else 443
    authority = parsed.hostname.lower()
    if port and port != default_port:
        authority = f"{authority}:{port}"
    return f"{parsed.scheme.lower()}://{authority}"


def _account_name(origin: str) -> str:
    digest = hashlib.sha256(origin.encode("utf-8")).hexdigest()
    return f"client-api-key:{digest}"
```

The adapter must catch keyring backend exceptions and raise
`ClientCredentialStoreError` without including the credential or backend
payload in the message.

- [ ] **Step 4: Add failing precedence, generation, and fail-closed tests**

```python
def test_environment_wins_without_persisting(fake_store):
    credential = resolve_client_credential(
        "http://127.0.0.1:8787",
        environ={"CUTCTX_API_KEY": "env-secret"},
        store=fake_store,
    )
    assert credential == ClientCredential(
        proxy_origin="http://127.0.0.1:8787",
        value="env-secret",
        source="environment",
    )
    assert fake_store.set_calls == []


def test_ensure_local_generates_256_bit_secret_once(fake_store):
    first = ensure_local_client_credential("http://127.0.0.1:8787", store=fake_store)
    second = ensure_local_client_credential("http://127.0.0.1:8787", store=fake_store)
    assert first.value == second.value
    assert len(base64.urlsafe_b64decode(first.value + "==")) >= 32
    assert len(fake_store.set_calls) == 1


def test_required_auth_fails_closed_when_keyring_unavailable(failing_store):
    with pytest.raises(ClientCredentialUnavailableError, match="cutctx auth login"):
        apply_client_auth(
            {},
            proxy_url="https://proxy.example",
            required=True,
            store=failing_store,
        )


@pytest.mark.parametrize(
    ("status_code", "payload", "expected"),
    [
        (200, {"status": "valid", "expires_at": None}, "valid"),
        (
            401,
            {"error": {"code": "invalid_client_key"}},
            "invalid",
        ),
        (
            401,
            {"error": {"code": "expired_client_key"}},
            "expired",
        ),
    ],
)
def test_validation_preserves_actionable_status(
    httpx_mock, status_code, payload, expected
):
    httpx_mock.add_response(status_code=status_code, json=payload)
    status = validate_client_credential(
        "https://proxy.example",
        ClientCredential(
            "https://proxy.example",
            "client-secret",
            "environment",
        ),
    )
    assert status.state == expected
```

- [ ] **Step 5: Run the tests and confirm RED**

Run: `rtk pytest tests/auth/test_client_credentials.py -q`

Expected: failures for missing resolver, generator, and environment helper.

- [ ] **Step 6: Implement resolution, generation, and child-environment injection**

Use `secrets.token_urlsafe(32)`. `apply_client_auth` mutates only the supplied
child environment and returns redaction-safe metadata. The shared validation
helper calls `/v1/auth/client/status`, maps stable proxy error codes to
`valid`, `invalid`, or `expired`, and never includes the supplied credential
in exceptions:

```python
def apply_client_auth(
    env: dict[str, str],
    *,
    proxy_url: str,
    required: bool,
    store: ClientCredentialStore | None = None,
) -> ClientAuthResult:
    credential = resolve_client_credential(proxy_url, environ=env, store=store)
    if credential is None:
        if required:
            raise ClientCredentialUnavailableError(
                f"Cutctx client authentication is not configured for "
                f"{normalize_proxy_origin(proxy_url)}. Run `cutctx auth login`."
            )
        return ClientAuthResult(normalize_proxy_origin(proxy_url), False, None)
    env["CUTCTX_API_KEY"] = credential.value
    return ClientAuthResult(credential.proxy_origin, True, credential.source)
```

- [ ] **Step 7: Run the complete credential-store tests**

Run: `rtk pytest tests/auth/test_client_credentials.py -q`

Expected: all tests pass with no credential values in captured logs or
assertion output.

- [ ] **Step 8: Commit**

```bash
rtk git add cutctx/auth tests/auth/test_client_credentials.py
rtk git commit -m "feat(auth): add origin-scoped client credential store"
```

---

### Task 2: Least-Privilege Agent Route Authentication

**Files:**
- Create: `cutctx/proxy/agent_auth.py`
- Create: `tests/test_agent_client_auth.py`
- Modify: `cutctx/proxy/models.py`
- Modify: `cutctx/proxy/server.py`
- Modify: `cutctx/proxy/deployment_security.py`
- Modify: `cutctx/cli/proxy.py`
- Modify: `tests/test_deployment_security.py`
- Modify: `tests/test_cli/test_proxy.py`
- Modify: `tests/test_runtime_app_admin_auth.py`
- Modify: `tests/test_ccr_admin_auth.py`

**Interfaces:**
- Produces `require_agent_client(request, config) -> AgentAuthIdentity`.
- Adds `ProxyConfig.client_api_key: str | None`.
- Agent routes accept bearer or `X-Cutctx-Api-Key`; admin routes remain admin-only.

- [ ] **Step 1: Write failing privilege-separation tests**

```python
@pytest.fixture
def separated_client():
    app = create_app(
        ProxyConfig(
            host="127.0.0.1",
            admin_api_key="admin-secret",
            client_api_key="client-secret",
            optimize=False,
        )
    )
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield client


def test_client_key_can_compress_but_cannot_read_admin_stats(separated_client):
    headers = {"Authorization": "Bearer client-secret"}
    compressed = separated_client.post(
        "/v1/compress",
        headers=headers,
        json={"messages": [], "model": "gpt-4o"},
    )
    stats = separated_client.get("/stats", headers=headers)
    assert compressed.status_code == 200
    assert stats.status_code == 401


def test_admin_key_compatibility_on_agent_route_is_audited_once(separated_client, caplog):
    response = separated_client.post(
        "/v1/compress",
        headers={"Authorization": "Bearer admin-secret"},
        json={"messages": [], "model": "gpt-4o"},
    )
    assert response.status_code == 200
    assert sum("deprecated_agent_admin_auth" in r.message for r in caplog.records) == 1
```

- [ ] **Step 2: Run the tests and confirm RED**

Run: `rtk pytest tests/test_agent_client_auth.py -q`

Expected: `ProxyConfig` rejects `client_api_key` and `/v1/compress` still
requires the admin credential.

- [ ] **Step 3: Implement the agent auth dependency**

```python
@dataclass(frozen=True)
class AgentAuthIdentity:
    kind: Literal["client", "admin_compat", "loopback_open"]


def require_agent_client(request: Request, config: Any) -> AgentAuthIdentity:
    expected = getattr(config, "client_api_key", None) or os.getenv(
        "CUTCTX_CLIENT_API_KEY"
    )
    if not expected:
        if is_loopback_host(getattr(config, "host", None)):
            return AgentAuthIdentity("loopback_open")
        raise AgentClientAuthError("Cutctx client authentication is required.")
    supplied = _bearer(request.headers) or request.headers.get(
        "x-cutctx-api-key", ""
    )
    if supplied and hmac.compare_digest(supplied, expected):
        return AgentAuthIdentity("client")
    if _matches_admin_compat(request, config):
        _warn_admin_compat_once()
        return AgentAuthIdentity("admin_compat")
    raise AgentClientAuthError("Invalid or expired Cutctx client credential.")
```

Wire a FastAPI wrapper that returns a stable payload:

```json
{
  "error": {
    "type": "client_authentication_error",
    "code": "invalid_or_expired_client_key",
    "message": "Invalid or expired Cutctx client credential.",
    "remediation": "Run `cutctx auth login --proxy-url <origin>`."
  }
}
```

- [ ] **Step 4: Replace admin dependencies only on agent routes**

Change the dependencies for `/v1/compress`, `/v1/retrieve`,
`/v1/retrieve/{hash}`, `/v1/retrieve/stats`, and
`/v1/retrieve/tool_call`. Do not change admin routers, hosted compression,
provider routes, `/stats`, or `/metrics`.

Add `GET /v1/auth/client/status` behind the client dependency and return only:

```python
{"status": "valid", "scope": "agent", "expires_at": None}
```

Before the Click proxy command builds `ProxyConfig`, resolve the verifier with
this precedence:

1. explicit `CUTCTX_CLIENT_API_KEY`;
2. `CUTCTX_API_KEY` for a foreground process intentionally configured with
   one shared environment secret;
3. the OS-keyring entry for the normalized loopback bind origin, or for the
   explicit `CUTCTX_PUBLIC_URL` origin on a non-loopback listener.

Assign only the resolved value to `ProxyConfig.client_api_key`. For
non-loopback and wildcard bind addresses, accept either
`CUTCTX_CLIENT_API_KEY` from the deployment secret environment or a keyring
entry addressed by explicit `CUTCTX_PUBLIC_URL`; never guess a loopback or
public origin. Add tests proving `0.0.0.0` without either source fails closed.

- [ ] **Step 5: Add and verify non-loopback deployment tests**

```python
def test_non_loopback_requires_dedicated_agent_client_key():
    with pytest.raises(DeploymentSecurityError, match="client authentication"):
        require_secure_deployment(
            ProxyConfig(
                host="0.0.0.0",
                admin_api_key="admin",
                proxy_api_key="proxy",
                client_api_key=None,
            )
        )
```

Run:

```bash
rtk pytest tests/test_agent_client_auth.py tests/test_deployment_security.py \
  tests/test_runtime_app_admin_auth.py tests/test_ccr_admin_auth.py \
  tests/test_cli/test_proxy.py -q
```

Expected: all tests pass; existing admin and provider-route tests remain green.

- [ ] **Step 6: Commit**

```bash
rtk git add cutctx/proxy tests/test_agent_client_auth.py \
  tests/test_deployment_security.py tests/test_runtime_app_admin_auth.py \
  tests/test_ccr_admin_auth.py cutctx/cli/proxy.py tests/test_cli/test_proxy.py
rtk git commit -m "feat(auth): separate agent credentials from admin access"
```

---

### Task 3: Auth CLI and One-Time Setup

**Files:**
- Create: `cutctx/cli/auth.py`
- Create: `tests/test_cli/test_auth.py`
- Modify: `cutctx/cli/main.py`
- Modify: `cutctx/cli/setup.py`
- Modify: `tests/test_cli/test_setup.py`

**Interfaces:**
- Adds `cutctx auth login|status|rotate|logout|exec`.
- Setup calls `ensure_local_client_credential`.
- Remote credentials are validated before persistence.

- [ ] **Step 1: Write failing CLI tests**

```python
def test_login_hides_input_validates_then_stores(runner, fake_store, monkeypatch):
    monkeypatch.setattr(auth_mod, "_store", lambda: fake_store)
    monkeypatch.setattr(auth_mod, "_validate", lambda origin, key: AuthStatus("valid"))
    result = runner.invoke(
        main,
        ["auth", "login", "--proxy-url", "https://proxy.example"],
        input="client-secret\n",
    )
    assert result.exit_code == 0
    assert fake_store.get("https://proxy.example") == "client-secret"
    assert "client-secret" not in result.output


def test_rotate_keeps_old_key_when_replacement_is_invalid(
    runner, fake_store, monkeypatch
):
    monkeypatch.setattr(auth_mod, "_store", lambda: fake_store)
    monkeypatch.setattr(
        auth_mod,
        "_validate",
        lambda origin, key: AuthStatus("invalid"),
    )
    fake_store.set("https://proxy.example", "old-secret")
    result = runner.invoke(
        main,
        ["auth", "rotate", "--proxy-url", "https://proxy.example"],
        input="bad-secret\n",
    )
    assert result.exit_code != 0
    assert fake_store.get("https://proxy.example") == "old-secret"


def test_status_reports_expired_without_printing_key(
    runner, fake_store, monkeypatch
):
    fake_store.set("https://proxy.example", "client-secret")
    monkeypatch.setattr(auth_mod, "_store", lambda: fake_store)
    monkeypatch.setattr(
        auth_mod,
        "validate_client_credential",
        lambda origin, credential: ClientCredentialStatus("expired"),
    )
    result = runner.invoke(
        main,
        ["auth", "status", "--proxy-url", "https://proxy.example"],
    )
    assert result.exit_code != 0
    assert "expired" in result.output.lower()
    assert "client-secret" not in result.output


def test_exec_injects_key_without_putting_it_in_argv(
    runner, fake_store, monkeypatch
):
    captured = {}
    fake_store.set("https://proxy.example", "client-secret")
    monkeypatch.setattr(auth_mod, "_store", lambda: fake_store)
    monkeypatch.setattr(
        auth_mod.subprocess,
        "run",
        lambda command, env: captured.update(command=command, env=env)
        or SimpleNamespace(returncode=0),
    )
    result = runner.invoke(
        main,
        ["auth", "exec", "--proxy-url", "https://proxy.example", "--", "probe"],
    )
    assert captured["command"] == ("probe",)
    assert captured["env"]["CUTCTX_API_KEY"] == "client-secret"
    assert "client-secret" not in result.output
```

- [ ] **Step 2: Run the tests and confirm RED**

Run: `rtk pytest tests/test_cli/test_auth.py -q`

Expected: `cutctx auth` is not registered.

- [ ] **Step 3: Register and implement the command group**

Add `"auth": "auth"` to `_SIDE_EFFECT_COMMAND_MODULES` and `"auth"` to the
Getting Started help group. Implement hidden Click prompts:

```python
key = click.prompt(
    "Cutctx client API key",
    hide_input=True,
    confirmation_prompt=False,
    type=str,
).strip()
```

Use the shared validation helper from Task 1, which sends:

```python
httpx.get(
    f"{origin}/v1/auth/client/status",
    headers={"Authorization": f"Bearer {key}"},
    timeout=5.0,
)
```

`login` and `rotate` validate before `store.set`. `status` never prints the key
and distinguishes missing, invalid, expired, unreachable, and valid states.
`logout` removes only the selected origin. `exec` uses
`subprocess.run(command, env=child_env)` and never appends the key to the
command.

- [ ] **Step 4: Write failing local setup bootstrap tests**

```python
def test_setup_bootstraps_client_auth_before_start(monkeypatch):
    events = []
    checks = iter(
        [
            {"running": False, "status": None},
            {"running": True, "status": 200},
        ]
    )
    synthetic_credential = ClientCredential(
        "http://127.0.0.1:8787",
        "synthetic-secret",
        "generated",
    )
    monkeypatch.setattr(setup_mod, "_check_cutctx_installed", lambda: True)
    monkeypatch.setattr(setup_mod, "_detect_agents", lambda: [])
    monkeypatch.setattr(setup_mod, "_check_health", lambda port: next(checks))
    monkeypatch.setattr(
        setup_mod,
        "ensure_local_client_credential",
        lambda url: events.append(("auth", url)) or synthetic_credential,
    )
    monkeypatch.setattr(
        setup_mod,
        "_start_proxy",
        lambda port, client_api_key: events.append(
            ("proxy", port, client_api_key)
        )
        or True,
    )
    result = CliRunner().invoke(
        setup_mod.setup,
        ["--no-detect", "--no-mcp"],
    )
    assert result.exit_code == 0
    assert events[0] == ("auth", "http://127.0.0.1:8787")
    assert events[1] == ("proxy", 8787, "synthetic-secret")
    assert "synthetic-secret" not in result.output
```

- [ ] **Step 5: Implement setup bootstrap and fail-closed messaging**

Expand setup to six explicit stages, with client authentication before MCP
registration and proxy startup. Pass the generated value to the proxy only
through the subprocess environment as `CUTCTX_CLIENT_API_KEY`; never include
it in argv or setup output. On keyring failure, print the platform-neutral
remediation:

```text
Secure credential storage is unavailable.
Install/configure an OS keyring backend, or set CUTCTX_API_KEY and
CUTCTX_CLIENT_API_KEY through your CI/container secret manager.
```

- [ ] **Step 6: Run CLI and setup tests**

Run:

```bash
rtk pytest tests/test_cli/test_auth.py tests/test_cli/test_setup.py \
  tests/test_cli/test_main_help_version.py -q
```

Expected: all tests pass and captured output contains no synthetic secrets.

- [ ] **Step 7: Commit**

```bash
rtk git add cutctx/cli/auth.py cutctx/cli/main.py cutctx/cli/setup.py \
  tests/test_cli/test_auth.py tests/test_cli/test_setup.py \
  tests/test_cli/test_main_help_version.py
rtk git commit -m "feat(auth): add secure login and local bootstrap"
```

---

### Task 4: Shared Wrapper and Persistent Runtime Injection

**Files:**
- Modify: `cutctx/cli/wrap.py`
- Modify: `cutctx/install/runtime.py`
- Create: `tests/test_cli/test_wrap_client_auth.py`
- Modify: `tests/test_install_runtime.py`
- Modify: existing wrapper tests only where direct launch seams require coverage

**Interfaces:**
- `_launch_tool` resolves once, injects `CUTCTX_API_KEY` into the harness child,
  and passes the same value as `CUTCTX_CLIENT_API_KEY` to a newly started
  private proxy.
- `_launch_tool(..., client_credential_origin: str | None = None)` separates
  the stable credential scope from an ephemeral private proxy connection URL.
- Direct Claude and proxy-only watcher paths call the same helper.
- Persistent Python and container runtimes inject only the server-side name.

- [ ] **Step 1: Write failing common-launch and direct-launch tests**

```python
def test_common_launcher_injects_client_key_and_redacts_display(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        wrap_mod,
        "resolve_client_credential",
        lambda url, environ: ClientCredential(url, "client-secret", "keyring"),
    )
    monkeypatch.setattr(wrap_mod, "_register_proxy_client", lambda port: None)
    monkeypatch.setattr(wrap_mod, "_make_cleanup", lambda holder, port: lambda: None)
    monkeypatch.setattr(wrap_mod, "_ensure_proxy", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        wrap_mod.subprocess,
        "run",
        lambda command, env: captured.update(command=command, env=env)
        or SimpleNamespace(returncode=0),
    )
    with pytest.raises(SystemExit) as exc:
        wrap_mod._launch_tool(
            binary="probe",
            args=(),
            env={},
            port=8787,
            no_proxy=False,
            tool_label="PROBE",
            env_vars_display=["CUTCTX_BASE_URL=http://127.0.0.1:8787"],
        )
    assert exc.value.code == 0
    assert captured["env"]["CUTCTX_API_KEY"] == "client-secret"


def test_started_proxy_receives_server_side_client_name(monkeypatch):
    captured = {}
    monkeypatch.setattr(wrap_mod, "_check_proxy_ready", lambda port: True)
    monkeypatch.setattr(
        wrap_mod.subprocess,
        "Popen",
        lambda command, **kwargs: captured.update(command=command, kwargs=kwargs)
        or SimpleNamespace(poll=lambda: None),
    )
    wrap_mod._start_proxy(8787, client_api_key="client-secret")
    proxy_env = captured["kwargs"]["env"]
    assert proxy_env["CUTCTX_CLIENT_API_KEY"] == "client-secret"
    assert "CUTCTX_API_KEY" not in proxy_env


def test_ephemeral_launcher_uses_requested_port_credential(monkeypatch):
    origins = []
    captured = {}
    monkeypatch.setattr(
        wrap_mod,
        "resolve_client_credential",
        lambda url, environ: origins.append(url)
        or ClientCredential(url, "client-secret", "keyring"),
    )
    monkeypatch.setattr(
        wrap_mod,
        "_ensure_proxy",
        lambda port, **kwargs: captured.update(port=port, **kwargs),
    )
    monkeypatch.setattr(wrap_mod, "_register_proxy_client", lambda port: None)
    monkeypatch.setattr(wrap_mod, "_make_cleanup", lambda holder, port: lambda: None)
    monkeypatch.setattr(
        wrap_mod.subprocess,
        "run",
        lambda command, env: SimpleNamespace(returncode=0),
    )
    with pytest.raises(SystemExit):
        wrap_mod._launch_tool(
            binary="probe",
            args=(),
            env={},
            port=54321,
            no_proxy=False,
            tool_label="PROBE",
            env_vars_display=[],
            client_credential_origin="http://127.0.0.1:8787",
        )
    assert origins == ["http://127.0.0.1:8787"]
    assert captured["port"] == 54321
    assert captured["client_api_key"] == "client-secret"
```

- [ ] **Step 2: Run the wrapper tests and confirm RED**

Run:

```bash
rtk pytest tests/test_cli/test_wrap_client_auth.py \
  tests/test_cli/test_wrap_opencode.py -q
```

Expected: child environments lack `CUTCTX_API_KEY`.

- [ ] **Step 3: Resolve once at the shared launch boundary**

At the beginning of `_launch_tool`, before `_ensure_proxy`, call:

```python
proxy_url = f"http://127.0.0.1:{port}"
credential_origin = client_credential_origin or proxy_url
credential = resolve_client_credential(credential_origin, environ=env)
if credential is not None:
    env["CUTCTX_API_KEY"] = credential.value
client_api_key = credential.value if credential is not None else None
```

Thread `client_api_key` through `_ensure_proxy` and `_start_proxy`; set only
`proxy_env["CUTCTX_CLIENT_API_KEY"]`. Do not append either key to
`env_vars_display`.

After `_ensure_proxy` reports ready and before spawning the harness, call the
Task 1 validation helper against the actual connection URL using the resolved
credential. Abort with an actionable `cutctx auth login`/`rotate` message for
invalid or expired credentials. Preserve the existing explicit behavior for
an unreachable remote proxy. This makes expired credentials fail once at the
launch boundary instead of producing warning storms inside every harness.

Factor the same operation into a small `_apply_wrap_client_auth` helper and
call it from the direct Claude flow and proxy-only watcher paths. OpenCode
receives both `CUTCTX_BASE_URL` and `CUTCTX_API_KEY` automatically.

When OpenCode reassigns a shared requested port to an ephemeral private port,
pass the pre-reassignment loopback origin as `client_credential_origin`. The
private proxy listens on the assigned port but uses the existing requested
origin's credential. This prevents every ephemeral port from creating a new
keyring entry.

- [ ] **Step 4: Add persistent runtime RED tests**

```python
def test_runtime_env_injects_keyring_client_key(monkeypatch, manifest):
    monkeypatch.setattr(
        runtime,
        "resolve_client_credential",
        lambda url: ClientCredential(url, "client-secret", "keyring"),
    )
    env = runtime._runtime_env(manifest)
    assert env["CUTCTX_CLIENT_API_KEY"] == "client-secret"
    assert "CUTCTX_API_KEY" not in env


def test_container_command_passes_client_key_by_name_not_value(
    monkeypatch, manifest
):
    monkeypatch.setattr(
        runtime,
        "resolve_client_credential",
        lambda url: ClientCredential(url, "client-secret", "keyring"),
    )
    command = build_runtime_command(manifest)
    assert "CUTCTX_CLIENT_API_KEY" in command
    assert all("client-secret" not in arg for arg in command)
```

- [ ] **Step 5: Implement persistent Python/container handling**

Python user services may resolve the key and place it in their process
environment. Docker commands must use `--env CUTCTX_CLIENT_API_KEY` with the
value supplied to the Docker subprocess environment, never
`--env CUTCTX_CLIENT_API_KEY=<value>` in argv.

- [ ] **Step 6: Run all wrapper and runtime tests**

Run:

```bash
rtk pytest tests/test_cli/test_wrap_*.py tests/test_install_runtime.py -q
```

Expected: all wrapper families pass; no captured display or argv contains a
synthetic secret.

- [ ] **Step 7: Commit**

```bash
rtk git add cutctx/cli/wrap.py cutctx/install/runtime.py \
  tests/test_cli/test_wrap_client_auth.py tests/test_cli/test_wrap_*.py \
  tests/test_install_runtime.py
rtk git commit -m "fix(wrap): propagate client auth across all harnesses"
```

---

### Task 5: MCP Uses Client Auth Without Persisting It

**Files:**
- Modify: `cutctx/cli/mcp.py`
- Modify: `cutctx/mcp_server.py`
- Modify: `cutctx/mcp_registry/install.py`
- Modify: `tests/test_cli/test_mcp.py`
- Modify: `tests/test_ccr_mcp_server.py`
- Modify: MCP registry tests

**Interfaces:**
- `create_ccr_mcp_server(proxy_url: str, api_key: str | None = None)`.
- `CutctxMCPServer(proxy_url: str, api_key: str | None = None)` uses
  `_agent_headers`.
- MCP specs contain a proxy URL only.

- [ ] **Step 1: Write failing MCP auth and persistence tests**

```python
def test_mcp_serve_resolves_origin_scoped_client_key(monkeypatch, runner):
    factory_kwargs = {}
    fake_server = SimpleNamespace(
        run_stdio=AsyncMock(),
        cleanup=AsyncMock(),
    )
    monkeypatch.setattr(
        mcp_cli,
        "resolve_client_credential",
        lambda url: ClientCredential(url, "client-secret", "keyring"),
    )
    monkeypatch.setattr(
        "cutctx.mcp_server.create_ccr_mcp_server",
        lambda **kwargs: factory_kwargs.update(kwargs) or fake_server,
    )
    result = runner.invoke(
        main,
        ["mcp", "serve", "--proxy-url", "https://proxy.example"],
    )
    assert result.exit_code == 0
    assert factory_kwargs["api_key"] == "client-secret"


async def test_proxy_retrieve_uses_client_not_admin_header(httpx_mock):
    server = CutctxMCPServer(
        proxy_url="http://127.0.0.1:8787",
        api_key="client-secret",
    )
    await server._retrieve_via_proxy("hash", None)
    request = httpx_mock.get_request()
    assert request.headers["Authorization"] == "Bearer client-secret"
    assert "x-cutctx-admin-key" not in request.headers


def test_registered_mcp_spec_never_persists_client_key(monkeypatch):
    monkeypatch.setenv("CUTCTX_API_KEY", "client-secret")
    spec = build_cutctx_spec("https://proxy.example")
    assert spec.env == {"CUTCTX_PROXY_URL": "https://proxy.example"}
    assert "client-secret" not in repr(spec)
```

- [ ] **Step 2: Run tests and confirm RED**

Run:

```bash
rtk pytest tests/test_cli/test_mcp.py tests/test_ccr_mcp_server.py \
  tests/test_mcp_registry.py -q
```

Expected: the server factory has no API-key parameter and proxy retrieval sends
no client header.

- [ ] **Step 3: Implement MCP runtime resolution and client headers**

Resolve in `mcp_serve` and pass the value in memory. Add:

```python
def _agent_headers(self) -> dict[str, str]:
    if not self.api_key:
        return {}
    return {"Authorization": f"Bearer {self.api_key}"}
```

Use it only for agent endpoints. Keep `_admin_headers` exclusively for
explicit administrative MCP tools such as audit and organization management.
Stop using `/stats` from the model-facing `cutctx_stats` tool; combine local
session stats with `/v1/retrieve/stats`, which is agent-scoped.

- [ ] **Step 4: Verify MCP behavior and config redaction**

Run:

```bash
rtk pytest tests/test_cli/test_mcp.py tests/test_ccr_mcp_server.py \
  tests/test_mcp_registry.py tests/test_mcp_registry_codex.py \
  tests/test_mcp_registry_claude.py -q
```

Expected: all tests pass and MCP specs contain no client or admin secret.

- [ ] **Step 5: Commit**

```bash
rtk git add cutctx/cli/mcp.py cutctx/mcp_server.py cutctx/mcp_registry \
  tests/test_cli/test_mcp.py tests/test_ccr_mcp_server.py \
  tests/test_mcp_registry*.py
rtk git commit -m "fix(mcp): resolve least-privilege client auth at runtime"
```

---

### Task 6: SDK Error Contract and OpenCode Regression

**Files:**
- Modify: `sdk/typescript/src/errors.ts`
- Modify: `sdk/typescript/src/client.ts`
- Modify: `sdk/typescript/test/client.test.ts`
- Modify: `plugins/cutctx-opencode/cutctx.ts`
- Modify: `plugins/cutctx-opencode/test/compress.test.ts`
- Rebuild: `plugins/cutctx-opencode/dist/cutctx.js`
- Replace: `cutctx/providers/opencode/plugin/cutctx.js`

**Interfaces:**
- `CutctxAuthError` carries `code` and `remediation`.
- OpenCode emits one authentication warning per plugin process while
  preserving original output/history.

- [ ] **Step 1: Write failing SDK error-metadata test**

```typescript
it("preserves client auth code and remediation from a 401", async () => {
  mockFetch.mockResolvedValueOnce(errorResponse(401, {
    error: {
      type: "client_authentication_error",
      code: "invalid_or_expired_client_key",
      message: "Invalid or expired Cutctx client credential.",
      remediation: "Run cutctx auth login.",
    },
  }));
  const client = new CutctxClient({ baseUrl: "http://localhost:8787" });
  await expect(client.compress(sampleMessages)).rejects.toMatchObject({
    name: "CutctxAuthError",
    details: {
      code: "invalid_or_expired_client_key",
      remediation: "Run cutctx auth login.",
    },
  });
});
```

- [ ] **Step 2: Run the SDK test and confirm RED**

Run: `cd sdk/typescript && rtk npm test -- --run test/client.test.ts`

Expected: auth error details do not contain the proxy code/remediation.

- [ ] **Step 3: Pass structured proxy error metadata into `mapProxyError`**

Change `mapProxyError` to accept the parsed error object, preserving only
redaction-safe fields:

```typescript
if (status === 401) {
  return new CutctxAuthError(message, {
    code: error.code,
    remediation: error.remediation,
  });
}
```

- [ ] **Step 4: Write failing OpenCode repeated-warning tests**

```typescript
it("warns once for repeated authentication failures", async () => {
  const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.mocked(compress).mockRejectedValue(new CutctxAuthError(
    "Invalid or expired Cutctx client credential.",
    { code: "invalid_or_expired_client_key" },
  ));
  const handlers = await plugin(fakeInput());
  await runLargeToolOutput(handlers);
  await runLargeToolOutput(handlers);
  expect(warn).toHaveBeenCalledTimes(1);
  expect(warn.mock.calls[0]![0]).toContain("cutctx auth login");
});
```

- [ ] **Step 5: Run the plugin test and confirm RED**

Run: `cd plugins/cutctx-opencode && rtk npm test -- --run test/compress.test.ts`

Expected: two warnings are emitted.

- [ ] **Step 6: Add session-scoped auth warning suppression**

Use a module-level boolean only for `CutctxAuthError`; unrelated compression
errors retain their existing warning behavior. Preserve tool output and history
unchanged on failure.

- [ ] **Step 7: Build and verify packaged artifacts**

Run:

```bash
cd plugins/cutctx-opencode
rtk npm run typecheck
rtk npm test
rtk npm run build
cmp dist/cutctx.js ../../cutctx/providers/opencode/plugin/cutctx.js ||
  cp dist/cutctx.js ../../cutctx/providers/opencode/plugin/cutctx.js
```

Expected: typecheck and tests pass; the packaged plugin is byte-identical to
the rebuilt distributable after copying.

- [ ] **Step 8: Commit**

```bash
rtk git add sdk/typescript plugins/cutctx-opencode \
  cutctx/providers/opencode/plugin/cutctx.js
rtk git commit -m "fix(opencode): use shared client auth and suppress warning storms"
```

---

### Task 7: End-to-End Evidence, Documentation, and Final Verification

**Files:**
- Create: `tests/test_cross_harness_client_auth_e2e.py`
- Create or modify: `docs/content/docs/authentication.mdx`
- Modify: `docs/content/docs/troubleshooting.mdx`
- Modify: `README.md`

**Interfaces:**
- Establishes the approved acceptance criteria across proxy, wrapper, MCP, and
  redaction boundaries.

- [ ] **Step 1: Write the failing end-to-end test**

```python
def test_client_key_round_trip_and_admin_separation(
    tmp_path, fake_keyring, monkeypatch
):
    key = "synthetic-client-key-for-e2e"
    origin = "http://127.0.0.1:8787"
    store = KeyringClientCredentialStore(keyring_backend=fake_keyring)
    store.set(origin, key)
    child_env = {}
    auth_result = apply_client_auth(
        child_env,
        proxy_url=origin,
        required=True,
        store=store,
    )
    assert auth_result.configured is True
    assert child_env["CUTCTX_API_KEY"] == key

    app = create_app(
        ProxyConfig(
            host="127.0.0.1",
            client_api_key=key,
            admin_api_key="synthetic-admin",
            optimize=False,
            cache_enabled=False,
            rate_limit_enabled=False,
        )
    )
    headers = {"Authorization": f"Bearer {child_env['CUTCTX_API_KEY']}"}
    with TestClient(app, base_url=origin) as client:
        compress = client.post(
            "/v1/compress",
            headers=headers,
            json={"messages": [], "model": "gpt-4o"},
        )
        retrieve_stats = client.get("/v1/retrieve/stats", headers=headers)
        admin_stats = client.get("/stats", headers=headers)

    assert compress.status_code == 200
    assert retrieve_stats.status_code == 200
    assert admin_stats.status_code == 401
    mcp_spec = build_cutctx_spec(origin)
    assert key not in repr(mcp_spec)
```

- [ ] **Step 2: Run it and confirm RED**

Run: `rtk pytest tests/test_cross_harness_client_auth_e2e.py -q`

Expected: one or more integration seams are not yet wired or the helper does
not exist.

- [ ] **Step 3: Complete only the missing integration wiring exposed by RED**

Do not add new credential mechanisms. Use the Task 1 store, Task 2 dependency,
Task 4 launcher, and Task 5 MCP path. Re-run until the end-to-end test passes.

- [ ] **Step 4: Document setup and rotation**

Document these exact flows:

```bash
# Local interactive setup: generates and stores a client credential
cutctx setup

# Remote proxy: prompt once, store in the OS credential manager
cutctx auth login --proxy-url https://proxy.example

# Inspect without displaying the secret
cutctx auth status --proxy-url https://proxy.example

# Validate replacement before overwriting the current key
cutctx auth rotate --proxy-url https://proxy.example

# Generic third-party CLI launch
cutctx auth exec --proxy-url https://proxy.example -- third-party-agent

# CI/container injection through the platform secret manager
CUTCTX_API_KEY="$CI_CUTCTX_API_KEY" cutctx wrap opencode
```

State explicitly that `CUTCTX_ADMIN_API_KEY` must not be used as the client
credential and that MCP/harness configs never contain the key.

- [ ] **Step 5: Run targeted security and behavior verification**

Run:

```bash
rtk pytest tests/auth/test_client_credentials.py \
  tests/test_agent_client_auth.py \
  tests/test_cli/test_auth.py \
  tests/test_cli/test_setup.py \
  tests/test_cli/test_wrap_client_auth.py \
  tests/test_install_runtime.py \
  tests/test_cli/test_mcp.py \
  tests/test_ccr_mcp_server.py \
  tests/test_cross_harness_client_auth_e2e.py -q
cd sdk/typescript && rtk npm test
cd ../../plugins/cutctx-opencode && rtk npm run typecheck
rtk npm test
```

Expected: all targeted Python and TypeScript tests pass.

- [ ] **Step 6: Run broader regression verification**

Run:

```bash
rtk pytest tests/test_cli tests/test_proxy_client_auth.py \
  tests/test_runtime_app_admin_auth.py tests/test_proxy_compress_endpoint.py \
  tests/test_ccr_admin_auth.py -q
rtk ruff check cutctx/auth cutctx/cli/auth.py cutctx/proxy/agent_auth.py \
  cutctx/cli/wrap.py cutctx/install/runtime.py cutctx/mcp_server.py
rtk mypy cutctx/auth cutctx/cli/auth.py cutctx/proxy/agent_auth.py
```

Expected: zero failures, lint errors, or type errors.

- [ ] **Step 7: Run a diff and artifact secret scan**

Use a synthetic sentinel, never a real key:

```bash
RIPGREP_CONFIG_PATH= rg -n \
  'synthetic-client-key-for-e2e|client-secret|CUTCTX_API_KEY.*=' \
  docs README.md cutctx/providers/opencode/plugin/cutctx.js \
  plugins/cutctx-opencode/dist/cutctx.js
rtk git diff --check
rtk git status --short
```

Expected: no persisted synthetic key in production artifacts or docs; examples
reference secret-manager variables rather than literal credentials; diff check
passes.

- [ ] **Step 8: Commit**

```bash
rtk git add tests/test_cross_harness_client_auth_e2e.py \
  docs/content/docs/authentication.mdx \
  docs/content/docs/troubleshooting.mdx README.md
rtk git commit -m "docs(auth): document cross-harness credential lifecycle"
```

- [ ] **Step 9: Final acceptance audit**

Re-read
`docs/superpowers/specs/2026-07-20-cross-harness-client-auth-design.md` and
record evidence for all eight acceptance criteria in the final handoff:

1. one-time local setup;
2. one-time remote login;
3. OpenCode history compression without admin auth;
4. agent/admin privilege separation;
5. no secrets in generated config;
6. CI environment support;
7. atomic rotation;
8. full targeted verification.
