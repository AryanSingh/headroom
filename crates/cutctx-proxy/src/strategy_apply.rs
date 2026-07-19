//! Active structural context strategies.

use cutctx_core::ccr::CcrStore;
use cutctx_core::compression_policy::CompressionPolicy;
use cutctx_core::transforms::context_strategy::{
    ContextStrategy, StrategyConfig, StrategyDecision,
};
use serde::Deserialize;
use serde_json::value::RawValue;
use serde_json::Value;

#[derive(Debug)]
pub(crate) struct StructuralMutation {
    pub(crate) body: Vec<u8>,
    pub(crate) markers_inserted: Vec<String>,
    pub(crate) snapshot_key: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum StrategyApplyError {
    MalformedBody,
    RawViewMismatch,
    MissingRawItem,
    InvalidRange,
    Serialization,
}

impl StrategyApplyError {
    pub(crate) fn as_str(self) -> &'static str {
        match self {
            Self::MalformedBody => "malformed_body",
            Self::RawViewMismatch => "raw_view_mismatch",
            Self::MissingRawItem => "missing_raw_item",
            Self::InvalidRange => "invalid_range",
            Self::Serialization => "serialization",
        }
    }
}

impl std::fmt::Display for StrategyApplyError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter.write_str(self.as_str())
    }
}

impl std::error::Error for StrategyApplyError {}

pub(crate) type StrategyApplyResult = Result<Option<StructuralMutation>, StrategyApplyError>;

#[derive(Deserialize)]
struct RawBodyView<'a> {
    #[serde(borrow, default)]
    messages: Option<Vec<&'a RawValue>>,
    #[serde(borrow, default)]
    input: Option<Vec<&'a RawValue>>,
}

impl<'a> RawBodyView<'a> {
    fn items(&self, array_name: &str) -> Option<&Vec<&'a RawValue>> {
        match array_name {
            "messages" => self.messages.as_ref(),
            "input" => self.input.as_ref(),
            _ => None,
        }
    }
}

struct Replacement {
    range: (usize, usize),
    replacement: Vec<u8>,
}

fn raw_range(body: &[u8], raw: &RawValue) -> Option<(usize, usize)> {
    let body_start = body.as_ptr() as usize;
    let body_end = body_start + body.len();
    let raw_start = raw.get().as_ptr() as usize;
    let raw_end = raw_start + raw.get().len();
    (raw_start >= body_start && raw_end <= body_end)
        .then_some((raw_start - body_start, raw_end - body_start))
}

fn apply_replacements(
    body: &[u8],
    mut replacements: Vec<Replacement>,
) -> Result<Vec<u8>, StrategyApplyError> {
    replacements.sort_by_key(|replacement| replacement.range.0);
    let mut cursor = 0;
    let mut output = Vec::with_capacity(body.len());
    for replacement in replacements {
        if replacement.range.0 < cursor || replacement.range.1 > body.len() {
            return Err(StrategyApplyError::InvalidRange);
        }
        output.extend_from_slice(&body[cursor..replacement.range.0]);
        output.extend_from_slice(&replacement.replacement);
        cursor = replacement.range.1;
    }
    output.extend_from_slice(&body[cursor..]);
    Ok(output)
}

fn finalize_rewrite(
    body: &[u8],
    replacements: Vec<Replacement>,
    pending_writes: Vec<(String, String)>,
    store: &dyn CcrStore,
) -> Result<Vec<u8>, StrategyApplyError> {
    let rewritten = apply_replacements(body, replacements)?;
    for (key, payload) in pending_writes {
        store.put(&key, &payload);
    }
    Ok(rewritten)
}

