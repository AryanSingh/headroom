# crates/cutctx-core/src/

## Responsibility
Implements Cutctx's reusable native domain layer: compression policy and transforms, auth/cache/licensing primitives, CCR persistence, semantic relevance, detection signals, tokenization, and cross-file stack graphs.

## Design
`lib.rs` exposes cohesive modules and a minimal stable re-export surface. Stateful facilities use explicit stores/managers; algorithm families use traits plus factories/builders; transform outputs carry manifests and statistics rather than hidden side effects.

## Flow
Provider payload fragments enter auth/content detection and tokenizer selection -> policy and signals choose safe transforms -> pipelines or specialized compressors generate smaller content -> callers may store originals through CCR and consume manifests for observability.

## Integration
- Used by native proxy handlers and PyO3/parity crates.
- Child maps cover `ccr/`, `relevance/`, `signals/`, `stack_graph/`, `tokenizer/`, and `transforms/`.
- Root modules also implement compression policy, semantic cache, cache-control counting, license signature verification, and anti-debug protection.
