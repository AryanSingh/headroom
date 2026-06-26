//! Provider-native compaction support — Anthropic `compact-2026-01-12`.
//!
//! Anthropic offers native conversation-history compaction via the
//! `anthropic-beta: compact-2026-01-12` header. This module positions
//! Cutctx as complementary to provider-native compaction by detecting
//! when it's requested and choosing the optimal strategy.
//!
//! # Strategy selection
//!
//! | Strategy         | When selected                                     |
//! |------------------|---------------------------------------------------|
//! | CutctxNative   | Default — Cutctx compresses, no provider header  |
//! | ProviderNative   | Client sends compact header, hybrid_mode=false     |
//! | Hybrid            | Client sends compact header, hybrid_mode=true      |
//!
//! # Hybrid mode
//!
//! When both Cutctx and provider-native compaction are applied:
//! 1. Cutctx compresses first (deletion-based, streaming-aware).
//! 2. Provider native compaction handles the remaining history.
//! 3. Response metadata includes both layers of compression stats.

use http::HeaderMap;

// ── Detection ───────────────────────────────────────────────────────────────

/// Check if the request includes Anthropic's native compaction header.
///
/// The header format is: `anthropic-beta: compact-2026-01-12`
/// It may be comma-separated with other beta features.
pub fn is_anthropic_compact_requested(headers: &HeaderMap) -> bool {
    headers
        .get("anthropic-beta")
        .and_then(|v| v.to_str().ok())
        .map(|v| v.split(',').any(|s| s.trim() == "compact-2026-01-12"))
        .unwrap_or(false)
}

/// Check if the response indicates provider-native compaction was applied.
///
/// Looks for the `anthropic-compacted: true` response header.
pub fn is_native_compaction_applied(headers: &HeaderMap) -> bool {
    headers
        .get("anthropic-compacted")
        .and_then(|v| v.to_str().ok())
        .map(|v| v == "true")
        .unwrap_or(false)
}

// ── Strategy ────────────────────────────────────────────────────────────────

/// The compaction strategy for a request.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CompactionStrategy {
    /// Use Cutctx's own compression (default).
    CutctxNative,
    /// Pass through to Anthropic's native compaction.
    ProviderNative,
    /// Apply both: Cutctx first, then provider native for remaining.
    Hybrid,
}

/// Configuration for strategy selection.
#[derive(Debug, Clone)]
pub struct StrategyConfig {
    /// Default strategy when no provider header is present.
    pub default_strategy: CompactionStrategy,
    /// Allow provider-native compaction. Default: true.
    pub allow_provider_native: bool,
    /// Enable hybrid mode (both layers). Default: false.
    pub hybrid_mode: bool,
}

impl Default for StrategyConfig {
    fn default() -> Self {
        Self {
            default_strategy: CompactionStrategy::CutctxNative,
            allow_provider_native: true,
            hybrid_mode: false,
        }
    }
}

/// Determine the best compaction strategy for this request.
pub fn select_strategy(config: &StrategyConfig, headers: &HeaderMap) -> CompactionStrategy {
    // If provider native is not allowed, always use CutctxNative
    if !config.allow_provider_native {
        return CompactionStrategy::CutctxNative;
    }

    // If the client explicitly requested provider native compaction
    if is_anthropic_compact_requested(headers) {
        return if config.hybrid_mode {
            CompactionStrategy::Hybrid
        } else {
            CompactionStrategy::ProviderNative
        };
    }

    // Default to Cutctx's own compression
    config.default_strategy
}

// ── Response enhancement ────────────────────────────────────────────────────

/// Metadata about Cutctx's compression for response enhancement.
#[derive(Debug, Clone)]
pub struct CompressionMetadata {
    /// Number of tokens saved by Cutctx compression.
    pub tokens_saved: u32,
    /// Compression ratio achieved.
    pub compression_ratio: f32,
    /// List of strategies applied.
    pub strategies: Vec<String>,
}

