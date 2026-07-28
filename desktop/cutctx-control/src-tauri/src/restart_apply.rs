//! Build `cutctx proxy` argv from a profile of feature values — restart applies these.

use crate::argv::{build_proxy_argv, FeatureValue, ProxyProfile};

/// Snapshot whether a restart would change the process command line.
pub fn restart_would_change_argv(before: &ProxyProfile, after: &ProxyProfile) -> bool {
    build_proxy_argv(before) != build_proxy_argv(after)
}

/// Apply a bool feature flip and return the argv that a restart must use.
pub fn argv_after_bool_toggle(mut profile: ProxyProfile, key: &str, enabled: bool) -> Vec<String> {
    profile
        .features
        .insert(key.into(), FeatureValue::bool(enabled));
    build_proxy_argv(&profile)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn enabling_memory_changes_argv_for_restart() {
        let before = ProxyProfile::default_profile();
        let after_argv = argv_after_bool_toggle(before.clone(), "memory", true);
        assert!(
            after_argv.iter().any(|a| a == "--memory"),
            "restart argv must include --memory after toggle"
        );
        assert!(restart_would_change_argv(
            &before,
            &{
                let mut p = before.clone();
                p.features
                    .insert("memory".into(), FeatureValue::bool(true));
                p
            }
        ));
    }

    #[test]
    fn disabling_optimize_adds_no_optimize_on_restart_argv() {
        let before = ProxyProfile::default_profile();
        let argv = argv_after_bool_toggle(before, "optimize", false);
        assert!(argv.iter().any(|a| a == "--no-optimize"));
    }

    #[test]
    fn identical_profiles_do_not_claim_restart_change() {
        let p = ProxyProfile::default_profile();
        assert!(!restart_would_change_argv(&p, &p));
    }
}
