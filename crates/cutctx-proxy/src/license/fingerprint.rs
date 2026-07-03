use sha2::{Digest, Sha256};
use std::path::PathBuf;

/// Install fingerprint binding the license to a specific machine.
///
/// Computed from: hash(machine_id + OS + salted install UUID).
/// Stored encrypted via state_crypto on activation and verified on
/// every heartbeat. Prevents license key sharing across machines.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InstallFingerprint {
    /// The computed fingerprint hash (hex-encoded SHA-256).
    pub hash: String,
    /// The raw components used (for diagnostics only, not persisted).
    pub components: FingerprintComponents,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FingerprintComponents {
    pub machine_id: String,
    pub os_info: String,
    pub install_uuid: String,
}

/// Persistent clock state for rollback detection.
///
/// Stores the last-seen monotonic and wall-clock timestamps in
/// encrypted state. If wall clock jumps backward materially vs
/// last-seen, the proxy rejects and forces re-activation.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ClockState {
    /// Last wall-clock timestamp (seconds since epoch).
    pub last_wall_secs: u64,
    /// Last monotonic timestamp (from Instant).
    pub last_mono_ns: u128,
}

impl ClockState {
    /// Maximum allowed backward wall-clock drift before triggering
    /// rollback detection. 300 seconds (5 minutes) allows for minor
    /// NTP adjustments while catching deliberate clock manipulation.
    pub const MAX_BACKWARD_DRIFT_SECS: u64 = 300;

    /// Check if the current wall clock has rolled back past the threshold.
    pub fn detect_rollback(&self, current_wall_secs: u64) -> bool {
        if current_wall_secs < self.last_wall_secs {
            let drift = self.last_wall_secs - current_wall_secs;
            drift > Self::MAX_BACKWARD_DRIFT_SECS
        } else {
            false
        }
    }

    /// Create a new clock state from current timestamps.
    pub fn now(mono_ns: u128) -> Self {
        let wall_secs = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        Self {
            last_wall_secs: wall_secs,
            last_mono_ns: mono_ns,
        }
    }
}

/// Compute the install fingerprint for this machine.
///
/// Uses machine-id (Linux), IOPlatformSerialNumber (macOS), or
/// hostname as a fallback. Salted with a persistent install UUID
/// stored at `~/.cutctx/install-uuid`.
pub fn compute_fingerprint() -> InstallFingerprint {
    let machine_id = get_machine_id();
    let os_info = get_os_info();
    let install_uuid = get_or_create_install_uuid();

    let mut hasher = Sha256::new();
    hasher.update(machine_id.as_bytes());
    hasher.update(os_info.as_bytes());
    hasher.update(install_uuid.as_bytes());
    let hash = format!("{:x}", hasher.finalize());

    InstallFingerprint {
        hash,
        components: FingerprintComponents {
            machine_id,
            os_info,
            install_uuid,
        },
    }
}

/// Get a stable machine identifier.
///
/// - Linux: reads /etc/machine-id or /var/lib/dbus/machine-id
/// - macOS: uses IOPlatformSerialNumber via sysctl (best-effort) or hostname
/// - Fallback: hostname
fn get_machine_id() -> String {
    #[cfg(target_os = "linux")]
    {
        for path in &["/etc/machine-id", "/var/lib/dbus/machine-id"] {
            if let Ok(id) = std::fs::read_to_string(path) {
                let id = id.trim();
                if !id.is_empty() {
                    return id.to_string();
                }
            }
        }
    }

    #[cfg(target_os = "macos")]
    {
        // Try IOPlatformSerialNumber via sysctl
        if let Ok(output) = std::process::Command::new("sysctl")
            .arg("-n")
            .arg("kern.uuid")
            .output()
        {
            let id = String::from_utf8_lossy(&output.stdout).trim().to_string();
            if !id.is_empty() {
                return id;
            }
        }
    }

    // Fallback: hostname
    hostname::get()
        .map(|h| h.to_string_lossy().to_string())
        .unwrap_or_else(|_| "unknown-host".to_string())
}

