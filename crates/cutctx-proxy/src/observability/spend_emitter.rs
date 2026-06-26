use reqwest::Client;
use serde::{Deserialize, Serialize};
use tokio::sync::mpsc;
use tracing::{debug, error, warn};

/// Spend event schema corresponding to the Phase 2 specification.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpendEvent {
    pub ts: u64,
    pub org_id: Option<String>,
    pub workspace_id: Option<String>,
    pub project_id: Option<String>,
    pub agent_id: Option<String>,
    pub model: Option<String>,
    pub provider: Option<String>,
    pub auth_mode: String,
    pub input_tokens: u64,
    pub output_tokens: u64,
    pub tokens_saved: u64,
    pub est_cost_usd: Option<f64>,
    pub est_cost_saved_usd: Option<f64>,
    pub request_id: String,
}

/// A non-blocking, batched emitter for spend events.
pub struct SpendEmitter {
    tx: mpsc::Sender<SpendEvent>,
}

impl SpendEmitter {
    /// Creates a new spend emitter that batches and posts to `ledger_url`.
    /// The background task will drop events and log a warning if the queue overflows.
    pub fn new(ledger_url: url::Url) -> Self {
        // Bounded channel to prevent memory exhaustion
        let (tx, mut rx) = mpsc::channel::<SpendEvent>(10_000);
        let client = Client::builder()
            .timeout(std::time::Duration::from_secs(5))
            .build()
            .unwrap_or_else(|_| Client::new());

        tokio::spawn(async move {
            let mut batch = Vec::with_capacity(100);
            let mut interval = tokio::time::interval(std::time::Duration::from_millis(500));

            loop {
                tokio::select! {
                    _ = interval.tick() => {
                        if !batch.is_empty() {
                            Self::flush_batch(&client, &ledger_url, &mut batch).await;
                        }
                    }
                    maybe_event = rx.recv() => {
                        match maybe_event {
                            Some(event) => {
                                batch.push(event);
                                if batch.len() >= 100 {
                                    Self::flush_batch(&client, &ledger_url, &mut batch).await;
                                }
                            }
                            None => {
                                // Channel closed, flush remaining and exit
                                if !batch.is_empty() {
                                    Self::flush_batch(&client, &ledger_url, &mut batch).await;
                                }
                                break;
                            }
                        }
                    }
                }
            }
        });

        Self { tx }
    }

    async fn flush_batch(client: &Client, url: &url::Url, batch: &mut Vec<SpendEvent>) {
        debug!(
            event = "spend_emitter_flush",
            count = batch.len(),
            "Flushing spend events"
        );
        // POST /v1/spend/events is expected to accept a JSON array
        match client.post(url.clone()).json(&batch).send().await {
            Ok(res) if res.status().is_success() => {
                debug!(
                    event = "spend_emitter_success",
                    count = batch.len(),
                    "Successfully emitted spend events"
                );
            }
            Ok(res) => {
                error!(
                    event = "spend_emitter_failure",
                    status = %res.status(),
                    "Failed to emit spend events: non-success status"
                );
            }
            Err(e) => {
                error!(
                    event = "spend_emitter_error",
                    error = %e,
                    "Error emitting spend events"
                );
            }
        }
        batch.clear();
    }

    /// Emits a single spend event. Fails fast with a warning if the queue is full.
    pub fn emit(&self, event: SpendEvent) {
        if let Err(e) = self.tx.try_send(event) {
            warn!(
                event = "spend_emitter_overflow",
                error = %e,
                "Spend event dropped: queue full or closed"
            );
        }
    }
}
