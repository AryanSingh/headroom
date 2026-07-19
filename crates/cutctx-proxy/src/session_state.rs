//! Session state tracking for smart context strategies.
//!
//! Per-session LRU keyed by stable session identity. Mirrors the [`DriftState`]
//! pattern from `cache_stabilization/drift_detector.rs` — thread-safe, bounded
//! capacity, evicts LRU on overflow.
//!
//! Session key resolution follows the header-ladder priority documented in
//! `docs/specs/spec-smart-context-strategies.md` §5.2, implementing byte-for-byte
//! parity with Python's `cutctx/proxy/canary_identity.py::resolve_canary_identity`
//! for the supported rung subset.
//!
//! [`DriftState`]: crate::cache_stabilization::drift_detector::DriftState

use std::num::NonZeroUsize;
use std::sync::{Arc, Mutex};
use std::time::Instant;

use axum::http::HeaderMap;
use lru::LruCache;

/// Resolved session identity with metadata for strategy selection.
///
/// `value` is the canonical session key string (opaque to the caller).
/// `sticky` = true means the session will be retained in the LRU across
/// requests (first-class session); sticky = false (fallback request_id)
/// means non-sticky sessions are never stored, only observed transiently.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SessionKey {
    pub value: String,
    pub sticky: bool,
}

/// Resolve a stable session key from request headers and request_id.
///
/// Priority ladder (first present-and-non-empty wins):
/// 1. `x-cutctx-session-id` → raw value, sticky=true
/// 2. `x-session-id` → raw value, sticky=true
/// 3. `session-id` → raw value, sticky=true
/// 4. Derived caller identity:
///    - If ANY of `authorization` or `x-api-key` is present, build material
///      as the credential value plus (if present) x-cutctx-user-id or x-user-id
///      plus (if present) x-cutctx-project or x-project-id, joined with '\n'.
///    - Hash material via `cutctx_core::ccr::compute_key` (BLAKE3, 16-hex prefix).
///    - Return with sticky=true.
/// 5. Fallback: request_id string, sticky=false.
///
/// Header values that are not valid UTF-8 are treated as absent.
pub fn resolve_session_key(headers: &HeaderMap, request_id: &str) -> SessionKey {
    // Normalize header names to lowercase for comparison.
    let get_header = |name: &str| -> Option<String> {
        headers
            .get(name)
            .and_then(|v| v.to_str().ok())
            .filter(|s| !s.is_empty())
            .map(|s| s.to_string())
    };

    // Rung 1: x-cutctx-session-id
    if let Some(value) = get_header("x-cutctx-session-id") {
        return SessionKey {
            value,
            sticky: true,
        };
    }

    // Rung 2: x-session-id
    if let Some(value) = get_header("x-session-id") {
        return SessionKey {
            value,
            sticky: true,
        };
    }

    // Rung 3: session-id
    if let Some(value) = get_header("session-id") {
        return SessionKey {
            value,
            sticky: true,
        };
    }

    // Rung 4: Derived caller identity
    let auth = get_header("authorization").or_else(|| get_header("x-api-key"));
    let user = get_header("x-cutctx-user-id").or_else(|| get_header("x-user-id"));
    let project = get_header("x-cutctx-project").or_else(|| get_header("x-project-id"));

    if let Some(auth) = auth {
        // Build material: join present values with '\n'.
        let mut material_parts = vec![auth];
        if let Some(u) = user {
            material_parts.push(u);
        }
        if let Some(p) = project {
            material_parts.push(p);
        }
        let material = material_parts.join("\n");

        // Hash via the shared CCR key function (BLAKE3, 16-hex prefix).
        // Reuses cutctx-core's hashing rather than adding a direct blake3
        // dependency to this crate; determinism is what matters here.
        let value = cutctx_core::ccr::compute_key(material.as_bytes());

        return SessionKey {
            value,
            sticky: true,
        };
    }

    // Rung 5: Fallback to request_id (non-sticky).
    SessionKey {
        value: request_id.to_string(),
        sticky: false,
    }
}

