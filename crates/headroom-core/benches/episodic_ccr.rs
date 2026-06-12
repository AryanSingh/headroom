//! Episodic memory CCR compression benchmark.
//!
//! Measures the latency of the full episodic memory compression path:
//! detect prefix -> SHA-256 hash -> store in CCR -> emit marker string.
//!
//! Target: < 5ms for CCR compression of typical episodic memory blocks.
//!
//! Run with:
//!     cargo bench -p headroom-core --bench episodic_ccr

use std::sync::Arc;

use criterion::{black_box, criterion_group, criterion_main, Criterion, Throughput};
use headroom_core::ccr::backends::SqliteCcrStore;
use headroom_core::ccr::{CcrStore, InMemoryCcrStore};
use headroom_core::transforms::smart_crusher::compaction::ir::OpaqueKind;
use headroom_core::transforms::smart_crusher::compaction::walker::emit_opaque_ccr_marker;

/// Generate a realistic episodic memory block of approximately `target_chars` characters.
fn generate_episodic_memory(target_chars: usize) -> String {
    let sections = vec![
        "# Session 2025-01-15\n\n\
         ## User Requests\n\
         - Refactored authentication module to use OAuth2\n\
         - Fixed memory leak in WebSocket handler\n\
         - Deployed v2.3.1 to staging\n\n\
         ## Key Decisions\n\
         - Chose SQLite over PostgreSQL for local cache (simpler deployment)\n\
         - Added circuit breaker pattern to payment service\n\
         - Switched from REST to gRPC for inter-service communication\n\n\
         ## Errors Encountered\n\
         - `ConnectionTimeout` in payment gateway (resolved by increasing pool size)\n\
         - `OutOfMemoryError` during batch processing (resolved by streaming)\n\n\
         ## Files Modified\n\
         - `src/auth/oauth2.rs` - new OAuth2 flow\n\
         - `src/ws/handler.rs` - fixed buffer overflow\n\
         - `deploy/staging.yaml` - v2.3.1 config\n\n\
         ---\n\n\
         # Session 2025-01-12\n\n\
         ## User Requests\n\
         - Implemented rate limiting middleware\n\
         - Added Prometheus metrics endpoint\n\
         - Migrated database schema for multi-tenancy\n\n\
         ## Key Decisions\n\
         - Used token bucket algorithm for rate limiting (100 req/s per tenant)\n\
         - Metrics stored in time-series format for Grafana dashboards\n\
         - Schema migration via blue-green with backward-compatible views\n\n\
         ## Errors Encountered\n\
         - `RateLimitExceeded` errors during load test (tuned thresholds)\n\
         - Schema migration deadlock (added lock timeout)\n\n\
         ## Files Modified\n\
         - `src/middleware/rate_limit.rs` - token bucket implementation\n\
         - `src/metrics/prometheus.rs` - new metrics endpoint\n\
         - `migrations/003_multi_tenant.sql` - schema changes\n",
    ];

    let section_text = sections.join("\n");
    let mut result = String::new();
    while result.len() < target_chars {
        result.push_str(&section_text);
    }
    result.truncate(target_chars);
    result
}

fn bench_episodic_ccr_roundtrip(c: &mut Criterion) {
    let store: Arc<dyn CcrStore> = Arc::new(InMemoryCcrStore::new());

    let mut group = c.benchmark_group("episodic_ccr/roundtrip");

    for (size_label, chars) in &[
        ("1KB", 1_000),
        ("5KB", 5_000),
        ("10KB", 10_000),
        ("20KB", 20_000),
    ] {
        let memory_text = generate_episodic_memory(*chars);
        let prefix = "[SYSTEM: Past Session Memories]\n";
        let full_text = format!("{prefix}{memory_text}");

        group.throughput(Throughput::Bytes(full_text.len() as u64));
        group.bench_with_input(
            format!("detect_and_store/{size_label}"),
            &full_text,
            |b, text| {
                b.iter(|| {
                    // This is the exact path from walker.rs walk_string()
                    if text.starts_with("[SYSTEM: Past Session Memories]") {
                        black_box(emit_opaque_ccr_marker(
                            text,
                            &OpaqueKind::EpisodicMemory,
                            Some(&store),
                        ));
                    }
                });
            },
        );
    }
    group.finish();
}

fn bench_emit_opaque_ccr_marker(c: &mut Criterion) {
    let store: Arc<dyn CcrStore> = Arc::new(InMemoryCcrStore::new());

    let mut group = c.benchmark_group("episodic_ccr/emit_marker");

    for (size_label, chars) in &[
        ("1KB", 1_000),
        ("5KB", 5_000),
        ("10KB", 10_000),
    ] {
        let payload = generate_episodic_memory(*chars);
        group.throughput(Throughput::Bytes(payload.len() as u64));
        group.bench_function(format!("sha256_hash_and_store/{size_label}"), |b| {
            b.iter(|| {
                black_box(emit_opaque_ccr_marker(
                    black_box(&payload),
                    &OpaqueKind::EpisodicMemory,
                    Some(&store),
                ));
            });
        });
    }
    group.finish();
}

fn bench_ccr_store_put_get(c: &mut Criterion) {
    let store: Arc<dyn CcrStore> = Arc::new(InMemoryCcrStore::new());
    let payload_5k = generate_episodic_memory(5_000);

    let mut group = c.benchmark_group("episodic_ccr/store_ops");
    group.throughput(Throughput::Elements(1));

    // Pre-populate for get benchmark
    store.put("test_hash_001", &payload_5k);

    group.bench_function("put_5KB_payload", |b| {
        let mut i = 0u64;
        b.iter(|| {
            let key = format!("bench_{i:012x}");
            store.put(black_box(&key), black_box(&payload_5k));
            i += 1;
        });
    });

    group.bench_function("get_5KB_payload", |b| {
        b.iter(|| {
            black_box(store.get(black_box("test_hash_001")));
        });
    });

    group.finish();
}

fn bench_sqlite_ccr(c: &mut Criterion) {
    // Benchmark SQLite CCR store (the production backend)
    let tmp = std::env::temp_dir().join("headroom_bench_episodic");
    let _ = std::fs::remove_dir_all(&tmp);
    std::fs::create_dir_all(&tmp).unwrap();
    let db_path = tmp.join("bench.db");

    let store = SqliteCcrStore::open(&db_path, 300).expect("failed to create sqlite store");
    let payload_5k = generate_episodic_memory(5_000);

    let mut group = c.benchmark_group("episodic_ccr/sqlite");
    group.throughput(Throughput::Elements(1));

    group.bench_function("put_5KB", |b| {
        let mut i = 0u64;
        b.iter(|| {
            let key = format!("bench_{i:012x}");
            store.put(black_box(&key), black_box(&payload_5k));
            i += 1;
        });
    });

    store.put("hit_key", &payload_5k);
    group.bench_function("get_5KB_hit", |b| {
        b.iter(|| {
            black_box(store.get(black_box("hit_key")));
        });
    });

    group.finish();
    let _ = std::fs::remove_dir_all(&tmp);
}

criterion_group!(
    benches,
    bench_episodic_ccr_roundtrip,
    bench_emit_opaque_ccr_marker,
    bench_ccr_store_put_get,
    bench_sqlite_ccr,
);
criterion_main!(benches);