pub(crate) fn apply_selective_clear(
    body: &[u8],
    frozen_count: usize,
    policy: &CompressionPolicy,
    config: &StrategyConfig,
    store: &dyn CcrStore,
) -> StrategyApplyResult {
    let parsed: Value =
        serde_json::from_slice(body).map_err(|_| StrategyApplyError::MalformedBody)?;
    let array_name = if parsed.get("messages").and_then(Value::as_array).is_some() {
        "messages"
    } else if parsed.get("input").and_then(Value::as_array).is_some() {
        "input"
    } else {
        return Ok(None);
    };
    let messages = parsed
        .get(array_name)
        .and_then(Value::as_array)
        .ok_or(StrategyApplyError::RawViewMismatch)?;
    let live_count = messages.len().saturating_sub(frozen_count);
    let clear_cap = ((live_count as f32) * config.max_clear_ratio).floor() as usize;
    if clear_cap == 0 {
        return Ok(None);
    }
    let candidates = crate::strategy_shadow::low_value_turn_indices(
        &parsed,
        messages,
        frozen_count,
        policy,
        config,
    );
    let raw_view: RawBodyView<'_> =
        serde_json::from_slice(body).map_err(|_| StrategyApplyError::RawViewMismatch)?;
    let raw_messages = raw_view
        .items(array_name)
        .ok_or(StrategyApplyError::RawViewMismatch)?;
    let mut markers_inserted = Vec::new();
    let mut replacements = Vec::new();
    let mut pending_writes = Vec::new();
    for index in candidates.into_iter().take(clear_cap) {
        let original = raw_messages
            .get(index)
            .ok_or(StrategyApplyError::MissingRawItem)?
            .get();
        let key = cutctx_core::ccr::compute_key(original.as_bytes());
        let marker = cutctx_core::ccr::marker_for(&key);
        let replacement = format!("[cutctx: turn elided — retrieve with {marker}]");
        let mut rewritten_message = messages
            .get(index)
            .ok_or(StrategyApplyError::MissingRawItem)?
            .clone();
        if replace_message_text(&mut rewritten_message, &replacement) {
            markers_inserted.push(marker);
            pending_writes.push((key, original.to_string()));
            replacements.push(Replacement {
                range: raw_range(
                    body,
                    raw_messages
                        .get(index)
                        .ok_or(StrategyApplyError::MissingRawItem)?,
                )
                .ok_or(StrategyApplyError::InvalidRange)?,
                replacement: serde_json::to_vec(&rewritten_message)
                    .map_err(|_| StrategyApplyError::Serialization)?,
            });
        }
    }

    if markers_inserted.is_empty() {
        return Ok(None);
    }
    let rewritten_body = finalize_rewrite(body, replacements, pending_writes, store)?;
    Ok(Some(StructuralMutation {
        body: rewritten_body,
        markers_inserted,
        snapshot_key: None,
    }))
}

pub(crate) fn apply_snapshot_resume(
    body: &[u8],
    frozen_count: usize,
    session_key: &str,
    last_snapshot_key: Option<&str>,
    config: &StrategyConfig,
    store: &dyn CcrStore,
) -> StrategyApplyResult {
    let parsed: Value =
        serde_json::from_slice(body).map_err(|_| StrategyApplyError::MalformedBody)?;
    let array_name = if parsed.get("messages").and_then(Value::as_array).is_some() {
        "messages"
    } else if parsed.get("input").and_then(Value::as_array).is_some() {
        "input"
    } else {
        return Ok(None);
    };
    let messages = parsed
        .get(array_name)
        .and_then(Value::as_array)
        .ok_or(StrategyApplyError::RawViewMismatch)?;
    let Some(snapshot_end) = messages.len().checked_sub(config.keep_tail_turns) else {
        return Ok(None);
    };
    if snapshot_end <= frozen_count {
        return Ok(None);
    }
    if !crate::tool_integrity::snapshot_range_preserves_tool_pairs(
        messages,
        frozen_count,
        snapshot_end,
    ) {
        return Ok(None);
    }
    let snapshotted_messages = messages[frozen_count..snapshot_end].to_vec();

    let mut pending_snapshot = None;
    let snapshot_key = if let Some(existing) = last_snapshot_key
        .filter(|key| cached_snapshot_matches(store, key, session_key, &snapshotted_messages))
    {
        existing.to_string()
    } else {
        let document = serde_json::json!({
            "version": 1,
            "session_key": session_key,
            "messages": snapshotted_messages,
        });
        let payload =
            serde_json::to_string(&document).map_err(|_| StrategyApplyError::Serialization)?;
        let key = cutctx_core::ccr::compute_key(payload.as_bytes());
        pending_snapshot = Some((key.clone(), payload));
        key
    };
    let marker = cutctx_core::ccr::marker_for(&snapshot_key);
    let mut digests = snapshotted_messages
        .iter()
        .map(|message| message_digest(message, config.digest_chars))
        .collect::<Vec<_>>();
    digests.push(marker.clone());
    let summary = format!("[cutctx: session snapshot]\n{}", digests.join("\n"));
    let summary_message = if array_name == "input" {
        serde_json::json!({
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": summary}],
        })
    } else {
        serde_json::json!({"role": "user", "content": summary})
    };
    let raw_view: RawBodyView<'_> =
        serde_json::from_slice(body).map_err(|_| StrategyApplyError::RawViewMismatch)?;
    let raw_messages = raw_view
        .items(array_name)
        .ok_or(StrategyApplyError::RawViewMismatch)?;
    let first_range = raw_range(
        body,
        raw_messages
            .get(frozen_count)
            .ok_or(StrategyApplyError::MissingRawItem)?,
    )
    .ok_or(StrategyApplyError::InvalidRange)?;
    let last_range = raw_range(
        body,
        raw_messages
            .get(snapshot_end - 1)
            .ok_or(StrategyApplyError::MissingRawItem)?,
    )
    .ok_or(StrategyApplyError::InvalidRange)?;
    let pending_writes = pending_snapshot.into_iter().collect();
    let rewritten_body = finalize_rewrite(
        body,
        vec![Replacement {
            range: (first_range.0, last_range.1),
            replacement: serde_json::to_vec(&summary_message)
                .map_err(|_| StrategyApplyError::Serialization)?,
        }],
        pending_writes,
        store,
    )?;

    Ok(Some(StructuralMutation {
        body: rewritten_body,
        markers_inserted: vec![marker],
        snapshot_key: Some(snapshot_key),
    }))
}

