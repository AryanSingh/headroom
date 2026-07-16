# crates/cutctx-core/benches/

## Responsibility
Contains Criterion benchmark targets for tokenizer, CCR storage, auth-mode classification, and episodic-CCR performance.

## Design
Each Cargo bench target isolates one core hot path and is registered with `harness = false`; benchmark code is not linked into production artifacts.

## Flow
Criterion constructs representative inputs, invokes public `cutctx-core` APIs repeatedly, and records throughput/latency distributions.

## Integration
- Declared by `cutctx-core/Cargo.toml` and executed through Cargo bench tooling.
- Depends only on the public core surfaces it measures.
