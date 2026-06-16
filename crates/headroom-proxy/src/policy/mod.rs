pub mod client;

use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::OnceLock;

/// Payload inside the JWT-like hrp1 policy token
#[derive(Debug, Deserialize, Serialize, Clone, Default)]
pub struct PolicyPayload {
    pub v: u64,
    pub budget_usd: Option<f64>,
    pub budget_period: Option<String>,
    pub rpm: Option<u64>,
    pub tpm: Option<u64>,
    pub models: Option<String>,
    pub req_comp: Option<bool>,
    pub ts: Option<u64>,
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
        let env_keys = std::env::var("HEADROOM_POLICY_PUBLIC_KEYS")
            .or_else(|_| std::env::var("HEADROOM_LICENSE_PUBLIC_KEYS"))
            .unwrap_or_default();
            
        for pair in env_keys.split(',') {
            if let Some((kid, hex_key)) = pair.split_once(':') {
                if let Ok(bytes) = hex::decode(hex_key) {
                    if let Ok(key) = VerifyingKey::try_from(bytes.as_slice()) {
                        map.insert(kid.to_string(), key);
                    }
                }
            }
        }
        map
    })
}

pub fn verify_policy_token(token: &str) -> Option<PolicyPayload> {
    // Format: hrp1.{kid}.{payload_base64url}.{signature_base64url}
    let parts: Vec<&str> = token.split('.').collect();
    if parts.len() != 4 || parts[0] != "hrp1" {
        tracing::warn!("Policy token rejected: invalid hrp1 format");
        return None;
    }

    let kid = parts[1];
    let payload_b64 = parts[2];
    let sig_b64 = parts[3];

    let keys = public_keys();
    let verifying_key = match keys.get(kid) {
        Some(k) => k,
        None => {
            tracing::warn!("Policy token rejected: unknown kid '{}'", kid);
            return None;
        }
    };

    let sig_bytes = match URL_SAFE_NO_PAD.decode(sig_b64) {
        Ok(b) => b,
        Err(_) => {
            tracing::warn!("Policy token rejected: invalid signature encoding");
            return None;
        }
    };

    let signature = match Signature::from_slice(&sig_bytes) {
        Ok(s) => s,
        Err(_) => {
            tracing::warn!("Policy token rejected: invalid signature length");
            return None;
        }
    };

    // The signed message is "hrp1.{kid}.{payload_base64url}"
    let signed_message = format!("hrp1.{}.{}", kid, payload_b64);

    if verifying_key
        .verify(signed_message.as_bytes(), &signature)
        .is_err()
    {
        tracing::warn!("Policy token rejected: signature verification failed");
        return None;
    }

    let payload_bytes = match URL_SAFE_NO_PAD.decode(payload_b64) {
        Ok(b) => b,
        Err(_) => {
            tracing::warn!("Policy token rejected: invalid payload encoding");
            return None;
        }
    };

    let payload: PolicyPayload = match serde_json::from_slice(&payload_bytes) {
        Ok(p) => p,
        Err(_) => {
            tracing::warn!("Policy token rejected: invalid payload JSON");
            return None;
        }
    };

    Some(payload)
}