fn cached_snapshot_matches(
    store: &dyn CcrStore,
    key: &str,
    session_key: &str,
    messages: &[Value],
) -> bool {
    store
        .get(key)
        .and_then(|payload| serde_json::from_str::<Value>(&payload).ok())
        .is_some_and(|snapshot| {
            snapshot.get("version").and_then(Value::as_u64) == Some(1)
                && snapshot.get("session_key").and_then(Value::as_str) == Some(session_key)
                && snapshot
                    .get("messages")
                    .and_then(Value::as_array)
                    .is_some_and(|stored| stored.as_slice() == messages)
        })
}

pub(crate) fn apply_selected_structural_strategy(
    body: &[u8],
    decision: &StrategyDecision,
    policy: &CompressionPolicy,
    config: &StrategyConfig,
    store: &dyn CcrStore,
    session_key: &crate::session_state::SessionKey,
    session_state: &crate::session_state::SessionStateStore,
) -> StrategyApplyResult {
    match decision.strategy {
        ContextStrategy::SelectiveClear => apply_selective_clear(
            body,
            decision.signals.frozen_message_count,
            policy,
            config,
            store,
        ),
        ContextStrategy::SnapshotResume => {
            let last_snapshot_key = session_state
                .get(session_key)
                .and_then(|entry| entry.last_snapshot_key);
            let mutation = apply_snapshot_resume(
                body,
                decision.signals.frozen_message_count,
                &session_key.value,
                last_snapshot_key.as_deref(),
                config,
                store,
            )?;
            if let Some(snapshot_key) = mutation
                .as_ref()
                .and_then(|result| result.snapshot_key.as_ref())
            {
                session_state.set_snapshot_key(session_key, snapshot_key.clone());
            }
            Ok(mutation)
        }
        ContextStrategy::RollingWindow | ContextStrategy::SmartCompact => Ok(None),
    }
}

fn message_digest(message: &Value, max_chars: usize) -> String {
    let role = message
        .get("role")
        .and_then(Value::as_str)
        .unwrap_or("item");
    let mut text = crate::strategy_shadow::message_text(message);
    let mut tools = Vec::new();
    if let Some(calls) = message.get("tool_calls").and_then(Value::as_array) {
        tools.extend(calls.iter().filter_map(|call| {
            call.get("function")
                .and_then(|function| function.get("name"))
                .and_then(Value::as_str)
                .map(|name| format!("tool:{name}"))
        }));
    }
    if let Some(blocks) = message.get("content").and_then(Value::as_array) {
        tools.extend(blocks.iter().filter_map(|block| {
            (block.get("type").and_then(Value::as_str) == Some("tool_use"))
                .then(|| block.get("name").and_then(Value::as_str))
                .flatten()
                .map(|name| format!("tool:{name}"))
        }));
    }
    if !tools.is_empty() {
        if !text.is_empty() {
            text.push(' ');
        }
        text.push_str(&tools.join(" "));
    }
    let digest = text.chars().take(max_chars).collect::<String>();
    format!("{role}: {}", digest.replace('\n', " "))
}

