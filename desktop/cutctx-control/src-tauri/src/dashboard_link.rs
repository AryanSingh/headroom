//! Dashboard deep-link helpers for CutCtx Control.

pub fn dashboard_url_for_port(port: u16) -> String {
    format!("http://127.0.0.1:{port}/dashboard")
}

/// The token is opaque and single-use; this URL never contains a credential.
pub fn dashboard_connect_url_for_port(port: u16, token: &str) -> String {
    format!("http://127.0.0.1:{port}/dashboard/connect?token={token}")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_route_is_dashboard() {
        let url = dashboard_url_for_port(8787);
        assert_eq!(url, "http://127.0.0.1:8787/dashboard");
        assert!(url.ends_with("/dashboard"));
        assert!(!url.ends_with("8787/"));
    }

    #[test]
    fn connect_route_carries_only_an_opaque_bootstrap_token() {
        let url = dashboard_connect_url_for_port(8787, "opaque-token");

        assert_eq!(
            url,
            "http://127.0.0.1:8787/dashboard/connect?token=opaque-token"
        );
        assert!(!url.contains("cutctx_"));
    }
}
