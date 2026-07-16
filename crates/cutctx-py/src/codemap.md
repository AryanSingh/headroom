# crates/cutctx-py/src/

## Responsibility
Defines the PyO3 wrapper layer and `_core` module registration for native Cutctx functionality.

## Design
`lib.rs` contains thin wrapper classes/functions that translate Python arguments, serde JSON, Rust result types, and exceptions. Algorithms are delegated to `cutctx-core`; wrapper state is limited to owned native managers/configuration.

## Flow
Module initialization adds classes/functions -> Python invokes wrapper -> inputs are validated/converted -> core tokenizer, transform, detector, live-zone, or stack-graph API runs -> typed results or Python exceptions are returned.

## Integration
- Compiled as the `cutctx._core` extension by the parent crate.
- Re-exports core behavior to the Python package without transport/server concerns.