fn replace_message_text(message: &mut Value, replacement: &str) -> bool {
    if let Some(content) = message.get_mut("content") {
        match content {
            Value::String(text) => {
                *text = replacement.to_string();
                return true;
            }
            Value::Array(blocks) => {
                if let Some(mut block) = blocks
                    .iter()
                    .find(|block| block.get("text").and_then(Value::as_str).is_some())
                    .cloned()
                {
                    if let Some(text) = block.get_mut("text") {
                        *text = Value::String(replacement.to_string());
                        *blocks = vec![block];
                        return true;
                    }
                }
            }
            _ => {}
        }
    }
    if message.get("text").and_then(Value::as_str).is_some() {
        message["text"] = Value::String(replacement.to_string());
        return true;
    }
    false
}

#[cfg(test)]
mod tests {
    use super::*;
    use cutctx_core::auth_mode::AuthMode;
    use cutctx_core::ccr::InMemoryCcrStore;
    use serde_json::{json, Value};

    #[test]
    fn failed_rewrite_does_not_commit_staged_ccr_entries() {
        let store = InMemoryCcrStore::new();
        let error = finalize_rewrite(
            b"abcdef",
            vec![
                Replacement {
                    range: (1, 4),
                    replacement: b"x".to_vec(),
                },
                Replacement {
                    range: (3, 5),
                    replacement: b"y".to_vec(),
                },
            ],
            vec![("pending-key".to_string(), "pending-payload".to_string())],
            &store,
        )
        .expect_err("overlapping ranges must fail");

        assert_eq!(error, StrategyApplyError::InvalidRange);
        assert_eq!(
            store.len(),
            0,
            "failed rewrites must not leave orphan CCR data"
        );
    }

    #[test]
    fn selective_clear_preserves_frozen_prefix_roles_cap_and_originals() {
        let mut messages = Vec::new();
        for index in 0..12 {
            messages.push(json!({
                "role": if index % 2 == 0 { "user" } else { "assistant" },
                "content": format!(
                    "obsolete_topic_{index} {}",
                    format!("archive_token_{index} ").repeat(140)
                )
            }));
        }
        messages.push(json!({
            "role": "user",
            "content": "fix websocket authentication handshake"
        }));
        let original = json!({
            "model": "claude-3-5-sonnet",
            "messages": messages
        });
        let body = serde_json::to_vec(&original).unwrap();
        let store = InMemoryCcrStore::new();

        let mutation = apply_selective_clear(
            &body,
            2,
            &CompressionPolicy::for_mode(AuthMode::Payg),
            &StrategyConfig::default(),
            &store,
        )
        .expect("strategy application should succeed")
        .expect("eligible old turns should be elided");
        let rewritten: Value = serde_json::from_slice(&mutation.body).unwrap();
        let rewritten_messages = rewritten["messages"].as_array().unwrap();
        let original_messages = original["messages"].as_array().unwrap();

        assert_eq!(&rewritten_messages[..2], &original_messages[..2]);
        assert_eq!(mutation.markers_inserted.len(), 5);
        assert_eq!(store.len(), 5);
        assert!(mutation.snapshot_key.is_none());

        for (before, after) in original_messages.iter().zip(rewritten_messages) {
            assert_eq!(before["role"], after["role"]);
        }
        for marker in &mutation.markers_inserted {
            let key = marker
                .strip_prefix("<<ccr:")
                .and_then(|value| value.strip_suffix(">>"))
                .expect("canonical CCR marker");
            let payload = store.get(key).expect("original turn retrievable");
            let original_turn: Value = serde_json::from_str(&payload).unwrap();
            assert!(original_messages.contains(&original_turn));
        }
    }

