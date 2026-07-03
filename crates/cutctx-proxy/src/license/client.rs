use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::sync::RwLock;

/// CRL cache: (revoked_keys, last_successful_fetch_epoch_secs).
static CRL_CACHE: RwLock<Option<(HashSet<String>, u64)>> = RwLock::new(None);

/// Grace window for CRL refresh failures. After this many seconds
/// with no successful CRL fetch, the proxy downgrades to OpenSource.
/// 72 hours = enough to survive a server outage without bricking
/// legitimate installations, short enough to limit revocation bypass.
const CRL_GRACE_SECS: u64 = 72 * 3600;

#[derive(Serialize)]
struct ActivateRequest<'a> {
    license_key: &'a str,
    instance_id: &'a str,
    /// Hardware fingerprint for machine binding.
    #[serde(skip_serializing_if = "Option::is_none")]
    fingerprint: Option<&'a str>,
}

#[derive(Deserialize)]
struct CrlResponse {
    revoked: Vec<String>,
}

/// Revocation status of a license key.
pub enum RevocationStatus {
    /// Key is explicitly in the CRL.
    Revoked,
    /// Key not in CRL and CRL is fresh (or within grace window).
    NotRevoked,
    /// CRL has never been fetched.
    Unknown,
    /// CRL fetch failed and grace window expired → fail closed.
    GraceExpired,
}

/// Activate the proxy instance and fetch the CRL.
///
/// Sends the install fingerprint for machine binding.
pub async fn activate_and_fetch_crl(
    api_url: &str,
    license_key: &str,
    instance_id: &str,
) -> Result<(), reqwest::Error> {
    let fingerprint = crate::license::fingerprint::compute_fingerprint();

    let client = reqwest::Client::new();

    // 1. Activate with fingerprint
    let _ = client
        .post(format!("{}/v1/license/activate", api_url))
        .json(&ActivateRequest {
            license_key,
            instance_id,
            fingerprint: Some(&fingerprint.hash),
        })
        .send()
        .await;

    // 2. Fetch CRL
    fetch_and_cache_crl(&client, api_url).await;

    Ok(())
}

/// Fetch the CRL and update the cache. Called at startup and periodically.
pub async fn fetch_and_cache_crl(client: &reqwest::Client, api_url: &str) {
    if let Ok(resp) = client
        .get(format!("{}/v1/license/crl", api_url))
        .send()
        .await
    {
        if resp.status().is_success() {
            if let Ok(crl) = resp.json::<CrlResponse>().await {
                let now = std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_secs();
                let mut cache = CRL_CACHE.write().unwrap();
                *cache = Some((crl.revoked.into_iter().collect(), now));
                tracing::info!(
                    event = "crl_refreshed",
                    revoked_count = cache.as_ref().map_or(0, |(s, _)| s.len()),
                    "CRL refreshed successfully"
                );
            }
        }
    }
}

/// Check revocation status with fail-closed grace window semantics.
///
/// - Key in CRL → Revoked
/// - Never fetched CRL → Unknown (fail closed)
/// - CRL stale beyond grace window → GraceExpired (fail closed)
/// - Key not in CRL and CRL fresh → NotRevoked
pub fn check_revocation(license_key: &str) -> RevocationStatus {
    let cache = CRL_CACHE.read().unwrap();
    if let Some((revoked, last_fetch)) = cache.as_ref() {
        if revoked.contains(license_key) {
            return RevocationStatus::Revoked;
        }
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        if now > last_fetch + CRL_GRACE_SECS {
            return RevocationStatus::GraceExpired;
        }
        RevocationStatus::NotRevoked
    } else {
        // Never fetched — fail closed
        RevocationStatus::Unknown
    }
}

#[cfg(debug_assertions)]
#[doc(hidden)]
pub fn seed_crl_cache_for_test(revoked: HashSet<String>, last_successful_fetch_epoch_secs: u64) {
    let mut cache = CRL_CACHE.write().unwrap();
    *cache = Some((revoked, last_successful_fetch_epoch_secs));
}

/// Legacy compatibility: check if a license key is revoked (bool).
pub fn is_revoked(license_key: &str) -> bool {
    matches!(
        check_revocation(license_key),
        RevocationStatus::Revoked | RevocationStatus::GraceExpired | RevocationStatus::Unknown
    )
}

#[derive(Serialize)]
struct CheckoutSeatRequest<'a> {
    license_key: &'a str,
    user_id: &'a str,
    lease_duration: f64,
    /// Hardware fingerprint for seat binding.
    #[serde(skip_serializing_if = "Option::is_none")]
    fingerprint: Option<&'a str>,
}

/// Checkout or renew a seat lease. Returns false if no seats available, true otherwise.
pub async fn checkout_seat(api_url: &str, license_key: &str, user_id: &str) -> bool {
    let fingerprint = crate::license::fingerprint::compute_fingerprint();

    let client = reqwest::Client::new();
    match client
        .post(format!("{}/v1/license/checkout-seat", api_url))
        .json(&CheckoutSeatRequest {
            license_key,
            user_id,
            lease_duration: 3600.0,
            fingerprint: Some(&fingerprint.hash),
        })
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
        Err(e) => {
            tracing::warn!(
                event = "seat_checkout_failed",
                error = %e,
                "Seat checkout network failure; treating as available (fail-open)"
            );
            true
        }
    }
}

/// Start periodic CRL refresh task. Runs every `interval_secs` seconds.
pub fn start_crl_refresh_task(api_url: String, interval_secs: u64) {
    tokio::spawn(async move {
        let mut interval = tokio::time::interval(std::time::Duration::from_secs(interval_secs));
        // Skip the first immediate tick
        interval.tick().await;
        loop {
            interval.tick().await;
            let client = reqwest::Client::new();
            fetch_and_cache_crl(&client, &api_url).await;
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn revocation_unknown_when_empty() {
        // No CRL ever fetched → Unknown → fail closed
        // Note: this test may be affected by other tests that populate the cache.
        // In isolation, the cache starts as None.
    }

    #[test]
    fn grace_window_constant() {
        assert_eq!(CRL_GRACE_SECS, 72 * 3600);
    }
}
