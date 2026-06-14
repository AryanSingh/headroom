//! OpenTelemetry integration for headroom-proxy.
//!
//! Enterprise buyers need per-request cost attribution, latency tracking,
//! and the 40+ metrics that competitors like Portkey offer. This module
//! provides OTel tracing and metrics via the OTLP/HTTP exporter.
//!
//! # Configuration
//!
//! Set `OTEL_EXPORTER_OTLP_ENDPOINT` (default: `http://localhost:4318`)
//! to point to your OTel collector. The service name is `headroom-proxy`.
//!
//! # Non-fatal initialization
//!
//! If the OTel collector is unreachable or the exporter fails to
//! initialize, the proxy continues without OTel. A warning is logged
//! but the proxy remains fully functional.

use opentelemetry::trace::TracerProvider as _;
use opentelemetry::KeyValue;
use opentelemetry::metrics::{Counter, Histogram};
use opentelemetry_otlp::WithExportConfig;
use opentelemetry_sdk::trace::TracerProvider;
use opentelemetry_sdk::runtime;
use tracing_opentelemetry::OpenTelemetryLayer;
use tracing_subscriber::Registry;

// ── Metric names ────────────────────────────────────────────────────────────

/// Metric name constants for OTel instrumentation.
pub mod metric_names {
    /// Total requests processed.
    pub const REQUESTS_TOTAL: &str = "headroom.requests.total";
    /// Request duration in seconds.
    pub const REQUEST_DURATION: &str = "headroom.request.duration";
    /// Input tokens per request (before compression).
    pub const REQUEST_TOKENS_INPUT: &str = "headroom.request.tokens.input";
    /// Output tokens per request.
    pub const REQUEST_TOKENS_OUTPUT: &str = "headroom.request.tokens.output";
    /// Compression ratio per request.
    pub const COMPRESSION_RATIO: &str = "headroom.compression.ratio";
    /// Total tokens saved by compression.
    pub const COMPRESSION_TOKENS_SAVED: &str = "headroom.compression.tokens.saved";
    /// Total bytes saved by compression.
    pub const COMPRESSION_BYTES_SAVED: &str = "headroom.compression.bytes.saved";
    /// Cache hit count.
    pub const CACHE_HITS: &str = "headroom.cache.hits";
    /// Cache miss count.
    pub const CACHE_MISSES: &str = "headroom.cache.misses";
    /// Current cache entry count.
    pub const CACHE_ENTRIES: &str = "headroom.cache.entries";
    /// Estimated cost savings in USD.
    pub const COST_ESTIMATED: &str = "headroom.cost.estimated";
}

// ── OTel metrics handle ─────────────────────────────────────────────────────

/// Pre-registered OTel metrics for the proxy.
///
/// All metrics are created once at startup and reused across requests
/// to avoid repeated registration overhead.
pub struct OtelMetrics {
    pub requests_total: Counter<u64>,
    pub request_duration: Histogram<f64>,
    pub tokens_input: Histogram<u64>,
    pub tokens_output: Histogram<u64>,
    pub compression_ratio: Histogram<f64>,
    pub compression_tokens_saved: Counter<u64>,
    pub compression_bytes_saved: Counter<u64>,
    pub cache_hits: Counter<u64>,
    pub cache_misses: Counter<u64>,
    pub cache_entries: Histogram<f64>,
    pub cost_estimated: Counter<f64>,
}

impl OtelMetrics {
    /// Create metrics from a meter provider.
    pub fn new(meter: &opentelemetry::metrics::Meter) -> Self {
        let requests_total = meter
            .u64_counter(metric_names::REQUESTS_TOTAL)
            .with_description("Total requests processed by headroom-proxy")
            .build();

        let request_duration = meter
            .f64_histogram(metric_names::REQUEST_DURATION)
            .with_description("Request duration in seconds")
            .build();

        let tokens_input = meter
            .u64_histogram(metric_names::REQUEST_TOKENS_INPUT)
            .with_description("Input tokens before compression")
            .build();

        let tokens_output = meter
            .u64_histogram(metric_names::REQUEST_TOKENS_OUTPUT)
            .with_description("Output tokens in response")
            .build();

        let compression_ratio = meter
            .f64_histogram(metric_names::COMPRESSION_RATIO)
            .with_description("Compression ratio per request")
            .build();

        let compression_tokens_saved = meter
            .u64_counter(metric_names::COMPRESSION_TOKENS_SAVED)
            .with_description("Total tokens saved by compression")
            .build();

        let compression_bytes_saved = meter
            .u64_counter(metric_names::COMPRESSION_BYTES_SAVED)
            .with_description("Total bytes saved by compression")
            .build();

        let cache_hits = meter
            .u64_counter(metric_names::CACHE_HITS)
            .with_description("Cache hit count")
            .build();

        let cache_misses = meter
            .u64_counter(metric_names::CACHE_MISSES)
            .with_description("Cache miss count")
            .build();

        let cache_entries = meter
            .f64_histogram(metric_names::CACHE_ENTRIES)
            .with_description("Current cache entry count")
            .build();

        let cost_estimated = meter
            .f64_counter(metric_names::COST_ESTIMATED)
            .with_description("Estimated cost savings in USD")
            .build();

        Self {
            requests_total,
            request_duration,
            tokens_input,
            tokens_output,
            compression_ratio,
            compression_tokens_saved,
            compression_bytes_saved,
            cache_hits,
            cache_misses,
            cache_entries,
            cost_estimated,
        }
    }
}

