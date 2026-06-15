pub mod client;

use crate::config::LicenseTier;
use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::OnceLock;

/// Payload inside the JWT-like hrk1 token
#[derive(Debug, Deserialize, Serialize)]
pub struct LicensePayload {
    pub tier: String,
}

/// Public keys mapped by Key ID (kid).
fn public_keys() -> &'static HashMap<String, VerifyingKey> {
    static KEYS: OnceLock<HashMap<String, VerifyingKey>> = OnceLock::new();
    KEYS.get_or_init(|| {
        let mut map = HashMap::new();
        
        // Load from env for testing and dynamic injection. Format: "kid1:hex1,kid2:hex2"
        if let Ok(env_keys) = std::env::var("HEADROOM_LICENSE_PUBLIC_KEYS") {
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

pub fn verify_license_token(token: &str) -> LicenseTier {
    // Format: hrk1.{kid}.{payload_base64url}.{signature_base64url}
    let parts: Vec<&str> = token.split('.').collect();
    if parts.len() != 4 || parts[0] != "hrk1" {
        tracing::warn!("License token rejected: invalid hrk1 format");
        return LicenseTier::OpenSource;
    }

    let kid = parts[1];
    let payload_b64 = parts[2];
    let sig_b64 = parts[3];

    let keys = public_keys();
    let verifying_key = match keys.get(kid) {
        Some(k) => k,
        None => {
            tracing::warn!("License token rejected: unknown kid '{}'", kid);
            return LicenseTier::OpenSource;
        }
    };

    let sig_bytes = match URL_SAFE_NO_PAD.decode(sig_b64) {
        Ok(b) => b,
        Err(_) => {
            tracing::warn!("License token rejected: invalid signature encoding");
            return LicenseTier::OpenSource;
        }
    };

    let signature = match Signature::from_slice(&sig_bytes) {
        Ok(s) => s,
        Err(_) => {
            tracing::warn!("License token rejected: invalid signature length");
            return LicenseTier::OpenSource;
        }
    };

    // The signed message is "hrk1.{kid}.{payload_base64url}"
    let signed_message = format!("hrk1.{}.{}", kid, payload_b64);

    if verifying_key.verify(signed_message.as_bytes(), &signature).is_err() {
        tracing::warn!("License token rejected: signature verification failed");
        return LicenseTier::OpenSource;
    }

    let payload_bytes = match URL_SAFE_NO_PAD.decode(payload_b64) {
        Ok(b) => b,
        Err(_) => {
            tracing::warn!("License token rejected: invalid payload encoding");
            return LicenseTier::OpenSource;
        }
    };

    let payload: LicensePayload = match serde_json::from_slice(&payload_bytes) {
        Ok(p) => p,
        Err(_) => {
            tracing::warn!("License token rejected: invalid payload JSON");
            return LicenseTier::OpenSource;
        }
    };

    if crate::license::client::is_revoked(token) {
        tracing::warn!("License token rejected: key is revoked via CRL");
        return LicenseTier::OpenSource;
    }

    match payload.tier.as_str() {
        "enterprise" => LicenseTier::Enterprise,
        "business" => LicenseTier::Business,
        "team" => LicenseTier::Team,
        _ => LicenseTier::OpenSource,
    }
}
