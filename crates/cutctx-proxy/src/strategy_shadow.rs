//! Context strategy selection (spec-smart-context-strategies.md).
//!
//! This module computes and selects an adaptive context strategy for each request:
//! - SmartCompact: active when selected and CCR is available (spec §5.4)
//! - SelectiveClear/SnapshotResume: selected here and applied by `strategy_apply`
//! - RollingWindow: default fallback for all other cases
//!
//! Every request triggers (when `--context-strategies` enabled):
//! - Computation of observable ContextSignals from body + session state
//! - Deterministic strategy selection based on utilization and policy
//! - Structured logging and metric emission for observability
//!
//! SmartCompact decisions: when returned from `shadow_select`, the proxy's
//! `forward_http` handler threads the strategy into the compression dispatch.
//! If CCR is unavailable, SmartCompact degrades to RollingWindow (loud warning).
//!
//! When the `--context-strategies` flag is off (default), no computation occurs.

use cutctx_core::relevance::{BM25Scorer, RelevanceScorer};
use cutctx_core::signals::{
    ImportanceCategory, ImportanceContext, KeywordDetector, LineImportanceDetector,
};
use cutctx_core::tokenizer::Tokenizer;
use cutctx_core::transforms::context_strategy::{ContextSignals, StrategyDecision};
use http::HeaderMap;
use serde_json::Value;

fn content_text(content: &Value) -> String {
    match content {
        Value::String(text) => text.clone(),
        Value::Array(blocks) => blocks
            .iter()
            .filter_map(|block| {
                block
                    .get("text")
                    .or_else(|| block.get("content"))
                    .and_then(Value::as_str)
            })
            .collect::<Vec<_>>()
            .join("\n"),
        _ => String::new(),
    }
}

pub(crate) fn message_text(message: &Value) -> String {
    message
        .get("content")
        .or_else(|| message.get("text"))
        .map(content_text)
        .unwrap_or_default()
}

fn relevance_context(parsed: &Value, messages: &[Value]) -> String {
    let mut parts = Vec::new();
    if let Some(system) = parsed.get("system") {
        let text = content_text(system);
        if !text.is_empty() {
            parts.push(text);
        }
    }

    let mut recent_user_messages = messages
        .iter()
        .rev()
        .filter(|message| message.get("role").and_then(Value::as_str) == Some("user"))
        .map(message_text)
        .filter(|text| !text.is_empty())
        .take(2)
        .collect::<Vec<_>>();
    recent_user_messages.reverse();
    parts.extend(recent_user_messages);
    parts.join("\n")
}

fn has_protected_importance(text: &str, detector: &KeywordDetector) -> bool {
    text.lines().any(|line| {
        [ImportanceContext::Text, ImportanceContext::Diff]
            .into_iter()
            .filter_map(|context| detector.score(line, context).category)
            .any(|category| {
                matches!(
                    category,
                    ImportanceCategory::Error | ImportanceCategory::Security
                )
            })
    })
}

fn low_value_turn_ratio(
    parsed: &Value,
    messages: &[Value],
    frozen_count: usize,
    compression_policy: &cutctx_core::compression_policy::CompressionPolicy,
    config: &cutctx_core::transforms::context_strategy::StrategyConfig,
) -> f32 {
    let live_messages = messages.get(frozen_count..).unwrap_or_default();
    if live_messages.is_empty() {
        return 0.0;
    }

    low_value_turn_indices(parsed, messages, frozen_count, compression_policy, config).len() as f32
        / live_messages.len() as f32
}

pub(crate) fn low_value_turn_indices(
    parsed: &Value,
    messages: &[Value],
    frozen_count: usize,
    compression_policy: &cutctx_core::compression_policy::CompressionPolicy,
    config: &cutctx_core::transforms::context_strategy::StrategyConfig,
) -> Vec<usize> {
    let context = relevance_context(parsed, messages);
    let scorer = BM25Scorer::default();
    let importance_detector = KeywordDetector::default();
    let tokenizer = cutctx_core::tokenizer::EstimatingCounter::default();
    messages
        .iter()
        .enumerate()
        .skip(frozen_count)
        .filter_map(|(index, message)| {
            let text = message_text(message);
            (tokenizer.count_text(&text) >= compression_policy.volatile_token_threshold as usize
                && !has_protected_importance(&text, &importance_detector)
                && scorer.score(&text, &context).score < config.low_value_score)
                .then_some(index)
        })
        .collect()
}

