//! Product-facing feature catalog for CutCtx Control.
//!
//! Maps toggle keys to CLI flags / env vars and whether a change can apply
//! live or requires a proxy restart.

use serde::{Deserialize, Serialize};

/// How a feature change is applied to a running proxy.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ApplyMode {
    Live,
    Restart,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FeatureKind {
    Bool,
    Choice,
    Text,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct FeatureDef {
    pub key: &'static str,
    pub group: &'static str,
    pub label: &'static str,
    pub kind: FeatureKind,
    pub apply: ApplyMode,
    /// CLI flag when enabled (bool) or flag prefix for valued options.
    pub cli_flag: &'static str,
    /// Optional negated CLI flag when disabled (bool features).
    pub cli_flag_off: Option<&'static str>,
    /// Choices for `FeatureKind::Choice`.
    pub choices: &'static [&'static str],
    pub default_bool: bool,
    pub default_text: &'static str,
}

/// Curated v1 catalog — not every CLI flag, only product-facing controls.
pub fn catalog() -> &'static [FeatureDef] {
    FEATURES
}

pub fn get(key: &str) -> Option<&'static FeatureDef> {
    FEATURES.iter().find(|f| f.key == key)
}

#[cfg(test)]
pub fn group_keys() -> Vec<&'static str> {
    let mut groups = Vec::new();
    for f in FEATURES {
        if !groups.contains(&f.group) {
            groups.push(f.group);
        }
    }
    groups
}

