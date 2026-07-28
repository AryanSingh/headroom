//! Permission-restricted local credential store for CutCtx Control.
//!
//! Once a token is saved it is locked: the UI may only show a masked hint.
//! Replacing it requires an explicit rotate. The raw secret is never returned
//! to the frontend after save. Values are plaintext on disk with mode 0600 on
//! Unix; this is not an encrypted keychain.

use crate::private_file::write_private;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};

pub const OPENAI_API_KEY: &str = "openai_api_key";
pub const CUTCTX_LICENSE_KEY: &str = "cutctx_license_key";

fn license_key_path(home: &Path) -> PathBuf {
    home.join(".cutctx").join("license_key.txt")
}

/// Persist the license where the proxy already looks (`~/.cutctx/license_key.txt`).
pub fn sync_license_key_file(home: &Path, token: &str) -> std::io::Result<()> {
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

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StoredCredential {
    pub id: String,
    pub token: String,
    pub updated_at_unix: u64,
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

#[derive(Debug, Default)]
pub struct CredentialVault {
    /// In-memory rotate session: id -> allowed to overwrite once.
    rotate_allowed: std::collections::BTreeSet<String>,
}

impl CredentialVault {
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
        let mut vault = Self::load(home)?;
        // Bootstrap from the canonical license file if Control has never saved one.
        if id == CUTCTX_LICENSE_KEY && !vault.credentials.iter().any(|c| c.id == id) {
            if let Some(token) = import_existing_license_file(home)? {
                vault.credentials.push(StoredCredential {
                    id: id.into(),
                    token,
                    updated_at_unix: 0,
                });
                Self::persist(home, &vault)?;
            }
        }
        match vault.credentials.iter().find(|c| c.id == id) {
            Some(c) => Ok(CredentialStatus {
                id: id.into(),
                configured: true,
                masked: Some(Self::mask_token(&c.token)),
                unlocked_for_entry: self.rotate_allowed.contains(id),
            }),
            None => Ok(CredentialStatus {
                id: id.into(),
                configured: false,
                masked: None,
                unlocked_for_entry: true,
            }),
        }
    }

    #[cfg(test)]
    pub fn get_secret(&self, home: &Path, id: &str) -> std::io::Result<Option<String>> {
        // Ensure license file bootstrap is visible to supervised launches.
        if id == CUTCTX_LICENSE_KEY {
            let _ = self.status(home, id)?;
        }
        let vault = Self::load(home)?;
        Ok(vault
            .credentials
            .into_iter()
            .find(|c| c.id == id)
            .map(|c| c.token))
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
        let mut vault = Self::load(home).map_err(|e| e.to_string())?;
        let exists = vault.credentials.iter().any(|c| c.id == id);
        if exists && !self.rotate_allowed.contains(id) {
            return Err("Credential is locked. Rotate it to replace the saved value.".into());
        }
        vault.credentials.retain(|c| c.id != id);
        vault.credentials.push(StoredCredential {
            id: id.into(),
            token: token.into(),
            updated_at_unix: now_unix,
        });
        Self::persist(home, &vault).map_err(|e| e.to_string())?;
        if id == CUTCTX_LICENSE_KEY {
            sync_license_key_file(home, token).map_err(|e| e.to_string())?;
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
    use std::time::{SystemTime, UNIX_EPOCH};

    fn tmp_home() -> PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let rand = std::process::id();
        let dir = std::env::temp_dir().join(format!("cutctx-cred-{nanos}-{rand}"));
        fs::create_dir_all(&dir).unwrap();
        dir
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
        let mut vault = CredentialVault::default();
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
        let mut vault = CredentialVault::default();
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

        let secret = vault.get_secret(&home, OPENAI_API_KEY).unwrap().unwrap();
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
        let mut vault = CredentialVault::default();
        vault
            .save(&home, OPENAI_API_KEY, "sk-keep-token-zzzz", 1)
            .unwrap();
        vault.begin_rotate(&home, OPENAI_API_KEY).unwrap();
        let status = vault.cancel_rotate(&home, OPENAI_API_KEY).unwrap();
        assert!(!status.unlocked_for_entry);
        assert_eq!(
            vault.get_secret(&home, OPENAI_API_KEY).unwrap().unwrap(),
            "sk-keep-token-zzzz"
        );
        let _ = fs::remove_dir_all(&home);
    }

    #[test]
    fn empty_token_rejected() {
        let home = tmp_home();
        let mut vault = CredentialVault::default();
        let err = vault.save(&home, OPENAI_API_KEY, "   ", 1).unwrap_err();
        assert!(err.to_lowercase().contains("empty"));
        let _ = fs::remove_dir_all(&home);
    }

    #[test]
    fn license_save_writes_canonical_license_key_file() {
        let home = tmp_home();
        let mut vault = CredentialVault::default();
        let key = "cutctx_7409d60fb5684fe8868fac057cff8596";
        vault.save(&home, CUTCTX_LICENSE_KEY, key, 42).unwrap();
        let path = license_key_path(&home);
        assert!(path.is_file());
        assert_eq!(fs::read_to_string(&path).unwrap().trim(), key);
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
        let vault = CredentialVault::default();
        let status = vault.status(&home, CUTCTX_LICENSE_KEY).unwrap();
        assert!(status.configured);
        assert!(!status.unlocked_for_entry);
        let secret = vault
            .get_secret(&home, CUTCTX_LICENSE_KEY)
            .unwrap()
            .unwrap();
        assert_eq!(secret, "cutctx_preexisting_license_key");
        let _ = fs::remove_dir_all(&home);
    }
}