/// Enhance the response when provider-native compaction was applied.
///
/// Merges Cutctx's compression metadata into the response for
/// visibility into both layers of compression.
pub fn enhance_native_compacted_response(
    original_body: &str,
    cutctx_metadata: Option<&CompressionMetadata>,
) -> Result<String, serde_json::Error> {
    let mut response: serde_json::Value = serde_json::from_str(original_body)?;

    if let Some(metadata) = cutctx_metadata {
        let stats = serde_json::json!({
            "cutctx_compression": {
                "tokens_saved": metadata.tokens_saved,
                "compression_ratio": metadata.compression_ratio,
                "strategies_applied": metadata.strategies,
            },
            "provider_compaction": true,
            "combined_savings_percent": format!("{:.1}%", metadata.compression_ratio * 100.0),
        });

        // Add to response metadata if present, otherwise create it
        if let Some(meta) = response.get_mut("metadata") {
            if let Some(obj) = meta.as_object_mut() {
                obj.insert("cutctx_stats".to_string(), stats);
            }
        } else {
            let mut metadata_obj = serde_json::Map::new();
            metadata_obj.insert("cutctx_stats".to_string(), stats);
            response["metadata"] = serde_json::Value::Object(metadata_obj);
        }
    }

    serde_json::to_string(&response)
}

// ── Header management ───────────────────────────────────────────────────────

