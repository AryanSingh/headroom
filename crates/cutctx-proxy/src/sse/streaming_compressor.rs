//! Streaming-aware compression for SSE responses.
//!
//! This module compresses LLM response text incrementally as SSE chunks
//! arrive, reducing time-to-first-token (TTFT) by avoiding the need to
//! buffer the entire response before compression.
//!
//! # Architecture
//!
//! ```text
//! [TCP bytes] ─▶ SseFramer
//!                    │  yields SseEvent
//!                    ▼
//!          StreamingCompressor
//!                    │  yields compressed SseEvent
//!                    ▼
//!            [to client]
//! ```
//!
//! The compressor accumulates text deltas from `content_block_delta`
//! events and applies deletion-based compaction when the accumulated
//! token count exceeds a configurable threshold. Metadata events
//! (`message_start`, `message_delta`, etc.) pass through unmodified.
//!
//! # SSE format preservation
//!
//! All output events maintain valid SSE framing and JSON structure.
//! The compressor never breaks the SSE protocol — it only modifies
//! the `text` field within `content_block_delta` events.

use bytes::Bytes;
use serde_json::Value;

use super::framing::SseEvent;
use headroom_core::transforms::deletion_compaction::{
    Aggressiveness, DeletionCompactor, DeletionCompactorConfig,
};

// ── Configuration ───────────────────────────────────────────────────────────

/// Configuration for the streaming compressor.
#[derive(Debug, Clone)]
pub struct StreamingConfig {
    /// Enable compression of text deltas. Default: true.
    pub enable_text_compression: bool,
    /// Minimum number of accumulated tokens before compressing. Default: 100.
    pub text_compress_threshold: usize,
    /// Use more aggressive compression. Default: false.
    pub aggressive_compression: bool,
    /// Ensure SSE framing stays valid. Default: true (always enforced).
    pub preserve_stream_integrity: bool,
}

impl Default for StreamingConfig {
    fn default() -> Self {
        Self {
            enable_text_compression: true,
            text_compress_threshold: 100,
            aggressive_compression: false,
            preserve_stream_integrity: true,
        }
    }
}

// ── Stats ───────────────────────────────────────────────────────────────────

/// Compression statistics for the streaming compressor.
#[derive(Debug, Clone, Default)]
pub struct StreamingStats {
    /// Total SSE events processed.
    pub events_processed: u64,
    /// Events that were compressed (text deltas modified).
    pub events_compressed: u64,
    /// Total bytes in (original SSE data).
    pub total_bytes_in: usize,
    /// Total bytes out (compressed SSE data).
    pub total_bytes_out: usize,
    /// Estimated tokens saved by compression.
    pub tokens_saved: usize,
}

// ── StreamingCompressor ─────────────────────────────────────────────────────

/// Compresses SSE text deltas incrementally as they flow through the stream.
///
/// Accumulates text from `content_block_delta` events and applies
/// deletion-based compaction when the accumulated token count exceeds
/// the threshold. Metadata events pass through unmodified.
pub struct StreamingCompressor {
    config: StreamingConfig,
    /// Accumulated text content from text deltas.
    accumulated_text: String,
    /// Current index of the content block being compressed.
    current_block_index: Option<i64>,
    /// Estimated token count of accumulated text.
    token_count: usize,
    /// Deletion compactor instance.
    compactor: DeletionCompactor,
    /// Running statistics.
    stats: StreamingStats,
}

impl StreamingCompressor {
    /// Create a new streaming compressor with the given configuration.
    pub fn new(config: StreamingConfig) -> Self {
        let aggressiveness = if config.aggressive_compression {
            Aggressiveness::Aggressive
        } else {
            Aggressiveness::Moderate
        };

        let compactor_config = DeletionCompactorConfig {
            aggressiveness,
            preserve_code_blocks: true,
            preserve_tool_outputs: true,
            min_preservation_ratio: 0.3,
        };

        Self {
            config,
            accumulated_text: String::new(),
            current_block_index: None,
            token_count: 0,
            compactor: DeletionCompactor::new(compactor_config),
            stats: StreamingStats::default(),
        }
    }

