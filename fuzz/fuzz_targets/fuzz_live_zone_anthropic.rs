#![no_main]

//! Fuzz target for Anthropic live-zone compression.
//!
//! Fuzzes compress_anthropic_live_zone with arbitrary byte payloads to find:
//! - Panics on malformed JSON
//! - Panics on edge-case message structures
//! - Buffer overflows in byte-range surgery
//! - Excessive allocation on adversarial inputs

use libfuzzer_sys::fuzz_target;
use cutctx_core::auth_mode::AuthMode;
use cutctx_core::compression_policy::CompressionPolicy;

fuzz_target!(|data: &[u8]| {
    // Skip tiny inputs (< 10 bytes — can't form valid JSON)
    if data.len() < 10 {
        return;
    }

    // Fuzz with default compression policy
    let policy = CompressionPolicy::for_mode(AuthMode::Payg);

    // compress_anthropic_live_zone handles:
    // - Invalid JSON → BodyNotJson error
    // - Missing messages array → NoMessagesArray error
    // - Empty messages → NoChange
    // - Valid requests → compressed or NoChange
    let _result = cutctx_core::transforms::live_zone::compress_anthropic_live_zone(
        data,
        0, // frozen_message_count
        AuthMode::Payg,
        "claude-3-haiku-20240307",
    );
});
