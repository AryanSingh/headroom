//! Semantic caching for LLM prompts — competitive feature parity with Portkey.
//!
//! Portkey offers exact + semantic deduplication of similar prompts. Headroom's
//! existing `CacheAligner` only stabilizes prefixes for deterministic hashing;
//! it cannot detect that two prompts are semantically equivalent despite
//! surface-level differences.
//!
//! This module provides a vector-similarity cache backed by `fastembed`
//! (BGE-small-en-v1.5 embeddings) and `dashmap` for lock-free concurrent
//! lookups. The workflow is:
//!
//! 1. On each incoming prompt, compute an embedding.
//! 2. Scan existing cache entries for cosine similarity ≥ threshold.
//! 3. If found → return the cached response (cache hit).
//! 4. If not found → forward to the LLM, then insert the result.
//!
//! The cache is bounded (`max_entries`) and TTL-based (entries expire after
//! `ttl`). Eviction uses LRU-by-hit-count when the capacity limit is reached.

use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use dashmap::DashMap;
use fastembed::{EmbeddingModel, InitOptions, TextEmbedding};
use thiserror::Error;

// ── Errors ──────────────────────────────────────────────────────────────────

#[derive(Debug, Error)]
pub enum SemanticCacheError {
    #[error("embedding model initialization failed: {0}")]
    EmbeddingInit(String),

    #[error("embedding inference failed: {0}")]
    EmbeddingInference(String),
}

// ── Configuration ───────────────────────────────────────────────────────────

/// Configuration for the semantic cache.
#[derive(Debug, Clone)]
pub struct SemanticCacheConfig {
    /// Minimum cosine similarity to consider a cache entry a match.
    /// Default: 0.95 (very high — near-identical prompts only).
    pub similarity_threshold: f32,

    /// Maximum number of entries before LRU eviction kicks in.
    /// Default: 10,000.
    pub max_entries: usize,

    /// Time-to-live for cache entries. Default: 300 seconds (5 minutes).
    pub ttl: Duration,

    /// HuggingFace embedding model identifier.
    /// Default: "BAAI/bge-small-en-v1.5".
    pub embedding_model: String,
}

impl Default for SemanticCacheConfig {
    fn default() -> Self {
        Self {
            similarity_threshold: 0.95,
            max_entries: 10_000,
            ttl: Duration::from_secs(300),
            embedding_model: "BAAI/bge-small-en-v1.5".to_string(),
        }
    }
}

// ── Cache entry ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
#[allow(dead_code)]
struct CacheEntry {
    /// BLAKE3-based cache key (first 16 hex chars).
    key: String,
    /// The embedding vector for this prompt.
    embedding: Vec<f32>,
    /// The LLM response text.
    response: String,
    /// Number of tokens saved by serving from cache.
    tokens_saved: u32,
    /// When this entry was created.
    created_at: Instant,
    /// Time-to-live for this entry.
    ttl: Duration,
    /// Number of times this entry has been served.
    hit_count: u32,
}

// ── Stats ───────────────────────────────────────────────────────────────────

/// Aggregate statistics for the semantic cache.
#[derive(Debug, Clone, Default)]
pub struct CacheStats {
    /// Total cache hits.
    pub hits: u64,
    /// Total cache misses.
    pub misses: u64,
    /// Current number of entries.
    pub entries: usize,
    /// Estimated memory usage in bytes.
    pub memory_bytes: usize,
}

impl CacheStats {
    /// Hit rate as a fraction [0.0, 1.0].
    pub fn hit_rate(&self) -> f32 {
        let total = self.hits + self.misses;
        if total == 0 {
            0.0
        } else {
            self.hits as f32 / total as f32
        }
    }
}

// ── SemanticCache ───────────────────────────────────────────────────────────

/// A vector-similarity cache for LLM prompts.
///
/// Uses BGE-small-en-v1.5 embeddings for semantic similarity search and
/// cosine similarity scoring. Entries are evicted by TTL or LRU when the
/// capacity limit is reached.
pub struct SemanticCache {
    /// Concurrent map from cache key → entry.
    entries: DashMap<String, CacheEntry>,
    /// Text embedding model (BGE-small-en-v1.5 via fastembed), wrapped in Mutex.
    embedder: Mutex<TextEmbedding>,
    /// Configuration parameters.
    config: SemanticCacheConfig,
    /// Global hit counter (atomic for lock-free reads).
    hit_counter: AtomicU64,
    /// Global miss counter.
    miss_counter: AtomicU64,
}

