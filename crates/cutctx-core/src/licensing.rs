use hmac::{Hmac, Mac};
use sha2::Sha256;
use std::env;

type HmacSha256 = Hmac<Sha256>;

/// Minimum accepted signature length (hex chars = bits/4).
/// 32 hex chars = 128 bits of HMAC-SHA256 — sufficient for a license key
/// that is rate-limited and not brute-forceable in practice.
const SIG_HEX_LEN: usize = 32;

/// Verifies a Cutctx license HMAC signature.
///
/// Signature format: first `SIG_HEX_LEN` hex chars of
/// `HMAC-SHA256(secret, "{tier}:{random_id}:{customer_id}")`.
///
/// Comparison is done with a constant-time byte-level equality check to
/// prevent timing-oracle attacks. Returns `false` if the secret env var
/// is unset, if the MAC setup fails, or if the provided signature does not
/// match the expected value.
pub fn verify_license_signature(
    tier: &str,
    random_id: &str,
    customer_id: &str,
    signature_hex: &str,
) -> bool {
    // Reject obviously wrong signature lengths up front.
    if signature_hex.len() < SIG_HEX_LEN {
        return false;
    }

    let secret = match env::var("CUTCTX_LICENSE_HMAC_SECRET") {
        Ok(val) if !val.is_empty() => val,
        _ => return false,
    };

    let payload = format!("{}:{}:{}", tier, random_id, customer_id);

    let mut mac = match HmacSha256::new_from_slice(secret.as_bytes()) {
        Ok(m) => m,
        Err(_) => return false,
    };

    mac.update(payload.as_bytes());
    let result = mac.finalize();
    let expected_hex = hex::encode(result.into_bytes()); // 64 lowercase hex chars

    // Constant-time comparison of the first SIG_HEX_LEN characters.
    // We compare byte arrays (same length), not string slices, to avoid
    // any short-circuit branching that leaks timing information.
    let expected_bytes = expected_hex[..SIG_HEX_LEN].as_bytes();
    let provided_bytes = signature_hex[..SIG_HEX_LEN].as_bytes();

    // Constant-time XOR fold: result is 0 iff all bytes are equal.
    let diff: u8 = expected_bytes
        .iter()
        .zip(provided_bytes.iter())
        .fold(0u8, |acc, (a, b)| acc | (a ^ b));

    diff == 0
}