/// Compute ContextSignals and select a strategy.
///
/// # Inputs
/// - `body`: raw request body bytes (parsed as JSON to extract messages + model)
/// - `model_hint`: optional model name from request context
/// - `headers`: request headers (used to derive session identity)
/// - `request_id`: per-request correlation id (for logging)
/// - `cache_control_policy`: frozen-message-floor computation policy
/// - `compression_policy`: per-auth-mode policy (gates strategy selections)
/// - `session_state`: per-session state store (request count, frozen advance tracking)
///
/// # Returns
/// `None` if the body is malformed JSON or missing required fields (messages/input).
/// `Some(decision)` with the selected strategy and rationale + structured logging.
/// No side effects on the request body or compression behavior.
#[cfg(test)]
pub(crate) fn shadow_select(
    body: &[u8],
    model_hint: Option<&str>,
    headers: &HeaderMap,
    request_id: &str,
    cache_control_policy: crate::config::CacheControlAutoFrozen,
    compression_policy: &cutctx_core::compression_policy::CompressionPolicy,
    session_state: &crate::session_state::SessionStateStore,
) -> Option<StrategyDecision> {
    shadow_select_with_config(
        body,
        model_hint,
        headers,
        request_id,
        cache_control_policy,
        compression_policy,
        &cutctx_core::transforms::context_strategy::StrategyConfig::default(),
        session_state,
    )
}

