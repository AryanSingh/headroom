use crate::policy::{verify_policy_token, PolicyPayload};
use serde::Deserialize;
use std::collections::HashMap;
use std::sync::RwLock;

static POLICY_CACHE: RwLock<Option<HashMap<String, (PolicyPayload, u64)>>> = RwLock::new(None);

#[derive(Deserialize)]
struct PolicyResponse {
    signed_policy: String,
}

/// Fetch the signed policy for an org/workspace and cache it.
pub async fn fetch_and_cache_policy(
    api_url: &str,
    org_id: &str,
    workspace_id: Option<&str>,
) -> Option<PolicyPayload> {
    let client = reqwest::Client::new();

    let url = if let Some(ws) = workspace_id {
        format!(
            "{}/v1/policies/{}/signed?workspace_id={}",
            api_url, org_id, ws
        )
    } else {
        format!("{}/v1/policies/{}/signed", api_url, org_id)
    };

    if let Ok(resp) = client.get(&url).send().await {
        if resp.status().is_success() {
            if let Ok(data) = resp.json::<PolicyResponse>().await {
                if let Some(payload) = verify_policy_token(&data.signed_policy) {
                    let now = std::time::SystemTime::now()
                        .duration_since(std::time::UNIX_EPOCH)
                        .unwrap()
                        .as_secs();

                    let key = if let Some(ws) = workspace_id {
                        format!("{}::{}", org_id, ws)
                    } else {
                        org_id.to_string()
                    };

                    let mut cache = POLICY_CACHE.write().unwrap();
                    if cache.is_none() {
                        *cache = Some(HashMap::new());
                    }
                    if let Some(map) = cache.as_mut() {
                        map.insert(key, (payload.clone(), now));
                    }

                    return Some(payload);
                }
            }
        }
    }
    None
}

pub fn get_policy(
    api_url: &str,
    org_id: &str,
    workspace_id: Option<&str>,
) -> Option<PolicyPayload> {
    let key = if let Some(ws) = workspace_id {
        format!("{}::{}", org_id, ws)
    } else {
        org_id.to_string()
    };

    let cache = POLICY_CACHE.read().unwrap();
    let mut needs_refresh = false;
    let mut ret_payload = None;

    if let Some(map) = cache.as_ref() {
        if let Some((payload, timestamp)) = map.get(&key) {
            let now = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs();

            // 5 min TTL for refresh
            if now > timestamp + 300 {
                needs_refresh = true;
            }
            ret_payload = Some(payload.clone());
        } else {
            needs_refresh = true;
        }
    } else {
        needs_refresh = true;
    }

    if needs_refresh {
        let api_url = api_url.to_string();
        let org_id = org_id.to_string();
        let ws_id = workspace_id.map(String::from);

        tokio::spawn(async move {
            fetch_and_cache_policy(&api_url, &org_id, ws_id.as_deref()).await;
        });
    }

    ret_payload
}
