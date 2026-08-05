# Desktop Secure Credential Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove plaintext desktop API and license secrets while preserving managed proxy startup through a shared OS-keychain credential.

**Architecture:** Rust Control stores secrets through an injected `SecretStore` abstraction backed by keyring-rs 3.6.3 in production and deterministic memory/failure stores in tests. `credentials.json` retains only masked metadata. The Python proxy resolves the same service/account before legacy file/cache fallbacks, so a desktop-managed runtime can start without `license_key.txt`.

**Tech Stack:** Rust 1.77.2, Tauri 2, keyring-rs 3.6.3, Python 3.12, pytest, Ruff 0.9.4.

## Global Constraints

- Follow strict RED → GREEN → REFACTOR for every production behavior change.
- Preserve the existing dirty `uv.lock`; never stage it.
- Never read, print, or migrate the operator's real credentials during tests.
- Use temporary homes and injected stores only.
- Do not place secrets in argv, logs, Tauri return values, launch configuration, or metadata files.
- Delete a legacy plaintext file only after the secure-store write and metadata persistence succeed.
- Keep keyring-rs pinned to `3.6.3`; keyring 4 requires Rust 1.88 and violates the crate's 1.77.2 floor.

---

## File Structure

- `desktop/cutctx-control/src-tauri/src/credentials.rs`: secure-store interface, keyring implementation, metadata-only vault, and legacy migration.
- `desktop/cutctx-control/src-tauri/Cargo.toml`: target-native keyring dependency features.
- `desktop/cutctx-control/src-tauri/Cargo.lock`: reproducible desktop dependency graph.
- `cutctx/auth/operator_credentials.py`: shared service/account constants and bounded Python keyring read.
- `cutctx/proxy/deployment_security.py`: keyring-first local license resolution with legacy fallbacks.
- `cutctx/cli/wrap.py`: reuse the shared license resolver instead of duplicating plaintext-file logic.
- `tests/auth/test_operator_credentials.py`: Python secure-store contract tests.
- `tests/test_deployment_security.py`: proxy resolution precedence and fallback tests.
- `tests/test_cli/test_wrap_helpers.py`: wrapper keyring license resolution test.

### Task 1: Metadata-only Rust vault with injectable secure storage

**Files:**
- Modify: `desktop/cutctx-control/src-tauri/src/credentials.rs`

**Interfaces:**
- Produces: `trait SecretStore: Send + Sync { get, set, delete }`.
- Produces: `CredentialVault::with_store(Arc<dyn SecretStore>)` for deterministic tests.
- Preserves: `status`, `save`, `begin_rotate`, `cancel_rotate`, and `token_for_internal_use` public behavior.

- [ ] **Step 1: Write failing plaintext-exclusion and migration tests**

Add this test support and the four focused tests inside `credentials.rs`:

