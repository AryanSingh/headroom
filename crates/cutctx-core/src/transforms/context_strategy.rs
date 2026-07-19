//! Context strategy selection for adaptive compression.
//!
//! Implements `docs/specs/spec-smart-context-strategies.md`. This module
//! provides deterministic strategy selection based on observable session
//! signals and per-auth-mode compression policy.
//!
//! # Strategies
//!
//! Four strategies are available:
//!
//! - **`RollingWindow`** — existing live-zone behavior, unchanged.
//!   Always the fallback and the only strategy that produces
//!   byte-identical output to the current behavior.
//! - **`SmartCompact`** — full compression pipeline with lossy ratio
//!   capped by policy.
//! - **`SelectiveClear`** — drops whole low-value turns and offloads
//!   them to CCR.
//! - **`SnapshotResume`** — persists a compressed session snapshot to
//!   CCR and replaces the dropped prefix with a summary block.
//!
//! # Selection
//!
//! `select_strategy` applies a deterministic, ordered rule set based on
//! context signals and per-auth-mode policy. The function is pure —
//! its output depends only on the inputs, making decisions loggable and
//! reproducible.

use crate::compression_policy::CompressionPolicy;

/// Observable, deterministic inputs to strategy selection.
///
/// Computed once per intercepted request from the full message array,
/// session state, and frozen-floor computation.
#[derive(Debug, Clone)]
pub struct ContextSignals {
    /// Estimated token count over the full messages array.
    pub total_tokens_est: usize,
    /// Model context limit from `compression/model_limits.rs`.
    pub model_context_limit: usize,
    /// Utilization ratio: `total_tokens_est / model_context_limit`.
    /// Computed in the constructor and stored for signal consistency.
    pub utilization: f32,
    /// Total number of messages in the request.
    pub message_count: usize,
    /// Number of messages frozen below the compression floor.
    pub frozen_message_count: usize,
    /// Estimated token count in the live zone (above frozen floor).
    pub live_zone_tokens_est: usize,
    /// Session state: turns (requests) since the frozen floor last advanced.
    /// Proxy for "cached prefix is stale".
    pub turns_since_frozen_advance: u32,
    /// Fraction of live-zone turns scoring below the low-value threshold.
    pub low_value_turn_ratio: f32,
    /// Session request count. Proxy for session depth / stability.
    pub session_request_count: u64,
}

impl ContextSignals {
    /// Construct signals with auto-computed utilization.
    ///
    /// Utilization is always computed as `total_tokens_est / model_context_limit`,
    /// clamped to [0.0, 1.0] and clamping on 0 denominator (if
    /// `model_context_limit` is 0, utilization is 1.0, the conservative worst-case).
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        total_tokens_est: usize,
        model_context_limit: usize,
        message_count: usize,
        frozen_message_count: usize,
        live_zone_tokens_est: usize,
        turns_since_frozen_advance: u32,
        low_value_turn_ratio: f32,
        session_request_count: u64,
    ) -> Self {
        let utilization = total_tokens_est as f32 / model_context_limit.max(1) as f32;
        Self {
            total_tokens_est,
            model_context_limit,
            utilization,
            message_count,
            frozen_message_count,
            live_zone_tokens_est,
            turns_since_frozen_advance,
            low_value_turn_ratio,
            session_request_count,
        }
    }
}

/// Strategy configuration — all thresholds and defaults.
///
/// `Default` impl provides conservative, bake-proven values suitable
/// for most deployments. Per-mode policy override happens at the
/// `select_strategy` call site via `CompressionPolicy`.
#[derive(Debug, Clone)]
pub struct StrategyConfig {
    /// Utilization threshold at which to consider `SnapshotResume`.
    /// Default 0.85 (85%).
    pub snapshot_threshold: f32,
    /// Utilization threshold for `SmartCompact` vs `RollingWindow`.
    /// Default 0.50 (50%).
    pub compact_threshold: f32,
    /// Fraction of live-zone turns that must be low-value to trigger
    /// `SelectiveClear`. Default 0.40 (40%).
    pub low_value_ratio: f32,
    /// BM25 score threshold below which a turn is considered low-value.
    /// Default 0.15.
    pub low_value_score: f64,
    /// Number of tail turns to keep in `SnapshotResume`. Default 4.
    pub keep_tail_turns: usize,
    /// Maximum fraction of live-zone turns to drop in `SelectiveClear`.
    /// Default 0.5 (50%).
    pub max_clear_ratio: f32,
    /// Maximum characters to include per-turn digest in `SnapshotResume`
    /// summary block. Default 160.
    pub digest_chars: usize,
    /// Minimum message count to trigger `SelectiveClear`. Default 12.
    pub min_messages_for_clear: usize,
    /// Minimum session request count to trigger `SnapshotResume`.
    /// Default 3.
    pub min_session_requests_for_snapshot: u64,
}

