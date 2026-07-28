//! Supervised `cutctx proxy` process lifecycle.

use crate::argv::{build_proxy_argv, ProxyProfile};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

pub struct ProxySupervisor {
    pub cutctx_bin: PathBuf,
    child: Mutex<Option<Child>>,
}

impl ProxySupervisor {
    pub fn new(cutctx_bin: impl Into<PathBuf>) -> Self {
        Self {
            cutctx_bin: cutctx_bin.into(),
            child: Mutex::new(None),
        }
    }

    pub fn is_running(&self) -> bool {
        let mut guard = self.child.lock().expect("supervisor lock");
        match guard.as_mut() {
            None => false,
            Some(child) => match child.try_wait() {
                Ok(None) => true,
                Ok(Some(_)) => {
                    *guard = None;
                    false
                }
                Err(_) => false,
            },
        }
    }

    pub fn spawn_plan(profile: &ProxyProfile) -> Vec<String> {
        build_proxy_argv(profile)
    }

    pub fn start(
        &self,
        profile: &ProxyProfile,
        env_vars: &[(String, String)],
    ) -> Result<(), String> {
        if self.is_running() {
            return Err("proxy already supervised".into());
        }
        let args = Self::spawn_plan(profile);
        let mut cmd = Command::new(&self.cutctx_bin);
        cmd.args(&args)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::piped());
        for (key, value) in env_vars {
            cmd.env(key, value);
        }
        let child = cmd
            .spawn()
            .map_err(|e| format!("failed to spawn {}: {e}", self.cutctx_bin.display()))?;
        let mut guard = self.child.lock().expect("supervisor lock");
        *guard = Some(child);
        Ok(())
    }

    pub fn stop(&self) -> Result<(), String> {
        let mut guard = self.child.lock().expect("supervisor lock");
        if let Some(mut child) = guard.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
        Ok(())
    }

    /// Stop the supervised child and best-effort free `port` so a restart can
    /// respawn with a new argv (including when we previously attached external).
    pub fn stop_and_reclaim_port(&self, port: u16) -> Result<(), String> {
        self.stop()?;
        reclaim_listeners_on_port(port);
        // Brief settle so the OS releases the bind.
        std::thread::sleep(std::time::Duration::from_millis(300));
        Ok(())
    }
}

/// Best-effort: terminate processes listening on `port` (Unix `lsof`).
fn reclaim_listeners_on_port(port: u16) {
    #[cfg(unix)]
    {
        use std::process::Command;
        let output = Command::new("lsof")
            .args(["-nP", &format!("-iTCP:{port}"), "-sTCP:LISTEN", "-t"])
            .output();
        let Ok(output) = output else {
            return;
        };
        if !output.status.success() {
            return;
        }
        let stdout = String::from_utf8_lossy(&output.stdout);
        for pid in stdout.split_whitespace() {
            let Ok(pid) = pid.parse::<i32>() else {
                continue;
            };
            let _ = Command::new("kill").args(["-TERM", &pid.to_string()]).status();
        }
        std::thread::sleep(std::time::Duration::from_millis(200));
        // Force stubborn listeners.
        let output = Command::new("lsof")
            .args(["-nP", &format!("-iTCP:{port}"), "-sTCP:LISTEN", "-t"])
            .output();
        if let Ok(output) = output {
            let stdout = String::from_utf8_lossy(&output.stdout);
            for pid in stdout.split_whitespace() {
                let _ = Command::new("kill").args(["-KILL", pid]).status();
            }
        }
    }
    #[cfg(not(unix))]
    {
        let _ = port;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::argv::ProxyProfile;

    #[test]
    fn spawn_plan_starts_with_proxy_subcommand() {
        let plan = ProxySupervisor::spawn_plan(&ProxyProfile::default_profile());
        assert_eq!(plan.first().map(String::as_str), Some("proxy"));
    }

    #[test]
    fn fresh_supervisor_is_not_running() {
        let s = ProxySupervisor::new("cutctx");
        assert!(!s.is_running());
    }
}
