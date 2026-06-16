//! headroom-proxy: transparent reverse proxy binary.
//!
//! Drops in front of the existing Python proxy. End-users hit the public
//! port; this binary forwards every HTTP/SSE/WebSocket request verbatim to
//! `--upstream`. See RUST_DEV.md for the operator runbook.

use std::net::SocketAddr;
use std::sync::Arc;

use clap::Parser;
use headroom_core::ccr::backends::CcrBackendConfig;
use headroom_proxy::config::{CcrBackendKind, CliArgs};
use headroom_proxy::{build_app, AppState, Config};
use tracing_subscriber::layer::SubscriberExt;
use tracing_subscriber::util::SubscriberInitExt;
use tracing_subscriber::EnvFilter;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let args = CliArgs::parse();
    let config = Config::from_cli(args);

    init_tracing(&config.log_level);

    tracing::info!(
        listen = %config.listen,
        upstream = %config.upstream,
        upstream_timeout_s = config.upstream_timeout.as_secs(),
        upstream_connect_timeout_s = config.upstream_connect_timeout.as_secs(),
        max_body_bytes = config.max_body_bytes,
        rewrite_host = config.rewrite_host,
        graceful_shutdown_timeout_s = config.graceful_shutdown_timeout.as_secs(),
        "headroom-proxy starting"
    );

    let mut state = AppState::new(config.clone())?;

    // Wire CCR store when configured. The live-zone dispatcher uses
    // this to stash original block content keyed by BLAKE3 hash so
    // downstream agents can retrieve it via `headroom_retrieve(hash)`.
    if let Some(ccr_store) = init_ccr_store(&config) {
        // Box<dyn CcrStore> → Arc<dyn CcrStore> via leak+Box::into_raw
        // (the store lives for process lifetime, so no leak concern).
        let store: Arc<dyn headroom_core::ccr::CcrStore> = Arc::from(ccr_store);
        state = state.with_ccr_store(store);
    }

    // PR-D1: resolve AWS credentials at startup via the `aws-config`
    // default chain. Loaded once so per-request signing is cheap.
    // Failure is NOT fatal — the proxy may run in front of a non-AWS
    // upstream — but the Bedrock invoke handler refuses to forward
    // unsigned requests when `bedrock_credentials` is `None`
    // (see `bedrock::invoke::handle_invoke`).
    if config.enable_bedrock_native {
        match load_bedrock_credentials(&config).await {
            Ok(creds) => {
                state = state.with_bedrock_credentials(creds);
                tracing::info!(
                    event = "bedrock_credentials_loaded",
                    region = %config.bedrock_region,
                    profile = ?config.aws_profile,
                    "AWS credentials resolved for Bedrock SigV4 signing"
                );
            }
            Err(e) => {
                tracing::warn!(
                    event = "bedrock_credentials_unavailable",
                    region = %config.bedrock_region,
                    profile = ?config.aws_profile,
                    error = %e,
                    "AWS credentials not available at startup; Bedrock invoke will 5xx until creds are configured"
                );
            }
        }
    }

    // SP-1: License enforcement hardening — fingerprint binding, CRL refresh,
    // heartbeat lease, clock rollback detection.
    if let Some(key) = config.license_key.as_deref() {
        let api_url = std::env::var("HEADROOM_LICENSE_API_URL")
            .unwrap_or_else(|_| "https://api.cutctx.dev".to_string());

        // Compute install fingerprint for machine binding
        let fingerprint = headroom_proxy::license::fingerprint::compute_fingerprint();
        let instance_id = uuid::Uuid::new_v4().to_string();

        // SP-1.4: Clock rollback detection at startup
        if let Some(clock_state) = headroom_proxy::license::fingerprint::load_clock_state() {
            let now = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs();
            if clock_state.detect_rollback(now) {
                tracing::warn!(
                    event = "clock_rollback_detected_startup",
                    "System clock rolled back >{}s since last run. \
                     Forcing re-activation.",
                    headroom_proxy::license::fingerprint::ClockState::MAX_BACKWARD_DRIFT_SECS
                );
            }
        }

        tracing::info!(
            event = "license_activation",
            fingerprint = %fingerprint.hash,
            "Activating license and fetching CRL from {}...",
            api_url
        );
        if let Err(e) =
            headroom_proxy::license::client::activate_and_fetch_crl(&api_url, key, &instance_id)
                .await
        {
            tracing::warn!(
                event = "license_activation_failed",
                error = %e,
                "Failed to activate license / fetch CRL"
            );
        }

        // SP-1.5: Start periodic CRL refresh (fail-closed after grace)
        headroom_proxy::license::client::start_crl_refresh_task(
            api_url.clone(),
            config.crl_refresh_interval_secs,
        );
        tracing::info!(
            event = "crl_refresh_started",
            interval_secs = config.crl_refresh_interval_secs,
            "CRL refresh task started"
        );

        // SP-1.3: Periodic heartbeat / seat lease with fingerprint
        let api_url_clone = api_url.clone();
        let key_clone = key.to_string();
        let fp_clone = fingerprint.hash.clone();
        let heartbeat_interval = config.heartbeat_interval_secs;
        let license_check_interval = config.license_check_interval_secs;
        tokio::spawn(async move {
            let mut heartbeat_interval =
                tokio::time::interval(std::time::Duration::from_secs(heartbeat_interval));
            let mut license_check_interval =
                tokio::time::interval(std::time::Duration::from_secs(license_check_interval));
            // Skip first immediate ticks
            heartbeat_interval.tick().await;
            license_check_interval.tick().await;

            loop {
                tokio::select! {
                    _ = heartbeat_interval.tick() => {
                        let user_id = format!("proxy-{}", &fp_clone[..12]);
                        if !headroom_proxy::license::client::checkout_seat(
                            &api_url_clone,
                            &key_clone,
                            &user_id,
                        )
                        .await
                        {
                            tracing::error!(
                                event = "seat_limit_exceeded",
                                "License seat limit exceeded! Running in degraded mode."
                            );
                        } else {
                            tracing::debug!(
                                event = "seat_lease_renewed",
                                "Successfully renewed seat lease"
                            );
                        }
                    }
                    _ = license_check_interval.tick() => {
                        // SP-1.3: Verify lease is still valid (clock rollback + expiration)
                        let tier = headroom_proxy::license::verify_license_token(&key_clone);
                        if tier == headroom_proxy::config::LicenseTier::OpenSource {
                            tracing::warn!(
                                event = "license_recheck_failed",
                                "License re-verification failed — features downgraded to OpenSource"
                            );
                        }
                    }
                }
            }
        });
    }

    let app = build_app(state).into_make_service_with_connect_info::<SocketAddr>();

    let listener = tokio::net::TcpListener::bind(config.listen).await?;
    tracing::info!(addr = %listener.local_addr()?, "listening");

    let grace = config.graceful_shutdown_timeout;
    axum::serve(listener, app)
        .with_graceful_shutdown(async move {
            shutdown_signal().await;
            tracing::info!(
                timeout_s = grace.as_secs(),
                "draining in-flight requests before exit"
            );
            tokio::time::sleep(grace).await;
        })
        .await?;

    Ok(())
}

