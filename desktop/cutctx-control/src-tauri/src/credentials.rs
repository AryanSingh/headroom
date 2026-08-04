//! OS-backed credential store for CutCtx Control.
//!
//! Once a token is saved it is locked: the UI may only show a masked hint.
//! Replacing it requires an explicit rotate. The raw secret is never returned
//! to the frontend after save. The metadata file contains masked hints only;
//! raw values live behind the injected secure-store boundary.

use crate::private_file::write_private;
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Arc;

pub const OPENAI_API_KEY: &str = "openai_api_key";
pub const CUTCTX_LICENSE_KEY: &str = "cutctx_license_key";
pub const SERVICE_NAME: &str = "io.cutctx.control";

fn license_key_path(home: &Path) -> PathBuf {
    home.join(".cutctx").join("license_key.txt")
}

/// Create a legacy plaintext fixture for one-way migration tests.
#[cfg(test)]
fn sync_license_key_file(home: &Path, token: &str) -> std::io::Result<()> {
    let path = license_key_path(home);
    write_private(&path, format!("{}\n", token.trim()).as_bytes())
}

fn import_existing_license_file(home: &Path) -> std::io::Result<Option<String>> {
    let path = license_key_path(home);
    if !path.exists() {
        return Ok(None);
    }
    let raw = fs::read_to_string(path)?;
    let token = raw.trim();
    if token.is_empty() {
        return Ok(None);
    }
    Ok(Some(token.to_string()))
}

pub trait SecretStore: Send + Sync {
    fn get(&self, id: &str) -> Result<Option<String>, String>;
    fn set(&self, id: &str, token: &str) -> Result<(), String>;
    fn delete(&self, id: &str) -> Result<(), String>;
}

pub struct PlatformSecretStore;

impl PlatformSecretStore {
    fn identity(id: &str) -> (&'static str, &str) {
        (SERVICE_NAME, id)
    }

    fn entry(id: &str) -> Result<keyring::Entry, String> {
        let (service, account) = Self::identity(id);
        keyring::Entry::new(service, account)
            .map_err(|_| "secure credential store is unavailable".into())
    }
}

impl SecretStore for PlatformSecretStore {
    fn get(&self, id: &str) -> Result<Option<String>, String> {
        match Self::entry(id)?.get_password() {
            Ok(token) => Ok(Some(token)),
            Err(keyring::Error::NoEntry) => Ok(None),
            Err(_) => Err("secure credential store is unavailable".into()),
        }
    }

    fn set(&self, id: &str, token: &str) -> Result<(), String> {
        Self::entry(id)?
            .set_password(token)
            .map_err(|_| "secure credential store is unavailable".into())
    }