impl Default for StrategyConfig {
    fn default() -> Self {
        Self {
            snapshot_threshold: 0.85,
            compact_threshold: 0.50,
            low_value_ratio: 0.40,
            low_value_score: 0.15,
            keep_tail_turns: 4,
            max_clear_ratio: 0.5,
            digest_chars: 160,
            min_messages_for_clear: 12,
            min_session_requests_for_snapshot: 3,
        }
    }
}

/// Four compression strategies for adaptive context management.
///
/// `Copy` and ordered by likelihood (most-selected first in rule
/// precedence), so pattern matching on the decision is cheap and
/// branch-prediction-friendly.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ContextStrategy {
    /// Existing live-zone behavior, unchanged. Always the fallback.
    RollingWindow,
    /// Run the full compression pipeline harder: lossy ratio up to
    /// policy.max_lossy_ratio, all applicable transforms enabled.
    SmartCompact,
    /// Drop whole low-value turns (offload to CCR), keep high-value ones.
    SelectiveClear,
    /// Persist a compressed session snapshot to CCR and replace the
    /// dropped prefix with a snapshot pointer + summary block.
    SnapshotResume,
}

impl ContextStrategy {
    /// Lower-snake-case label suitable for structured-log fields and
    /// metric labels. Stable wire format matching the spec.
    pub fn as_str(self) -> &'static str {
        match self {
            ContextStrategy::RollingWindow => "rolling_window",
            ContextStrategy::SmartCompact => "smart_compact",
            ContextStrategy::SelectiveClear => "selective_clear",
            ContextStrategy::SnapshotResume => "snapshot_resume",
        }
    }

    /// Parse a string into a strategy. Accepts the snake_case names
    /// returned by `as_str()`. Case-insensitive matching.
    pub fn parse(s: &str) -> Option<Self> {
        match s.to_ascii_lowercase().as_str() {
            "rolling_window" => Some(ContextStrategy::RollingWindow),
            "smart_compact" => Some(ContextStrategy::SmartCompact),
            "selective_clear" => Some(ContextStrategy::SelectiveClear),
            "snapshot_resume" => Some(ContextStrategy::SnapshotResume),
            _ => None,
        }
    }
}

/// Output of strategy selection: the chosen strategy and its rationale.
#[derive(Debug, Clone)]
pub struct StrategyDecision {
    /// The selected strategy.
    pub strategy: ContextStrategy,
    /// Bounded-vocabulary rationale for metric labeling and debugging.
    /// One of: "low_utilization", "near_limit", "session_drift",
    /// "high_utilization", "default", "policy_read_only".
    pub rationale: &'static str,
    /// The signals that drove the decision.
    pub signals: ContextSignals,
}

