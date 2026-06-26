#![no_main]

//! Fuzz target for DiffCompressor.
//!
//! Fuzzes DiffCompressor::new().compress() with arbitrary strings to find:
//! - Panics on malformed diff input
//! - Excessive memory allocation
//! - Incorrect diff generation
//! - Edge cases in line splitting (memchr path)

use libfuzzer_sys::fuzz_target;
use cutctx_core::transforms::diff_compressor::{DiffCompressor, DiffCompressorConfig};

fuzz_target!(|data: &[u8]| {
    // Only fuzz valid UTF-8
    let s = match std::str::from_utf8(data) {
        Ok(s) => s,
        Err(_) => return,
    };

    let config = DiffCompressorConfig::default();
    let compressor = DiffCompressor::new(config);

    // Fuzz compress — should handle any string input
    let _result = compressor.compress(s, "context");

    // Fuzz with different context strings
    if s.len() > 100 {
        let _result2 = compressor.compress(&s[..100], &s[100..]);
    }
});
