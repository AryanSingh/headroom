use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::sync::RwLock;

static CRL_CACHE: RwLock<Option<HashSet<String>>> = RwLock::new(None);

#[derive(Serialize)]
struct ActivateRequest<'a> {
    license_key: &'a str,
    instance_id: &'a str,
}

#[derive(Deserialize)]
struct CrlResponse {
    revoked: Vec<String>,
}

/// Activate the proxy instance and fetch the CRL. Fails open on errors.
pub async fn activate_and_fetch_crl(
    api_url: &str,
    license_key: &str,
    instance_id: &str,
) -> Result<(), reqwest::Error> {
    let client = reqwest::Client::new();
    
    // 1. Activate
    let _ = client.post(&format!("{}/v1/license/activate", api_url))
        .json(&ActivateRequest { license_key, instance_id })
        .send()
        .await;
        
    // 2. Fetch CRL
    if let Ok(resp) = client.get(&format!("{}/v1/license/crl", api_url)).send().await {
        if resp.status().is_success() {
            if let Ok(crl) = resp.json::<CrlResponse>().await {
                let mut cache = CRL_CACHE.write().unwrap();
                *cache = Some(crl.revoked.into_iter().collect());
            }
        }
    }
    
    Ok(())
}

/// Check if a license is revoked. Uses the local CRL cache and fails open.
pub fn is_revoked(license_key: &str) -> bool {
    let cache = CRL_CACHE.read().unwrap();
    if let Some(revoked) = cache.as_ref() {
        revoked.contains(license_key)
    } else {
        false
    }
}

#[derive(Serialize)]
struct CheckoutSeatRequest<'a> {
    license_key: &'a str,
    user_id: &'a str,
    lease_duration: f64,
}

/// Checkout or renew a seat lease. Returns false if no seats available, true otherwise (fails open).
pub async fn checkout_seat(api_url: &str, license_key: &str, user_id: &str) -> bool {
    let client = reqwest::Client::new();
    match client.post(&format!("{}/v1/license/checkout-seat", api_url))
        .json(&CheckoutSeatRequest { license_key, user_id, lease_duration: 3600.0 })
        .send()
        .await 
    {
        Ok(resp) => {
            if resp.status() == reqwest::StatusCode::TOO_MANY_REQUESTS {
                false // No seats available
            } else {
                true // OK or other error (fail open)
            }
        }
        Err(_) => true // Fail open on network error
    }
}