/// Per-session state snapshot used by strategy selection logic.
///
/// Tracks request count, frozen-floor stability, and last-seen snapshot key.
/// Cloned when returned from `SessionStateStore::observe` so the caller gets
/// an immutable snapshot.
#[derive(Debug, Clone, PartialEq)]
pub struct SessionEntry {
    /// Number of requests seen on this session so far.
    pub request_count: u64,
    /// Last observed frozen message count. Used to detect cache-floor advance.
    pub last_frozen_count: usize,
    /// Turns elapsed since the frozen floor last advanced. Resets to 0 when
    /// frozen_count increases; increments otherwise. Proxy for "cache prefix
    /// is stale and ripe for snapshot".
    pub turns_since_frozen_advance: u32,
    /// Instant the entry was last observed. Used for potential future TTL
    /// eviction (not yet wired; present for completeness).
    pub last_seen: Instant,
    /// Key of the last snapshot stored to CCR for this session (if any).
    /// Used for idempotency when re-requesting the same frozen range.
    pub last_snapshot_key: Option<String>,
}

/// Default capacity for the session state LRU.
pub const SESSION_STATE_CAPACITY: usize = 1000;

/// Thread-safe, bounded LRU keyed by session key string.
///
/// Mirrors the `DriftState` pattern: wrapped in `Arc<Mutex<…>>` for cheap
/// cloning into request handlers. Non-sticky sessions (sticky=false) are
/// never stored; only sticky sessions persist in the LRU.
#[derive(Clone)]
pub struct SessionStateStore {
    cache: Arc<Mutex<LruCache<String, SessionEntry>>>,
}

impl SessionStateStore {
    /// Build a new `SessionStateStore` bounded to `capacity` sessions.
    ///
    /// # Panics
    ///
    /// Panics if `capacity == 0`. Use `SESSION_STATE_CAPACITY` for production
    /// (1000 sessions); tests pass small values to exercise LRU eviction cheaply.
    pub fn new(capacity: usize) -> Self {
        let cap = NonZeroUsize::new(capacity).expect("SessionStateStore capacity must be > 0");
        Self {
            cache: Arc::new(Mutex::new(LruCache::new(cap))),
        }
    }

    /// Observe a request on a session. Updates counters and returns the current
    /// state snapshot.
    ///
    /// For sticky sessions: increments request_count, updates last_seen,
    /// compares frozen_count against last_frozen_count to decide whether to
    /// reset turns_since_frozen_advance or increment it. Returns a clone of
    /// the updated entry.
    ///
    /// For non-sticky sessions (sticky=false): returns a transient entry with
    /// request_count=1 without storing anything.
    pub fn observe(&self, key: &SessionKey, frozen_count: usize) -> SessionEntry {
        if !key.sticky {
            // Non-sticky sessions are not stored; return a transient default.
            return SessionEntry {
                request_count: 1,
                last_frozen_count: frozen_count,
                turns_since_frozen_advance: 0,
                last_seen: Instant::now(),
                last_snapshot_key: None,
            };
        }

        let mut cache = match self.cache.lock() {
            Ok(c) => c,
            Err(poisoned) => {
                tracing::warn!(
                    event = "session_state_mutex_poisoned",
                    "session state mutex was poisoned by a panicking task; recovering"
                );
                poisoned.into_inner()
            }
        };

        if let Some(e) = cache.get_mut(&key.value) {
            e.request_count += 1;
            e.last_seen = Instant::now();
            if frozen_count > e.last_frozen_count {
                e.last_frozen_count = frozen_count;
                e.turns_since_frozen_advance = 0;
                e.last_snapshot_key = None;
            } else {
                e.turns_since_frozen_advance += 1;
            }
            return e.clone();
        }

        let new_entry = SessionEntry {
            request_count: 1,
            last_frozen_count: frozen_count,
            turns_since_frozen_advance: 0,
            last_seen: Instant::now(),
            last_snapshot_key: None,
        };
        cache.put(key.value.clone(), new_entry.clone());
        new_entry
    }