```rust
#[derive(Default)]
struct MemorySecretStore(Mutex<BTreeMap<String, String>>);

impl SecretStore for MemorySecretStore {
    fn get(&self, id: &str) -> Result<Option<String>, String> {
        Ok(self.0.lock().unwrap().get(id).cloned())
    }

    fn set(&self, id: &str, token: &str) -> Result<(), String> {
        self.0.lock().unwrap().insert(id.into(), token.into());
        Ok(())
    }

    fn delete(&self, id: &str) -> Result<(), String> {
        self.0.lock().unwrap().remove(id);
        Ok(())
    }
}

struct FailingSecretStore;

impl SecretStore for FailingSecretStore {
    fn get(&self, _id: &str) -> Result<Option<String>, String> { Ok(None) }
    fn set(&self, _id: &str, _token: &str) -> Result<(), String> {
        Err("secure store unavailable".into())
    }
    fn delete(&self, _id: &str) -> Result<(), String> { Ok(()) }
}

#[test]
fn first_save_persists_metadata_without_the_secret() {
    let home = tmp_home();
    let store = Arc::new(MemorySecretStore::default());
    let mut vault = CredentialVault::with_store(store);
    vault.save(&home, OPENAI_API_KEY, "sk-test-secret-token-1234", 10).unwrap();

    let raw = fs::read_to_string(CredentialVault::path(&home)).unwrap();
    assert!(!raw.contains("sk-test-secret-token-1234"));
    assert!(raw.contains("sk-…1234"));
    assert_eq!(
        vault.token_for_internal_use(&home, OPENAI_API_KEY).unwrap().as_deref(),
        Some("sk-test-secret-token-1234"),
    );
}

#[test]
fn legacy_plaintext_vault_is_migrated_and_rewritten() {
    let home = tmp_home();
    let path = CredentialVault::path(&home);
    fs::create_dir_all(path.parent().unwrap()).unwrap();
    fs::write(
        &path,
        r#"{"credentials":[{"id":"openai_api_key","token":"sk-legacy-secret-9999","updated_at_unix":7}]}"#,
    ).unwrap();
    let store = Arc::new(MemorySecretStore::default());
    let vault = CredentialVault::with_store(store.clone());

    let status = vault.status(&home, OPENAI_API_KEY).unwrap();

    assert!(status.configured);
    assert_eq!(store.get(OPENAI_API_KEY).unwrap().as_deref(), Some("sk-legacy-secret-9999"));
    let rewritten = fs::read_to_string(path).unwrap();
    assert!(!rewritten.contains("sk-legacy-secret-9999"));
    assert!(rewritten.contains("sk-…9999"));
}

#[test]
fn legacy_license_file_is_removed_only_after_secure_migration() {
    let home = tmp_home();
    sync_license_key_file(&home, "cutctx_legacy_license_1234").unwrap();
    let path = license_key_path(&home);
    let store = Arc::new(MemorySecretStore::default());
    let vault = CredentialVault::with_store(store.clone());

    let status = vault.status(&home, CUTCTX_LICENSE_KEY).unwrap();

    assert!(status.configured);
    assert_eq!(store.get(CUTCTX_LICENSE_KEY).unwrap().as_deref(), Some("cutctx_legacy_license_1234"));
    assert!(!path.exists());
}

#[test]
fn failed_secure_migration_preserves_the_legacy_license_file() {
    let home = tmp_home();
    sync_license_key_file(&home, "cutctx_keep_on_failure").unwrap();
    let path = license_key_path(&home);
    let original = fs::read(&path).unwrap();
    let vault = CredentialVault::with_store(Arc::new(FailingSecretStore));

    assert!(vault.status(&home, CUTCTX_LICENSE_KEY).is_err());
    assert_eq!(fs::read(path).unwrap(), original);
}
```

- [ ] **Step 2: Run the new tests and witness RED**

Run:

```bash
rtk cargo test --manifest-path desktop/cutctx-control/src-tauri/Cargo.toml credentials::tests:: -- --nocapture
```

Expected: failures because `CredentialVault::with_store` and metadata-only persistence do not exist and the current file contains the raw token.

- [ ] **Step 3: Implement the minimal secure-store boundary**

Implement:

```rust
trait SecretStore: Send + Sync {
    fn get(&self, id: &str) -> Result<Option<String>, String>;
    fn set(&self, id: &str, token: &str) -> Result<(), String>;
    fn delete(&self, id: &str) -> Result<(), String>;
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct StoredCredential {
    id: String,
    #[serde(default)]
    masked: Option<String>,
    updated_at_unix: u64,
    #[serde(default, skip_serializing)]
    token: Option<String>,
}
```

`load_and_migrate` must write each legacy `token` to `SecretStore`, replace it with `masked`, persist the sanitized vault, and only then remove a successfully imported license file. `save` writes the secure store first and metadata second. `token_for_internal_use` reads only from `SecretStore` after migration.

- [ ] **Step 4: Run the Rust credential tests and witness GREEN**

Run the Task 1 command again. Expected: all credential tests pass and no test fixture contains a persisted raw token.

### Task 2: Native keyring backend and dependency lock

**Files:**
- Modify: `desktop/cutctx-control/src-tauri/Cargo.toml`
- Modify: `desktop/cutctx-control/src-tauri/Cargo.lock`
- Modify: `desktop/cutctx-control/src-tauri/src/credentials.rs`

**Interfaces:**
- Consumes: `SecretStore` from Task 1.
- Produces: `PlatformSecretStore` using service `io.cutctx.control` and credential IDs as account names.

