# Graphiti temporal memory completion design

## Goal

Complete the `omos/graphiti-temporal-memory` branch as an opt-in temporal
knowledge-graph backend without changing the behavior of existing local or
`qdrant-neo4j` memory backends. The completed lane must preserve tenant and
session isolation, avoid data loss on partial failures, provide truthful
deletion semantics, remain durable across proxy workers, and pass the existing
memory and repository release gates.

## Compatibility boundary

The existing `graphiti-core>=0.8.0` declaration spans incompatible Graphiti
APIs. Graphiti 0.21 and 0.22 provide the graph-partition `group_id` behavior and
`previous_episode_uuids` support required by this adapter. Later releases route
group identifiers through database selection and therefore require a separate
database-provisioning architecture.

This branch will support `graphiti-core>=0.21,<0.23`. The adapter will fail with
an actionable version error if an incompatible runtime is imported. Supporting
Graphiti's database-per-partition API is outside this branch and requires a
separate design.

## Scope and identity model

Raw CutCtx identifiers will never be sent to Graphiti. A deterministic SHA-256
partition key will be derived from the user and optional session scope. The key
will use only Graphiti-safe characters and will not disclose user identifiers.

- A save with a session uses the user-and-session partition.
- A session-scoped search queries exactly that partition.
- A user-wide search queries only partitions recorded for that user in the
  durable ledger, including the user's no-session partition.
- Results whose supporting episodes are not owned by the requested scope are
  rejected locally as defense in depth.
- Existing backends retain their current identifiers and scoping behavior.

## Durable episode ledger

The JSON snapshot ledger will be replaced by a SQLite ledger stored at the
configured Graphiti ledger path. SQLite provides cross-process transactions and
safe concurrent access without adding a new project dependency.

The ledger records:

- episode UUID;
- opaque user key and optional opaque session key;
- Graphiti partition ID;
- lifecycle state (`write_pending`, `active`, `superseded`, `delete_pending`,
  `deleted`);
- supersession and deletion timestamps;
- replacement episode linkage;
- last remote-deletion error where applicable.

It also owns partition-scoped operation locks. Every Graphiti write and origin
deletion acquires a cross-process OS file lock for the opaque partition and
holds it through remote mutation and ledger finalization. The lock has no
expiry or steal path; the OS releases it if the holder exits. Lock acquisition
runs off the event loop and times out without performing a mutation. This
supports multiple workers sharing one local ledger/filesystem. Distributed
hosts require an externally fenced backend and are outside this adapter.

Schema creation is idempotent. The branch's pre-release JSON ledger does not
contain session ownership or opaque partition identifiers, so it cannot be
converted without mis-scoping remote data. Detecting that format fails closed
with `GraphitiLegacyMigrationRequired`. Rewriting legacy remote groups into
opaque partitions is a separately consented migration and is not performed
automatically.

## Write and supersession flow

Normal saves accept an optional idempotency key and first reserve the episode
UUID, scope, partition, payload digest, and hashed idempotency key as a durable
`write_pending` record. Calls without a supplied key generate a fresh key, so
independent identical saves are never coalesced. They then acquire the partition
lock, write the Graphiti episode, and promote the record to `active`. If
promotion fails after a successful remote write, the pending record remains
retryable with the same key and UUID and the operation raises a recovery
exception carrying both. Reusing a key with a different scope or payload is
rejected. It never reports a fully successful CutCtx save without durable
ownership metadata.

Supersession follows write-new-then-close-old ordering:

1. Reserve the replacement as `write_pending` without changing the old record.
2. Write the replacement episode to Graphiti using the reserved UUID.
3. In one SQLite transaction, promote the replacement to `active` and mark the
   old episode superseded.
4. Return the replacement.

If step 1 fails, the old episode remains current. If step 2 fails, the operation
raises; the old episode remains visible, favoring duplication over data loss.

## Search flow

The ledger resolves allowed partitions before Graphiti search. A requested
session with no recorded partition returns no results. Graphiti results are
mapped only when at least one supporting episode is owned by the requested
scope. Lifecycle and temporal filters are applied from durable ledger state.

Multi-parent facts remain visible while at least one supporting episode is
active in the requested scope. Deleting or superseding one parent must not hide
a fact still supported by another active parent.

## Deletion and clear semantics

Deletion means confirmed remote erasure, not merely local hiding. Graphiti
0.21/0.22 may remove a shared fact edge when deleting its first supporting
episode, so every deletion is preflighted against remote edge provenance.

- A non-origin supporting episode may be deleted directly.
- Preflight and remote removal run while holding the partition operation lock;
  writes cannot add a supporter to that partition between those steps.
- An origin episode with active supporters outside the deletion set is refused
  with a safe-deletion error; the adapter never destroys their shared fact.
