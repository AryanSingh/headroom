//! Profile persistence under `~/.cutctx/control/profiles`.

use crate::argv::ProxyProfile;
use serde_json;
use std::fs;
use std::path::{Path, PathBuf};

pub fn control_dir(home: &Path) -> PathBuf {
    home.join(".cutctx").join("control")
}

pub fn profiles_dir(home: &Path) -> PathBuf {
    control_dir(home).join("profiles")
}

pub fn ensure_dirs(home: &Path) -> std::io::Result<PathBuf> {
    let dir = profiles_dir(home);
    fs::create_dir_all(&dir)?;
    Ok(dir)
}

fn profile_path(home: &Path, name: &str) -> PathBuf {
    let safe: String = name
        .chars()
        .map(|c| if c.is_ascii_alphanumeric() || c == '-' || c == '_' { c } else { '-' })
        .collect();
    profiles_dir(home).join(format!("{safe}.json"))
}

pub fn save_profile(home: &Path, profile: &ProxyProfile) -> std::io::Result<PathBuf> {
    ensure_dirs(home)?;
    let path = profile_path(home, &profile.name);
    let data = serde_json::to_vec_pretty(profile)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
    fs::write(&path, data)?;
    Ok(path)
}

pub fn load_profile(home: &Path, name: &str) -> std::io::Result<ProxyProfile> {
    let path = profile_path(home, name);
    let data = fs::read_to_string(path)?;
    serde_json::from_str(&data)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))
}

pub fn list_profiles(home: &Path) -> std::io::Result<Vec<String>> {
    let dir = profiles_dir(home);
    if !dir.exists() {
        return Ok(Vec::new());
    }
    let mut names = Vec::new();
    for entry in fs::read_dir(dir)? {
        let entry = entry?;
        let path = entry.path();
        if path.extension().and_then(|s| s.to_str()) == Some("json") {
            if let Some(stem) = path.file_stem().and_then(|s| s.to_str()) {
                names.push(stem.to_string());
            }
        }
    }
    names.sort();
    Ok(names)
}

pub fn delete_profile(home: &Path, name: &str) -> std::io::Result<()> {
    let path = profile_path(home, name);
    if path.exists() {
        fs::remove_file(path)?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::argv::ProxyProfile;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn tmp_home() -> PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        std::env::temp_dir().join(format!("cutctx-control-test-{nanos}"))
    }

    #[test]
    fn save_load_roundtrip() {
        let home = tmp_home();
        let mut p = ProxyProfile::default_profile();
        p.name = "slim".into();
        p.port = 9999;
        save_profile(&home, &p).unwrap();
        let loaded = load_profile(&home, "slim").unwrap();
        assert_eq!(loaded.port, 9999);
        assert_eq!(loaded.name, "slim");
        let _ = fs::remove_dir_all(&home);
    }

    #[test]
    fn list_and_delete() {
        let home = tmp_home();
        let mut a = ProxyProfile::default_profile();
        a.name = "a".into();
        let mut b = ProxyProfile::all_optional_on();
        b.name = "b".into();
        save_profile(&home, &a).unwrap();
        save_profile(&home, &b).unwrap();
        assert_eq!(list_profiles(&home).unwrap(), vec!["a", "b"]);
        delete_profile(&home, "a").unwrap();
        assert_eq!(list_profiles(&home).unwrap(), vec!["b"]);
        let _ = fs::remove_dir_all(&home);
    }
}