/// Prepare outbound headers based on the compaction strategy.
///
/// For `ProviderNative`: keeps the compact header.
/// For `CutctxNative`: removes the compact header (Cutctx handles compression).
/// For `Hybrid`: keeps the compact header (both layers apply).
pub fn prepare_outbound_headers(
    incoming_headers: &HeaderMap,
    strategy: CompactionStrategy,
) -> HeaderMap {
    let mut headers = HeaderMap::new();

    match strategy {
        CompactionStrategy::ProviderNative | CompactionStrategy::Hybrid => {
            // Keep the compact header — let Anthropic handle it
            if let Some(value) = incoming_headers.get("anthropic-beta") {
                headers.insert("anthropic-beta", value.clone());
            }
        }
        CompactionStrategy::CutctxNative => {
            // Remove compact header — Cutctx will handle compression
            for (key, value) in incoming_headers.iter() {
                if key == "anthropic-beta" {
                    // Filter out compact-2026-01-12 from comma-separated list
                    if let Ok(v) = value.to_str() {
                        let filtered: Vec<&str> = v
                            .split(',')
                            .map(|s| s.trim())
                            .filter(|s| *s != "compact-2026-01-12")
                            .collect();
                        if !filtered.is_empty() {
                            if let Ok(new_value) = http::HeaderValue::from_str(&filtered.join(", "))
                            {
                                headers.insert(key.clone(), new_value);
                            }
                        }
                    }
                } else {
                    headers.insert(key.clone(), value.clone());
                }
            }
        }
    }

    // Copy all non-anthropic-beta headers
    for (key, value) in incoming_headers.iter() {
        if key != "anthropic-beta" {
            headers.insert(key.clone(), value.clone());
        }
    }

    headers
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_header(name: &'static str, value: &str) -> HeaderMap {
        let mut headers = HeaderMap::new();
        headers.insert(
            http::HeaderName::from_static(name),
            http::HeaderValue::from_str(value).unwrap(),
        );
        headers
    }

    #[test]
    fn detect_compact_header_present() {
        let headers = make_header("anthropic-beta", "compact-2026-01-12");
        assert!(is_anthropic_compact_requested(&headers));
    }

    #[test]
    fn detect_compact_header_in_list() {
        let headers = make_header("anthropic-beta", "-messages-2024-01, compact-2026-01-12");
        assert!(is_anthropic_compact_requested(&headers));
    }

    #[test]
    fn detect_compact_header_absent() {
        let headers = make_header("anthropic-beta", "messages-2024-01");
        assert!(!is_anthropic_compact_requested(&headers));
    }

    #[test]
    fn detect_compact_header_no_header() {
        let headers = HeaderMap::new();
        assert!(!is_anthropic_compact_requested(&headers));
    }

    #[test]
    fn detect_native_compaction_applied() {
        let headers = make_header("anthropic-compacted", "true");
        assert!(is_native_compaction_applied(&headers));
    }

    #[test]
    fn detect_native_compaction_not_applied() {
        let headers = make_header("anthropic-compacted", "false");
        assert!(!is_native_compaction_applied(&headers));
    }

    #[test]
    fn strategy_selection_default() {
        let config = StrategyConfig::default();
        let headers = HeaderMap::new();
        assert_eq!(
            select_strategy(&config, &headers),
            CompactionStrategy::CutctxNative
        );
    }

    #[test]
    fn strategy_selection_provider_native() {
        let config = StrategyConfig::default();
        let headers = make_header("anthropic-beta", "compact-2026-01-12");
        assert_eq!(
            select_strategy(&config, &headers),
            CompactionStrategy::ProviderNative
        );
    }

    #[test]
    fn strategy_selection_hybrid() {
        let config = StrategyConfig {
            hybrid_mode: true,
            ..Default::default()
        };
        let headers = make_header("anthropic-beta", "compact-2026-01-12");
        assert_eq!(
            select_strategy(&config, &headers),
            CompactionStrategy::Hybrid
        );
    }

    #[test]
    fn strategy_selection_provider_disabled() {
        let config = StrategyConfig {
            allow_provider_native: false,
            ..Default::default()
        };
        let headers = make_header("anthropic-beta", "compact-2026-01-12");
        assert_eq!(
            select_strategy(&config, &headers),
            CompactionStrategy::CutctxNative
        );
    }

    #[test]
    fn prepare_headers_provider_native_keeps_compact() {
        let incoming = make_header("anthropic-beta", "compact-2026-01-12");
        let outgoing = prepare_outbound_headers(&incoming, CompactionStrategy::ProviderNative);
        assert!(outgoing.contains_key("anthropic-beta"));
    }

    #[test]
    fn prepare_headers_cutctx_native_removes_compact() {
        let incoming = make_header("anthropic-beta", "compact-2026-01-12");
        let outgoing = prepare_outbound_headers(&incoming, CompactionStrategy::CutctxNative);
        assert!(!outgoing.contains_key("anthropic-beta"));
    }

    #[test]
    fn prepare_headers_cutctx_native_keeps_other_betas() {
        let mut incoming = HeaderMap::new();
        incoming.insert(
            "anthropic-beta",
            http::HeaderValue::from_str("messages-2024-01, compact-2026-01-12").unwrap(),
        );
        let outgoing = prepare_outbound_headers(&incoming, CompactionStrategy::CutctxNative);
        assert!(outgoing.contains_key("anthropic-beta"));
        let value = outgoing["anthropic-beta"].to_str().unwrap();
        assert_eq!(value, "messages-2024-01");
    }

    #[test]
    fn enhance_response_with_metadata() {
        let body = r#"{"id":"msg_123","type":"message"}"#;
        let metadata = CompressionMetadata {
            tokens_saved: 500,
            compression_ratio: 0.75,
            strategies: vec!["deletion_compaction".to_string()],
        };
        let enhanced = enhance_native_compacted_response(body, Some(&metadata)).unwrap();
        let json: serde_json::Value = serde_json::from_str(&enhanced).unwrap();
        assert!(json["metadata"]["cutctx_stats"].is_object());
    }

    #[test]
    fn enhance_response_without_metadata() {
        let body = r#"{"id":"msg_123","type":"message"}"#;
        let enhanced = enhance_native_compacted_response(body, None).unwrap();
        let json: serde_json::Value = serde_json::from_str(&enhanced).unwrap();
        assert_eq!(json["id"], "msg_123");
    }
}
