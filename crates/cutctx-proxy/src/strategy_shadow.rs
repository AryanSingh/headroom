//! Context strategy selection (spec-smart-context-strategies.md).
//!
//! This module computes and selects an adaptive context strategy for each request:
//! - SmartCompact: ACTIVE when selected and CCR available (spec §5.4)
//! - SelectiveClear/SnapshotResume: shadow-only (observed, logged, no effect)
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

use cutctx_core::tokenizer::Tokenizer;
use cutctx_core::transforms::context_strategy::{ContextSignals, StrategyDecision};
use http::HeaderMap;
use serde_json::Value;

/// Compute ContextSignals and select a strategy in shadow mode.
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
pub(crate) fn shadow_select(
    body: &[u8],
    model_hint: Option<&str>,
    headers: &HeaderMap,
    request_id: &str,
    cache_control_policy: crate::config::CacheControlAutoFrozen,
    compression_policy: &cutctx_core::compression_policy::CompressionPolicy,
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
    let frozen_count = crate::compression::resolve_frozen_count(&parsed, cache_control_policy, request_id);

    // Token estimation over the full raw body (cheap, provider-agnostic; estimate
    // deliberately uses raw bytes rather than parsed messages to avoid lossy
    // serialization artifacts and keep the cost minimal on hot path).
    let total_tokens_est =
        cutctx_core::tokenizer::EstimatingCounter::default()
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

    // Construct ContextSignals. Note: low_value_turn_ratio = 0.0 because
    // BM25 scoring is not yet computed in shadow mode (spec §5.4 SelectiveClear
    // rule 3 cannot fire). TODO: wire per-turn BM25 scoring once infrastructure exists.
    let signals = ContextSignals::new(
        total_tokens_est,
        model_context_limit,
        messages.len(),
        frozen_count,
        live_zone_tokens_est,
        entry.turns_since_frozen_advance,
        0.0, // low_value_turn_ratio placeholder — BM25 scoring deferred
        entry.request_count,
    );

    // Run deterministic strategy selection with default config.
    let decision = cutctx_core::transforms::context_strategy::select_strategy(
        &signals,
        compression_policy,
        &cutctx_core::transforms::context_strategy::StrategyConfig::default(),
    );

    // Emit observability: metric + structured log.
    crate::observability::record_context_strategy(decision.strategy.as_str(), decision.rationale);
    tracing::info!(
        event = "context_strategy_shadow",
        request_id = %request_id,
        strategy = decision.strategy.as_str(),
        rationale = decision.rationale,
        utilization = decision.signals.utilization,
        message_count = decision.signals.message_count,
        frozen_count = decision.signals.frozen_message_count,
        session_sticky = key.sticky,
        "shadow context strategy decision (no behavior change)"
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
}