impl SemanticCache {
    /// Create a new semantic cache with the given configuration.
    ///
    /// Initializes the embedding model on first call. The model file
    /// (~30 MB int8-quantized ONNX) auto-downloads from HuggingFace Hub
    /// on first use.
    pub fn new(config: SemanticCacheConfig) -> Result<Self, SemanticCacheError> {
        let model = EmbeddingModel::BGESmallENV15;
        let options = InitOptions::new(model).with_show_download_progress(false);
        let embedder =
            TextEmbedding::try_new(options).map_err(|e| SemanticCacheError::EmbeddingInit(e.to_string()))?;

        Ok(Self {
            entries: DashMap::with_capacity(config.max_entries.min(4096)),
            embedder: Mutex::new(embedder),
            config,
            hit_counter: AtomicU64::new(0),
            miss_counter: AtomicU64::new(0),
        })
    }

    /// Look up a prompt in the cache. Returns `Some(response)` if a
    /// semantically similar prompt was found within the similarity threshold.
    pub fn get(&self, prompt: &str) -> Option<String> {
        let span = tracing::info_span!(
            "semantic_cache_lookup",
            cache_hit = false,
            similarity = tracing::field::Empty,
            tokens_saved = tracing::field::Empty
        );
        let _enter = span.enter();

        let prompt_embedding = self.embed(prompt).ok()?;

        // Evict expired entries before scanning
        self.evict_expired();

        let mut best_match: Option<(String, f32)> = None;

        for entry in self.entries.iter() {
            let entry = entry.value();
            if entry.created_at.elapsed() > entry.ttl {
                continue; // expired
            }
            let similarity = cosine_similarity(&prompt_embedding, &entry.embedding);
            if similarity >= self.config.similarity_threshold {
                match &best_match {
                    Some((_, best_sim)) if similarity <= *best_sim => {}
                    _ => {
                        best_match = Some((entry.key.clone(), similarity));
                    }
                }
            }
        }

        if let Some((key, similarity)) = best_match {
            span.record("cache_hit", true);
            span.record("similarity", similarity);
            self.hit_counter.fetch_add(1, Ordering::Relaxed);
            if let Some(mut entry) = self.entries.get_mut(&key) {
                entry.hit_count += 1;
                span.record("tokens_saved", entry.tokens_saved);
                return Some(entry.response.clone());
            }
        }

        self.miss_counter.fetch_add(1, Ordering::Relaxed);
        None
    }

    /// Insert a prompt-response pair into the cache.
    pub fn insert(&self, prompt: &str, response: String, tokens_saved: u32) {
        let prompt_embedding = match self.embed(prompt) {
            Ok(e) => e,
            Err(_) => return, // silently skip if embedding fails
        };

        let key = compute_cache_key(prompt);

        // If at capacity, evict the entry with the lowest hit count
        if self.entries.len() >= self.config.max_entries {
            self.evict_lru();
        }

        let entry = CacheEntry {
            key: key.clone(),
            embedding: prompt_embedding,
            response,
            tokens_saved,
            created_at: Instant::now(),
            ttl: self.config.ttl,
            hit_count: 0,
        };

        self.entries.insert(key, entry);
    }

    /// Remove expired entries from the cache.
    pub fn evict_expired(&self) {
        let now = Instant::now();
        self.entries.retain(|_, entry| {
            now.duration_since(entry.created_at) <= entry.ttl
        });
    }

    /// Get aggregate cache statistics.
    pub fn stats(&self) -> CacheStats {
        self.evict_expired();

        let entries = self.entries.len();
        // Rough memory estimate: each entry ≈ embedding vector (384 * 4 bytes)
        // + response string + overhead
        let memory_bytes = entries * (384 * 4 + 256 + 64);

        CacheStats {
            hits: self.hit_counter.load(Ordering::Relaxed),
            misses: self.miss_counter.load(Ordering::Relaxed),
            entries,
            memory_bytes,
        }
    }

