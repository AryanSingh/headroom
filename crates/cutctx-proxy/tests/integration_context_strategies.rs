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

#[tokio::test]
async fn context_strategies_off_keeps_openai_wire_bytes_independent_of_ccr_store() {
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

    let with_store = start_proxy_with_state(
        &upstream.uri(),
        |config| {
            config.compression = true;
            config.compression_mode = CompressionMode::LiveZone;
            config.context_strategies = false;
        },
        |state| state.with_ccr_store(Arc::new(InMemoryCcrStore::new())),
    )
    .await;
    let without_store = start_proxy_with_state(
        &upstream.uri(),
        |config| {
            config.compression = true;
            config.compression_mode = CompressionMode::LiveZone;
            config.context_strategies = false;
        },
        |state| state,
    )
    .await;
    let log_output = (0..400)
        .map(|index| {
            format!("[2024-01-01 00:00:00] INFO compile.rs:42 building module foo_{index}\n")
        })
        .collect::<String>();

    let requests = [
        (
            "/v1/chat/completions",
            json!({
                "model": "gpt-4o",
                "messages": [
                    {"role": "assistant", "content": "diagnostic output"},
                    {"role": "user", "content": log_output}
                ]
            }),
        ),
        (
            "/v1/responses",
            json!({
                "model": "gpt-4o",
                "input": [{
                    "type": "local_shell_call_output",
                    "call_id": "call_1",
                    "output": log_output
                }]
            }),
        ),
    ];

    for (path, request) in requests {
        let bytes = serde_json::to_vec(&request).unwrap();
        for proxy in [&with_store, &without_store] {
            let response = reqwest::Client::new()
                .post(format!("{}{path}", proxy.url()))
                .header("content-type", "application/json")
                .header("x-api-key", "test-payg-key")
                .body(bytes.clone())
                .send()
                .await
                .unwrap();
            assert_eq!(response.status(), 200);
        }
    }

    let anthropic = json!({
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 128,
        "messages": [
            {"role": "assistant", "content": "diagnostic output"},
            {"role": "user", "content": log_output}
        ]
    });
    let response = reqwest::Client::new()
        .post(format!("{}/v1/messages", with_store.url()))
        .header("content-type", "application/json")
        .header("x-api-key", "test-payg-key")
        .json(&anthropic)
        .send()
        .await
        .unwrap();
    assert_eq!(response.status(), 200);

    let captured = captured.lock().unwrap().clone();
    assert_eq!(captured.len(), 5);
    assert_eq!(
        captured[0], captured[1],
        "Chat bytes changed because CCR existed"
    );
    assert_eq!(
        captured[2], captured[3],
        "Responses bytes changed because CCR existed"
    );
    assert!(captured[..4]
        .iter()
        .all(|body| !body.windows(6).any(|w| w == b"<<ccr:")));
    assert!(
        captured[4].windows(6).any(|window| window == b"<<ccr:"),
        "Anthropic must retain its licensed pre-feature CCR behavior"
    );

    with_store.shutdown().await;
    without_store.shutdown().await;
}