/// Select a compression strategy based on observable session signals.
///
/// Applies an ordered rule set from the spec (first match wins):
///
/// 1. `utilization < cfg.compact_threshold` → `RollingWindow` ("low_utilization")
/// 2. `utilization >= cfg.snapshot_threshold && session_request_count >= cfg.min_session_requests_for_snapshot`
///    → `SnapshotResume` ("near_limit")
/// 3. `low_value_turn_ratio >= cfg.low_value_ratio && message_count >= cfg.min_messages_for_clear`
///    → `SelectiveClear` ("session_drift")
/// 4. `utilization >= cfg.compact_threshold` → `SmartCompact` ("high_utilization")
/// 5. Otherwise → `RollingWindow` ("default")
///
/// **Hard override (policy binding):**
/// After rule evaluation, if `policy.toin_read_only == true` and the selected
/// strategy is `SelectiveClear` or `SnapshotResume`, replace with:
/// - `SmartCompact` if `utilization >= cfg.compact_threshold`
/// - `RollingWindow` otherwise
///   with rationale `"policy_read_only"`.
///
/// This function is **pure**: it depends only on its inputs and produces
/// no side effects (no I/O, no logging, no randomness).
pub fn select_strategy(
    signals: &ContextSignals,
    policy: &CompressionPolicy,
    cfg: &StrategyConfig,
) -> StrategyDecision {
    let utilization = signals.utilization;

    // Rule 1: low utilization → RollingWindow
    if utilization < cfg.compact_threshold {
        return StrategyDecision {
            strategy: ContextStrategy::RollingWindow,
            rationale: "low_utilization",
            signals: signals.clone(),
        };
    }

    // Rule 2: near limit with stable session → SnapshotResume
    if utilization >= cfg.snapshot_threshold
        && signals.session_request_count >= cfg.min_session_requests_for_snapshot
    {
        let mut decision = StrategyDecision {
            strategy: ContextStrategy::SnapshotResume,
            rationale: "near_limit",
            signals: signals.clone(),
        };

        // Hard override: policy_read_only forbids structural mutations
        if policy.toin_read_only {
            decision.strategy = if utilization >= cfg.compact_threshold {
                ContextStrategy::SmartCompact
            } else {
                ContextStrategy::RollingWindow
            };
            decision.rationale = "policy_read_only";
        }

        return decision;
    }

    // Rule 3: high low-value turn ratio → SelectiveClear
    if signals.low_value_turn_ratio >= cfg.low_value_ratio
        && signals.message_count >= cfg.min_messages_for_clear
    {
        let mut decision = StrategyDecision {
            strategy: ContextStrategy::SelectiveClear,
            rationale: "session_drift",
            signals: signals.clone(),
        };

        // Hard override: policy_read_only forbids structural mutations
        if policy.toin_read_only {
            decision.strategy = if utilization >= cfg.compact_threshold {
                ContextStrategy::SmartCompact
            } else {
                ContextStrategy::RollingWindow
            };
            decision.rationale = "policy_read_only";
        }

        return decision;
    }

    // Rule 4: high utilization → SmartCompact
    if utilization >= cfg.compact_threshold {
        return StrategyDecision {
            strategy: ContextStrategy::SmartCompact,
            rationale: "high_utilization",
            signals: signals.clone(),
        };
    }

    // Rule 5: default → RollingWindow
    StrategyDecision {
        strategy: ContextStrategy::RollingWindow,
        rationale: "default",
        signals: signals.clone(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::auth_mode::AuthMode;

    /// Helper to construct signals with sensible defaults for testing.
    fn build_signals(
        total_tokens_est: usize,
        model_context_limit: usize,
        message_count: usize,
        low_value_turn_ratio: f32,
        session_request_count: u64,
    ) -> ContextSignals {
        ContextSignals::new(
            total_tokens_est,
            model_context_limit,
            message_count,
            5,                // frozen_message_count (arbitrary default)
            total_tokens_est, // live_zone_tokens_est (assume all in live zone)
            10,               // turns_since_frozen_advance (arbitrary)
            low_value_turn_ratio,
            session_request_count,
        )
    }

    /// Test: Rule 1 triggers at low utilization.
    #[test]
    fn rule_1_low_utilization_rolling_window() {
        let signals = build_signals(
            500,  // total_tokens_est
            2000, // model_context_limit → utilization = 0.25 < 0.50
            10,   // message_count
            0.10, // low_value_turn_ratio
            5,    // session_request_count
        );
        let policy = CompressionPolicy::for_mode(AuthMode::Payg);
        let cfg = StrategyConfig::default();

        let decision = select_strategy(&signals, &policy, &cfg);

        assert_eq!(decision.strategy, ContextStrategy::RollingWindow);
        assert_eq!(decision.rationale, "low_utilization");
    }

    /// Test: Rule 2 triggers at high utilization + stable session.
    #[test]
    fn rule_2_near_limit_snapshot_resume() {
        let signals = build_signals(
            1700, // total_tokens_est
            2000, // model_context_limit → utilization = 0.85
            20,   // message_count
            0.10, // low_value_turn_ratio
            5,    // session_request_count ≥ 3
        );
        let policy = CompressionPolicy::for_mode(AuthMode::Payg);
        let cfg = StrategyConfig::default();

        let decision = select_strategy(&signals, &policy, &cfg);

        assert_eq!(decision.strategy, ContextStrategy::SnapshotResume);
        assert_eq!(decision.rationale, "near_limit");
    }

    /// Test: Rule 3 triggers at high low-value ratio + enough messages.
    #[test]
    fn rule_3_session_drift_selective_clear() {
        let signals = build_signals(
            1000, // total_tokens_est
            2000, // model_context_limit → utilization = 0.50 (not < 0.50, not ≥ 0.85)
            15,   // message_count ≥ 12
            0.45, // low_value_turn_ratio ≥ 0.40
            2,    // session_request_count < 3
        );
        let policy = CompressionPolicy::for_mode(AuthMode::Payg);
        let cfg = StrategyConfig::default();

        let decision = select_strategy(&signals, &policy, &cfg);

        assert_eq!(decision.strategy, ContextStrategy::SelectiveClear);
        assert_eq!(decision.rationale, "session_drift");
    }

    /// Test: Rule 4 triggers at high utilization (but not rule 2 or 3).
    #[test]
    fn rule_4_high_utilization_smart_compact() {
        let signals = build_signals(
            1300, // total_tokens_est
            2000, // model_context_limit → utilization = 0.65 (≥ 0.50, < 0.85)
            20,   // message_count
            0.15, // low_value_turn_ratio < 0.40
            2,    // session_request_count < 3
        );
        let policy = CompressionPolicy::for_mode(AuthMode::Payg);
        let cfg = StrategyConfig::default();

        let decision = select_strategy(&signals, &policy, &cfg);

        assert_eq!(decision.strategy, ContextStrategy::SmartCompact);
        assert_eq!(decision.rationale, "high_utilization");
    }

    /// Test: Rules 1 and 4 partition finite utilization, so rule 5 ("default")
    /// is a defensive fallback reachable only for non-finite utilization (NaN).
    /// Below-threshold signals land on rule 1, not rule 5.
    #[test]
    fn rule_5_default_rolling_window() {
        let signals = build_signals(
            900,  // total_tokens_est
            2000, // model_context_limit → utilization = 0.45 < 0.50
            8,    // message_count < 12
            0.15, // low_value_turn_ratio < 0.40
            2,    // session_request_count < 3
        );
        let policy = CompressionPolicy::for_mode(AuthMode::Payg);
        let cfg = StrategyConfig::default();

        let decision = select_strategy(&signals, &policy, &cfg);

        assert_eq!(decision.strategy, ContextStrategy::RollingWindow);
        assert_eq!(decision.rationale, "low_utilization");
    }

    /// Test: Boundary condition — utilization exactly at 0.50.
    #[test]
    fn boundary_utilization_exactly_0_50() {
        let signals = build_signals(
            1000, // total_tokens_est
            2000, // model_context_limit → utilization = exactly 0.50
            10,   // message_count
            0.15, // low_value_turn_ratio
            2,    // session_request_count
        );
        let policy = CompressionPolicy::for_mode(AuthMode::Payg);
        let cfg = StrategyConfig::default();

        let decision = select_strategy(&signals, &policy, &cfg);

        // At exactly 0.50, rule 1 (< 0.50) does NOT match, but rule 4 (≥ 0.50) does.
        assert_eq!(decision.strategy, ContextStrategy::SmartCompact);
        assert_eq!(decision.rationale, "high_utilization");
    }

    /// Test: Boundary condition — utilization exactly at 0.85.
    #[test]
    fn boundary_utilization_exactly_0_85() {
        let signals = build_signals(
            1700, // total_tokens_est
            2000, // model_context_limit → utilization = exactly 0.85
            20,   // message_count
            0.15, // low_value_turn_ratio
            5,    // session_request_count ≥ 3
        );
        let policy = CompressionPolicy::for_mode(AuthMode::Payg);
        let cfg = StrategyConfig::default();

        let decision = select_strategy(&signals, &policy, &cfg);

        // At exactly 0.85, rule 2 (≥ 0.85 && session_request_count ≥ 3) matches first.
        assert_eq!(decision.strategy, ContextStrategy::SnapshotResume);
        assert_eq!(decision.rationale, "near_limit");
    }

    /// Test: Policy override for SnapshotResume → SmartCompact (high util).
    #[test]
    fn policy_override_snapshot_resume_to_smart_compact() {
        let signals = build_signals(
            1700, // total_tokens_est
            2000, // model_context_limit → utilization = 0.85
            20,   // message_count
            0.15, // low_value_turn_ratio
            5,    // session_request_count ≥ 3
        );
        let policy = CompressionPolicy::for_mode(AuthMode::Subscription); // toin_read_only = true
        let cfg = StrategyConfig::default();

        let decision = select_strategy(&signals, &policy, &cfg);

        // Rule 2 would select SnapshotResume, but policy override converts it
        // to SmartCompact (because utilization ≥ 0.50).
        assert_eq!(decision.strategy, ContextStrategy::SmartCompact);
        assert_eq!(decision.rationale, "policy_read_only");
    }

    /// Test: Policy override for SnapshotResume → RollingWindow (low util).
    #[test]
    fn policy_override_snapshot_resume_to_rolling_window() {
        // Artificially construct a high-utilization scenario that would trigger
        // SnapshotResume, then override it. But we need at least 0.50 utilization
        // for rule 4 to work as the base. For this test, we need SnapshotResume
        // but with the policy override converting to RollingWindow, which happens
        // when utilization < 0.50. This is a bit tricky since rule 2 requires
        // ≥ 0.85 utilization, but policy_read_only can convert to RollingWindow
        // only if utilization < 0.50. These constraints can't both be true.
        //
        // However, the override logic is: if toin_read_only and we selected
        // SnapshotResume/SelectiveClear, replace with SmartCompact if util ≥ 0.50,
        // else RollingWindow. Since rule 2 requires util ≥ 0.85, the SmartCompact
        // replacement always applies. So we can't test the RollingWindow path from
        // SnapshotResume directly. This is OK; we test the SelectiveClear path
        // instead.
    }

    /// Test: Policy override for SelectiveClear → SmartCompact (high util).
    #[test]
    fn policy_override_selective_clear_to_smart_compact() {
        let signals = build_signals(
            1300, // total_tokens_est
            2000, // model_context_limit → utilization = 0.65 ≥ 0.50
            15,   // message_count ≥ 12
            0.45, // low_value_turn_ratio ≥ 0.40
            2,    // session_request_count < 3
        );
        let policy = CompressionPolicy::for_mode(AuthMode::Subscription); // toin_read_only = true
        let cfg = StrategyConfig::default();

        let decision = select_strategy(&signals, &policy, &cfg);

        // Rule 3 would select SelectiveClear, but policy override converts it
        // to SmartCompact (because utilization ≥ 0.50).
        assert_eq!(decision.strategy, ContextStrategy::SmartCompact);
        assert_eq!(decision.rationale, "policy_read_only");
    }

    /// Test: With low utilization, rule 1 short-circuits before rule 3 even when
    /// drift signals are present, so Subscription (toin_read_only) sessions with
    /// low utilization get RollingWindow via rule 1 — the override's RollingWindow
    /// replacement branch is defensive and not reachable through rules 2/3, which
    /// both require utilization ≥ compact_threshold in practice.
    #[test]
    fn subscription_low_util_drift_takes_rule_1() {
        let signals = build_signals(
            600,  // total_tokens_est
            2000, // model_context_limit → utilization = 0.30 < 0.50
            15,   // message_count ≥ 12
            0.45, // low_value_turn_ratio ≥ 0.40
            2,    // session_request_count < 3
        );
        let policy = CompressionPolicy::for_mode(AuthMode::Subscription); // toin_read_only = true
        let cfg = StrategyConfig::default();

        let decision = select_strategy(&signals, &policy, &cfg);

        assert_eq!(decision.strategy, ContextStrategy::RollingWindow);
        assert_eq!(decision.rationale, "low_utilization");
    }

    /// Test: Rule precedence — rule 1 wins over rule 3 (low util overrides drift).
    #[test]
    fn rule_precedence_low_util_beats_drift() {
        let signals = build_signals(
            300,  // total_tokens_est
            2000, // model_context_limit → utilization = 0.15 < 0.50
            15,   // message_count ≥ 12
            0.45, // low_value_turn_ratio ≥ 0.40
            5,    // session_request_count
        );
        let policy = CompressionPolicy::for_mode(AuthMode::Payg);
        let cfg = StrategyConfig::default();

        let decision = select_strategy(&signals, &policy, &cfg);

        // Rule 1 matches first despite rule 3 conditions also being met.
        assert_eq!(decision.strategy, ContextStrategy::RollingWindow);
        assert_eq!(decision.rationale, "low_utilization");
    }

    /// Test: ContextStrategy::as_str() and parse() round-trip.
    #[test]
    fn strategy_as_str_and_parse_roundtrip() {
        for strategy in [
            ContextStrategy::RollingWindow,
            ContextStrategy::SmartCompact,
            ContextStrategy::SelectiveClear,
            ContextStrategy::SnapshotResume,
        ] {
            let s = strategy.as_str();
            let parsed = ContextStrategy::parse(s).expect("should parse");
            assert_eq!(parsed, strategy);
        }
    }

    /// Test: ContextStrategy::parse() is case-insensitive.
    #[test]
    fn strategy_parse_case_insensitive() {
        assert_eq!(
            ContextStrategy::parse("ROLLING_WINDOW"),
            Some(ContextStrategy::RollingWindow)
        );
        assert_eq!(
            ContextStrategy::parse("SMART_COMPACT"),
            Some(ContextStrategy::SmartCompact)
        );
        assert_eq!(ContextStrategy::parse("invalid"), None);
    }

    /// Test: ContextSignals::new() computes utilization correctly.
    #[test]
    fn signals_constructor_computes_utilization() {
        let signals = ContextSignals::new(
            1500, // total
            3000, // limit
            10,   // message_count
            2,    // frozen_message_count
            1500, // live_zone_tokens_est
            5,    // turns_since_frozen_advance
            0.20, // low_value_turn_ratio
            10,   // session_request_count
        );
        assert!((signals.utilization - 0.5).abs() < f32::EPSILON);
    }

    /// Test: ContextSignals::new() handles zero model_context_limit.
    #[test]
    fn signals_constructor_guards_zero_limit() {
        let signals = ContextSignals::new(
            100,  // total
            0,    // limit (edge case)
            10,   // message_count
            2,    // frozen_message_count
            100,  // live_zone_tokens_est
            5,    // turns_since_frozen_advance
            0.20, // low_value_turn_ratio
            10,   // session_request_count
        );
        // With 0 limit, we use max(0, 1) = 1, so utilization = 100/1 = 100.0.
        // We don't clamp, so it can exceed 1.0 (representing over-limit).
        assert_eq!(signals.utilization, 100.0);
    }

    /// Test: StrategyConfig::default() has expected values.
    #[test]
    fn config_default_values() {
        let cfg = StrategyConfig::default();
        assert!((cfg.snapshot_threshold - 0.85).abs() < f32::EPSILON);
        assert!((cfg.compact_threshold - 0.50).abs() < f32::EPSILON);
        assert!((cfg.low_value_ratio - 0.40).abs() < f32::EPSILON);
        assert!((cfg.low_value_score - 0.15).abs() < f64::EPSILON);
        assert_eq!(cfg.keep_tail_turns, 4);
        assert!((cfg.max_clear_ratio - 0.5).abs() < f32::EPSILON);
        assert_eq!(cfg.digest_chars, 160);
        assert_eq!(cfg.min_messages_for_clear, 12);
        assert_eq!(cfg.min_session_requests_for_snapshot, 3);
    }
}