    fn delete(&self, id: &str) -> Result<(), String> {
        match Self::entry(id)?.delete_credential() {
            Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
            Err(_) => Err("secure credential store is unavailable".into()),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
struct StoredCredential {
    pub id: String,
    #[serde(default)]
    pub masked: Option<String>,
    pub updated_at_unix: u64,
    /// Legacy plaintext field accepted only for one-way migration.
    #[serde(default, skip_serializing)]
    pub token: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
struct VaultFile {
    credentials: Vec<StoredCredential>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CredentialStatus {
    pub id: String,
    pub configured: bool,
    /// Masked hint like `sk-…abc1` — never the full token.
    pub masked: Option<String>,
    /// When true, the UI may show an input. False when configured and not rotating.
    pub unlocked_for_entry: bool,
}

pub struct CredentialVault {
    /// In-memory rotate session: id -> allowed to overwrite once.
    rotate_allowed: BTreeSet<String>,
    store: Arc<dyn SecretStore>,
}

impl Default for CredentialVault {
    fn default() -> Self {
        Self::with_store(Arc::new(PlatformSecretStore))
    }
}

impl CredentialVault {
    pub fn with_store(store: Arc<dyn SecretStore>) -> Self {
        Self {
            rotate_allowed: BTreeSet::new(),
            store,
        }
    }

    pub fn path(home: &Path) -> PathBuf {
        home.join(".cutctx")
            .join("control")
            .join("credentials.json")
    }

    fn load(home: &Path) -> std::io::Result<VaultFile> {
        let path = Self::path(home);
        if !path.exists() {
            return Ok(VaultFile::default());
        }
        let data = fs::read_to_string(path)?;
        serde_json::from_str(&data)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))
    }

    fn persist(home: &Path, vault: &VaultFile) -> std::io::Result<()> {
        let path = Self::path(home);
        let data = serde_json::to_vec_pretty(vault)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
        write_private(&path, &data)
    }

    fn load_and_migrate(&self, home: &Path) -> Result<VaultFile, String> {
        let mut vault = Self::load(home).map_err(|e| e.to_string())?;
        let mut changed = false;

        for credential in &mut vault.credentials {
            let Some(token) = credential.token.take() else {
                continue;
            };
            let token = token.trim();
            if token.is_empty() {
                changed = true;
                continue;
            }
            let effective = match self.store.get(&credential.id)? {
                Some(existing) => existing,
                None => {
                    self.store.set(&credential.id, token)?;
                    token.to_string()
                }
            };
            credential.masked = Some(Self::mask_token(&effective));
            changed = true;
        }

        if changed {
            Self::persist(home, &vault).map_err(|e| e.to_string())?;
        }
        Ok(vault)
    }

    fn ensure_metadata_for_store_value(
        &self,
        home: &Path,
        vault: &mut VaultFile,
        id: &str,
        token: &str,
    ) -> Result<(), String> {
        let masked = Self::mask_token(token);
        if let Some(credential) = vault
            .credentials
            .iter_mut()
            .find(|credential| credential.id == id)
        {
            if credential.masked.as_deref() == Some(masked.as_str()) {
                return Ok(());
            }
            credential.masked = Some(masked);
            return Self::persist(home, vault).map_err(|e| e.to_string());
        }
        vault.credentials.push(StoredCredential {
            id: id.into(),
            masked: Some(masked),
            updated_at_unix: 0,
            token: None,
        });
        Self::persist(home, vault).map_err(|e| e.to_string())
    }

    pub fn mask_token(token: &str) -> String {
        let trimmed = token.trim();
        if trimmed.is_empty() {
            return String::new();
        }
        let suffix: String = trimmed
            .chars()
            .rev()
            .take(4)
            .collect::<String>()
            .chars()
            .rev()
            .collect();
        let prefix: String = trimmed.chars().take(3).collect();
        if trimmed.len() <= 8 {
            return format!("{prefix}…");
        }
        format!("{prefix}…{suffix}")
    }

    pub fn status(&self, home: &Path, id: &str) -> std::io::Result<CredentialStatus> {
        self.status_inner(home, id)
            .map_err(|e| std::io::Error::other(e))
    }

    fn status_inner(&self, home: &Path, id: &str) -> Result<CredentialStatus, String> {
        let mut vault = self.load_and_migrate(home)?;
        let mut token = self.store.get(id)?;

        // Bootstrap the desktop-managed runtime from the legacy license file.
        // Remove the file only after both the secure write and sanitized
        // metadata persistence have succeeded.
        if id == CUTCTX_LICENSE_KEY && license_key_path(home).exists() {
            if token.is_none() {
                if let Some(imported) =
                    import_existing_license_file(home).map_err(|e| e.to_string())?
                {
                    self.store.set(id, &imported)?;
                    self.ensure_metadata_for_store_value(home, &mut vault, id, &imported)?;
                    token = Some(imported);
                }
            } else if let Some(existing) = token.as_deref() {
                self.ensure_metadata_for_store_value(home, &mut vault, id, existing)?;
            }
            if token.is_some() {
                fs::remove_file(license_key_path(home)).map_err(|e| e.to_string())?;
            }
        }

        if let Some(value) = token.as_deref() {
            self.ensure_metadata_for_store_value(home, &mut vault, id, value)?;
        }

        match vault.credentials.iter().find(|c| c.id == id) {
            Some(c) => Ok(CredentialStatus {
                id: id.into(),
                configured: token.is_some(),
                masked: token
                    .as_deref()
                    .map(Self::mask_token)
                    .or_else(|| c.masked.clone()),
                unlocked_for_entry: token.is_none() || self.rotate_allowed.contains(id),
            }),
            None => Ok(CredentialStatus {
                id: id.into(),
                configured: false,
                masked: None,
                unlocked_for_entry: true,
            }),
        }
    }

    /// Return a credential only to native Control runtime code. This is never
    /// exposed through a Tauri command or returned to the web frontend.
    pub fn token_for_internal_use(&self, home: &Path, id: &str) -> std::io::Result<Option<String>> {
        // Ensure license-file bootstrap is visible to native Control calls.
        let _ = self.status(home, id)?;
        self.store.get(id).map_err(std::io::Error::other)
    }

    /// Save a new credential. Fails if one already exists and rotation was not begun.
    pub fn save(
        &mut self,
        home: &Path,
        id: &str,
        token: &str,
        now_unix: u64,
    ) -> Result<CredentialStatus, String> {
        let token = token.trim();
        if token.is_empty() {
            return Err("Credential cannot be empty".into());
        }
        let mut vault = self.load_and_migrate(home)?;
        let previous = self.store.get(id)?;
        let exists = previous.is_some();
        if exists && !self.rotate_allowed.contains(id) {
            return Err("Credential is locked. Rotate it to replace the saved value.".into());
        }
        vault.credentials.retain(|c| c.id != id);
        self.store.set(id, token)?;
        vault.credentials.push(StoredCredential {
            id: id.into(),
            masked: Some(Self::mask_token(token)),
            updated_at_unix: now_unix,
            token: None,
        });
        if let Err(error) = Self::persist(home, &vault) {
            match previous {
                Some(previous) => {
                    let _ = self.store.set(id, &previous);
                }
                None => {
                    let _ = self.store.delete(id);
                }
            }
            return Err(error.to_string());
        }
        self.rotate_allowed.remove(id);
        self.status(home, id).map_err(|e| e.to_string())
    }

    /// Unlock the credential for a single replacement save.
    pub fn begin_rotate(&mut self, home: &Path, id: &str) -> Result<CredentialStatus, String> {
        let mut status = self.status(home, id).map_err(|e| e.to_string())?;
        if !status.configured {
            return Err("No saved credential to rotate".into());
        }
        self.rotate_allowed.insert(id.into());
        status.unlocked_for_entry = true;
        Ok(status)
    }

    pub fn cancel_rotate(&mut self, home: &Path, id: &str) -> Result<CredentialStatus, String> {
        self.rotate_allowed.remove(id);
        self.status(home, id).map_err(|e| e.to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeMap;
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::sync::{Arc, Mutex};
    use std::time::{SystemTime, UNIX_EPOCH};

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
        fn get(&self, _id: &str) -> Result<Option<String>, String> {
            Ok(None)
        }

        fn set(&self, _id: &str, _token: &str) -> Result<(), String> {
            Err("secure store unavailable".into())
        }

        fn delete(&self, _id: &str) -> Result<(), String> {
            Ok(())
        }
    }

    fn tmp_home() -> PathBuf {
        static NEXT_ID: AtomicU64 = AtomicU64::new(0);
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let rand = std::process::id();
        let id = NEXT_ID.fetch_add(1, Ordering::Relaxed);
        let dir = std::env::temp_dir().join(format!("cutctx-cred-{nanos}-{rand}-{id}"));
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    fn test_vault() -> CredentialVault {
        CredentialVault::with_store(Arc::new(MemorySecretStore::default()))
    }

    #[test]
    fn mask_hides_middle_keeps_edges() {
        let masked = CredentialVault::mask_token("sk-proj-abcdefghijklmnop");
        assert!(masked.starts_with("sk-"));
        assert!(masked.contains('…'));
        assert!(masked.ends_with("mnop"));
        assert!(!masked.contains("abcdefgh"));
    }

    #[test]
    fn first_save_unlocks_then_locks() {
        let home = tmp_home();
        let mut vault = test_vault();
        let status = vault.status(&home, OPENAI_API_KEY).unwrap();
        assert!(!status.configured);
        assert!(status.unlocked_for_entry);

        let saved = vault
            .save(&home, OPENAI_API_KEY, "sk-test-secret-token-1234", 10)
            .unwrap();
        assert!(saved.configured);
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            assert_eq!(
                fs::metadata(CredentialVault::path(&home))
                    .unwrap()
                    .permissions()
                    .mode()
                    & 0o777,
                0o600
            );
        }
        assert!(!saved.unlocked_for_entry);
        assert_eq!(saved.masked.as_deref(), Some("sk-…1234"));

        let err = vault
            .save(&home, OPENAI_API_KEY, "sk-another-token-9999", 11)
            .unwrap_err();
        assert!(err.to_lowercase().contains("locked"));
        let _ = fs::remove_dir_all(&home);
    }

    #[test]
    fn rotate_allows_one_replacement() {
        let home = tmp_home();
        let mut vault = test_vault();
        vault
            .save(&home, OPENAI_API_KEY, "sk-old-token-aaaa", 1)
            .unwrap();
        let unlocked = vault.begin_rotate(&home, OPENAI_API_KEY).unwrap();
        assert!(unlocked.unlocked_for_entry);

        let replaced = vault
            .save(&home, OPENAI_API_KEY, "sk-new-token-bbbb", 2)
            .unwrap();
        assert!(replaced.configured);
        assert!(!replaced.unlocked_for_entry);
        assert_eq!(replaced.masked.as_deref(), Some("sk-…bbbb"));

        let secret = vault
            .token_for_internal_use(&home, OPENAI_API_KEY)
            .unwrap()
            .unwrap();
        assert_eq!(secret, "sk-new-token-bbbb");

        // Second save without rotate fails again
        let err = vault
            .save(&home, OPENAI_API_KEY, "sk-third-cccc", 3)
            .unwrap_err();
        assert!(err.to_lowercase().contains("locked"));
        let _ = fs::remove_dir_all(&home);
    }

    #[test]
    fn cancel_rotate_re_locks_without_changing_secret() {
        let home = tmp_home();
        let mut vault = test_vault();
        vault
            .save(&home, OPENAI_API_KEY, "sk-keep-token-zzzz", 1)
            .unwrap();
        vault.begin_rotate(&home, OPENAI_API_KEY).unwrap();
        let status = vault.cancel_rotate(&home, OPENAI_API_KEY).unwrap();
        assert!(!status.unlocked_for_entry);
        assert_eq!(
            vault
                .token_for_internal_use(&home, OPENAI_API_KEY)
                .unwrap()
                .unwrap(),
            "sk-keep-token-zzzz"
        );
        let _ = fs::remove_dir_all(&home);
    }

    #[test]
    fn empty_token_rejected() {
        let home = tmp_home();
        let mut vault = test_vault();
        let err = vault.save(&home, OPENAI_API_KEY, "   ", 1).unwrap_err();
        assert!(err.to_lowercase().contains("empty"));
        let _ = fs::remove_dir_all(&home);
    }

    #[test]
    fn license_save_uses_secure_store_without_plaintext_file() {
        let home = tmp_home();
        let mut vault = test_vault();
        let key = "cutctx_7409d60fb5684fe8868fac057cff8596";
        vault.save(&home, CUTCTX_LICENSE_KEY, key, 42).unwrap();
        let path = license_key_path(&home);
        assert!(!path.exists());
        assert_eq!(
            vault
                .token_for_internal_use(&home, CUTCTX_LICENSE_KEY)
                .unwrap()
                .as_deref(),
            Some(key)
        );
        let status = vault.status(&home, CUTCTX_LICENSE_KEY).unwrap();
        assert!(status.configured);
        assert!(!status.unlocked_for_entry);
        assert!(status.masked.as_deref().unwrap().contains('…'));
        let err = vault
            .save(&home, CUTCTX_LICENSE_KEY, "cutctx_replacement_key_zzzz", 43)
            .unwrap_err();
        assert!(err.to_lowercase().contains("locked"));
        let _ = fs::remove_dir_all(&home);
    }

    #[test]
    fn status_imports_existing_license_key_file() {
        let home = tmp_home();
        sync_license_key_file(&home, "cutctx_preexisting_license_key").unwrap();
        let vault = test_vault();
        let status = vault.status(&home, CUTCTX_LICENSE_KEY).unwrap();
        assert!(status.configured);
        assert!(!status.unlocked_for_entry);
        let secret = vault
            .token_for_internal_use(&home, CUTCTX_LICENSE_KEY)
            .unwrap()
            .unwrap();
        assert_eq!(secret, "cutctx_preexisting_license_key");
        let _ = fs::remove_dir_all(&home);
    }

    #[test]
    fn first_save_persists_metadata_without_the_secret() {
        let home = tmp_home();
        let store = Arc::new(MemorySecretStore::default());
        let mut vault = CredentialVault::with_store(store);
        vault
            .save(&home, OPENAI_API_KEY, "sk-test-secret-token-1234", 10)
            .unwrap();

        let raw = fs::read_to_string(CredentialVault::path(&home)).unwrap();
        assert!(!raw.contains("sk-test-secret-token-1234"));
        assert!(raw.contains("sk-…1234"));
        assert_eq!(
            vault
                .token_for_internal_use(&home, OPENAI_API_KEY)
                .unwrap()
                .as_deref(),
            Some("sk-test-secret-token-1234"),
        );
        let _ = fs::remove_dir_all(&home);
    }

    #[test]
    fn legacy_plaintext_vault_is_migrated_and_rewritten() {
        let home = tmp_home();
        let path = CredentialVault::path(&home);
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(
            &path,
            r#"{"credentials":[{"id":"openai_api_key","token":"sk-legacy-secret-9999","updated_at_unix":7}]}"#,
        )
        .unwrap();
        let store = Arc::new(MemorySecretStore::default());
        let vault = CredentialVault::with_store(store.clone());

        let status = vault.status(&home, OPENAI_API_KEY).unwrap();

        assert!(status.configured);
        assert_eq!(
            store.get(OPENAI_API_KEY).unwrap().as_deref(),
            Some("sk-legacy-secret-9999")
        );
        let rewritten = fs::read_to_string(path).unwrap();
        assert!(!rewritten.contains("sk-legacy-secret-9999"));
        assert!(rewritten.contains("sk-…9999"));
        let _ = fs::remove_dir_all(&home);
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
        assert_eq!(
            store.get(CUTCTX_LICENSE_KEY).unwrap().as_deref(),
            Some("cutctx_legacy_license_1234")
        );
        assert!(!path.exists());
        let _ = fs::remove_dir_all(&home);
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
        let _ = fs::remove_dir_all(&home);
    }

    #[test]
    fn platform_store_uses_stable_non_secret_identity() {
        let (service, account) = PlatformSecretStore::identity(OPENAI_API_KEY);
        assert_eq!(service, "io.cutctx.control");
        assert_eq!(account, OPENAI_API_KEY);
        assert!(!service.contains("secret"));
        assert!(!account.contains("sk-"));
    }

    #[test]
    fn stale_metadata_without_a_secure_value_can_be_replaced() {
        let home = tmp_home();
        let path = CredentialVault::path(&home);
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(
            &path,
            r#"{"credentials":[{"id":"openai_api_key","masked":"sk-…gone","updated_at_unix":7}]}"#,
        )
        .unwrap();
        let mut vault = test_vault();

        let status = vault.status(&home, OPENAI_API_KEY).unwrap();
        assert!(!status.configured);
        assert!(status.unlocked_for_entry);
        vault
            .save(&home, OPENAI_API_KEY, "sk-recovered-value-1234", 8)
            .unwrap();
        assert_eq!(
            vault
                .token_for_internal_use(&home, OPENAI_API_KEY)
                .unwrap()
                .as_deref(),
            Some("sk-recovered-value-1234")
        );
        let _ = fs::remove_dir_all(&home);
    }

    #[test]
    fn legacy_plaintext_does_not_overwrite_a_newer_secure_value() {
        let home = tmp_home();
        let path = CredentialVault::path(&home);
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(
            &path,
            r#"{"credentials":[{"id":"openai_api_key","token":"sk-legacy-value-1111","updated_at_unix":7}]}"#,
        )
        .unwrap();
        let store = Arc::new(MemorySecretStore::default());
        store
            .set(OPENAI_API_KEY, "sk-newer-secure-value-2222")
            .unwrap();
        let vault = CredentialVault::with_store(store.clone());

        let status = vault.status(&home, OPENAI_API_KEY).unwrap();

        assert_eq!(
            store.get(OPENAI_API_KEY).unwrap().as_deref(),
            Some("sk-newer-secure-value-2222")
        );
        assert_eq!(status.masked.as_deref(), Some("sk-…2222"));
        assert!(!fs::read_to_string(path)
            .unwrap()
            .contains("sk-legacy-value-1111"));
        let _ = fs::remove_dir_all(&home);
    }

    #[test]
    fn existing_secure_license_allows_legacy_file_cleanup() {
        let home = tmp_home();
        sync_license_key_file(&home, "cutctx_stale_plaintext_1111").unwrap();
        let path = license_key_path(&home);
        let store = Arc::new(MemorySecretStore::default());
        store
            .set(CUTCTX_LICENSE_KEY, "cutctx_secure_license_2222")
            .unwrap();
        let vault = CredentialVault::with_store(store);

        let status = vault.status(&home, CUTCTX_LICENSE_KEY).unwrap();

        assert!(status.configured);
        assert_eq!(status.masked.as_deref(), Some("cut…2222"));
        assert!(!path.exists());
        let _ = fs::remove_dir_all(&home);
    }
}
