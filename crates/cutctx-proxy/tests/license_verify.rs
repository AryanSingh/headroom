use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
use ed25519_dalek::{Signer, SigningKey};
use cutctx_proxy::config::LicenseTier;
use serde_json::json;

#[test]
fn test_ed25519_license_verification() {
    let secret_bytes = [42u8; 32];
    let signing_key = SigningKey::from_bytes(&secret_bytes);
    let verifying_key = signing_key.verifying_key();

    // Convert public key to hex for env injection
    let hex_pub = hex::encode(verifying_key.as_bytes());
    std::env::set_var(
        "CUTCTX_LICENSE_PUBLIC_KEYS",
        format!("testkid:{}", hex_pub),
    );

    // Construct valid token
    let payload = json!({
        "tier": "enterprise",
        "org_id": "org_123"
    });
    let payload_b64 = URL_SAFE_NO_PAD.encode(payload.to_string());

    let signed_message = format!("hrk1.testkid.{}", payload_b64);
    let signature = signing_key.sign(signed_message.as_bytes());
    let sig_b64 = URL_SAFE_NO_PAD.encode(signature.to_bytes());

    let token = format!("{}.{}", signed_message, sig_b64);

    // Verify it resolves to Enterprise
    let tier = cutctx_proxy::license::verify_license_token(&token);
    assert_eq!(tier, LicenseTier::Enterprise);

    // Verify fallback from config matches
    let config_tier = LicenseTier::from_license_key(&token);
    assert_eq!(config_tier, LicenseTier::Enterprise);

    // Test tamper resistance
    let mut tampered_token = token.clone();
    tampered_token.replace_range(15..16, "X"); // Corrupt payload a bit
    assert_eq!(
        LicenseTier::from_license_key(&tampered_token),
        LicenseTier::OpenSource
    );

    // Test unknown kid
    let unknown_kid = token.replace("testkid", "unknown");
    assert_eq!(
        LicenseTier::from_license_key(&unknown_kid),
        LicenseTier::OpenSource
    );
}