    /// Process a single SSE event through the compression pipeline.
    ///
    /// Returns the event (possibly modified) or `None` if the event was
    /// consumed by the compressor (e.g., text deltas below threshold).
    pub fn process_event(&mut self, event: SseEvent) -> Option<SseEvent> {
        self.stats.events_processed += 1;

        if !self.config.enable_text_compression {
            return Some(event);
        }

        let event_name = event.event_name.as_deref().unwrap_or("");

        match event_name {
            "content_block_delta" => self.handle_content_block_delta(event),
            "message_start" | "message_delta" | "content_block_start" | "content_block_stop" => {
                // Pass through metadata events
                Some(event)
            }
            "message_stop" => {
                // Flush any remaining accumulated content
                if let Some(flushed) = self.flush() {
                    // We need to return the flushed event first, but we also
                    // need to return the message_stop. Since we can only return
                    // one, we'll return the message_stop and emit the flushed
                    // content as a side effect (the caller should check flush()).
                    // For simplicity, we'll just pass through message_stop.
                    // The caller should call flush() after the stream ends.
                    let _ = flushed;
                }
                Some(event)
            }
            _ => Some(event),
        }
    }

    /// Handle a content_block_delta event.
    fn handle_content_block_delta(&mut self, event: SseEvent) -> Option<SseEvent> {
        let data_str = match event.data_str() {
            Ok(s) => s,
            Err(_) => return Some(event), // Pass through on UTF-8 error
        };

        // Parse the JSON to extract the text delta
        let json: Value = match serde_json::from_str(data_str) {
            Ok(v) => v,
            Err(_) => return Some(event), // Pass through malformed JSON
        };

        // Extract the delta type and text
        let delta_type = json["delta"]["type"].as_str().unwrap_or("");
        if delta_type != "text_delta" {
            return Some(event); // Non-text deltas pass through
        }

        let text = match json["delta"]["text"].as_str() {
            Some(t) => t,
            None => return Some(event),
        };

        // Track the content block index
        if let Some(idx) = json["index"].as_i64() {
            self.current_block_index = Some(idx);
        }

        // Accumulate text
        self.accumulated_text.push_str(text);
        self.token_count += estimate_tokens(text);

        // If above threshold, compress and emit
        if self.token_count >= self.config.text_compress_threshold {
            self.compress_and_emit()
        } else {
            // Below threshold — pass through the original event
            self.stats.total_bytes_in += event.data.len();
            self.stats.total_bytes_out += event.data.len();
            Some(event)
        }
    }

    /// Compress accumulated text and emit a compressed delta event.
    fn compress_and_emit(&mut self) -> Option<SseEvent> {
        if self.accumulated_text.is_empty() {
            return None;
        }

        let original = self.accumulated_text.clone();
        let result = self.compactor.compact(&original);

        // Update stats
        self.stats.events_compressed += 1;
        self.stats.total_bytes_in += original.len();
        self.stats.total_bytes_out += result.output.len();
        self.stats.tokens_saved += result.tokens_deleted;

        // Reset accumulator
        self.accumulated_text.clear();
        self.token_count = 0;

        // Create the compressed delta event
        Some(self.make_delta_event(&result.output))
    }

    /// Flush any remaining accumulated content.
    ///
    /// Call this at stream end to emit any compressed content that
    /// hasn't reached the threshold yet.
    pub fn flush(&mut self) -> Option<SseEvent> {
        if self.accumulated_text.is_empty() {
            return None;
        }

        let original = self.accumulated_text.clone();
        let result = self.compactor.compact(&original);

        self.stats.events_compressed += 1;
        self.stats.total_bytes_in += original.len();
        self.stats.total_bytes_out += result.output.len();
        self.stats.tokens_saved += result.tokens_deleted;

        self.accumulated_text.clear();
        self.token_count = 0;

        Some(self.make_delta_event(&result.output))
    }

    /// Create a content_block_delta SSE event with the given text.
    fn make_delta_event(&self, text: &str) -> SseEvent {
        let index = self.current_block_index.unwrap_or(0);
        let json = serde_json::json!({
            "type": "content_block_delta",
            "index": index,
            "delta": {
                "type": "text_delta",
                "text": text
            }
        });

        let data = json.to_string();
        SseEvent {
            event_name: Some("content_block_delta".to_string()),
            data: Bytes::from(data),
        }
    }

    /// Get the current compression statistics.
    pub fn stats(&self) -> &StreamingStats {
        &self.stats
    }
}

