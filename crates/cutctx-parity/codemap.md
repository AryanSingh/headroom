# crates/cutctx-parity/

## Responsibility
Provides a command-line/fixture harness for comparing deterministic Rust `cutctx-core` behavior with Python-side expectations.

## Design
The library defines serializable operations, inputs, outputs, and structured errors; the `parity-run` binary reads a request and emits machine-comparable JSON. It deliberately avoids embedding Python in the current implementation.

## Flow
Fixture/CLI input selects an operation -> library dispatches to `cutctx-core` -> result is normalized into stable JSON -> external tooling compares it with the corresponding Python output.

## Integration
- Depends on `cutctx-core`, serde, anyhow, and clap.
- `examples/` demonstrates fixture diffing; `src/bin/` provides the executable surface.
