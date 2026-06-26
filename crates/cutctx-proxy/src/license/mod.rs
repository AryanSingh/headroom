pub mod client;
pub mod fingerprint;

use crate::config::LicenseTier;
use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::OnceLock;

/// CRL grace window in seconds. After this period with no successful
/// CRL refresh, the proxy downgrades to OpenSource (commercial features off).
pub const CRL_GRACE_SECS: u64 = 72 * 3600; // 72 hours

/// Payload inside the JWT-like hrk1 token
#[derive(Debug, Deserialize, Serialize)]
pub struct LicensePayload {
    pub tier: String,
    pub exp: Option<u64>,
    pub nbf: Option<u64>,
    /// Optional install fingerprint for machine binding.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub fingerprint: Option<String>,
}

/// Signed entitlement lease — a short-lived token proving valid license.
/// Refreshed periodically via heartbeat; persisted encrypted.
#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct EntitlementLease {
    /// The tier the user is entitled to.
    pub tier: LicenseTier,
    /// Unix timestamp when this lease expires.
    pub expires_at: u64,
    /// The license key this lease is for.
    pub license_key_hash: String,
    /// The install fingerprint this lease is bound to.
    pub fingerprint: String,
}

impl EntitlementLease {
    /// Check if this lease is still valid (not expired and fingerprint matches).
    pub fn is_valid(&self, current_fingerprint: &str) -> bool {
        if self.fingerprint != current_fingerprint {
            return false;
        }
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        now < self.expires_at
    }
}

/// Public keys mapped by Key ID (kid).
fn public_keys() -> &'static HashMap<String, VerifyingKey> {
    static KEYS: OnceLock<HashMap<String, VerifyingKey>> = OnceLock::new();
    KEYS.get_or_init(|| {
        let mut map = HashMap::new();
        // Default compiled-in key for production fallback
        let default_kid = "prod-1";
        let default_hex = "14ae1a81a66d9757d002ff074975d26d2ea2aed88806a5b806f42ad301b5de30";
        if let Ok(bytes) = hex::decode(default_hex) {
            if let Ok(key) = VerifyingKey::try_from(bytes.as_slice()) {
                map.insert(default_kid.to_string(), key);
            }
        }

        // Load from env for testing and dynamic injection. Format: "kid1:hex1,kid2:hex2"
        if let Ok(env_keys) = std::env::var("CUTCTX_LICENSE_PUBLIC_KEYS") {
            for pair in env_keys.split(',') {
                if let Some((kid, hex_key)) = pair.split_once(':') {
                    if let Ok(bytes) = hex::decode(hex_key) {
                        if let Ok(key) = VerifyingKey::try_from(bytes.as_slice()) {
                            map.insert(kid.to_string(), key);
                        }
                    }
                }
            }
        }
        map
    })
}

/// Result of license verification including clock rollback detection.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum LicenseVerifyResult {
    /// License is valid for this tier.
    Valid(LicenseTier),
    /// License is valid but fingerprint doesn't match (possible sharing).
    FingerprintMismatch(LicenseTier),
    /// Clock rollback detected — force re-activation.
    ClockRollbackDetected,
    /// License expired.
    Expired,
    /// License not yet valid.
    NotYetValid,
    /// License revoked via CRL.
    Revoked,
    /// CRL grace window expired — downgrade to OpenSource.
    CrlGraceExpired,
    /// Token format invalid.
    InvalidToken,
}

pub fn verify_license_token(token: &str) -> LicenseTier {
    // Legacy compatibility: return just the tier for callers that don't
    // need the full verification result.
    match verify_license_token_detailed(token, None) {
        LicenseVerifyResult::Valid(tier)
        | LicenseVerifyResult::FingerprintMismatch(tier) => tier,
        _ => LicenseTier::OpenSource,
    }
}

