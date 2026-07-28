//! Copy text to the system clipboard without relying on the webview Clipboard API.

use std::io::Write;
use std::process::{Command, Stdio};

pub fn copy_text(text: &str) -> Result<(), String> {
    #[cfg(target_os = "macos")]
    {
        pipe_to_command("pbcopy", &[], text)
    }
    #[cfg(target_os = "windows")]
    {
        pipe_to_command("clip", &[], text)
    }
    #[cfg(all(unix, not(target_os = "macos")))]
    {
        if pipe_to_command("wl-copy", &[], text).is_ok() {
            return Ok(());
        }
        pipe_to_command("xclip", &["-selection", "clipboard"], text)
    }
    #[cfg(not(any(target_os = "macos", target_os = "windows", unix)))]
    {
        let _ = text;
        Err("clipboard copy is not supported on this platform".into())
    }
}

fn pipe_to_command(bin: &str, args: &[&str], text: &str) -> Result<(), String> {
    let mut child = Command::new(bin)
        .args(args)
        .stdin(Stdio::piped())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|e| format!("failed to run {bin}: {e}"))?;
    {
        let stdin = child
            .stdin
            .as_mut()
            .ok_or_else(|| format!("{bin} stdin unavailable"))?;
        stdin
            .write_all(text.as_bytes())
            .map_err(|e| format!("failed writing to {bin}: {e}"))?;
    }
    let status = child
        .wait()
        .map_err(|e| format!("{bin} wait failed: {e}"))?;
    if status.success() {
        Ok(())
    } else {
        Err(format!("{bin} exited with {status}"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn copy_text_roundtrip_smoke() {
        // Best-effort: platforms without a clipboard tool should still compile.
        let _ = copy_text("cutctx-control-clipboard-smoke");
    }
}