    /// Record the CCR key of a snapshot stored for this session.
    ///
    /// Called after `CcrStore::put` so that repeat requests on the same
    /// session can reuse the snapshot if the frozen floor hasn't advanced.
    pub fn set_snapshot_key(&self, key: &SessionKey, snapshot_key: String) {
        if !key.sticky {
            return; // Non-sticky sessions: no-op.
        }

        let mut cache = match self.cache.lock() {
            Ok(c) => c,
            Err(poisoned) => poisoned.into_inner(),
        };

        if let Some(entry) = cache.get_mut(&key.value) {
            entry.last_snapshot_key = Some(snapshot_key);
        }
    }

    /// Look up the current state of a session (if stored).
    ///
    /// Returns `None` if the session is not in the cache (either never seen,
    /// or evicted). Non-sticky sessions are never stored, so this always
    /// returns `None` for them.
    pub fn get(&self, key: &SessionKey) -> Option<SessionEntry> {
        if !key.sticky {
            return None; // Non-sticky sessions: never stored.
        }

        let mut cache = match self.cache.lock() {
            Ok(c) => c,
            Err(poisoned) => poisoned.into_inner(),
        };

        cache.get(&key.value).cloned()
    }
}

impl std::fmt::Debug for SessionStateStore {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let len = self.cache.lock().map(|c| c.len()).unwrap_or(0);
        f.debug_struct("SessionStateStore")
            .field("len", &len)
            .finish()
    }
}