    #[test]
    fn selective_clear_skips_tool_protocol_turns() {
        let tool_text = format!("obsolete tool planning {}", "archive_token ".repeat(80));
        let tool_result = format!("obsolete tool result {}", "result_token ".repeat(80));
        let plain_text = format!("obsolete plain archive {}", "plain_token ".repeat(80));
        let original = json!({
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": tool_text},
                        {
                            "type": "tool_use",
                            "id": "toolu_1",
                            "name": "search",
                            "input": {"query": "old"}
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_1",
                            "content": tool_result
                        }
                    ]
                },
                {"role": "assistant", "content": plain_text},
                {"role": "user", "content": "fix websocket authentication"}
            ]
        });
        let body = serde_json::to_vec(&original).unwrap();
        let store = InMemoryCcrStore::new();
        let mut policy = CompressionPolicy::for_mode(AuthMode::Payg);
        policy.volatile_token_threshold = 1;
        let config = StrategyConfig {
            max_clear_ratio: 1.0,
            low_value_score: 1.0,
            ..StrategyConfig::default()
        };

        let mutation = apply_selective_clear(&body, 0, &policy, &config, &store)
            .expect("strategy application should succeed")
            .expect("the unrelated plain-text turn remains eligible");
        let rewritten: Value = serde_json::from_slice(&mutation.body).unwrap();

        assert_eq!(
            rewritten["messages"][0], original["messages"][0],
            "assistant tool_use turn must remain intact"
        );
        assert_eq!(
            rewritten["messages"][1], original["messages"][1],
            "paired tool_result turn must remain intact"
        );
        assert_ne!(
            rewritten["messages"][2], original["messages"][2],
            "unrelated low-value text should still be elided"
        );
    }

    #[test]
    fn snapshot_resume_stores_prefix_and_replaces_it_with_retrievable_summary() {
        let messages = (0..8)
            .map(|index| {
                json!({
                    "role": if index % 2 == 0 { "user" } else { "assistant" },
                    "content": format!("turn {index} {}", "details ".repeat(30))
                })
            })
            .collect::<Vec<_>>();
        let original = json!({ "model": "gpt-5", "messages": messages });
        let body = serde_json::to_vec(&original).unwrap();
        let store = InMemoryCcrStore::new();

        let mutation = apply_snapshot_resume(
            &body,
            2,
            "session-42",
            None,
            &StrategyConfig::default(),
            &store,
        )
        .expect("strategy application should succeed")
        .expect("live prefix before the four-turn tail should be snapshotted");
        let rewritten: Value = serde_json::from_slice(&mutation.body).unwrap();
        let rewritten_messages = rewritten["messages"].as_array().unwrap();
        let original_messages = original["messages"].as_array().unwrap();
        let snapshot_key = mutation.snapshot_key.as_deref().expect("snapshot key");
        let snapshot: Value =
            serde_json::from_str(&store.get(snapshot_key).expect("snapshot retrievable")).unwrap();

        assert_eq!(&rewritten_messages[..2], &original_messages[..2]);
        assert_eq!(snapshot["version"], 1);
        assert_eq!(snapshot["session_key"], "session-42");
        assert!(
            snapshot.get("created_unix").is_none(),
            "snapshot identity must not include wall-clock time"
        );
        assert_eq!(
            snapshot["messages"].as_array().unwrap(),
            &original_messages[2..4]
        );
        assert_eq!(rewritten_messages.len(), 7);
        assert_eq!(rewritten_messages[2]["role"], "user");
        assert!(rewritten_messages[2]["content"]
            .as_str()
            .unwrap()
            .contains(&cutctx_core::ccr::marker_for(snapshot_key)));
    }

    #[test]
    fn snapshot_resume_rejects_a_tool_pair_split_by_the_tail_boundary() {
        let original = json!({
            "messages": [
                {"role": "user", "content": "old context"},
                {
                    "role": "assistant",
                    "content": "calling search",
                    "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "search", "arguments": "{}"}
                    }]
                },
                {"role": "tool", "tool_call_id": "call_1", "content": "result"},
                {"role": "user", "content": "tail one"},
                {"role": "assistant", "content": "tail two"},
                {"role": "user", "content": "tail three"}
            ]
        });
        let store = InMemoryCcrStore::new();

        let mutation = apply_snapshot_resume(
            &serde_json::to_vec(&original).unwrap(),
            0,
            "tool-session",
            None,
            &StrategyConfig::default(),
            &store,
        );

        assert!(
            mutation
                .expect("boundary rejection is not an application error")
                .is_none(),
            "a split tool pair must not be snapshotted"
        );
        assert_eq!(store.len(), 0, "ineligible snapshots must not write CCR");
    }

    #[test]
    fn snapshot_resume_replaces_a_complete_tool_pair_together() {
        let original = json!({
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "search", "arguments": "{}"}
                    }]
                },
                {"role": "tool", "tool_call_id": "call_1", "content": "result"},
                {"role": "user", "content": "tail one"},
                {"role": "assistant", "content": "tail two"},
                {"role": "user", "content": "tail three"},
                {"role": "assistant", "content": "tail four"}
            ]
        });
        let store = InMemoryCcrStore::new();

        let mutation = apply_snapshot_resume(
            &serde_json::to_vec(&original).unwrap(),
            0,
            "complete-tool-session",
            None,
            &StrategyConfig::default(),
            &store,
        )
        .unwrap()
        .expect("a complete pair is safe to snapshot");
        let rewritten: Value = serde_json::from_slice(&mutation.body).unwrap();

        assert_eq!(rewritten["messages"].as_array().unwrap().len(), 5);
        assert!(!rewritten
            .to_string()
            .contains("\"tool_call_id\":\"call_1\""));
        assert!(store
            .get(mutation.snapshot_key.as_deref().unwrap())
            .is_some());
    }

    #[test]
    fn snapshot_key_is_deterministic_across_fresh_stores() {
        let original = json!({
            "messages": (0..8)
                .map(|index| json!({"role": "user", "content": format!("turn {index}")}))
                .collect::<Vec<_>>()
        });
        let body = serde_json::to_vec(&original).unwrap();
        let first_store = InMemoryCcrStore::new();
        let second_store = InMemoryCcrStore::new();

        let first = apply_snapshot_resume(
            &body,
            0,
            "stable-session",
            None,
            &StrategyConfig::default(),
            &first_store,
        )
        .unwrap()
        .unwrap();
        let second = apply_snapshot_resume(
            &body,
            0,
            "stable-session",
            None,
            &StrategyConfig::default(),
            &second_store,
        )
        .unwrap()
        .unwrap();

        assert_eq!(first.snapshot_key, second.snapshot_key);
    }

    #[test]
    fn snapshot_resume_reuses_existing_snapshot_key_without_rewriting_store() {
        let original = json!({
            "messages": (0..8)
                .map(|index| json!({"role": "user", "content": format!("turn {index}")}))
                .collect::<Vec<_>>()
        });
        let body = serde_json::to_vec(&original).unwrap();
        let store = InMemoryCcrStore::new();
        let cached = json!({
            "version": 1,
            "session_key": "session-42",
            "created_unix": 1,
            "messages": original["messages"].as_array().unwrap()[..4],
        })
        .to_string();
        store.put("existing-key", &cached);

        let mutation = apply_snapshot_resume(
            &body,
            0,
            "session-42",
            Some("existing-key"),
            &StrategyConfig::default(),
            &store,
        )
        .unwrap()
        .unwrap();

        assert_eq!(mutation.snapshot_key.as_deref(), Some("existing-key"));
        assert_eq!(store.len(), 1);
        assert_eq!(store.get("existing-key").as_deref(), Some(cached.as_str()));
    }

    #[test]
    fn snapshot_resume_rebuilds_missing_cached_snapshot() {
        let original = json!({
            "messages": (0..8)
                .map(|index| json!({"role": "user", "content": format!("turn {index}")}))
                .collect::<Vec<_>>()
        });
        let body = serde_json::to_vec(&original).unwrap();
        let store = InMemoryCcrStore::new();

        let mutation = apply_snapshot_resume(
            &body,
            0,
            "session-42",
            Some("expired-key"),
            &StrategyConfig::default(),
            &store,
        )
        .unwrap()
        .unwrap();
        let snapshot_key = mutation.snapshot_key.unwrap();

        assert_ne!(snapshot_key, "expired-key");
        assert!(store.get(&snapshot_key).is_some());
    }

    #[test]
    fn snapshot_resume_rebuilds_when_snapshotted_range_changes() {
        let initial = json!({
            "messages": (0..8)
                .map(|index| json!({"role": "user", "content": format!("turn {index}")}))
                .collect::<Vec<_>>()
        });
        let store = InMemoryCcrStore::new();
        let first = apply_snapshot_resume(
            &serde_json::to_vec(&initial).unwrap(),
            0,
            "session-42",
            None,
            &StrategyConfig::default(),
            &store,
        )
        .unwrap()
        .unwrap();
        let first_key = first.snapshot_key.unwrap();

        let mut changed = initial;
        changed["messages"][0]["content"] = json!("changed historical turn");
        let second = apply_snapshot_resume(
            &serde_json::to_vec(&changed).unwrap(),
            0,
            "session-42",
            Some(&first_key),
            &StrategyConfig::default(),
            &store,
        )
        .unwrap()
        .unwrap();

        assert_ne!(second.snapshot_key.as_deref(), Some(first_key.as_str()));
        assert_eq!(store.len(), 2);
    }

    #[test]
    fn selective_clear_preserves_responses_text_block_shape() {
        let original = json!({
            "input": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "obsolete archive payload"}]
                },
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "fix websocket authentication"}]
                }
            ]
        });
        let body = serde_json::to_vec(&original).unwrap();
        let store = InMemoryCcrStore::new();
        let mut policy = CompressionPolicy::for_mode(AuthMode::Payg);
        policy.volatile_token_threshold = 1;

        let mutation = apply_selective_clear(&body, 0, &policy, &StrategyConfig::default(), &store)
            .expect("strategy application should succeed")
            .expect("old Responses message should be elided");
        let rewritten: Value = serde_json::from_slice(&mutation.body).unwrap();

        assert_eq!(rewritten["input"][0]["content"][0]["type"], "output_text");
        assert!(rewritten["input"][0]["content"][0]["text"]
            .as_str()
            .unwrap()
            .contains("<<ccr:"));
        assert_eq!(rewritten["input"][1], original["input"][1]);
    }

    #[test]
    fn snapshot_resume_emits_valid_responses_summary_message() {
        let original = json!({
            "input": (0..6)
                .map(|index| json!({
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": format!("turn {index}")}]
                }))
                .collect::<Vec<_>>()
        });
        let store = InMemoryCcrStore::new();
        let mutation = apply_snapshot_resume(
            &serde_json::to_vec(&original).unwrap(),
            0,
            "responses-session",
            None,
            &StrategyConfig::default(),
            &store,
        )
        .unwrap()
        .unwrap();
        let rewritten: Value = serde_json::from_slice(&mutation.body).unwrap();

        assert_eq!(rewritten["input"][0]["type"], "message");
        assert_eq!(rewritten["input"][0]["role"], "user");
        assert_eq!(rewritten["input"][0]["content"][0]["type"], "input_text");
        assert!(rewritten["input"][0]["content"][0]["text"]
            .as_str()
            .unwrap()
            .contains("<<ccr:"));
    }

    #[test]
    fn snapshot_resume_preserves_frozen_message_bytes_exactly() {
        let body = br#"{
  "model" : "gpt-5",
  "messages" : [
    { "content" : "frozen prefix", "role" : "user" },
    {"role":"assistant","content":"old one"},
    {"role":"user","content":"old two"},
    {"role":"assistant","content":"tail one"},
    {"role":"user","content":"tail two"},
    {"role":"assistant","content":"tail three"},
    {"role":"user","content":"tail four"}
  ]
}"#;
        let frozen = br#"{ "content" : "frozen prefix", "role" : "user" }"#;
        let store = InMemoryCcrStore::new();

        let mutation = apply_snapshot_resume(
            body,
            1,
            "byte-stable-session",
            None,
            &StrategyConfig::default(),
            &store,
        )
        .unwrap()
        .unwrap();

        assert!(
            mutation
                .body
                .windows(frozen.len())
                .any(|window| window == frozen),
            "frozen message bytes must be copied without reserialization"
        );
    }

    #[test]
    fn selective_clear_preserves_frozen_bytes_and_stores_exact_turn_json() {
        let body = br#"{
  "messages" : [
    { "content" : "frozen prefix", "role" : "user" },
    { "role" : "assistant", "content" : "obsolete archive payload" },
    {"role":"user","content":"fix websocket authentication"}
  ]
}"#;
        let frozen = br#"{ "content" : "frozen prefix", "role" : "user" }"#;
        let original_turn = r#"{ "role" : "assistant", "content" : "obsolete archive payload" }"#;
        let store = InMemoryCcrStore::new();
        let mut policy = CompressionPolicy::for_mode(AuthMode::Payg);
        policy.volatile_token_threshold = 1;

        let mutation = apply_selective_clear(body, 1, &policy, &StrategyConfig::default(), &store)
            .unwrap()
            .unwrap();
        let key = mutation.markers_inserted[0]
            .strip_prefix("<<ccr:")
            .unwrap()
            .strip_suffix(">>")
            .unwrap();

        assert!(mutation
            .body
            .windows(frozen.len())
            .any(|window| window == frozen));
        assert_eq!(store.get(key).as_deref(), Some(original_turn));
    }
}