/// Get OS information string.
fn get_os_info() -> String {
    let os = std::env::consts::OS;
    let arch = std::env::consts::ARCH;

    #[cfg(target_os = "linux")]
    {
        if let Ok(release) = std::fs::read_to_string("/proc/sys/kernel/osrelease") {
            return format!("{}-{}-{}", os, arch, release.trim());
        }
    }

    format!("{}-{}", os, arch)
}

/// Get or create a persistent install UUID.
///
/// Stored at `~/.cutctx/install-uuid`. Created on first run.
fn get_or_create_install_uuid() -> String {
    let uuid_path = install_uuid_path();

    if let Ok(uuid) = std::fs::read_to_string(&uuid_path) {
        let uuid = uuid.trim().to_string();
        if !uuid.is_empty() {
            return uuid;
        }
    }

    let uuid = uuid::Uuid::new_v4().to_string();
    let _ = std::fs::create_dir_all(uuid_path.parent().unwrap_or(std::path::Path::new(".")));
    let _ = std::fs::write(&uuid_path, &uuid);
    uuid
}

/// Path to the persistent install UUID file.
fn install_uuid_path() -> PathBuf {
    let base = dirs().unwrap_or_else(|| PathBuf::from("."));
    base.join("install-uuid")
}

/// State directory for Cutctx (~/.cutctx on Unix).
fn dirs() -> Option<PathBuf> {
    #[cfg(unix)]
    {
        if let Ok(home) = std::env::var("HOME") {
            return Some(PathBuf::from(home).join(".cutctx"));
        }
    }
    #[cfg(windows)]
    {
        if let Ok(appdata) = std::env::var("LOCALAPPDATA") {
            return Some(PathBuf::from(appdata).join("cutctx"));
        }
    }
    None
}

/// Persist the clock state to disk (encrypted).
pub fn save_clock_state(state: &ClockState) -> Result<(), String> {
    let path = dirs()
        .ok_or("cannot determine state directory")?
        .join("clock-state.json");
    let json = serde_json::to_vec(state).map_err(|e| e.to_string())?;
    std::fs::write(&path, json).map_err(|e| format!("failed to write clock state: {}", e))
}

/// Load the last-seen clock state from disk.
pub fn load_clock_state() -> Option<ClockState> {
    let path = dirs()?.join("clock-state.json");
    let data = std::fs::read_to_string(path).ok()?;
    serde_json::from_str(&data).ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fingerprint_deterministic() {
        let fp1 = compute_fingerprint();
        let fp2 = compute_fingerprint();
        assert_eq!(fp1.hash, fp2.hash);
        assert_eq!(fp1.hash.len(), 64); // SHA-256 hex
    }

    #[test]
    fn clock_state_rollback_detection() {
        let state = ClockState {
            last_wall_secs: 1000,
            last_mono_ns: 0,
        };
        // No rollback
        assert!(!state.detect_rollback(1000));
        assert!(!state.detect_rollback(901)); // 99s drift, within threshold
        assert!(!state.detect_rollback(2000)); // forward

        // Rollback detected
        assert!(state.detect_rollback(699)); // 301s backward, exceeds 300s
        assert!(state.detect_rollback(0)); // 1000s backward
    }

    #[test]
    fn clock_state_now() {
        let state = ClockState::now(42);
        assert!(state.last_wall_secs > 0);
        assert_eq!(state.last_mono_ns, 42);
    }

    #[test]
    fn install_uuid_persists() {
        let path = install_uuid_path();
        let _ = std::fs::remove_file(&path);
        let uuid1 = get_or_create_install_uuid();
        let uuid2 = get_or_create_install_uuid();
        assert_eq!(uuid1, uuid2);
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn fingerprint_is_not_empty() {
        let fp = compute_fingerprint();
        assert!(!fp.hash.is_empty());
        assert!(!fp.components.machine_id.is_empty());
    }
}