/// Full license verification with fingerprint binding, clock rollback
/// detection, and CRL fail-closed behavior.
pub fn verify_license_token_detailed(
    token: &str,
    current_fingerprint: Option<&str>,
) -> LicenseVerifyResult {
    // Format: hrk1.{kid}.{payload_base64url}.{signature_base64url}
    let parts: Vec<&str> = token.split('.').collect();
    if parts.len() != 4 || parts[0] != "hrk1" {
        tracing::warn!("License token rejected: invalid hrk1 format");
        return LicenseVerifyResult::InvalidToken;
    }

    let kid = parts[1];
    let payload_b64 = parts[2];
    let sig_b64 = parts[3];

    let keys = public_keys();
    let verifying_key = match keys.get(kid) {
        Some(k) => k,
        None => {
            tracing::warn!("License token rejected: unknown kid '{}'", kid);
            return LicenseVerifyResult::InvalidToken;
        }
    };

    let sig_bytes = match URL_SAFE_NO_PAD.decode(sig_b64) {
        Ok(b) => b,
        Err(_) => {
            tracing::warn!("License token rejected: invalid signature encoding");
            return LicenseVerifyResult::InvalidToken;
        }
    };

    let signature = match Signature::from_slice(&sig_bytes) {
        Ok(s) => s,
        Err(_) => {
            tracing::warn!("License token rejected: invalid signature length");
            return LicenseVerifyResult::InvalidToken;
        }
    };

    // The signed message is "hrk1.{kid}.{payload_base64url}"
    let signed_message = format!("hrk1.{}.{}", kid, payload_b64);

    if verifying_key
        .verify(signed_message.as_bytes(), &signature)
        .is_err()
    {
        tracing::warn!("License token rejected: signature verification failed");
        return LicenseVerifyResult::InvalidToken;
    }

    let payload_bytes = match URL_SAFE_NO_PAD.decode(payload_b64) {
        Ok(b) => b,
        Err(_) => {
            tracing::warn!("License token rejected: invalid payload encoding");
            return LicenseVerifyResult::InvalidToken;
        }
    };

    let payload: LicensePayload = match serde_json::from_slice(&payload_bytes) {
        Ok(p) => p,
        Err(_) => {
            tracing::warn!("License token rejected: invalid payload JSON");
            return LicenseVerifyResult::InvalidToken;
        }
    };

    // CRL check — fail-closed after grace window
    match client::check_revocation(token) {
        client::RevocationStatus::Revoked => {
            tracing::warn!("License token rejected: key is revoked via CRL");
            return LicenseVerifyResult::Revoked;
        }
        client::RevocationStatus::GraceExpired => {
            tracing::warn!(
                "License token rejected: CRL grace window expired ({}s); \
                 commercial features disabled until CRL refresh succeeds",
                CRL_GRACE_SECS
            );
            return LicenseVerifyResult::CrlGraceExpired;
        }
        client::RevocationStatus::NotRevoked => {}
        client::RevocationStatus::Unknown => {
            // Never fetched CRL — fail closed
            tracing::warn!("License token rejected: CRL never fetched (fail-closed)");
            return LicenseVerifyResult::CrlGraceExpired;
        }
    }

    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();

    if let Some(nbf) = payload.nbf {
        if now < nbf {
            tracing::warn!("License token rejected: not yet valid (nbf)");
            return LicenseVerifyResult::NotYetValid;
        }
    }

    if let Some(exp) = payload.exp {
        if now > exp {
            tracing::warn!("License token rejected: expired");
            return LicenseVerifyResult::Expired;
        }
    }

    // Clock rollback detection
    if let Some(fp) = current_fingerprint {
        if let Some(stored_fp) = &payload.fingerprint {
            if stored_fp != fp {
                tracing::warn!(
                    "License token: fingerprint mismatch (expected '{}', got '{}'); \
                     possible unauthorized machine transfer",
                    stored_fp,
                    fp
                );
                // Still return valid tier but flag the mismatch —
                // the caller can decide whether to downgrade.
                let tier = parse_tier(&payload.tier);
                return LicenseVerifyResult::FingerprintMismatch(tier);
            }
        }
    }

    // Check clock rollback using stored state
    if let Some(clock_state) = fingerprint::load_clock_state() {
        if clock_state.detect_rollback(now) {
            tracing::warn!(
                "License: clock rollback detected! Wall clock jumped backward by >{}s. \
                 Forcing re-activation.",
                fingerprint::ClockState::MAX_BACKWARD_DRIFT_SECS
            );
            return LicenseVerifyResult::ClockRollbackDetected;
        }
    }

    // Update clock state
    let clock_state = fingerprint::ClockState::now(0);
    let _ = fingerprint::save_clock_state(&clock_state);

    LicenseVerifyResult::Valid(parse_tier(&payload.tier))
}

fn parse_tier(tier_str: &str) -> LicenseTier {
    match tier_str {
        "enterprise" => LicenseTier::Enterprise,
        "business" => LicenseTier::Business,
        "team" => LicenseTier::Team,
        _ => LicenseTier::OpenSource,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_tier_variants() {
        assert_eq!(parse_tier("enterprise"), LicenseTier::Enterprise);
        assert_eq!(parse_tier("business"), LicenseTier::Business);
        assert_eq!(parse_tier("team"), LicenseTier::Team);
        assert_eq!(parse_tier("unknown"), LicenseTier::OpenSource);
        assert_eq!(parse_tier(""), LicenseTier::OpenSource);
    }

    #[test]
    fn entitlement_lease_validity() {
        use std::time::{SystemTime, UNIX_EPOCH};
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        let lease = EntitlementLease {
            tier: LicenseTier::Enterprise,
            expires_at: now + 3600,
            license_key_hash: "abc123".into(),
            fingerprint: "fp1".into(),
        };
        assert!(lease.is_valid("fp1"));
        assert!(!lease.is_valid("fp2")); // wrong fingerprint

        let expired_lease = EntitlementLease {
            tier: LicenseTier::Enterprise,
            expires_at: now - 100,
            license_key_hash: "abc123".into(),
            fingerprint: "fp1".into(),
        };
        assert!(!expired_lease.is_valid("fp1")); // expired
    }

    #[test]
    fn verify_invalid_format() {
        assert_eq!(
            verify_license_token_detailed("not-a-token", None),
            LicenseVerifyResult::InvalidToken
        );
        assert_eq!(
            verify_license_token_detailed("hrk1.kid.payload.sig.extra", None),
            LicenseVerifyResult::InvalidToken
        );
        assert_eq!(
            verify_license_token_detailed("", None),
            LicenseVerifyResult::InvalidToken
        );
    }
}