static FEATURES: &[FeatureDef] = &[
    FeatureDef {
        key: "optimize",
        group: "Optimization",
        label: "Optimization",
        kind: FeatureKind::Bool,
        apply: ApplyMode::Restart,
        cli_flag: "",
        cli_flag_off: Some("--no-optimize"),
        choices: &[],
        default_bool: true,
        default_text: "",
    },
    FeatureDef {
        key: "mode",
        group: "Optimization",
        label: "Mode",
        kind: FeatureKind::Choice,
        apply: ApplyMode::Restart,
        cli_flag: "--mode",
        cli_flag_off: None,
        choices: &["token", "cache"],
        default_bool: true,
        default_text: "token",
    },
    FeatureDef {
        key: "cache",
        group: "Optimization",
        label: "Semantic cache",
        kind: FeatureKind::Bool,
        apply: ApplyMode::Restart,
        cli_flag: "",
        cli_flag_off: Some("--no-cache"),
        choices: &[],
        default_bool: true,
        default_text: "",
    },
    FeatureDef {
        key: "rate_limit",
        group: "Optimization",
        label: "Rate limiting",
        kind: FeatureKind::Bool,
        apply: ApplyMode::Restart,
        cli_flag: "",
        cli_flag_off: Some("--no-rate-limit"),
        choices: &[],
        default_bool: true,
        default_text: "",
    },
    FeatureDef {
        key: "ccr_inject_tool",
        group: "CCR",
        label: "CCR retrieve tool",
        kind: FeatureKind::Bool,
        apply: ApplyMode::Restart,
        cli_flag: "",
        cli_flag_off: Some("--no-ccr-inject-tool"),
        choices: &[],
        default_bool: true,
        default_text: "",
    },
    FeatureDef {
        key: "ccr_marker",
        group: "CCR",
        label: "CCR markers",
        kind: FeatureKind::Bool,
        apply: ApplyMode::Restart,
        cli_flag: "",
        cli_flag_off: Some("--no-ccr-marker"),
        choices: &[],
        default_bool: true,
        default_text: "",
    },
    FeatureDef {
        key: "ccr_proactive_expansion",
        group: "CCR",
        label: "CCR proactive expansion",
        kind: FeatureKind::Bool,
        apply: ApplyMode::Restart,
        cli_flag: "",
        cli_flag_off: Some("--no-ccr-proactive-expansion"),
        choices: &[],
        default_bool: true,
        default_text: "",
    },
    FeatureDef {
        key: "memory",
        group: "Memory",
        label: "Persistent memory",
        kind: FeatureKind::Bool,
        apply: ApplyMode::Restart,
        cli_flag: "--memory",
        cli_flag_off: None,
        choices: &[],
        default_bool: false,
        default_text: "",
    },
    FeatureDef {
        key: "learn",
        group: "Memory",
        label: "Live traffic learning",
        kind: FeatureKind::Bool,
        apply: ApplyMode::Restart,
        cli_flag: "--learn",
        cli_flag_off: None,
        choices: &[],
        default_bool: false,
        default_text: "",
    },
    FeatureDef {
        key: "kompress",
        group: "Engines",
        label: "Kompress ML",
        kind: FeatureKind::Bool,
        apply: ApplyMode::Restart,
        cli_flag: "--enable-kompress",
        cli_flag_off: Some("--disable-kompress"),
        choices: &[],
        default_bool: false,
        default_text: "",
    },
    FeatureDef {
        key: "memoize",
        group: "Engines",
        label: "Memoize tool results",
        kind: FeatureKind::Bool,
        apply: ApplyMode::Restart,
        cli_flag: "--memoize",
        cli_flag_off: None,
        choices: &[],
        default_bool: false,
        default_text: "",
    },
    FeatureDef {
        key: "drain3",
        group: "Engines",
        label: "Drain3 log mining",
        kind: FeatureKind::Bool,
        apply: ApplyMode::Restart,
        cli_flag: "--drain3",
        cli_flag_off: Some("--no-drain3"),
        choices: &[],
        default_bool: true,
        default_text: "",
    },
    FeatureDef {
        key: "difftastic",
        group: "Engines",
        label: "Difftastic diffs",
        kind: FeatureKind::Bool,
        apply: ApplyMode::Restart,
        cli_flag: "--difftastic",
        cli_flag_off: None,
        choices: &[],
        default_bool: false,
        default_text: "",
    },
    FeatureDef {
        key: "code_aware",
        group: "Engines",
        label: "Code-aware AST",
        kind: FeatureKind::Bool,
        apply: ApplyMode::Restart,
        cli_flag: "--code-aware",
        cli_flag_off: Some("--no-code-aware"),
        choices: &[],
        default_bool: false,
        default_text: "",
    },
    FeatureDef {
        key: "reversible_code",
        group: "Engines",
        label: "Reversible code compression",
        kind: FeatureKind::Bool,
        apply: ApplyMode::Restart,
        cli_flag: "--enable-reversible-code",
        cli_flag_off: Some("--no-reversible-code"),
        choices: &[],
        default_bool: true,
        default_text: "",
    },
    FeatureDef {
        key: "code_graph",
        group: "Engines",
        label: "Code graph",
        kind: FeatureKind::Bool,
        apply: ApplyMode::Restart,
        cli_flag: "--code-graph",
        cli_flag_off: None,
        choices: &[],
        default_bool: false,
        default_text: "",
    },
    FeatureDef {
        key: "context_budget",
        group: "Intelligence",
        label: "Context budget",
        kind: FeatureKind::Bool,
        apply: ApplyMode::Restart,
        cli_flag: "--enable-context-budget",
        cli_flag_off: None,
        choices: &[],
        default_bool: false,
        default_text: "",
    },
    FeatureDef {
        key: "task_aware",
        group: "Intelligence",
        label: "Task-aware compression",
        kind: FeatureKind::Bool,
        apply: ApplyMode::Restart,
        cli_flag: "--enable-task-aware",
        cli_flag_off: None,
        choices: &[],
        default_bool: false,
        default_text: "",
    },
    FeatureDef {
        key: "semantic_dedup",
        group: "Intelligence",
        label: "Semantic dedup",
        kind: FeatureKind::Bool,
        apply: ApplyMode::Restart,
        cli_flag: "--enable-semantic-dedup",
        cli_flag_off: Some("--no-semantic-dedup"),
        choices: &[],
        default_bool: false,
        default_text: "",
    },
    FeatureDef {
        key: "firewall",
        group: "Security",
        label: "LLM Firewall",
        kind: FeatureKind::Bool,
        apply: ApplyMode::Restart,
        cli_flag: "--enable-firewall",
        cli_flag_off: None,
        choices: &[],
        default_bool: false,
        default_text: "",
    },
    FeatureDef {
        key: "subscription_tracking",
        group: "Security",
        label: "Subscription tracking",
        kind: FeatureKind::Bool,
        apply: ApplyMode::Restart,
        cli_flag: "",
        cli_flag_off: Some("--no-subscription-tracking"),
        choices: &[],
        default_bool: true,
        default_text: "",
    },
    FeatureDef {
        key: "model_routing_preset",
        group: "Routing",
        label: "Model routing preset",
        kind: FeatureKind::Text,
        apply: ApplyMode::Restart,
        cli_flag: "--model-routing-preset",
        cli_flag_off: None,
        choices: &[],
        default_bool: false,
        default_text: "codex-gpt54mini-high",
    },
];

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn catalog_includes_core_product_keys() {
        let keys: Vec<&str> = catalog().iter().map(|f| f.key).collect();
        for required in [
            "optimize",
            "memory",
            "kompress",
            "memoize",
            "firewall",
            "model_routing_preset",
            "difftastic",
            "context_budget",
        ] {
            assert!(keys.contains(&required), "missing key {required}");
        }
    }

    #[test]
    fn most_features_require_restart_today() {
        let restart = catalog()
            .iter()
            .filter(|f| f.apply == ApplyMode::Restart)
            .count();
        assert!(restart >= 15, "expected curated restart-heavy catalog");
    }

    #[test]
    fn groups_are_ordered_product_sections() {
        let groups = group_keys();
        assert_eq!(
            groups,
            vec![
                "Optimization",
                "CCR",
                "Memory",
                "Engines",
                "Intelligence",
                "Security",
                "Routing",
            ]
        );
    }

    #[test]
    fn get_returns_known_feature() {
        let f = get("memory").expect("memory");
        assert_eq!(f.cli_flag, "--memory");
        assert_eq!(f.apply, ApplyMode::Restart);
    }
}