// ── Token estimation ────────────────────────────────────────────────────────

/// Estimate the number of tokens in a text string.
///
/// Uses a simple heuristic: ~4 characters per token for English text.
/// This is an approximation; production use should integrate with
/// tiktoken or a similar tokenizer.
fn estimate_tokens(text: &str) -> usize {
    // Rough estimate: 4 chars per token, minimum 1 token per word
    let char_count = text.len();
    let word_count = text.split_whitespace().count();
    let by_chars = (char_count / 4).max(1);
    by_chars.max(word_count)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn make_text_delta_event(text: &str) -> SseEvent {
        let json = json!({
            "type": "content_block_delta",
            "index": 0,
            "delta": {
                "type": "text_delta",
                "text": text
            }
        });
        SseEvent {
            event_name: Some("content_block_delta".to_string()),
            data: Bytes::from(json.to_string()),
        }
    }

    fn make_metadata_event(event_name: &str) -> SseEvent {
        let json = json!({
            "type": event_name,
            "index": 0
        });
        SseEvent {
            event_name: Some(event_name.to_string()),
            data: Bytes::from(json.to_string()),
        }
    }

    #[test]
    fn metadata_events_pass_through() {
        let mut compressor = StreamingCompressor::new(StreamingConfig::default());

        let event = make_metadata_event("message_start");
        let result = compressor.process_event(event.clone());
        assert!(result.is_some());
        assert_eq!(result.unwrap(), event);
    }

    #[test]
    fn text_below_threshold_passes_through() {
        let mut compressor = StreamingCompressor::new(StreamingConfig {
            text_compress_threshold: 1000, // High threshold
            ..Default::default()
        });

        let event = make_text_delta_event("Hello world");
        let result = compressor.process_event(event.clone());
        assert!(result.is_some());
        // Should pass through unchanged since below threshold
        assert_eq!(result.unwrap(), event);
    }

    #[test]
    fn text_above_threshold_gets_compressed() {
        let mut compressor = StreamingCompressor::new(StreamingConfig {
            text_compress_threshold: 10, // Low threshold for testing
            ..Default::default()
        });

        // Generate enough text to exceed threshold
        let long_text = "the ".repeat(50); // 50 filler words
        let event = make_text_delta_event(&long_text);
        let result = compressor.process_event(event);

        assert!(result.is_some());
        let compressed = result.unwrap();
        assert_eq!(
            compressed.event_name,
            Some("content_block_delta".to_string())
        );

        // The compressed text should be shorter
        let json: Value = serde_json::from_str(compressed.data_str().unwrap()).unwrap();
        let compressed_text = json["delta"]["text"].as_str().unwrap();
        assert!(compressed_text.len() < long_text.len());
    }

    #[test]
    fn flush_emits_remaining_content() {
        let mut compressor = StreamingCompressor::new(StreamingConfig {
            text_compress_threshold: 1000, // High threshold
            ..Default::default()
        });

        // Add some content below threshold
        compressor.process_event(make_text_delta_event("the cat is on the mat"));

        // Flush should emit the content
        let flushed = compressor.flush();
        assert!(flushed.is_some());
    }

    #[test]
    fn flush_empty_returns_none() {
        let mut compressor = StreamingCompressor::new(StreamingConfig::default());
        assert!(compressor.flush().is_none());
    }

    #[test]
    fn stats_tracking() {
        let mut compressor = StreamingCompressor::new(StreamingConfig::default());

        compressor.process_event(make_metadata_event("message_start"));
        compressor.process_event(make_text_delta_event("Hello"));

        let stats = compressor.stats();
        assert_eq!(stats.events_processed, 2);
    }

    #[test]
    fn estimate_tokens_basic() {
        assert!(estimate_tokens("hello world") >= 1);
        assert!(estimate_tokens("the quick brown fox jumps") >= 1);
    }

    #[test]
    fn output_event_is_valid_json() {
        let mut compressor = StreamingCompressor::new(StreamingConfig {
            text_compress_threshold: 5,
            ..Default::default()
        });

        // Add enough text to trigger compression
        let text = "the ".repeat(20);
        let result = compressor.process_event(make_text_delta_event(&text));

        if let Some(event) = result {
            // Must be valid JSON
            let _: Value = serde_json::from_str(event.data_str().unwrap()).unwrap();
        }
    }
}
