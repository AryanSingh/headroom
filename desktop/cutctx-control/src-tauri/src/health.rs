//! Proxy health / tray status state machine.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ProxyPhase {
    Stopped,
    Starting,
    Healthy,
    Degraded,
    RestartPending,
    Stopping,
    Error,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ProxyStatus {
    pub phase: ProxyPhase,
    pub port: u16,
    pub message: String,
    pub tokens_saved: u64,
    pub external: bool,
}

impl ProxyStatus {
    pub fn stopped(port: u16) -> Self {
        Self {
            phase: ProxyPhase::Stopped,
            port,
            message: "Proxy stopped".into(),
            tokens_saved: 0,
            external: false,
        }
    }

    pub fn tray_color(&self) -> &'static str {
        match self.phase {
            ProxyPhase::Healthy => "green",
            ProxyPhase::RestartPending | ProxyPhase::Degraded => "amber",
            ProxyPhase::Error | ProxyPhase::Stopped => "red",
            ProxyPhase::Starting | ProxyPhase::Stopping => "grey",
        }
    }
}

#[derive(Debug)]
pub struct HealthMachine {
    pub status: ProxyStatus,
}

impl HealthMachine {
    pub fn new(port: u16) -> Self {
        Self {
            status: ProxyStatus::stopped(port),
        }
    }

    pub fn on_start_requested(&mut self) {
        self.status.phase = ProxyPhase::Starting;
        self.status.message = "Starting proxy…".into();
        self.status.external = false;
    }

    pub fn on_health_ok(&mut self, tokens_saved: u64) {
        let pending = self.status.phase == ProxyPhase::RestartPending;
        if pending {
            // stay amber until restart completes
            self.status.tokens_saved = tokens_saved;
            return;
        }
        self.status.phase = ProxyPhase::Healthy;
        self.status.message = "Healthy".into();
        self.status.tokens_saved = tokens_saved;
    }

    pub fn on_health_fail(&mut self, message: impl Into<String>) {
        if matches!(
            self.status.phase,
            ProxyPhase::Starting | ProxyPhase::Stopping
        ) {
            return;
        }
        self.status.phase = ProxyPhase::Error;
        self.status.message = message.into();
    }

    pub fn on_toggle_needs_restart(&mut self) {
        if matches!(
            self.status.phase,
            ProxyPhase::Healthy | ProxyPhase::Degraded | ProxyPhase::RestartPending
        ) {
            self.status.phase = ProxyPhase::RestartPending;
            self.status.message = "Restart required to apply changes".into();
        }
    }

    pub fn on_stop_requested(&mut self) {
        self.status.phase = ProxyPhase::Stopping;
        self.status.message = "Stopping…".into();
    }

    pub fn on_stopped(&mut self) {
        self.status.phase = ProxyPhase::Stopped;
        self.status.message = "Proxy stopped".into();
        self.status.tokens_saved = 0;
        self.status.external = false;
    }

    pub fn on_external_detected(&mut self) {
        self.status.phase = ProxyPhase::Healthy;
        self.status.external = true;
        self.status.message = "Attached to external proxy".into();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn start_then_healthy_is_green() {
        let mut m = HealthMachine::new(8787);
        m.on_start_requested();
        assert_eq!(m.status.tray_color(), "grey");
        m.on_health_ok(42);
        assert_eq!(m.status.phase, ProxyPhase::Healthy);
        assert_eq!(m.status.tray_color(), "green");
        assert_eq!(m.status.tokens_saved, 42);
    }

    #[test]
    fn toggle_marks_restart_pending_amber() {
        let mut m = HealthMachine::new(8787);
        m.on_start_requested();
        m.on_health_ok(0);
        m.on_toggle_needs_restart();
        assert_eq!(m.status.phase, ProxyPhase::RestartPending);
        assert_eq!(m.status.tray_color(), "amber");
    }

    #[test]
    fn stop_cycle() {
        let mut m = HealthMachine::new(8787);
        m.on_start_requested();
        m.on_health_ok(1);
        m.on_stop_requested();
        assert_eq!(m.status.tray_color(), "grey");
        m.on_stopped();
        assert_eq!(m.status.phase, ProxyPhase::Stopped);
        assert_eq!(m.status.tray_color(), "red");
    }
}
