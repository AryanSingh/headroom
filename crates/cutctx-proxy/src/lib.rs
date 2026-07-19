//! cutctx-proxy library: transparent reverse proxy in front of the Python
//! Cutctx proxy. Used by both `main.rs` and the integration tests.

pub mod bedrock;
pub mod cache_stabilization;
pub mod compression;
pub mod config;
pub mod error;
pub mod handlers;
pub mod headers;
pub mod health;
pub mod license;
pub mod observability;
pub mod policy;
pub mod protection;
pub mod proxy;
pub mod responses_items;
pub mod session_state;
pub mod sse;
pub mod vertex;
pub mod websocket;

pub use config::Config;
pub use error::ProxyError;
pub use proxy::{build_app, AppState};

/// Install a structured panic hook after tracing has been initialized.
///
/// The default hook is preserved so the standard panic report still reaches
/// stderr, while operators also receive a searchable event in JSON tracing
/// deployments before the process exits.
pub fn install_panic_hook() {
    let default_hook = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |info| {
        let location = info.location().map(|location| location.to_string());
        let payload = if let Some(message) = info.payload().downcast_ref::<&str>() {
            *message
        } else if let Some(message) = info.payload().downcast_ref::<String>() {
            message.as_str()
        } else {
            "non-string panic payload"
        };
        tracing::error!(event = "panic", panic_message = %payload, location = ?location, "cutctx-proxy panicked");
        default_hook(info);
    }));
}
