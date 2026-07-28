//! Build `cutctx proxy` argv from a profile of feature values.

use crate::catalog::{self, FeatureKind};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FeatureValue {
    pub enabled: bool,
    pub text: String,
}

impl FeatureValue {
    pub fn bool(enabled: bool) -> Self {
        Self {
            enabled,
            text: String::new(),
        }
    }

    pub fn text(text: impl Into<String>) -> Self {
        Self {
            enabled: true,
            text: text.into(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ProxyProfile {
    pub name: String,
    pub host: String,
    pub port: u16,
    pub features: BTreeMap<String, FeatureValue>,
}

impl ProxyProfile {
    pub fn default_profile() -> Self {
        let mut features = BTreeMap::new();
        for f in catalog::catalog() {
            features.insert(
                f.key.to_string(),
                FeatureValue {
                    enabled: f.default_bool,
                    text: f.default_text.to_string(),
                },
            );
        }
        Self {
            name: "default".into(),
            host: "127.0.0.1".into(),
            port: 8787,
            features,
        }
    }

    /// Profile with optional engines/intelligence/security enabled for release verification.
    pub fn all_optional_on() -> Self {
        let mut p = Self::default_profile();
        p.name = "release-verify-all-on".into();
        for key in [
            "memory",
            "learn",
            "kompress",
            "memoize",
            "difftastic",
            "code_aware",
            "code_graph",
            "context_budget",
            "task_aware",
            "semantic_dedup",
            "firewall",
        ] {
            if let Some(v) = p.features.get_mut(key) {
                v.enabled = true;
            }
        }
        p
    }
}

/// Build argv after the binary name, e.g. `["proxy", "--port", "8787", ...]`.
pub fn build_proxy_argv(profile: &ProxyProfile) -> Vec<String> {
    let mut args = vec![
        "proxy".into(),
        "--host".into(),
        profile.host.clone(),
        "--port".into(),
        profile.port.to_string(),
    ];

    for def in catalog::catalog() {
        let Some(value) = profile.features.get(def.key) else {
            continue;
        };
        match def.kind {
            FeatureKind::Bool => {
                if value.enabled {
                    if !def.cli_flag.is_empty() {
                        args.push(def.cli_flag.into());
                    }
                } else if let Some(off) = def.cli_flag_off {
                    args.push(off.into());
                }
            }
            FeatureKind::Choice | FeatureKind::Text => {
                let text = if value.text.is_empty() {
                    def.default_text
                } else {
                    value.text.as_str()
                };
                if text.is_empty() {
                    continue;
                }
                // Skip emitting default mode=token to keep argv small? Spec wants preset always.
                if def.key == "mode" && text == "token" {
                    // Still emit for explicitness in supervised runs.
                }
                if !def.cli_flag.is_empty() {
                    args.push(def.cli_flag.into());
                    args.push(text.into());
                }
            }
        }
    }

    args
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_profile_includes_port_and_host() {
        let argv = build_proxy_argv(&ProxyProfile::default_profile());
        assert_eq!(argv[0], "proxy");
        assert!(argv.windows(2).any(|w| w == ["--port", "8787"]));
        assert!(argv.windows(2).any(|w| w == ["--host", "127.0.0.1"]));
    }

    #[test]
    fn optimize_off_adds_no_optimize() {
        let mut p = ProxyProfile::default_profile();
        p.features
            .insert("optimize".into(), FeatureValue::bool(false));
        let argv = build_proxy_argv(&p);
        assert!(argv.iter().any(|a| a == "--no-optimize"));
    }

    #[test]
    fn memory_on_adds_memory_flag() {
        let mut p = ProxyProfile::default_profile();
        p.features
            .insert("memory".into(), FeatureValue::bool(true));
        let argv = build_proxy_argv(&p);
        assert!(argv.iter().any(|a| a == "--memory"));
    }

    #[test]
    fn routing_preset_emits_flag_and_value() {
        let mut p = ProxyProfile::default_profile();
        p.features.insert(
            "model_routing_preset".into(),
            FeatureValue::text("codex-gpt54mini-high"),
        );
        let argv = build_proxy_argv(&p);
        assert!(argv
            .windows(2)
            .any(|w| w == ["--model-routing-preset", "codex-gpt54mini-high"]));
    }

    #[test]
    fn all_optional_on_enables_release_flags() {
        let argv = build_proxy_argv(&ProxyProfile::all_optional_on());
        for flag in ["--memory", "--memoize", "--difftastic", "--enable-firewall"] {
            assert!(argv.iter().any(|a| a == flag), "missing {flag}");
        }
    }
}
