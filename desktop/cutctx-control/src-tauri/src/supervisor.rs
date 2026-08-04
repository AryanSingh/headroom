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

    /// Build the product-managed service command without exposing any secret.
    /// The full proxy profile is passed as repeated values so LaunchAgent
    /// startup uses the same feature configuration as an interactive start.
    pub fn product_runtime_plan(profile: &ProxyProfile, replace_existing: bool) -> Vec<String> {
        let mut plan = vec![
            "install".into(),
            "ensure-product-runtime".into(),
            "--port".into(),
            profile.port.to_string(),
            "--apply".into(),
        ];
        for arg in Self::spawn_plan(profile).into_iter().skip(1) {
            plan.push(format!("--proxy-arg={arg}"));
        }
        if replace_existing {
            plan.push("--replace-existing".into());
        }
        plan
    }

    pub fn ensure_product_runtime(
        &self,
        profile: &ProxyProfile,
        replace_existing: bool,
    ) -> Result<(), String> {
        let plan = Self::product_runtime_plan(profile, replace_existing);
        let status = Command::new(&self.cutctx_bin)
            .args(&plan)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .map_err(|e| format!("failed to ensure managed proxy runtime: {e}"))?;
        if status.success() {
            Ok(())
        } else {
            Err(format!("managed proxy runtime exited with {status}"))
        }
    }

    pub fn product_runtime_stop_plan() -> [&'static str; 4] {
        ["install", "stop", "--profile", "product"]
    }

    pub fn stop_product_runtime(&self) -> Result<(), String> {
        let status = Command::new(&self.cutctx_bin)
            .args(Self::product_runtime_stop_plan())
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .map_err(|e| format!("failed to stop managed proxy runtime: {e}"))?;
        if status.success() {
            Ok(())
        } else {
            Err("no stoppable product runtime is installed".into())
        }
    }

    #[cfg(test)]
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
        // Never pipe stdout/stderr without a drain — the startup banner can fill
        // the pipe buffer and stall the child before it binds the port.
        cmd.args(&args)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());
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
    fn product_runtime_plan_preserves_the_profile_and_enables_managed_startup() {
        let mut profile = ProxyProfile::default_profile();
        profile.port = 9123;
        profile
            .features
            .insert("memory".into(), crate::argv::FeatureValue::bool(true));

        let plan = ProxySupervisor::product_runtime_plan(&profile, false);

        assert_eq!(
            plan[..4],
            ["install", "ensure-product-runtime", "--port", "9123"]
        );
        assert!(plan.iter().any(|arg| arg == "--apply"));
        assert!(plan.iter().any(|arg| arg == "--proxy-arg=--memory"));
        assert!(plan
            .iter()
            .any(|arg| arg == "--proxy-arg=--enable-reversible-code"));
        assert!(!plan.iter().any(|arg| arg == "--replace-existing"));
        assert!(!plan.iter().any(|arg| {
            let normalized = arg.to_ascii_lowercase();
            normalized.contains("license")
                || normalized.contains("cutctx_test_secret")
                || normalized.contains("cutctx_7409")
        }));
    }

    #[test]
    fn explicit_restart_allows_replacing_a_different_managed_profile() {
        let profile = ProxyProfile::default_profile();

        let plan = ProxySupervisor::product_runtime_plan(&profile, true);

        assert!(plan.iter().any(|arg| arg == "--replace-existing"));
    }

    #[test]
    fn stop_plan_targets_only_the_named_product_runtime() {
        assert_eq!(
            ProxySupervisor::product_runtime_stop_plan(),
            ["install", "stop", "--profile", "product"]
        );
    }

    #[test]
    fn fresh_supervisor_is_not_running() {
        let s = ProxySupervisor::new("cutctx");
        assert!(!s.is_running());
    }

    #[test]
    fn supervised_restart_becomes_healthy() {
        // This exercises a real installed proxy plus a local license and is
        // intentionally opt-in.  It cannot be deterministic in the normal
        // unit suite (the local runtime may be upgrading or another process
        // may briefly own the test port).  Release CI enables it explicitly.
        if std::env::var("CUTCTX_LIVE_SUPERVISOR_TEST").as_deref() != Ok("1") {
            eprintln!("skip: set CUTCTX_LIVE_SUPERVISOR_TEST=1 for live supervisor smoke");
            return;
        }
        let bin = std::env::var("CUTCTX_BIN").unwrap_or_else(|_| "cutctx".into());
        let license = std::env::var("CUTCTX_LIVE_LICENSE_KEY").ok().or_else(|| {
            use crate::credentials::{PlatformSecretStore, SecretStore, CUTCTX_LICENSE_KEY};

            PlatformSecretStore.get(CUTCTX_LICENSE_KEY).ok().flatten()
        });
        let Some(license) = license else {
            eprintln!("skip: no live license in env or OS credential store");
            return;
        };
        let license = license.trim().to_string();
        if license.is_empty() {
            return;
        }
        let port: u16 = 8795;
        if std::net::TcpListener::bind(("127.0.0.1", port)).is_err() {
            eprintln!("skip: live supervisor test port {port} is already in use");
            return;
        }
        let s = ProxySupervisor::new(&bin);
        let mut profile = ProxyProfile::default_profile();
        profile.port = port;
        let env = vec![("CUTCTX_LICENSE_KEY".into(), license)];
        s.start(&profile, &env).expect("spawn");
        let mut healthy = false;
        for _ in 0..25 {
            std::thread::sleep(std::time::Duration::from_millis(400));
            let url = format!("http://127.0.0.1:{port}/health");
            if let Ok(resp) = ureq::get(&url)
                .timeout(std::time::Duration::from_secs(1))
                .call()
            {
                if (200..300).contains(&resp.status()) {
                    healthy = true;
                    break;
                }
            }
        }
        assert!(healthy, "proxy should become healthy after spawn");
        s.stop().unwrap();
        profile
            .features
            .insert("memory".into(), crate::argv::FeatureValue::bool(true));
        s.start(&profile, &env).expect("respawn");
        healthy = false;
        for _ in 0..25 {
            std::thread::sleep(std::time::Duration::from_millis(400));
            let url = format!("http://127.0.0.1:{port}/health");
            if let Ok(resp) = ureq::get(&url)
                .timeout(std::time::Duration::from_secs(1))
                .call()
            {
                if (200..300).contains(&resp.status()) {
                    healthy = true;
                    break;
                }
            }
        }
        let _ = s.stop();
        assert!(healthy, "proxy should become healthy after restart");
    }
}