    /// Compute the embedding for a text string.
    fn embed(&self, text: &str) -> Result<Vec<f32>, SemanticCacheError> {
        let mut guard = self
            .embedder
            .lock()
            .map_err(|e| SemanticCacheError::EmbeddingInference(format!("lock poisoned: {}", e)))?;
        guard
            .embed(vec![text], None)
            .map_err(|e| SemanticCacheError::EmbeddingInference(e.to_string()))?
            .into_iter()
            .next()
            .ok_or_else(|| SemanticCacheError::EmbeddingInference("empty embedding".into()))
    }

    /// Evict the entry with the lowest hit count (LRU-by-count).
    fn evict_lru(&self) {
        if self.entries.is_empty() {
            return;
        }

        // Find the key with the minimum hit_count
        let mut min_key: Option<String> = None;
        let mut min_count = u32::MAX;

        for entry in self.entries.iter() {
            if entry.value().hit_count < min_count {
                min_count = entry.value().hit_count;
                min_key = Some(entry.key().clone());
            }
        }

        if let Some(key) = min_key {
            self.entries.remove(&key);
        }
    }
}

// ── Helpers ─────────────────────────────────────────────────────────────────

/// Cosine similarity between two embedding vectors.
pub fn cosine_similarity(a: &[f32], b: &[f32]) -> f32 {
    if a.len() != b.len() || a.is_empty() {
        return 0.0;
    }
    let dot: f32 = a.iter().zip(b.iter()).map(|(x, y)| x * y).sum();
    let norm_a: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
    let norm_b: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();
    if norm_a == 0.0 || norm_b == 0.0 {
        0.0
    } else {
        dot / (norm_a * norm_b)
    }
}

/// Compute a cache key from a prompt using BLAKE3 (first 16 hex chars).
fn compute_cache_key(prompt: &str) -> String {
    let hash = blake3::hash(prompt.as_bytes());
    hash.to_hex()[..16].to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cosine_similarity_identical_vectors() {
        let v = vec![1.0, 2.0, 3.0];
        assert!((cosine_similarity(&v, &v) - 1.0).abs() < f32::EPSILON);
    }

    #[test]
    fn cosine_similarity_orthogonal_vectors() {
        let a = vec![1.0, 0.0];
        let b = vec![0.0, 1.0];
        assert!(cosine_similarity(&a, &b).abs() < f32::EPSILON);
    }

    #[test]
    fn cosine_similarity_opposite_vectors() {
        let a = vec![1.0, 0.0];
        let b = vec![-1.0, 0.0];
        assert!((cosine_similarity(&a, &b) - (-1.0)).abs() < f32::EPSILON);
    }

    #[test]
    fn cosine_similarity_empty_vectors() {
        assert_eq!(cosine_similarity(&[], &[]), 0.0);
    }

    #[test]
    fn cosine_similarity_different_lengths() {
        let a = vec![1.0, 2.0];
        let b = vec![1.0, 2.0, 3.0];
        assert_eq!(cosine_similarity(&a, &b), 0.0);
    }

    #[test]
    fn cosine_similarity_zero_vector() {
        let a = vec![0.0, 0.0];
        let b = vec![1.0, 2.0];
        assert_eq!(cosine_similarity(&a, &b), 0.0);
    }

    #[test]
    fn compute_cache_key_deterministic() {
        let k1 = compute_cache_key("hello world");
        let k2 = compute_cache_key("hello world");
        assert_eq!(k1, k2);
        assert_eq!(k1.len(), 16);
    }

    #[test]
    fn compute_cache_key_different_inputs() {
        let k1 = compute_cache_key("hello");
        let k2 = compute_cache_key("world");
        assert_ne!(k1, k2);
    }

    #[test]
    fn stats_default_values() {
        let stats = CacheStats::default();
        assert_eq!(stats.hits, 0);
        assert_eq!(stats.misses, 0);
        assert_eq!(stats.entries, 0);
        assert_eq!(stats.hit_rate(), 0.0);
    }

    #[test]
    fn stats_hit_rate_calculation() {
        let stats = CacheStats {
            hits: 7,
            misses: 3,
            ..Default::default()
        };
        assert!((stats.hit_rate() - 0.7).abs() < f32::EPSILON);
    }
}
