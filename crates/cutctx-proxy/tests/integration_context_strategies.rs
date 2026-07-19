mod common;

use std::sync::{Arc, Mutex};

use common::start_proxy_with_state;
use cutctx_core::ccr::{CcrStore, InMemoryCcrStore};
use cutctx_proxy::config::CompressionMode;
use serde_json::{json, Value};
use wiremock::matchers::method;
use wiremock::{Mock, MockServer, ResponseTemplate};

fn ccr_key(body: &Value) -> String {
    let serialized = serde_json::to_string(body).unwrap();
    let start = serialized.find("<<ccr:").expect("CCR marker") + "<<ccr:".len();
    serialized[start..start + 16].to_string()
}

#[tokio::test]
async fn selective_clear_is_reversible_across_buffered_provider_shapes() {
    let upstream = MockServer::start().await;
    let captured = Arc::new(Mutex::new(Vec::<(String, Vec<u8>)>::new()));
    let captured_for_mock = captured.clone();
    Mock::given(method("POST"))
        .respond_with(move |request: &wiremock::Request| {
            captured_for_mock
                .lock()
                .unwrap()
                .push((request.url.path().to_string(), request.body.clone()));
            ResponseTemplate::new(200).set_body_json(json!({"ok": true}))
        })
        .mount(&upstream)
        .await;

    let store = Arc::new(InMemoryCcrStore::new());
    let state_store = store.clone();
    let proxy = start_proxy_with_state(
        &upstream.uri(),
        |config| {
            config.compression = true;
            config.compression_mode = CompressionMode::LiveZone;
            config.context_strategies = true;
        },
        move |state| state.with_ccr_store(state_store),
    )
    .await;
    let long_old_turn = format!(
        "obsolete deployment archive {}",
        "legacy_payload_token ".repeat(160)
    );
    let requests = [
        (
            "/v1/messages",
            json!({
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 128,
                "messages": [
                    {"role": "user", "content": "earlier unrelated question"},
                    {"role": "assistant", "content": long_old_turn},
                    {"role": "user", "content": "fix websocket authentication"}
                ]
            }),
        ),
        (
            "/v1/chat/completions",
            json!({
                "model": "gpt-4o",
                "messages": [
                    {"role": "user", "content": "earlier unrelated question"},
                    {"role": "assistant", "content": long_old_turn},
                    {"role": "user", "content": "fix websocket authentication"}
                ]
            }),
        ),
        (
            "/v1/responses",
            json!({
                "model": "gpt-4o",
                "input": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": long_old_turn}]
                    },
                    {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "fix websocket authentication"}]
                    }
                ]
            }),
        ),
    ];

    for (path, body) in requests {
        let response = reqwest::Client::new()
            .post(format!("{}{path}", proxy.url()))
            .header("content-type", "application/json")
            .header("x-api-key", "test-payg-key")
            .header("x-cutctx-session-id", format!("session-{path}"))
            .header("x-cutctx-strategy", "selective_clear")
            .json(&body)
            .send()
            .await
            .unwrap();
        assert_eq!(response.status(), 200);
    }

    let captured = captured.lock().unwrap().clone();
    assert_eq!(captured.len(), 3);
    for (_, body) in captured.iter() {
        let body: Value = serde_json::from_slice(body).unwrap();
        let key = ccr_key(&body);
        assert!(
            store.get(&key).is_some(),
            "every marker must be retrievable"
        );
    }
    proxy.shutdown().await;
}

#[tokio::test]
async fn snapshot_resume_reuses_session_snapshot_on_repeat_request() {
    let upstream = MockServer::start().await;
    let captured = Arc::new(Mutex::new(Vec::<Vec<u8>>::new()));
    let captured_for_mock = captured.clone();
    Mock::given(method("POST"))
        .respond_with(move |request: &wiremock::Request| {
            captured_for_mock.lock().unwrap().push(request.body.clone());
            ResponseTemplate::new(200).set_body_json(json!({"ok": true}))
        })
        .mount(&upstream)
        .await;

    let store = Arc::new(InMemoryCcrStore::new());
    let state_store = store.clone();
    let proxy = start_proxy_with_state(
        &upstream.uri(),
        |config| {
            config.compression = true;
            config.compression_mode = CompressionMode::LiveZone;
            config.context_strategies = true;
        },
        move |state| state.with_ccr_store(state_store),
    )
    .await;
    let body = json!({
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 128,
        "messages": (0..8)
            .map(|index| json!({
                "role": if index % 2 == 0 { "user" } else { "assistant" },
                "content": format!("historical turn {index}")
            }))
            .collect::<Vec<_>>()
    });

    for _ in 0..2 {
        let response = reqwest::Client::new()
            .post(format!("{}/v1/messages", proxy.url()))
            .header("content-type", "application/json")
            .header("x-api-key", "test-payg-key")
            .header("x-cutctx-session-id", "stable-snapshot-session")
            .header("x-cutctx-strategy", "snapshot_resume")
            .json(&body)
            .send()
            .await
            .unwrap();
        assert_eq!(response.status(), 200);
    }

    let captured = captured.lock().unwrap().clone();
    assert_eq!(captured.len(), 2);
    let first: Value = serde_json::from_slice(&captured[0]).unwrap();
    let second: Value = serde_json::from_slice(&captured[1]).unwrap();
    let first_key = ccr_key(&first);
    let second_key = ccr_key(&second);
    assert_eq!(first_key, second_key);
    assert_eq!(store.len(), 1);
    assert!(store.get(&first_key).is_some());
    proxy.shutdown().await;
}