impl Default for SessionStateStore {
    fn default() -> Self {
        Self::new(SESSION_STATE_CAPACITY)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use http::header::HeaderName;

    fn test_headers() -> HeaderMap {
        HeaderMap::new()
    }

    fn insert_header(headers: &mut HeaderMap, name: &str, value: &str) {
        let name = HeaderName::from_bytes(name.as_bytes()).unwrap();
        headers.insert(name, value.parse().unwrap());
    }

    #[test]
    fn rung_1_x_cutctx_session_id_wins_over_all() {
        let mut headers = test_headers();
        insert_header(&mut headers, "x-cutctx-session-id", "explicit-1");
        insert_header(&mut headers, "x-session-id", "explicit-2");
        insert_header(&mut headers, "session-id", "explicit-3");
        insert_header(&mut headers, "authorization", "Bearer token123");

        let key = resolve_session_key(&headers, "req-123");
        assert_eq!(key.value, "explicit-1");
        assert!(key.sticky);
    }

    #[test]
    fn rung_2_x_session_id_wins_over_session_id_and_derived() {
        let mut headers = test_headers();
        insert_header(&mut headers, "x-session-id", "explicit-2");
        insert_header(&mut headers, "session-id", "explicit-3");
        insert_header(&mut headers, "authorization", "Bearer token123");

        let key = resolve_session_key(&headers, "req-123");
        assert_eq!(key.value, "explicit-2");
        assert!(key.sticky);
    }

    #[test]
    fn rung_3_session_id_wins_over_derived() {
        let mut headers = test_headers();
        insert_header(&mut headers, "session-id", "explicit-3");
        insert_header(&mut headers, "authorization", "Bearer token123");

        let key = resolve_session_key(&headers, "req-123");
        assert_eq!(key.value, "explicit-3");
        assert!(key.sticky);
    }

    #[test]
    fn rung_4_derived_from_authorization_header() {
        let mut headers = test_headers();
        insert_header(&mut headers, "authorization", "Bearer sk-secret-auth");

        let key = resolve_session_key(&headers, "req-123");
        assert!(key.sticky);
        // Shared compute_key: 16-hex BLAKE3 prefix.
        assert_eq!(key.value.len(), 16);
        assert!(key.value.chars().all(|c| c.is_ascii_hexdigit()));
        // Same headers should produce same key (determinism).
        let key2 = resolve_session_key(&headers, "req-different");
        assert_eq!(key.value, key2.value);
    }

    #[test]
    fn rung_4_derived_from_x_api_key_header() {
        let mut headers = test_headers();
        insert_header(&mut headers, "x-api-key", "sk-secret-key");

        let key = resolve_session_key(&headers, "req-123");
        assert!(key.sticky);
        assert_eq!(key.value.len(), 16);
        assert!(key.value.chars().all(|c| c.is_ascii_hexdigit()));
    }

    #[test]
    fn rung_4_authorization_wins_over_x_api_key() {
        let mut headers = test_headers();
        insert_header(&mut headers, "authorization", "Bearer auth-value");
        insert_header(&mut headers, "x-api-key", "key-value");

        let key = resolve_session_key(&headers, "req-123");
        assert!(key.sticky);

        // Different auth values should produce different hashes.
        let mut headers2 = test_headers();
        insert_header(&mut headers2, "authorization", "Bearer different-auth");
        insert_header(&mut headers2, "x-api-key", "key-value");

        let key2 = resolve_session_key(&headers2, "req-123");
        assert_ne!(key.value, key2.value);
    }

    #[test]
    fn rung_4_derived_includes_user_id_when_present() {
        let mut headers = test_headers();
        insert_header(&mut headers, "authorization", "Bearer auth");
        insert_header(&mut headers, "x-cutctx-user-id", "user-123");

        let key = resolve_session_key(&headers, "req-123");
        assert!(key.sticky);

        // Same auth but different user should produce different hash.
        let mut headers2 = test_headers();
        insert_header(&mut headers2, "authorization", "Bearer auth");
        insert_header(&mut headers2, "x-cutctx-user-id", "user-456");

        let key2 = resolve_session_key(&headers2, "req-123");
        assert_ne!(key.value, key2.value);
    }

    #[test]
    fn rung_4_derived_prefers_x_cutctx_user_id_over_x_user_id() {
        let mut headers = test_headers();
        insert_header(&mut headers, "authorization", "Bearer auth");
        insert_header(&mut headers, "x-cutctx-user-id", "user-cutctx");
        insert_header(&mut headers, "x-user-id", "user-legacy");

        let key = resolve_session_key(&headers, "req-123");

        // Verify it used x-cutctx-user-id by comparing against a version with
        // only x-user-id.
        let mut headers2 = test_headers();
        insert_header(&mut headers2, "authorization", "Bearer auth");
        insert_header(&mut headers2, "x-user-id", "user-cutctx");

        let key2 = resolve_session_key(&headers2, "req-123");
        // Should be equal because both use "user-cutctx" as the user part.
        assert_eq!(key.value, key2.value);
    }

    #[test]
    fn rung_4_derived_includes_project_when_present() {
        let mut headers = test_headers();
        insert_header(&mut headers, "authorization", "Bearer auth");
        insert_header(&mut headers, "x-cutctx-project", "project-123");

        let key = resolve_session_key(&headers, "req-123");
        assert!(key.sticky);

        // Same auth but different project should produce different hash.
        let mut headers2 = test_headers();
        insert_header(&mut headers2, "authorization", "Bearer auth");
        insert_header(&mut headers2, "x-cutctx-project", "project-456");

        let key2 = resolve_session_key(&headers2, "req-123");
        assert_ne!(key.value, key2.value);
    }

    #[test]
    fn rung_4_derived_prefers_x_cutctx_project_over_x_project_id() {
        let mut headers = test_headers();
        insert_header(&mut headers, "authorization", "Bearer auth");
        insert_header(&mut headers, "x-cutctx-project", "proj-cutctx");
        insert_header(&mut headers, "x-project-id", "proj-legacy");

        let key = resolve_session_key(&headers, "req-123");

        let mut headers2 = test_headers();
        insert_header(&mut headers2, "authorization", "Bearer auth");
        insert_header(&mut headers2, "x-project-id", "proj-cutctx");

        let key2 = resolve_session_key(&headers2, "req-123");
        assert_eq!(key.value, key2.value);
    }

    #[test]
    fn rung_5_fallback_request_id_non_sticky() {
        let headers = test_headers();
        let key = resolve_session_key(&headers, "req-fallback-123");
        assert_eq!(key.value, "req-fallback-123");
        assert!(!key.sticky);
    }

    #[test]
    fn empty_header_value_treated_as_absent() {
        let mut headers = test_headers();
        insert_header(&mut headers, "x-cutctx-session-id", "");
        insert_header(&mut headers, "authorization", "Bearer auth");

        let key = resolve_session_key(&headers, "req-123");
        // Empty x-cutctx-session-id is skipped; falls through to derived identity.
        assert!(key.sticky);
        assert_eq!(key.value.len(), 16); // Derived hash, not the empty string.
    }

    #[test]
    fn observe_increments_request_count_for_sticky_sessions() {
        let store = SessionStateStore::new(10);
        let key = SessionKey {
            value: "session-1".to_string(),
            sticky: true,
        };

        let entry1 = store.observe(&key, 0);
        assert_eq!(entry1.request_count, 1);

        let entry2 = store.observe(&key, 0);
        assert_eq!(entry2.request_count, 2);

        let entry3 = store.observe(&key, 0);
        assert_eq!(entry3.request_count, 3);
    }

    #[test]
    fn observe_non_sticky_never_stored() {
        let store = SessionStateStore::new(10);
        let key = SessionKey {
            value: "fallback-req".to_string(),
            sticky: false,
        };

        let entry1 = store.observe(&key, 0);
        assert_eq!(entry1.request_count, 1);

        // Call observe again; should still return request_count=1 (not stored).
        let entry2 = store.observe(&key, 0);
        assert_eq!(entry2.request_count, 1);

        // get() should return None for non-sticky.
        assert_eq!(store.get(&key), None);
    }

    #[test]
    fn observe_resets_turns_since_frozen_advance_when_frozen_count_increases() {
        let store = SessionStateStore::new(10);
        let key = SessionKey {
            value: "session-2".to_string(),
            sticky: true,
        };

        let mut entry = store.observe(&key, 0);
        assert_eq!(entry.turns_since_frozen_advance, 0);
        assert_eq!(entry.last_frozen_count, 0);

        // Next request with same frozen_count: turns_since_frozen_advance increments.
        entry = store.observe(&key, 0);
        assert_eq!(entry.turns_since_frozen_advance, 1);

        // Frozen count advances: turns_since_frozen_advance resets to 0.
        entry = store.observe(&key, 5);
        assert_eq!(entry.turns_since_frozen_advance, 0);
        assert_eq!(entry.last_frozen_count, 5);

        // Next request with same frozen_count: increments again.
        entry = store.observe(&key, 5);
        assert_eq!(entry.turns_since_frozen_advance, 1);
    }

    #[test]
    fn observe_updates_last_seen() {
        let store = SessionStateStore::new(10);
        let key = SessionKey {
            value: "session-3".to_string(),
            sticky: true,
        };

        let entry1 = store.observe(&key, 0);
        let time1 = entry1.last_seen;

        // Small delay.
        std::thread::sleep(std::time::Duration::from_millis(10));

        let entry2 = store.observe(&key, 0);
        let time2 = entry2.last_seen;

        assert!(time2 > time1);
    }

    #[test]
    fn set_snapshot_key_stores_for_sticky() {
        let store = SessionStateStore::new(10);
        let key = SessionKey {
            value: "session-4".to_string(),
            sticky: true,
        };

        store.observe(&key, 0);
        store.set_snapshot_key(&key, "snapshot-hash-abc123".to_string());

        let entry = store.get(&key).unwrap();
        assert_eq!(
            entry.last_snapshot_key,
            Some("snapshot-hash-abc123".to_string())
        );
    }

    #[test]
    fn frozen_floor_advance_clears_stale_snapshot_key() {
        let store = SessionStateStore::new(10);
        let key = SessionKey {
            value: "session-snapshot-floor".to_string(),
            sticky: true,
        };

        store.observe(&key, 1);
        store.set_snapshot_key(&key, "stale-snapshot".to_string());
        let entry = store.observe(&key, 2);

        assert_eq!(entry.last_snapshot_key, None);
    }

    #[test]
    fn set_snapshot_key_no_op_for_non_sticky() {
        let store = SessionStateStore::new(10);
        let key = SessionKey {
            value: "fallback-req-2".to_string(),
            sticky: false,
        };

        // Non-sticky: set_snapshot_key is a no-op and doesn't panic.
        store.set_snapshot_key(&key, "snapshot-hash".to_string());

        // get() still returns None.
        assert_eq!(store.get(&key), None);
    }

    #[test]
    fn get_returns_none_for_absent_session() {
        let store = SessionStateStore::new(10);
        let key = SessionKey {
            value: "never-seen".to_string(),
            sticky: true,
        };

        assert_eq!(store.get(&key), None);
    }

    #[test]
    fn lru_evicts_oldest_at_capacity() {
        let store = SessionStateStore::new(3); // Capacity 3.

        let k1 = SessionKey {
            value: "s1".to_string(),
            sticky: true,
        };
        let k2 = SessionKey {
            value: "s2".to_string(),
            sticky: true,
        };
        let k3 = SessionKey {
            value: "s3".to_string(),
            sticky: true,
        };
        let k4 = SessionKey {
            value: "s4".to_string(),
            sticky: true,
        };

        store.observe(&k1, 0);
        store.observe(&k2, 0);
        store.observe(&k3, 0);

        // All three are in the cache.
        assert!(store.get(&k1).is_some());
        assert!(store.get(&k2).is_some());
        assert!(store.get(&k3).is_some());

        // Insert a 4th session; k1 (LRU) is evicted.
        store.observe(&k4, 0);

        assert!(store.get(&k1).is_none(), "k1 should have been evicted");
        assert!(store.get(&k2).is_some(), "k2 should still be present");
        assert!(store.get(&k3).is_some(), "k3 should still be present");
        assert!(store.get(&k4).is_some(), "k4 should be present");
    }

    #[test]
    fn derived_identity_deterministic_same_headers() {
        let mut headers = test_headers();
        insert_header(&mut headers, "authorization", "Bearer auth-value");
        insert_header(&mut headers, "x-cutctx-user-id", "user-123");
        insert_header(&mut headers, "x-cutctx-project", "proj-456");

        let key1 = resolve_session_key(&headers, "req-1");
        let key2 = resolve_session_key(&headers, "req-2");
        let key3 = resolve_session_key(&headers, "req-3");

        // Same headers always produce same key (deterministic).
        assert_eq!(key1.value, key2.value);
        assert_eq!(key2.value, key3.value);
    }

    #[test]
    fn derived_identity_different_project_different_key() {
        let mut headers1 = test_headers();
        insert_header(&mut headers1, "authorization", "Bearer auth");
        insert_header(&mut headers1, "x-cutctx-project", "proj-A");

        let key1 = resolve_session_key(&headers1, "req-123");

        let mut headers2 = test_headers();
        insert_header(&mut headers2, "authorization", "Bearer auth");
        insert_header(&mut headers2, "x-cutctx-project", "proj-B");

        let key2 = resolve_session_key(&headers2, "req-123");

        // Different projects should produce different keys.
        assert_ne!(key1.value, key2.value);
    }

    #[test]
    fn default_capacity_constant_is_1000() {
        assert_eq!(SESSION_STATE_CAPACITY, 1000);
    }

    #[test]
    fn default_impl_uses_session_state_capacity() {
        let store = SessionStateStore::default();
        // Just verify it constructs without panic.
        let key = SessionKey {
            value: "test".to_string(),
            sticky: true,
        };
        let _ = store.observe(&key, 0);
    }
}