- [ ] **Step 1: Add a failing production-backend construction test**

Add a test that constructs `PlatformSecretStore::entry(OPENAI_API_KEY)` and asserts the account/service identifiers are non-secret and stable without performing a real keychain write.

- [ ] **Step 2: Witness RED**

Run:

```bash
rtk cargo test --manifest-path desktop/cutctx-control/src-tauri/Cargo.toml platform_store_uses_stable_non_secret_identity -- --nocapture
```

Expected: failure because `PlatformSecretStore` does not exist.

- [ ] **Step 3: Add keyring-rs 3.6.3 with native backends**

Add:

```toml
keyring = { version = "=3.6.3", features = ["apple-native", "windows-native", "linux-native-sync-persistent", "crypto-rust"] }
```

Implement `PlatformSecretStore` with `keyring::Entry::new(SERVICE_NAME, id)`, mapping `keyring::Error::NoEntry` to `Ok(None)` and redacting all other backend details from user-facing errors.

- [ ] **Step 4: Witness GREEN and verify the dependency graph**

Run:

```bash
rtk cargo test --manifest-path desktop/cutctx-control/src-tauri/Cargo.toml credentials::tests:: -- --nocapture
rtk cargo tree --manifest-path desktop/cutctx-control/src-tauri/Cargo.toml -i keyring
```

Expected: credential tests pass and exactly keyring 3.6.3 is selected.

### Task 3: Python resolver for the shared OS-keychain account

**Files:**
- Create: `cutctx/auth/operator_credentials.py`
- Create: `tests/auth/test_operator_credentials.py`
- Modify: `cutctx/proxy/deployment_security.py`
- Modify: `tests/test_deployment_security.py`

**Interfaces:**
- Produces: `read_operator_credential(account: str, timeout_seconds: float = 5.0) -> str | None`.
- Produces constants: `SERVICE_NAME = "io.cutctx.control"`, `CUTCTX_LICENSE_ACCOUNT = "cutctx_license_key"`.
- Preserves config/environment precedence over local stores.

- [ ] **Step 1: Write failing bounded-read and precedence tests**

Add these tests, using a `SimpleNamespace` fake module in `sys.modules["keyring"]` so no real keychain is touched:

```python
def test_reads_shared_desktop_license_account(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    def get_password(service: str, account: str) -> str | None:
        calls.append((service, account))
        return "cutctx-test-license"

    monkeypatch.setitem(sys.modules, "keyring", SimpleNamespace(get_password=get_password))

    assert read_operator_credential(CUTCTX_LICENSE_ACCOUNT) == "cutctx-test-license"
    assert calls == [(SERVICE_NAME, CUTCTX_LICENSE_ACCOUNT)]

def test_keyring_hang_fails_closed_before_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    release = threading.Event()
    monkeypatch.setitem(
        sys.modules,
        "keyring",
        SimpleNamespace(get_password=lambda *_args: release.wait()),
    )
    started = time.monotonic()
    try:
        assert read_operator_credential(CUTCTX_LICENSE_ACCOUNT, timeout_seconds=0.05) is None
        assert time.monotonic() - started < 0.5
    finally:
        release.set()

def test_effective_license_key_prefers_config_then_env_then_keyring(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(tmp_path))
    monkeypatch.setattr(
        deployment_security,
        "read_operator_credential",
        lambda account: "keyring-license" if account == CUTCTX_LICENSE_ACCOUNT else None,
    )
    (tmp_path / "license_key.txt").write_text("file-license\n", encoding="utf-8")
    config = SimpleNamespace(license_key="config-license")
    assert deployment_security.effective_license_key(config) == "config-license"
    config.license_key = None
    monkeypatch.setenv("CUTCTX_LICENSE_KEY", "env-license")
    assert deployment_security.effective_license_key(config) == "env-license"
    monkeypatch.delenv("CUTCTX_LICENSE_KEY")
    assert deployment_security.effective_license_key(config) == "keyring-license"
```

- [ ] **Step 2: Witness RED**

Run:

```bash
rtk uv run --python 3.12 --no-sync pytest tests/auth/test_operator_credentials.py tests/test_deployment_security.py -q
```

