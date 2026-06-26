#![no_main]

//! Fuzz target for SmartCrusher compression.
//!
//! Fuzzes the SmartCrusher with arbitrary JSON input to find:
//! - Panics on malformed input
//! - Excessive memory allocation
//! - Incorrect compression results
//! - Edge cases in array/object processing

use libfuzzer_sys::fuzz_target;
use serde_json::Value;

fuzz_target!(|data: &[u8]| {
    // Only fuzz valid UTF-8 (SmartCrusher operates on JSON strings)
    let s = match std::str::from_utf8(data) {
        Ok(s) => s,
        Err(_) => return,
    };

    // Only fuzz valid JSON
    let val: Value = match serde_json::from_str(s) {
        Ok(v) => v,
        Err(_) => return,
    };

    // Fuzz with default config
    let config = cutctx_core::transforms::smart_crusher::crusher::SmartCrusherConfig::default();
    let crusher = cutctx_core::transforms::smart_crusher::crusher::SmartCrusher::new(config);

    // process_value should never panic on valid JSON
    let _result = crusher.process_value(&val, "", 0.0);
});
