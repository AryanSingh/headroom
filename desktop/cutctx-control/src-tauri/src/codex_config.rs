//! Codex `config.toml` inject helpers for CutCtx routing + seat token.
//!
//! Codex reserves built-in provider IDs (`openai`, `ollama`, `lmstudio`).
//! Writing `[model_providers.openai]` makes Codex refuse to load config.
//! Match `cutctx wrap codex`: route via top-level `openai_base_url` only.

use std::path::{Path, PathBuf};

const TOP_MARKER: &str = "# --- Cutctx proxy (auto-injected by cutctx wrap codex) ---";
const END_MARKER: &str = "# --- end Cutctx ---";

/// Legacy Control blocks that illegally overrode `[model_providers.openai]`.
const LEGACY_HEADER_BEGIN: &str = "# --- Cutctx Control: openai provider headers ---";
const LEGACY_HEADER_ENDS: &[&str] = &[
    "# --- end Cutctx Control headers ---",
    "# --- end Cutctx Control: openai provider headers ---",
];

/// Build the top-level CutCtx base URL block.
pub fn base_url_block(port: u16) -> String {
    format!(
        "{TOP_MARKER}\nopenai_base_url = \"http://127.0.0.1:{port}/v1\"\nbase_url = \"http://127.0.0.1:{port}/v1\"\nsupports_websockets = true\n{END_MARKER}\n"
    )
}

/// Strip previously injected CutCtx top-level marker blocks.
pub fn strip_base_url_block(content: &str) -> String {
    strip_marker_span(content, TOP_MARKER, END_MARKER)
}

