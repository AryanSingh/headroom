//! Codex `config.toml` inject helpers for CutCtx routing + seat token header.

const TOP_MARKER: &str = "# --- Cutctx proxy (auto-injected by cutctx wrap codex) ---";
const END_MARKER: &str = "# --- end Cutctx ---";
const CONTROL_HEADER_BEGIN: &str = "# --- Cutctx Control: openai provider headers ---";
const CONTROL_HEADER_END: &str = "# --- end Cutctx Control headers ---";

/// Build the top-level CutCtx base URL block.
pub fn base_url_block(port: u16) -> String {
    format!(
        "{TOP_MARKER}\nopenai_base_url = \"http://127.0.0.1:{port}/v1\"\nbase_url = \"http://127.0.0.1:{port}/v1\"\nsupports_websockets = true\n{END_MARKER}\n"
    )
}

/// Strip previously injected CutCtx top-level marker blocks.
pub fn strip_base_url_block(content: &str) -> String {
    let mut out = String::new();
    let mut skipping = false;
    for line in content.lines() {
        if line.trim() == TOP_MARKER {
            skipping = true;
            continue;
        }
        if skipping {
            if line.trim() == END_MARKER {
                skipping = false;
            }
            continue;
        }
        out.push_str(line);
        out.push('\n');
    }
    out
}

pub fn inject_base_url(content: &str, port: u16) -> String {
    let stripped = strip_base_url_block(content);
    let block = base_url_block(port);
    if stripped.trim().is_empty() {
        block
    } else {
        format!("{block}\n{}", stripped.trim_start())
    }
}

pub fn strip_openai_header_block(content: &str) -> String {
    let mut out = String::new();
    let mut skipping = false;
    for line in content.lines() {
        if line.trim() == CONTROL_HEADER_BEGIN {
            skipping = true;
            continue;
        }
        if skipping {
            if line.trim() == CONTROL_HEADER_END {
                skipping = false;
            }
            continue;
        }
        out.push_str(line);
        out.push('\n');
    }
    out
}

/// Inject `[model_providers.openai] http_headers` with the seat token.
/// Does not change `model_provider` — keeps native openai for session history.
pub fn inject_seat_token_header(content: &str, token: &str) -> String {
    let stripped = strip_openai_header_block(content);
    let block = format!(
        "{CONTROL_HEADER_BEGIN}\n[model_providers.openai]\nhttp_headers = {{ \"X-Cutctx-User-Token\" = \"{token}\" }}\n{CONTROL_HEADER_END}\n"
    );
    if stripped.trim().is_empty() {
        block
    } else {
        format!("{}\n{block}", stripped.trim_end())
    }
}

pub fn remove_cutctx_routing(content: &str) -> String {
    strip_openai_header_block(&strip_base_url_block(content))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn inject_base_url_is_idempotent() {
        let once = inject_base_url("", 8787);
        let twice = inject_base_url(&once, 8787);
        assert_eq!(once.matches("openai_base_url").count(), 1);
        assert_eq!(twice.matches("openai_base_url").count(), 1);
        assert!(twice.contains("127.0.0.1:8787/v1"));
    }

    #[test]
    fn inject_preserves_user_content() {
        let original = "model = \"gpt-5.6-terra\"\n\n[features]\nmulti_agent = true\n";
        let out = inject_base_url(original, 8787);
        assert!(out.contains("model = \"gpt-5.6-terra\""));
        assert!(out.contains("[features]"));
        assert!(out.starts_with(TOP_MARKER));
    }

    #[test]
    fn seat_token_header_on_openai_provider() {
        let out = inject_seat_token_header("model = \"x\"\n", "ctu1.abc.def");
        assert!(out.contains("[model_providers.openai]"));
        assert!(out.contains("X-Cutctx-User-Token"));
        assert!(out.contains("ctu1.abc.def"));
        assert!(!out.contains("model_provider ="));
    }

    #[test]
    fn re_inject_token_replaces_previous() {
        let first = inject_seat_token_header("", "ctu1.old.sig");
        let second = inject_seat_token_header(&first, "ctu1.new.sig");
        assert_eq!(second.matches("ctu1.old.sig").count(), 0);
        assert_eq!(second.matches("ctu1.new.sig").count(), 1);
    }

    #[test]
    fn remove_routing_strips_both_blocks() {
        let mut c = inject_base_url("model = \"x\"\n", 8787);
        c = inject_seat_token_header(&c, "ctu1.t.s");
        let cleaned = remove_cutctx_routing(&c);
        assert!(!cleaned.contains("openai_base_url"));
        assert!(!cleaned.contains("X-Cutctx-User-Token"));
        assert!(cleaned.contains("model = \"x\""));
    }
}