#[allow(clippy::too_many_arguments)]
pub(crate) fn shadow_select_with_config(
    body: &[u8],
    model_hint: Option<&str>,
    headers: &HeaderMap,
    request_id: &str,
    cache_control_policy: crate::config::CacheControlAutoFrozen,
    compression_policy: &cutctx_core::compression_policy::CompressionPolicy,
    strategy_config: &cutctx_core::transforms::context_strategy::StrategyConfig,
    session_state: &crate::session_state::SessionStateStore,
) -> Option<StrategyDecision> {
    // Parse the request body as JSON.
    let parsed: Value = serde_json::from_slice(body).ok()?;

    // Extract messages array (handles both Anthropic "messages" and Responses API "input").
    let messages = parsed
        .get("messages")
        .or_else(|| parsed.get("input"))
        .and_then(|m| m.as_array())?;

    // Resolve model: priority is model_hint → body's "model" field → "" (unknown).
    let model = model_hint
        .or_else(|| parsed.get("model").and_then(|m| m.as_str()))
        .unwrap_or("");

    // Compute frozen-message floor from cache_control markers.
    let frozen_count =
        crate::compression::resolve_frozen_count(&parsed, cache_control_policy, request_id);

    // Token estimation over the full raw body (cheap, provider-agnostic; estimate
    // deliberately uses raw bytes rather than parsed messages to avoid lossy
    // serialization artifacts and keep the cost minimal on hot path).
    let total_tokens_est = cutctx_core::tokenizer::EstimatingCounter::default()
        .count_text(std::str::from_utf8(body).unwrap_or(""));

    // Token estimation for live zone (messages above frozen floor).
    let live_zone_tokens_est = if frozen_count < messages.len() {
        let live_messages = &messages[frozen_count..];
        if let Ok(live_json) = serde_json::to_string(live_messages) {
            cutctx_core::tokenizer::EstimatingCounter::default().count_text(&live_json)
        } else {
            0
        }
    } else {
        0
    };

    // Resolve session identity and observe request count.
    let key = crate::session_state::resolve_session_key(headers, request_id);
    let entry = session_state.observe(&key, frozen_count);

    // Model context limit from LiteLLM table (or DEFAULT_CONTEXT_WINDOW for unknown).
    let model_context_limit = crate::compression::model_limits::context_window_for(model) as usize;

    let low_value_turn_ratio = low_value_turn_ratio(
        &parsed,
        messages,
        frozen_count,
        compression_policy,
        strategy_config,
    );

    // Construct ContextSignals from the parsed request and current session.
    let signals = ContextSignals::new(
        total_tokens_est,
        model_context_limit,
        messages.len(),
        frozen_count,
        live_zone_tokens_est,
        entry.turns_since_frozen_advance,
        low_value_turn_ratio,
        entry.request_count,
    );

    // Run deterministic strategy selection with default config.
    let mut decision = cutctx_core::transforms::context_strategy::select_strategy(
        &signals,
        compression_policy,
        strategy_config,
    );
    if let Some(value) = headers
        .get("x-cutctx-strategy")
        .and_then(|value| value.to_str().ok())
    {
        if !value.eq_ignore_ascii_case("auto") {
            if let Some(override_strategy) =
                cutctx_core::transforms::context_strategy::ContextStrategy::parse(value)
            {
                let structural_forbidden = compression_policy.toin_read_only
                    && matches!(
                        override_strategy,
                        cutctx_core::transforms::context_strategy::ContextStrategy::SelectiveClear
                            | cutctx_core::transforms::context_strategy::ContextStrategy::SnapshotResume
                    );
                if structural_forbidden {
                    decision.strategy = if signals.utilization >= strategy_config.compact_threshold
                    {
                        cutctx_core::transforms::context_strategy::ContextStrategy::SmartCompact
                    } else {
                        cutctx_core::transforms::context_strategy::ContextStrategy::RollingWindow
                    };
                    decision.rationale = "policy_read_only";
                } else {
                    decision.strategy = override_strategy;
                    decision.rationale = "header_override";
                }
            } else {
                tracing::warn!(
                    event = "context_strategy_override_invalid",
                    request_id = %request_id,
                    value,
                    "ignoring invalid x-cutctx-strategy override"
                );
            }
        }
    }

    // Emit observability: metric + structured log.
    crate::observability::record_context_strategy(decision.strategy.as_str(), decision.rationale);
    tracing::info!(
        event = "context_strategy_selected",
        request_id = %request_id,
        strategy = decision.strategy.as_str(),
        rationale = decision.rationale,
        utilization = decision.signals.utilization,
        message_count = decision.signals.message_count,
        frozen_count = decision.signals.frozen_message_count,
        session_sticky = key.sticky,
        "context strategy selected"
    );

    Some(decision)
}

#[cfg(test)]
mod tests {
    use super::*;
    use cutctx_core::auth_mode::AuthMode;
    use cutctx_core::compression_policy::CompressionPolicy;
    use serde_json::json;

    #[test]
    fn non_json_body_returns_none() {
        let body = b"not json";
        let result = shadow_select(
            body,
            Some("claude-3-5-sonnet"),
            &HeaderMap::new(),
            "req-1",
            crate::config::CacheControlAutoFrozen::Enabled,
            &CompressionPolicy::for_mode(AuthMode::Payg),
            &crate::session_state::SessionStateStore::default(),
        );
        assert!(result.is_none());
    }

    #[test]
    fn json_without_messages_or_input_returns_none() {
        let body = json!({ "model": "claude-3-5-sonnet" }).to_string();
        let result = shadow_select(
            body.as_bytes(),
            None,
            &HeaderMap::new(),
            "req-2",
            crate::config::CacheControlAutoFrozen::Enabled,
            &CompressionPolicy::for_mode(AuthMode::Payg),
            &crate::session_state::SessionStateStore::default(),
        );
        assert!(result.is_none());
    }

    #[test]
    fn valid_anthropic_shaped_body_returns_decision() {
        let body = json!({
            "model": "claude-3-5-sonnet-20241022",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
                {"role": "user", "content": "How are you?"},
            ]
        })
        .to_string();