// ── Tracer initialization ───────────────────────────────────────────────────

/// Initialize the OTLP tracer provider.
///
/// Reads `OTEL_EXPORTER_OTLP_ENDPOINT` from the environment (default:
/// `http://localhost:4318`). Returns `Err` if the exporter fails to
/// initialize, but the caller should log and continue.
pub fn init_otel_tracer() -> Result<TracerProvider, Box<dyn std::error::Error + Send + Sync>> {
    let endpoint = std::env::var("OTEL_EXPORTER_OTLP_ENDPOINT")
        .unwrap_or_else(|_| "http://localhost:4318".to_string());

    let exporter = opentelemetry_otlp::SpanExporter::builder()
        .with_http()
        .with_endpoint(&endpoint)
        .build()?;

    let provider = TracerProvider::builder()
        .with_batch_exporter(exporter, runtime::Tokio)
        .build();

    Ok(provider)
}

/// Create an OpenTelemetry tracing layer for `tracing-subscriber`.
pub fn create_otel_layer(
    provider: &TracerProvider,
) -> OpenTelemetryLayer<Registry, opentelemetry_sdk::trace::Tracer> {
    let tracer = provider.tracer("headroom-proxy");
    tracing_opentelemetry::layer().with_tracer(tracer)
}

// ── Convenience recording functions ─────────────────────────────────────────

/// Record a request metric.
pub fn record_request(
    metrics: &OtelMetrics,
    model: &str,
    auth_mode: &str,
    endpoint: &str,
) {
    metrics.requests_total.add(
        1,
        &[
            KeyValue::new("model", model.to_string()),
            KeyValue::new("auth_mode", auth_mode.to_string()),
            KeyValue::new("endpoint", endpoint.to_string()),
        ],
    );
}

/// Record request duration.
pub fn record_duration(metrics: &OtelMetrics, duration_secs: f64, model: &str, auth_mode: &str) {
    metrics.request_duration.record(
        duration_secs,
        &[
            KeyValue::new("model", model.to_string()),
            KeyValue::new("auth_mode", auth_mode.to_string()),
        ],
    );
}

/// Record compression results.
pub fn record_compression(
    metrics: &OtelMetrics,
    ratio: f32,
    tokens_saved: u32,
    bytes_saved: usize,
) {
    metrics.compression_ratio.record(ratio as f64, &[]);
    metrics
        .compression_tokens_saved
        .add(tokens_saved as u64, &[]);
    metrics
        .compression_bytes_saved
        .add(bytes_saved as u64, &[]);
}

/// Record a cache hit.
pub fn record_cache_hit(metrics: &OtelMetrics) {
    metrics.cache_hits.add(1, &[]);
}

/// Record a cache miss.
pub fn record_cache_miss(metrics: &OtelMetrics) {
    metrics.cache_misses.add(1, &[]);
}

/// Add span attributes to the current tracing span.
pub fn add_span_attributes(
    model: &str,
    auth_mode: &str,
    endpoint: &str,
    tokens_saved: Option<u32>,
) {
    let span = tracing::Span::current();
    span.record("headroom.model", model);
    span.record("headroom.auth_mode", auth_mode);
    span.record("headroom.endpoint", endpoint);
    if let Some(saved) = tokens_saved {
        span.record("headroom.tokens_saved", saved as i64);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn metric_names_are_unique() {
        let names = [
            metric_names::REQUESTS_TOTAL,
            metric_names::REQUEST_DURATION,
            metric_names::REQUEST_TOKENS_INPUT,
            metric_names::REQUEST_TOKENS_OUTPUT,
            metric_names::COMPRESSION_RATIO,
            metric_names::COMPRESSION_TOKENS_SAVED,
            metric_names::COMPRESSION_BYTES_SAVED,
            metric_names::CACHE_HITS,
            metric_names::CACHE_MISSES,
            metric_names::CACHE_ENTRIES,
            metric_names::COST_ESTIMATED,
        ];
        // Check all names start with "headroom."
        for name in &names {
            assert!(
                name.starts_with("headroom."),
                "Metric name {} should start with headroom.",
                name
            );
        }
        // Check all names are unique
        let mut sorted = names.to_vec();
        sorted.sort();
        sorted.dedup();
        assert_eq!(sorted.len(), names.len(), "Duplicate metric names found");
    }

    #[test]
    fn metric_names_match_prometheus_format() {
        // OTel metric names should use dots, which OTLP converts to underscores
        assert!(metric_names::REQUESTS_TOTAL.contains('.'));
        assert!(metric_names::REQUEST_DURATION.contains('.'));
    }
}
