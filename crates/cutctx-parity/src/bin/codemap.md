# crates/cutctx-parity/src/bin/

## Responsibility
Provides the `parity-run` command-line entry point for executing one normalized Rust parity operation.

## Design
Clap handles input selection while the binary delegates operation semantics and serialization to the parity library.

## Flow
Parse CLI/input JSON -> invoke `cutctx_parity` dispatcher -> write canonical JSON to stdout -> exit nonzero on unrecoverable input/runtime errors.

## Integration
- Built as the `parity-run` Cargo binary.
- Consumed by parity scripts and CI comparison workflows.