        let result = shadow_select(
            body.as_bytes(),
            None,
            &HeaderMap::new(),
            "req-3",
            crate::config::CacheControlAutoFrozen::Enabled,
            &CompressionPolicy::for_mode(AuthMode::Payg),
            &crate::session_state::SessionStateStore::default(),
        );

        assert!(result.is_some());
        let decision = result.unwrap();
        assert_eq!(decision.signals.message_count, 3);
        assert_eq!(decision.signals.frozen_message_count, 0);
    }

    #[test]
    fn session_request_count_increments_across_calls() {
        let store = crate::session_state::SessionStateStore::default();
        let headers = {
            let mut h = HeaderMap::new();
            h.insert("x-cutctx-session-id", "session-1".parse().unwrap());
            h
        };
        let body = json!({
            "model": "claude-3-5-sonnet",
            "messages": [{"role": "user", "content": "msg"}]
        })
        .to_string();

        // First call
        let decision1 = shadow_select(
            body.as_bytes(),
            None,
            &headers,
            "req-4a",
            crate::config::CacheControlAutoFrozen::Enabled,
            &CompressionPolicy::for_mode(AuthMode::Payg),
            &store,
        );
        assert!(decision1.is_some());
        assert_eq!(decision1.unwrap().signals.session_request_count, 1);

        // Second call with same session id
        let decision2 = shadow_select(
            body.as_bytes(),
            None,
            &headers,
            "req-4b",
            crate::config::CacheControlAutoFrozen::Enabled,
            &CompressionPolicy::for_mode(AuthMode::Payg),
            &store,
        );
        assert!(decision2.is_some());
        assert_eq!(decision2.unwrap().signals.session_request_count, 2);
    }

    #[test]
    fn low_value_ratio_scores_old_turns_against_recent_user_intent() {
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
        let body = json!({
            "model": "claude-3-5-sonnet",
            "messages": messages
        })
        .to_string();

        let decision = shadow_select(
            body.as_bytes(),
            None,
            &HeaderMap::new(),
            "req-low-value",
            crate::config::CacheControlAutoFrozen::Enabled,
            &CompressionPolicy::for_mode(AuthMode::Payg),
            &crate::session_state::SessionStateStore::default(),
        )
        .expect("valid body should produce a strategy decision");

        assert!(
            decision.signals.low_value_turn_ratio >= 0.40,
            "unrelated historical turns should be classified as low value; ratio={}",
            decision.signals.low_value_turn_ratio
        );
    }

    #[test]
    fn low_value_ratio_excludes_error_bearing_turns() {
        let messages = vec![
            json!({
                "role": "assistant",
                "content": format!(
                    "ERROR connection refused {}",
                    "unrelated_diagnostic_payload ".repeat(140)
                )
            }),
            json!({
                "role": "user",
                "content": "plan the websocket authentication migration"
            }),
        ];
        let parsed = json!({ "messages": messages });
        let messages = parsed["messages"].as_array().unwrap();

        let ratio = low_value_turn_ratio(
            &parsed,
            messages,
            0,
            &CompressionPolicy::for_mode(AuthMode::Payg),
            &cutctx_core::transforms::context_strategy::StrategyConfig::default(),
        );

        assert_eq!(
            ratio, 0.0,
            "error-bearing turns must never be considered low value"
        );
    }

    #[test]
    fn valid_header_overrides_automatic_strategy() {
        let body = json!({
            "model": "claude-3-5-sonnet",
            "messages": [{"role": "user", "content": "hello"}]
        })
        .to_string();
        let mut headers = HeaderMap::new();
        headers.insert("x-cutctx-strategy", "selective_clear".parse().unwrap());

        let decision = shadow_select(
            body.as_bytes(),
            None,
            &headers,
            "req-header-override",
            crate::config::CacheControlAutoFrozen::Enabled,
            &CompressionPolicy::for_mode(AuthMode::Payg),
            &crate::session_state::SessionStateStore::default(),
        )
        .unwrap();

        assert_eq!(
            decision.strategy,
            cutctx_core::transforms::context_strategy::ContextStrategy::SelectiveClear
        );
        assert_eq!(decision.rationale, "header_override");
    }
}
