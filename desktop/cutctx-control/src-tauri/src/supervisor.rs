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
