# Orchestrator Contracts and Routing Mode Reliability

## Objective

Make the authenticated Orchestrator dashboard a responsive, first-run-usable control plane:

- an empty installation exposes one editable, non-persisted Implementation starter contract;
- UI-created contracts round-trip through save and simulation without schema rejection;
- contract loading is bounded, cancellable, retryable, and stale-response safe;
- switching Off, Balanced, or Aggressive remains visible while dashboard data refreshes;
- only the newest dashboard refresh may publish data;
- optimistic mode remains selected until the newest committed stats confirm it;
- API, persistence, UI, cleanup, concurrency, and packaged runtime behavior have repeatable evidence.

## Confirmed failure modes

The routing-mode write succeeds, but `DashboardDataProvider.refresh()` sets global `loading=true`, so `Orchestrator` replaces the feature with a loading panel. In the live reproduction, `/stats?cached=1` took about 11.8 seconds and `/health` about 13.4 seconds, making a successful Aggressive-to-Balanced transition look broken.

The contracts endpoint is healthy and returned HTTP 200 in about 649 ms once Routing Studio mounted. It returned no contracts because the durable store, legacy roles, and bindings were all empty. Routing Studio mounts only after unrelated stats/health work and has no timeout or Retry action.

The editor also sends a top-level `template` field, while backend contract parsing rejects that field. A direct authenticated PUT returned HTTP 400 with `Unknown contract fields: template`.

## Architecture

### Newest-request-wins dashboard data

`DashboardDataProvider` retains `loading` only for the initial request when no usable snapshot exists. Later polling and explicit refreshes use `refreshing` and preserve the last successful `stats`, `health`, and mounted feature tree.

Every load receives a monotonically increasing generation. A completion may update `stats`, `health`, `error`, `refreshError`, or `lastUpdated` only if its generation is still current. Older polling, initial, or explicit loads are ignored when they finish out of order. `refreshing` is owned by the newest explicit refresh generation, so an older completion cannot clear it while newer work remains.

`refresh()` returns a structured result describing whether the newest current-data load committed and whether it succeeded. It must not hide failures inside an internally caught promise. History refresh is launched and represented separately; a delayed, failed, or hung history request must not delay stats publication or routing-mode confirmation.

Fatal errors block Orchestrator only when no stats snapshot exists. Later refresh failures keep the feature mounted and expose a non-destructive warning.

### Routing mode acknowledgement and confirmation

The mode selector follows this state machine:

1. set the requested mode optimistically and disable another mutation;
2. POST `{"orchestrator_mode":"<mode>"}` to `/config/flags`;
3. require an explicit acknowledgement equal to the requested mode;
4. keep the optimistic mode selected while background refreshes run;
5. clear optimistic mode only when the newest committed stats report that exact mode.

A missing acknowledgement is an error, as is a mismatched acknowledgement. A failed POST restores the confirmed backend mode. If the POST succeeds but refresh fails or temporarily returns stale stats, the requested mode remains selected and a non-destructive warning explains that confirmation is pending. A later newest refresh confirming the exact mode clears the optimistic state and warning.

### First-run starter contract and schema parity

The backend owns the starter so every API client sees the same representation. When the durable store is revision `0` with no contracts and legacy conversion yields no contracts, `OrchestrationService.list_contracts()` returns one synthesized draft:

- id `implementation`, name `Implementation`, version `1`, state `draft`, template `implementation`;
- description `Production coding and implementation tasks`;
- role aliases `implementation` and `worker`; task type `implementation`;
- baseline `openai:gpt-5.4-mini`; no fallback models;
- required capabilities `reasoning` and `tool_calling`;
- objective `highest_quality_within_budget`, quality floor `0.9`, maximum cost `1` USD, maximum total latency `120000` ms, no TTFT limit, empty weights;
- reliability: connect `10`, first token `30`, attempt `30`, idle `30`, total `120` seconds, two attempts, one deployment, timeout/provider-outage triggers, no fallback-cost allowance;
- evaluation: accepted signals `verified` and `review_accepted`, minimum `20` samples, unsafe floor `0.8`, maximum unsafe rate `0.01`, canary `0.1`, empty rollback policy.

The synthesized value does not increment revision or write to disk. Saving it with expected revision `0` creates the first durable contract at revision `1`. Durable contracts take precedence over legacy contracts; legacy contracts take precedence over the starter.

`WorkloadContract` gains a persisted `template` string accepted by parsing and emitted by serialization. The template is descriptive metadata; selectors, task types, requirements, objective, reliability, and evaluation remain authoritative. Direct parser/serializer, save/fetch, and authenticated simulation tests cover the complete shape.

When the saved response returns, Routing Studio upserts by `(id, version)` rather than appending. Saving the starter therefore leaves exactly one visible contract. Revision conflicts leave the current list and draft unchanged and surface the existing error.

### Timed and cancellable contract loading

A small fetch helper composes caller cancellation with an internal timeout without leaking timers or listeners. Its required semantics are:

- an already-aborted caller signal aborts immediately;
- caller cancellation remains an abort and is not rewritten as a timeout;
- only an internally fired timeout becomes the actionable timeout error;
- timer/listener cleanup occurs on success, HTTP failure, caller abort, and timeout.

`listContracts()` uses a 10-second timeout. Routing Studio assigns every load a monotonic token, aborts an earlier request before retry, updates state only for the current token, treats retry/unmount aborts as silent, and prevents an old catch or finally block from clearing newer loading/error/data state. A dedicated error panel offers `Retry loading contracts`.

## Verification strategy

Tests are added and observed failing before production edits.

- Backend: direct schema round-trip, complete starter defaults, durable/legacy/starter precedence, revision `0 -> 1`, exact single-contract save/reload, conflicts, authenticated simulation with template.
- Fetch helper: Node unit tests with controlled timers and fetch outcomes for all abort/cleanup paths.
- Dashboard: deterministic out-of-order refresh tests; missing/mismatched acknowledgement; failed refresh; stale stats followed by confirmation; no remount; timeout/retry/stale load; save upsert and conflict immutability.
- Existing orchestration, keyboard, responsive, rollout, evidence, and auth suites remain green.
- Lint and build pass.
- Before generated asset synchronization, record dirty paths, hashes, and the exact pre-existing dashboard source diff. Build in an isolated clean worktree at the feature HEAD, apply that preserved unrelated source diff there, and generate the combined package from that controlled snapshot. Verify the resulting output retains both the pre-existing source changes and this feature before synchronizing only generated dashboard files back.
- Run a temporary authenticated proxy on an isolated non-8787 port with a temporary orchestration directory and admin key. Do not stop or mutate the active port-8787 proxy. Validate packaged desktop and 390px flows, exact revisions and modes, loaded asset hashes, network failures, and console errors, then terminate only the temporary proxy.

## Non-goals

- Redesigning the Orchestrator visual system.
- Changing routing preset definitions.
- Persisting the starter before explicit Save.
- Refactoring unrelated dashboard pages or proxy handlers.