- Every non-target supporter must resolve to ledger ownership and a conclusive
  lifecycle state. Unknown, foreign-scope, `write_pending`, or `delete_pending`
  supporters block origin deletion. Only confirmed `deleted` or `superseded`
  supporters are safe to disregard.
- The ledger records `delete_pending` only after the preflight succeeds.
- `delete_pending` remains visible in normal searches until remote erasure is
  confirmed.
- The adapter calls the supported Graphiti `remove_episode` API.
- On success, the ledger records `deleted` and the public method returns `True`.
- On failure, the ledger retains `delete_pending` plus the error and the public
  method raises a dedicated deletion error. It must not return success.
- Deleting an unknown or already-deleted ID returns `False`.

`clear_user` preflights the entire deletion set, removes non-origin supporters
before their origin episodes, and returns the count of confirmed deletions. If
any deletion is unsafe or fails, it continues independent safe deletions and
then raises an aggregate error with confirmed and failed counts so callers can
retry safely.

## Contradiction handling

Deterministic auto-supersession remains opt-in and conservative.

- Identical text and strict extension remain refinements.
- Broad non-exclusive predicates such as `owns`, `likes`, `uses`, and `works on`
  do not auto-contradict merely because their objects differ.
- Deterministic contradiction is limited to explicitly exclusive predicates
  with defined semantics.
- Ambiguous pairs remain independent.
- The public easy API accepts an optional classifier callable for the local
  hierarchical backend. Selecting
  `contradiction_classifier="llm"` without a callable fails during construction,
  before any memory write.
- Graphiti uses its own temporal extraction and does not run the CutCtx
  deterministic contradiction gate in this branch.
- Existing default behavior remains unchanged because contradiction detection
  is disabled by default.

## Configuration and public API

`GraphitiConfig` keeps environment-based Neo4j configuration and adds explicit
ledger/version validation. The easy `Memory` facade continues to accept
`backend="graphiti"`, adds optional `session_id` to `save` and `search`, adds an
optional `idempotency_key` to `save`, and gains separate optional Graphiti
connection parameters. Existing qdrant Neo4j
defaults, constructor defaults, and other backend paths remain source-compatible.

Operational documentation will cover:

- the supported Graphiti version range;
- required Neo4j and OpenAI-compatible Graphiti credentials;
- opaque partition behavior;
- ledger location and migration;
- deletion failure and retry semantics;
- lack of support for Graphiti's later database-per-partition releases.

## TDD and verification

Each behavior is implemented through a separate red-green cycle. Required
regressions include:

1. two sessions under one user cannot read each other;
2. common identifiers such as email addresses produce safe partitions;
3. a failed replacement write leaves the old episode current;
4. failed remote deletion is surfaced, remains visible, and is retained as
   retryable state;
5. shared-edge deletion is refused or safely ordered, and `clear_user` reports
   partial failure truthfully;
6. concurrent ledger writers retain all updates;
7. partial deletion of a multi-parent fact preserves remaining support;
8. non-exclusive predicates remain independent;
9. public LLM classifier injection works and missing injection fails fast;
10. incompatible Graphiti versions fail with an installation hint;
11. public facade session scoping reaches the Graphiti backend;
12. local and `qdrant-neo4j` behavior and defaults remain unchanged;
13. pre-release JSON state fails closed with migration guidance;
14. a two-worker write/delete race is serialized by the partition lock, and a
    terminated holder releases it without a stale-resume path;
15. unknown or pending shared provenance blocks destructive deletion;
16. independent identical saves do not share an idempotency record, while a
    retry using the recovery key reuses the reserved UUID.

Verification proceeds from focused tests to the complete memory suite, pinned
Ruff 0.9.4, targeted and ratcheted mypy, packaging metadata checks, secret and
diff checks, and the repository's broader release gates after bringing the
branch up to current `main`. A real Neo4j/Graphiti contract test is a shipping
gate for both supported Graphiti releases. It creates a shared edge in an
ephemeral Neo4j service, verifies ordered provenance returned by
`get_nodes_and_edges_by_episode`, and exercises first/non-first deletion behavior
without calling an external LLM. Local developer runs may report unavailable
Neo4j prerequisites, but CI must provide the service; mock-only evidence does
not satisfy this gate.

An independent reviewer must approve privacy, failure ordering, concurrency,
backward compatibility, and test coverage before the completion commit.

## Non-goals

- Provisioning one Neo4j database per tenant for Graphiti 0.23 and later.
- Enabling contradiction detection by default.
- Changing existing local, Mem0, Qdrant, Neo4j, or memory facade semantics
  outside the optional parameters described above.
- Introducing a new external database or lock service.
