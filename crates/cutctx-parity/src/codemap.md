# crates/cutctx-parity/src/

## Responsibility
Defines parity operation dispatch and stable serialization shared by the harness binary and external comparison tools.

## Design
`lib.rs` models tagged requests/results and maps supported operations to public `cutctx-core` APIs. Normalized response envelopes separate successful values from structured errors.

## Flow
Deserialize operation request -> validate parameters -> call core implementation -> serialize canonical result/error for byte- or value-level comparison.

## Integration
- Called by `src/bin/parity_run.rs` and the example fixture utility.
- Depends only on public core behavior and serialization libraries.
