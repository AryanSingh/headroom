//! Seat token helpers. Never log the raw token.

use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SeatTokenRecord {
    pub subject: String,
    pub token: String,
    pub issued_at_unix: u64,
}

pub fn header_line(token: &str) -> String {
    format!("X-Cutctx-User-Token: {token}")
}

pub fn seat_path(home: &Path) -> PathBuf {
    home.join(".cutctx").join("control").join("seat.json")
}

pub fn save_seat(home: &Path, record: &SeatTokenRecord) -> std::io::Result<PathBuf> {
    let dir = home.join(".cutctx").join("control");
    fs::create_dir_all(&dir)?;
    let path = seat_path(home);
    let data = serde_json::to_vec_pretty(record)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
    fs::write(&path, data)?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mut perms = fs::metadata(&path)?.permissions();
        perms.set_mode(0o600);
        fs::set_permissions(&path, perms)?;
    }
    Ok(path)
}

pub fn load_seat(home: &Path) -> std::io::Result<Option<SeatTokenRecord>> {
    let path = seat_path(home);
    if !path.exists() {
        return Ok(None);
    }
    let data = fs::read_to_string(path)?;
    let record = serde_json::from_str(&data)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
    Ok(Some(record))
}

/// Mint via `cutctx license token`. Returns the raw token string.
pub fn mint_via_cli(cutctx_bin: &str, subject: Option<&str>) -> Result<String, String> {
    let mut cmd = Command::new(cutctx_bin);
    cmd.args(["license", "token"]);
    if let Some(sub) = subject {
        cmd.args(["--subject", sub]);
    }
    let output = cmd.output().map_err(|e| format!("failed to run {cutctx_bin}: {e}"))?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("cutctx license token failed: {stderr}"));
    }
    let token = String::from_utf8_lossy(&output.stdout).trim().to_string();
    if !token.starts_with("ctu1.") {
        return Err("minted token was not a ctu1 user token".into());
    }
    Ok(token)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn header_line_format() {
        assert_eq!(
            header_line("ctu1.abc.def"),
            "X-Cutctx-User-Token: ctu1.abc.def"
        );
    }

    #[test]
    fn save_load_seat_roundtrip() {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let home = std::env::temp_dir().join(format!("cutctx-seat-{nanos}"));
        let record = SeatTokenRecord {
            subject: "aryan".into(),
            token: "ctu1.payload.sig".into(),
            issued_at_unix: 1,
        };
        save_seat(&home, &record).unwrap();
        let loaded = load_seat(&home).unwrap().unwrap();
        assert_eq!(loaded.token, "ctu1.payload.sig");
        let _ = fs::remove_dir_all(&home);
    }
}
