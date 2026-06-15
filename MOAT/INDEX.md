# Headroom — Moat Program Index

Engineering program to build durable defensibility. Specs are written to be handed directly to coding agents (one PR = one branch = one worktree; explicit files, schemas, acceptance criteria, tests).

**Read first:** [`00-overview.md`](00-overview.md) — strategy memo, why current "moats" aren't moats, the two decisions (open-source boundary; local-first vs. data loop), sequencing, and how to run the program with agents.

| File | Workstream | Moat type | Priority |
|------|------------|-----------|----------|
| [`00-overview.md`](00-overview.md) | — | Strategy + sequencing + agent operating rules | Read first |
| [`01-data-flywheel.md`](01-data-flywheel.md) | A | Learning / data network effect | Long game (start now) |
| [`02-memory-switching-costs.md`](02-memory-switching-costs.md) | B | Switching costs | **Build first** |
| [`03-control-plane-of-record.md`](03-control-plane-of-record.md) | C | Switching costs + embedding | Parallel (unblocks revenue + is auth/tenancy for A & B) |
| [`04-counter-positioning.md`](04-counter-positioning.md) | D | Counter-positioning | Positioning today; roadmap constraint |

## Cross-workstream dependencies

```
C1 (Ed25519 licensing) ─┬─> A7 (insight service auth)
                        ├─> B1 (team memory service auth)
                        └─> C4/C5/C6 (spend / policy / audit)
A2 (outcome signal) ───────> B2 (memory value scoring)   # outcomes feed memory value
A1..A6 ────────────────────> A8 (Rust learned scorer)
```

## Suggested first sprint (parallel agents)
1. **Agent 1 → C1** (`moat-C1-ed25519-licensing`) — closes the forgeable-license hole, unblocks A7/B1. Highest leverage.
2. **Agent 2 → B-track** (`moat-B1` → `B2` → `B3`) — fastest path to a real switching cost.
3. **Agent 3 → A-track** (`moat-A1` → `A2` → `A3`) — local episode capture; no server needed to start generating the corpus.

## Conventions
- Branch/worktree per PR; never mix workstreams.
- Every PR ends green: `make ci-precheck`, `cargo test -p <crate>`, `pytest <pkg>`.
- No request-path nondeterminism (TOIN observation-only contract).
- Every egress/sync/collection feature is flag-default-off with explicit opt-in.
- Privacy and determinism are **tests**, not comments — failing either blocks merge.
- Eval-gate every model; promote only on offline-eval win + shadow retrieval-rate win.