fn init_tracing(level: &str) {
    let filter = EnvFilter::try_new(level).unwrap_or_else(|_| EnvFilter::new("info"));
    let json_layer = tracing_subscriber::fmt::layer()
        .json()
        .with_current_span(false)
        .with_span_list(false);
    let _ = tracing_subscriber::registry()
        .with(filter)
        .with(json_layer)
        .try_init();
}

/// Initialize the CCR store based on configuration.
///
/// Returns `Some(Box<dyn CcrStore>)` when a backend is configured,
/// `None` when no CCR store is requested.
fn init_ccr_store(config: &Config) -> Option<Box<dyn headroom_core::ccr::CcrStore>> {
    let backend_kind = match config.ccr_backend {
        Some(kind) => kind,
        None => {
            // Auto-detect: if --ccr-path is set, default to sqlite.
            if config.ccr_path.is_some() {
                CcrBackendKind::Sqlite
            } else {
                return None;
            }
        }
    };

    let ttl = config.ccr_ttl_seconds;
    let backend_config = match backend_kind {
        CcrBackendKind::InMemory => CcrBackendConfig::InMemory {
            capacity: headroom_core::ccr::DEFAULT_CAPACITY,
            ttl_seconds: ttl,
        },
        CcrBackendKind::Sqlite => {
            let path = config.ccr_path.as_deref().unwrap_or("~/.headroom/ccr.db");
            // Expand ~ in path using HOME env var (cross-platform).
            let expanded = if let Some(rest) = path.strip_prefix('~') {
                match std::env::var("HOME") {
                    Ok(home) => std::path::PathBuf::from(home).join(rest.trim_start_matches('/')),
                    Err(_) => std::path::PathBuf::from(path),
                }
            } else {
                std::path::PathBuf::from(path)
            };
            // Ensure parent directory exists.
            if let Some(parent) = expanded.parent() {
                if let Err(e) = std::fs::create_dir_all(parent) {
                    tracing::warn!(
                        event = "ccr_dir_create_failed",
                        path = %expanded.display(),
                        error = %e,
                        "failed to create CCR store directory; SQLite open may fail"
                    );
                }
            }
            CcrBackendConfig::Sqlite {
                path: expanded,
                ttl_seconds: ttl,
            }
        }
    };

    match headroom_core::ccr::backends::from_config(&backend_config) {
        Ok(store) => {
            tracing::info!(
                event = "ccr_store_initialized",
                backend = ?backend_kind,
                ttl_seconds = ttl,
                "CCR store ready for retrieval-marker injection"
            );
            Some(store)
        }
        Err(e) => {
            tracing::error!(
                event = "ccr_store_init_failed",
                error = %e,
                "CCR store initialization failed; compression will work but \
                 retrieval markers cannot be stored. Agents using \
                 headroom_retrieve(hash) will get cache misses."
            );
            None
        }
    }
}

/// PR-D1: resolve AWS credentials for Bedrock SigV4 signing.
///
/// Uses the `aws-config` default chain (env vars → shared profile
/// file → IMDS / ECS task role). Honours `Config::aws_profile` when
/// set; otherwise the chain picks up `AWS_PROFILE` from the
/// environment automatically.
async fn load_bedrock_credentials(
    config: &Config,
) -> Result<aws_credential_types::Credentials, Box<dyn std::error::Error + Send + Sync>> {
    use aws_config::BehaviorVersion;
    use aws_credential_types::provider::ProvideCredentials;

    let mut loader = aws_config::defaults(BehaviorVersion::latest())
        .region(aws_config::Region::new(config.bedrock_region.clone()));
    if let Some(profile) = config.aws_profile.as_deref() {
        loader = loader.profile_name(profile);
    }
    let aws_config = loader.load().await;
    let creds_provider = aws_config
        .credentials_provider()
        .ok_or("no credentials provider configured")?;
    let creds = creds_provider.provide_credentials().await?;
    Ok(creds)
}

async fn shutdown_signal() {
    let ctrl_c = async {
        let _ = tokio::signal::ctrl_c().await;
    };
    #[cfg(unix)]
    let terminate = async {
        if let Ok(mut s) = tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
        {
            s.recv().await;
        }
    };
    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        _ = ctrl_c => {},
        _ = terminate => {},
    }
    tracing::info!("shutdown signal received");
}
