//! Dashboard deep-link helpers for CutCtx Control.

pub fn dashboard_url_for_port(port: u16) -> String {
    format!("http://127.0.0.1:{port}/dashboard")
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
}
