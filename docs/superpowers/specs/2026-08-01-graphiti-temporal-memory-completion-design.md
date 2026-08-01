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
- lifecycle state (`active`, `superseded`, `delete_pending`, `deleted`);
- supersession and deletion timestamps;
- replacement episode linkage;
- last remote-deletion error where applicable.

Schema creation is idempotent. A one-time importer will accept the branch's
pre-release JSON ledger format when present, import it transactionally, and
retain a recoverable backup. Malformed legacy data will produce an actionable
error rather than silently resurrecting memories.

## Write and supersession flow

Normal saves write the Graphiti episode first and then record ownership in the
ledger. If the local ledger commit fails after a successful remote write, the
operation raises and records enough context for diagnosis; it never reports a
fully successful CutCtx save without durable ownership metadata.

Supersession follows write-new-then-close-old ordering:

1. Write the replacement episode to Graphiti.
2. In one SQLite transaction, record the replacement and mark the old episode
   superseded.
3. Return the replacement.

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

Deletion means confirmed remote erasure, not merely local hiding.

- The ledger first records `delete_pending`.
- The adapter calls the supported Graphiti `remove_episode` API.
- On success, the ledger records `deleted` and the public method returns `True`.
- On failure, the ledger retains `delete_pending` plus the error and the public
  method raises a dedicated deletion error. It must not return success.
- Deleting an unknown or already-deleted ID returns `False`.

`clear_user` attempts every tracked active episode and returns the count of
confirmed deletions. If any deletion fails, it raises an aggregate error with
confirmed and failed counts so callers can retry safely.

## Contradiction handling

Deterministic auto-supersession remains opt-in and conservative.

- Identical text and strict extension remain refinements.
- Broad non-exclusive predicates such as `owns`, `likes`, `uses`, and `works on`
  do not auto-contradict merely because their objects differ.
- Deterministic contradiction is limited to explicitly exclusive predicates
  with defined semantics.
- Ambiguous pairs remain independent.
- The public easy API accepts an optional classifier callable. Selecting
  `contradiction_classifier="llm"` without a callable fails during construction,
  before any memory write.
- Existing default behavior remains unchanged because contradiction detection
  is disabled by default.

## Configuration and public API

`GraphitiConfig` keeps environment-based Neo4j configuration and adds explicit
ledger/version validation. The easy `Memory` facade continues to accept
`backend="graphiti"` and gains only optional Graphiti-specific parameters or a
classifier callable. Existing constructor defaults and other backend paths must
remain source-compatible.

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
4. failed remote deletion is surfaced and retained as retryable state;
5. `clear_user` reports partial failure truthfully;
6. concurrent ledger writers retain all updates;
7. partial deletion of a multi-parent fact preserves remaining support;
8. non-exclusive predicates remain independent;
9. public LLM classifier injection works and missing injection fails fast;
10. incompatible Graphiti versions fail with an installation hint;
11. local and `qdrant-neo4j` behavior remains unchanged.

Verification proceeds from focused tests to the complete memory suite, pinned
Ruff 0.9.4, targeted and ratcheted mypy, packaging metadata checks, secret and
diff checks, and the repository's broader release gates after bringing the
branch up to current `main`. A real Neo4j/Graphiti smoke test will run when the
required local service and credentials are available; otherwise the committed
contract test will validate the dependency boundary and the remaining live
limitation will be stated explicitly.

An independent reviewer must approve privacy, failure ordering, concurrency,
backward compatibility, and test coverage before the completion commit.

## Non-goals

- Provisioning one Neo4j database per tenant for Graphiti 0.23 and later.
- Enabling contradiction detection by default.
- Changing existing local, Mem0, Qdrant, Neo4j, or memory facade semantics
  outside the optional parameters described above.
- Introducing a new external database or lock service.