fn strip_marker_span(content: &str, begin: &str, end: &str) -> String {
    let mut out = String::new();
    let mut skipping = false;
    for line in content.lines() {
        let trimmed = line.trim();
        if trimmed == begin {
            skipping = true;
            continue;
        }
        if skipping {
            if trimmed == end {
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

/// Remove legacy `[model_providers.openai]` seat-header blocks (and any bare
/// leftover openai provider table) so Codex can load the file again.
///
/// Lines that are clearly unrelated user config (currently `notify = …`) are
/// preserved even if they were nested inside a broken marker span.
pub fn strip_openai_provider_override(content: &str) -> String {
    let salvaged: Vec<String> = content
        .lines()
        .filter(|line| line.trim_start().starts_with("notify ="))
        .map(str::to_string)
        .collect();
    let text = strip_legacy_header_block(content);
    let mut cleaned = strip_model_providers_openai_table(&text);
    for line in salvaged {
        if !cleaned.lines().any(|l| l.trim() == line.trim()) {
            if let Some(idx) = cleaned.find(END_MARKER) {
                let insert_at = idx + END_MARKER.len();
                cleaned = format!(
                    "{}\n{}\n{}",
                    &cleaned[..insert_at],
                    line,
                    &cleaned[insert_at..].trim_start()
                );
            } else {
                cleaned = format!("{line}\n{cleaned}");
            }
        }
    }
    cleaned
}

fn strip_legacy_header_block(content: &str) -> String {
    // Only strip when we see a matching end marker; otherwise a missing end
    // would swallow the rest of the file.
    let end_set: Vec<&str> = LEGACY_HEADER_ENDS.to_vec();
    let mut out = String::new();
    let mut skipping = false;
    for line in content.lines() {
        let trimmed = line.trim();
        if !skipping && trimmed == LEGACY_HEADER_BEGIN {
            skipping = true;
            continue;
        }
        if skipping {
            if end_set.contains(&trimmed) {
                skipping = false;
            }
            continue;
        }
        out.push_str(line);
        out.push('\n');
    }
    // If the begin marker was present but no end marker, do not drop the file:
    // fall back to the original content and rely on the bare-table strip.
    if skipping {
        return content.to_string();
    }
    out
}

fn strip_model_providers_openai_table(content: &str) -> String {
    let mut out = String::new();
    let mut skipping = false;
    for line in content.lines() {
        let trimmed = line.trim();
        if trimmed == "[model_providers.openai]" {
            skipping = true;
            continue;
        }
        if skipping {
            if trimmed.starts_with('[') && !trimmed.starts_with("[[") {
                skipping = false;
                // fall through to keep this new section header
            } else if trimmed.is_empty() || trimmed.starts_with('#') {
                continue;
            } else if trimmed.starts_with("http_headers") {
                // This is the only setting written by the legacy Control block.
                continue;
            } else {
                // Unknown content may belong to the user. Preserve it as
                // top-level TOML instead of deleting data we do not own.
                skipping = false;
            }
        }
        out.push_str(line);
        out.push('\n');
    }
    out
}

/// Prepare Codex config for CutCtx: ensure proxy base URL, never override
/// the reserved `openai` provider. Seat tokens cannot be attached via
/// `http_headers` on the built-in provider — mint/save them separately for
/// Claude / wrap launches.
pub fn inject_seat_token_header(content: &str, _token: &str) -> String {
    // Token intentionally unused: Codex forbids `[model_providers.openai]`.
    strip_openai_provider_override(content)
}

/// Apply the full Fix-seat-token write: strip illegal overrides + route via
/// `openai_base_url`.
pub fn apply_codex_cutctx_fix(content: &str, port: u16, token: &str) -> String {
    let cleaned = inject_seat_token_header(content, token);
    inject_base_url(&cleaned, port)
}

fn backup_path(path: &Path) -> PathBuf {
    match path.extension().and_then(|value| value.to_str()) {
        Some(extension) => path.with_extension(format!("{extension}.cutctx-backup")),
        None => path.with_extension("cutctx-backup"),
    }
}

/// Write a repaired Codex config while retaining the first pre-fix version.
pub fn write_config_with_backup(path: &Path, content: &str) -> std::io::Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let backup = backup_path(path);
    if path.exists() && !backup.exists() {
        std::fs::copy(path, backup)?;
    }
    std::fs::write(path, content)
}

#[cfg(test)]
pub fn remove_cutctx_routing(content: &str) -> String {
    strip_openai_provider_override(&strip_base_url_block(content))
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
    fn seat_fix_does_not_override_builtin_openai_provider() {
        let out = apply_codex_cutctx_fix("model = \"x\"\n", 8787, "ctu1.abc.def");
        assert!(out.contains("openai_base_url"));
        assert!(!out.contains("[model_providers.openai]"));
        assert!(!out.contains("model_provider ="));
        // Token must not be written into config (reserved-provider trap).
        assert!(!out.contains("ctu1.abc.def"));
    }

    #[test]
    fn strips_legacy_openai_provider_header_block() {
        let broken = format!(
            "{LEGACY_HEADER_BEGIN}\nnotify = [\"app\"]\n\n[model_providers.openai]\nhttp_headers = {{ \"X-Cutctx-User-Token\" = \"ctu1.old.sig\" }}\n{}\nmodel = \"x\"\n",
            LEGACY_HEADER_ENDS[1]
        );
        let fixed = apply_codex_cutctx_fix(&broken, 8787, "ctu1.new.sig");
        assert!(!fixed.contains("[model_providers.openai]"));
        assert!(!fixed.contains("ctu1.old.sig"));
        assert!(fixed.contains("notify = [\"app\"]"));
        assert!(fixed.contains("openai_base_url"));
        assert!(fixed.contains("model = \"x\""));
    }

    #[test]
    fn re_inject_is_idempotent_without_provider_table() {
        let first = apply_codex_cutctx_fix("", 8787, "ctu1.old.sig");
        let second = apply_codex_cutctx_fix(&first, 8799, "ctu1.new.sig");
        assert_eq!(second.matches("openai_base_url").count(), 1);
        assert!(second.contains("127.0.0.1:8799/v1"));
        assert!(!second.contains("[model_providers"));
    }

    #[test]
    fn remove_routing_strips_base_url_and_legacy_headers() {
        let mut c = apply_codex_cutctx_fix("model = \"x\"\n", 8787, "ctu1.t.s");
        c = format!(
            "{c}{LEGACY_HEADER_BEGIN}\n[model_providers.openai]\nhttp_headers = {{ \"X-Cutctx-User-Token\" = \"ctu1.t.s\" }}\n{}\n",
            LEGACY_HEADER_ENDS[0]
        );
        let cleaned = remove_cutctx_routing(&c);
        assert!(!cleaned.contains("openai_base_url"));
        assert!(!cleaned.contains("X-Cutctx-User-Token"));
        assert!(!cleaned.contains("[model_providers.openai]"));
        assert!(cleaned.contains("model = \"x\""));
    }

    #[test]
    fn strip_bare_openai_provider_table_without_markers() {
        let raw = "model = \"x\"\n\n[model_providers.openai]\nhttp_headers = { \"X\" = \"y\" }\n\n[features]\nok = true\n";
        let cleaned = strip_openai_provider_override(raw);
        assert!(!cleaned.contains("model_providers.openai"));
        assert!(cleaned.contains("[features]"));
        assert!(cleaned.contains("model = \"x\""));
    }

    #[test]
    fn strip_bare_openai_provider_preserves_unrecognized_user_keys() {
        let raw = "model = \"x\"\n\n[model_providers.openai]\nhttp_headers = { \"X-Cutctx-User-Token\" = \"old\" }\ncustom_user_setting = \"keep-me\"\n\n[features]\nok = true\n";
        let cleaned = strip_openai_provider_override(raw);
        assert!(!cleaned.contains("model_providers.openai"));
        assert!(!cleaned.contains("X-Cutctx-User-Token"));
        assert!(cleaned.contains("custom_user_setting = \"keep-me\""));
        assert!(cleaned.contains("[features]"));
    }

    #[test]
    fn config_write_keeps_the_first_recoverable_backup() {
        let temp = tempfile::tempdir().unwrap();
        let path = temp.path().join("config.toml");
        std::fs::write(&path, "model = \"original\"\n").unwrap();

        write_config_with_backup(&path, "model = \"first-fix\"\n").unwrap();
        write_config_with_backup(&path, "model = \"second-fix\"\n").unwrap();

        assert_eq!(
            std::fs::read_to_string(&path).unwrap(),
            "model = \"second-fix\"\n"
        );
        assert_eq!(
            std::fs::read_to_string(path.with_extension("toml.cutctx-backup")).unwrap(),
            "model = \"original\"\n"
        );
    }
}