Expected: collection/import failures for the missing module and failing keyring precedence.

- [ ] **Step 3: Implement the bounded shared-account reader**

Use a daemon thread plus `queue.Queue.get(timeout=...)`, matching the established deadline pattern in `cutctx/auth/client_credentials.py`. Return `None` for unavailable/no-entry stores and never include backend exception text or the secret in an error/log.

Update `_license_key_from_local_store` to check `read_operator_credential(CUTCTX_LICENSE_ACCOUNT)` before `license_key.txt` and signed cache fallbacks.

- [ ] **Step 4: Witness GREEN**

Run the Task 3 command again. Expected: all tests pass with no warnings or leaked backend payload.

### Task 4: Wrapper and managed-runtime compatibility without plaintext files

**Files:**
- Modify: `cutctx/cli/wrap.py`
- Modify: `tests/test_cli/test_wrap_helpers.py`
- Modify: `desktop/cutctx-control/src-tauri/src/supervisor.rs`

**Interfaces:**
- Consumes: `effective_license_key` from `cutctx.proxy.deployment_security`.
- Preserves: `ProxySupervisor::product_runtime_plan` contains no credential value.

- [ ] **Step 1: Write failing wrapper and supervisor boundary tests**

Add a wrapper test where config/env/files are empty and the fake shared keyring contains the license; `_resolve_license_key()` must return it. Extend the supervisor plan test to assert no argument contains `license`, `cutctx_`, or an injected test secret.

- [ ] **Step 2: Witness RED**

Run:

```bash
rtk uv run --python 3.12 --no-sync pytest tests/test_cli/test_wrap_helpers.py -q
rtk cargo test --manifest-path desktop/cutctx-control/src-tauri/Cargo.toml supervisor::tests:: -- --nocapture
```

Expected: the wrapper test fails because it duplicates file/cache resolution; the supervisor assertion documents the existing non-secret argv boundary.

- [ ] **Step 3: Reuse the shared resolver**

Replace `_resolve_license_key`'s duplicate logic with a minimal proxy-config shim passed to `effective_license_key`, retaining environment precedence. Do not add a credential argument to the managed runtime command.

- [ ] **Step 4: Witness GREEN**

Run both Task 4 commands again. Expected: all tests pass and managed runtime argv remains secret-free.

### Task 5: Full migration verification and commit

**Files:**
- All Task 1–4 files only.

- [ ] **Step 1: Run adjacent Python suites**

```bash
rtk uv run --python 3.12 --no-sync pytest tests/auth/test_operator_credentials.py tests/auth/test_client_credentials.py tests/test_deployment_security.py tests/test_cli/test_wrap_helpers.py tests/test_cli/test_setup.py -q
rtk uvx ruff@0.9.4 check cutctx/auth/operator_credentials.py cutctx/auth/client_credentials.py cutctx/proxy/deployment_security.py cutctx/cli/wrap.py tests/auth/test_operator_credentials.py tests/test_deployment_security.py tests/test_cli/test_wrap_helpers.py
```

- [ ] **Step 2: Run the complete desktop crate**

```bash
rtk cargo test --manifest-path desktop/cutctx-control/src-tauri/Cargo.toml
rtk cargo fmt --manifest-path desktop/cutctx-control/src-tauri/Cargo.toml -- --check
```

- [ ] **Step 3: Run secret and IPC regression gates**

```bash
rtk uv run --python 3.12 --no-sync pytest tests/test_desktop_ipc_contract.py tests/test_secret_pattern_hook.py tests/test_credential_redaction.py -q
rtk git diff --check
```

- [ ] **Step 4: Inspect the exact staged allowlist**

Stage only the files named in this plan. Confirm `uv.lock` is unstaged and no fixture contains `sk-test-secret-token-1234` outside test source literals.

- [ ] **Step 5: Commit**

```bash
rtk git commit -m "fix(desktop): migrate credentials to OS keychain"
```

- [ ] **Step 6: Update audit evidence**

Record RED/GREEN commands, dependency version, migration invariants, and residual platform limitations in `.slim/deepwork/release-audit-closeout.md` and change M12 only after the evidence path passes.
