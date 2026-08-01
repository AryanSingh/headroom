# Graphiti Temporal Memory Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the optional Graphiti temporal-memory backend with strict scope isolation, transactional lifecycle state, truthful erasure, conservative contradiction handling, and no regressions to existing memory backends.

**Architecture:** Keep `GraphitiBackend` as the provider adapter, move durable ownership and lifecycle state into a focused SQLite ledger, and derive opaque Graphiti-safe partitions from CutCtx scope. All behavior changes use one red-green cycle at a time; existing local and qdrant paths remain unchanged unless an optional argument is explicitly supplied.

**Tech Stack:** Python 3.10+, asyncio, stdlib SQLite and hashing, `filelock>=3.20,<4`, pytest/pytest-asyncio, Graphiti Core `>=0.21,<0.23`, Neo4j, Ruff 0.9.4, mypy ratchet.

## Global Constraints

- Preserve all existing local and `qdrant-neo4j` behavior and constructor defaults.
- Keep Graphiti and contradiction detection opt-in.
- Support exactly `graphiti-core>=0.21,<0.23`; reject incompatible loaded versions with an actionable error.
- Never send raw CutCtx user or session identifiers to Graphiti.
- Never report successful remote erasure unless Graphiti confirms it.
- Prefer duplicate visibility over losing the last valid fact when a partial failure occurs.
- Every production behavior change requires a focused test observed failing first.
- Prefix every shell command with `rtk` and keep test commands non-interactive.

---

## File responsibility map

- `cutctx/memory/backends/graphiti.py`: Graphiti API adapter, partition-aware save/search, lifecycle orchestration, runtime compatibility check.
- `cutctx/memory/backends/graphiti_ledger.py`: SQLite schema, scope/episode records, atomic lifecycle transitions, and fail-closed legacy JSON detection.
- `cutctx/memory/backends/graphiti_lock.py`: non-expiring partition-scoped cross-process OS locks.
- `cutctx/memory/contradiction.py`: deterministic classification policy only.
- `cutctx/memory/core.py`: classifier injection and contradiction-gate orchestration.
- `cutctx/memory/easy.py`: backward-compatible public configuration wiring.
- `cutctx/memory/config.py`: validated classifier configuration.
- `cutctx/memory/backends/local.py`: optional callable propagation only; default path unchanged.
- `tests/test_memory/test_graphiti_ledger.py`: real SQLite state/concurrency tests without Graphiti mocks.
- `tests/test_memory/test_graphiti_backend.py`: provider-contract and failure-ordering tests.
- `tests/test_memory/test_graphiti_upstream_contract.py`: exact installed Graphiti 0.21/0.22 import and async API contract.
- `tests/test_memory/test_contradiction.py`: deterministic and public-facade regression tests.
- `docs/content/docs/memory.mdx`: supported versions, configuration, durability, scope, and deletion semantics.
- `pyproject.toml`: bounded optional Graphiti dependency.

---

### Task 1: Runtime compatibility and opaque partitions

**Files:**
- Modify: `pyproject.toml`
- Modify: `.github/workflows/ci.yml`
- Modify: `cutctx/memory/backends/graphiti.py`
- Test: `tests/test_memory/test_graphiti_backend.py`
- Create: `tests/test_memory/test_graphiti_upstream_contract.py`

**Interfaces:**
- Produces: `_scope_partition(user_id: str, session_id: str | None) -> str`
- Produces: `_validate_graphiti_version(version: str) -> None`
- Consumes: `importlib.metadata.version("graphiti-core")`

- [ ] **Step 1: Add failing partition tests**

Add tests asserting that the same scope is stable, different sessions differ,
raw email/session text is absent, and the result matches
`r"^cutctx_[a-f0-9]{32}$"`:

```python
def test_scope_partition_is_stable_opaque_and_graphiti_safe() -> None:
    from cutctx.memory.backends.graphiti import _scope_partition

    first = _scope_partition("alice@example.com", "session/one")
    assert first == _scope_partition("alice@example.com", "session/one")
    assert first != _scope_partition("alice@example.com", "session/two")
    assert "alice" not in first and "session" not in first
    assert re.fullmatch(r"cutctx_[a-f0-9]{32}", first)
```

- [ ] **Step 2: Run the partition test and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 rtk pytest -p no:cacheprovider tests/test_memory/test_graphiti_backend.py::test_scope_partition_is_stable_opaque_and_graphiti_safe -q`

Expected: FAIL because `_scope_partition` is not defined.

- [ ] **Step 3: Implement the minimal partition helper**

Use a domain-separated SHA-256 digest over length-delimited UTF-8 values and
return `cutctx_` plus the first 32 hex characters. Do not use Python's randomized
`hash()`.

- [ ] **Step 4: Run the partition test and verify GREEN**

Run the Step 2 command. Expected: PASS.

- [ ] **Step 5: Add failing compatibility tests**

Parameterize accepted versions `0.21.0`, `0.22.9` and rejected versions
`0.20.9`, `0.23.0`, `0.29.3`, and `garbage`. Rejected errors must mention
`graphiti-core>=0.21,<0.23`.

- [ ] **Step 6: Run compatibility tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 rtk pytest -p no:cacheprovider tests/test_memory/test_graphiti_backend.py -k 'graphiti_version' -q`

Expected: FAIL because runtime compatibility is not validated.

- [ ] **Step 7: Implement compatibility validation and bound the extra**

Require the complete distribution version to match
`r"^0\.(?:21|22)(?:\.\d+)?$"`; this deliberately rejects prerelease, dev, and
local versions that are outside the tested contract. Do not add a core
packaging dependency.
Change the optional extra to:

```toml
graphiti = [
    "graphiti-core>=0.21,<0.23",
    "neo4j>=5.26.0,<6.0",
    "filelock>=3.20,<4",
]
```

Call validation only when initializing a real imported Graphiti client; injected
test clients remain dependency-free.

- [ ] **Step 8: Verify Task 1 GREEN and existing optional imports**

Run:

```text
PYTHONDONTWRITEBYTECODE=1 rtk pytest -p no:cacheprovider \
  tests/test_memory/test_graphiti_backend.py -k 'partition or version or optional' -q
```

Expected: all selected tests pass.

- [ ] **Step 9: Add the upstream dependency contract matrix**

Create `tests/test_memory/test_graphiti_upstream_contract.py` using
`pytest.importorskip("graphiti_core")`. Assert the installed distribution version
is accepted, `Graphiti` and `EpisodeType` import, and `inspect.signature` contains
the required parameters for `Graphiti.add_episode`, `Graphiti.search`,
`Graphiti.remove_episode`, and `Graphiti.get_nodes_and_edges_by_episode`. Use an
injected fake client in the adapter tests to verify each awaited call shape.

The same file must contain a `graphiti_live_contract` test that connects to the
CI Neo4j service. Do not call `Graphiti(...)`, which would construct default
OpenAI clients. Instead instantiate `Neo4jDriver`, allocate `Graphiti` with
`object.__new__(Graphiti)`, assign only `driver` and `max_coroutines=None`, and
persist `EpisodicNode`, `EntityNode`, `EntityEdge`, and `EpisodicEdge` objects
through their upstream `.save(driver)` methods. Create two episodic nodes, the
required MENTIONS edges, and one entity edge with ordered
`episodes=[origin_uuid, supporter_uuid]`, then verify:

- `get_nodes_and_edges_by_episode` returns both ordered UUIDs;
- removing the non-origin episode preserves the edge;
- removing the origin first removes the edge, proving why the adapter preflight
  is required.

Add a CI job with matrix `graphiti-version: [0.21.0, 0.22.0]` and a Neo4j 5.26
service with health check and test-only credentials. Install the checkout with
`.[graphiti]`, force-install the matrix version, and run:

```text
python -m pytest -p no:cacheprovider \
  -m graphiti_live_contract tests/test_memory/test_graphiti_upstream_contract.py \
  tests/test_memory/test_graphiti_backend.py -q
```

Locally run both isolated contracts:

```text
rtk proxy uv run --isolated --with 'graphiti-core==0.21.0' --with pytest \
  python -m pytest -p no:cacheprovider tests/test_memory/test_graphiti_upstream_contract.py -q
rtk proxy uv run --isolated --with 'graphiti-core==0.22.0' --with pytest \
  python -m pytest -p no:cacheprovider tests/test_memory/test_graphiti_upstream_contract.py -q
```

Expected: both versions pass including real ordered-provenance/deletion behavior;
the explicit 0.23 rejection unit test remains GREEN. This job is a shipping gate,
not allowed to skip for missing Neo4j. Explicitly unset `OPENAI_API_KEY` and
other provider keys in the job; the contract test must assert they are absent
and must never instantiate provider clients or make an outbound provider call.

- [ ] **Step 10: Commit Task 1**

Stage only Task 1 files and commit `fix(memory): bound Graphiti compatibility`.

---

### Task 2: Transactional SQLite episode ledger

**Files:**
- Create: `cutctx/memory/backends/graphiti_ledger.py`
- Create: `cutctx/memory/backends/graphiti_lock.py`
- Create: `tests/test_memory/test_graphiti_ledger.py`
- Create: `tests/test_memory/test_graphiti_lock.py`
- Modify: `cutctx/memory/backends/graphiti.py`

**Interfaces:**
- Produces: `EpisodeRecord` dataclass with `episode_id`, `user_key`, `session_key`, `partition_id`, `idempotency_key_hash`, `payload_digest`, `state`, `superseded_at`, `deleted_at`, `replacement_id`, and `last_error`.
- Produces: `SQLiteEpisodeLedger(path: Path)`.
- Produces ledger methods: `reserve_write(...)`, `activate(...)`, `record_replacement(...)`, `mark_delete_pending(...)`, `mark_deleted(...)`, `mark_delete_failed(...)`, `get(...)`, `find_by_idempotency_key(...)`, `partitions_for_scope(...)`, `records_for_user(...)`, and `invalid_at_for(...)`.
- Produces lock interface: `PartitionOperationLock(root: Path, partition_id: str, timeout: float)` as an async context manager backed by `filelock.FileLock` and `asyncio.to_thread`.
- Consumes: `_scope_partition` from Task 1.

- [ ] **Step 1: Write failing persistence, scope, and concurrency tests**

Tests must construct two ledger instances against the same temporary database,
reserve and activate episodes in different sessions, reopen the ledger, and assert exact
ownership/partition/state persistence. Assert `partitions_for_scope(user, s1)`
does not include `s2` and user-wide lookup includes both. Add a
`ThreadPoolExecutor` test with two independent ledger objects, a barrier, and 50
unique episodes per writer; assert all 100 records remain and no
`OperationalError` escapes. In `test_graphiti_lock.py`, add process-based tests
proving a second worker cannot enter while the holder lives, acquisition timeout
performs no work, normal release wakes the waiter, and terminating the holder
process releases the OS lock so a waiter proceeds. There is no expiry, heartbeat,
or steal operation to test.

- [ ] **Step 2: Run persistence tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 rtk pytest -p no:cacheprovider tests/test_memory/test_graphiti_ledger.py -k 'persistence or scope or concurrent' -q`

Expected: collection FAIL because the ledger module does not exist.

- [ ] **Step 3: Implement schema and atomic record methods**

Use `sqlite3.connect(path, timeout=30)`, `PRAGMA journal_mode=WAL`, explicit
transactions, primary key on `episode_id`, and indexes on `(user_key,
session_key, state)` and `partition_id`. Hash user/session keys before storage.
Each public method opens a short-lived connection and commits before returning.
Store only a SHA-256 payload digest and hashed idempotency key, never duplicate
memory content or caller tokens in the ledger. Implement partition lock paths
from opaque partition IDs only, under a sibling `graphiti-locks` directory with
owner-only permissions where supported. `filelock.FileLock` is acquired through
`asyncio.to_thread` and held until the async context exits; timeout raises
`GraphitiOperationLockTimeout` before any remote mutation. Set a 30-second
production SQLite busy timeout and retry only SQLite
`busy`/`locked` errors with a
bounded deterministic backoff; do not catch integrity or schema errors.

Enforce this transition table in SQL update predicates:

| From | To | Search visibility |
|---|---|---|
| absent | `write_pending` | hidden |
| `write_pending` | `active` | visible after activation |
| `active` | `superseded` | hidden from current search |
| `active` or `superseded` | `delete_pending` | visible iff it was active |
| `delete_pending` | `deleted` | hidden |
| `deleted` | none | terminal |

Retried `delete_pending` remains pending and visible until confirmation.

- [ ] **Step 4: Verify persistence GREEN**

Run the Step 2 command. Expected: PASS.

- [ ] **Step 5: Add lifecycle and multi-parent tests**

Cover every allowed transition, rejection of every invalid transition,
write-pending invisibility, atomic replacement, delete-pending visibility,
error/deleted transitions, unknown/foreign IDs, retry of pending deletion, and
`invalid_at_for()` remaining `None` while any parent is active. Hold a real
SQLite write transaction open with a short test-only timeout to deterministically
exercise retry, then assert a non-lock `OperationalError` is propagated.

- [ ] **Step 6: Verify all ledger tests GREEN**

Run: `PYTHONDONTWRITEBYTECODE=1 rtk pytest -p no:cacheprovider tests/test_memory/test_graphiti_ledger.py -q`

Expected: all ledger tests pass.

- [ ] **Step 7: Add failing legacy JSON fail-closed tests**

Write a JSON fixture matching the pre-release `superseded`, `deleted`, and
`user_episodes` shape. Assert construction raises
`GraphitiLegacyMigrationRequired`, names the path, explains that session and
opaque partition ownership cannot be reconstructed, and leaves the JSON bytes
unchanged. Cover malformed JSON and a legacy user with multiple unobservable
sessions; neither may be silently treated as user-wide state.

- [ ] **Step 8: Run migration tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 rtk pytest -p no:cacheprovider tests/test_memory/test_graphiti_ledger.py -k 'legacy or migration' -q`

Expected: FAIL because legacy state is currently loaded as JSON.

- [ ] **Step 9: Implement fail-closed legacy detection and verify GREEN**

Inspect the file header before opening SQLite. When it is JSON or otherwise not
a SQLite database, raise `GraphitiLegacyMigrationRequired` without renaming,
rewriting, or deleting it. Run all ledger tests; expected PASS.

- [ ] **Step 10: Commit Task 2**

Commit `feat(memory): add transactional Graphiti ledger`.

---

### Task 3: Strict scope-aware idempotent save and search

**Files:**
- Modify: `cutctx/memory/backends/graphiti.py`
- Modify: `cutctx/memory/easy.py`
- Modify: `tests/test_memory/test_graphiti_backend.py`
- Modify: `tests/test_memory/test_easy.py`

**Interfaces:**
- Consumes: `SQLiteEpisodeLedger`, `_scope_partition`.
- Changes: `save()` reserves a pending record, supplies the opaque partition, and activates ownership after Graphiti succeeds.
- Changes: `search_memories()` resolves allowed partitions before calling Graphiti and rejects unowned supporting episodes.
- Changes: public `Memory.save(..., session_id: str | None = None, idempotency_key: str | None = None)` and `Memory.search(..., session_id: str | None = None)` forward scope to every backend that already supports it without changing calls that omit it.

- [ ] **Step 1: Write the failing two-session isolation test**

Configure a mock client that returns edges from sessions `s1` and `s2`; persist
their episode ownership through the real SQLite ledger. Search `s1` and assert
only the `s1` edge is returned. Assert the Graphiti call uses only the `s1`
partition.

- [ ] **Step 2: Run the isolation test and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 rtk pytest -p no:cacheprovider tests/test_memory/test_graphiti_backend.py::test_search_enforces_session_partition -q`

Expected: FAIL because search currently sends raw user scope and admits results
without session metadata.

- [ ] **Step 3: Implement minimal scoped save/search**

On save, derive the partition from `memory.user_id` and `memory.session_id`.
Generate a fresh random idempotency key when none is supplied; never coalesce two
independent identical saves. Reserve `write_pending` with the hashed key and a
digest over the complete provider payload and scope. A supplied retry key may
reuse only its exact pending UUID/payload/scope; mismatches raise
`GraphitiIdempotencyConflict`. Acquire the partition operation lock, pass
the partition as `group_id` and the reserved episode ID as `uuid`, then activate
the episode. If
activation fails, raise
`GraphitiWriteRecoveryRequired(episode_id, partition_id, idempotency_key)` and
retain the pending record. On search, return `[]` without calling
Graphiti when a requested scope has no partitions. For each edge, keep only
supporting episode IDs owned by an allowed partition; discard the edge when none
remain.

- [ ] **Step 4: Verify session isolation GREEN**

Run the Step 2 command. Expected: PASS.

- [ ] **Step 5: Add failing facade, recovery, user-wide, unknown-session, entity, temporal, and multi-parent tests**

Assert the public facade forwards `session_id` and `idempotency_key` on save and
session scope on search; two facade
sessions cannot read each other; a simulated activation failure leaves a
pending UUID that only the returned recovery key with the exact payload/scope
can reuse; another scope or different payload conflicts. Assert two independent
identical saves without a key get distinct UUIDs. Assert user-wide search uses
all and only the user's recorded partitions;
unknown sessions return no results; existing entity and temporal filters retain
their behavior; a fact supported by one active and one closed episode remains
visible with only active provenance.

- [ ] **Step 6: Run the new search cases and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 rtk pytest -p no:cacheprovider tests/test_memory/test_graphiti_backend.py tests/test_memory/test_easy.py -k 'graphiti and (facade or recovery or user_wide or unknown_session or multi_parent or temporal)' -q`

Expected: at least the new user-wide and ownership cases fail.

- [ ] **Step 7: Complete result mapping and filtering minimally**

Populate returned metadata with filtered episode UUIDs only. Do not expose
partition, ledger user/session keys, raw scope values, or recovery identifiers
in normal results. Preserve score and entity-filter behavior.

- [ ] **Step 8: Verify Task 3 and existing Graphiti mapping tests GREEN**

Run: `PYTHONDONTWRITEBYTECODE=1 rtk pytest -p no:cacheprovider tests/test_memory/test_graphiti_backend.py -k 'search or wiring or save' -q`

Expected: all selected tests pass.

- [ ] **Step 9: Commit Task 3**

Commit `fix(memory): enforce Graphiti scope isolation`.

---

### Task 4: Failure-safe supersession and truthful erasure

**Files:**
- Modify: `cutctx/memory/backends/graphiti.py`
- Modify: `cutctx/memory/backends/graphiti_ledger.py`
- Modify: `tests/test_memory/test_graphiti_backend.py`

**Interfaces:**
- Produces: `GraphitiDeletionError` and `GraphitiClearError`.
- Produces: `GraphitiUnsafeDeletionError` and `_preflight_deletion(episode_ids: set[str]) -> list[str]`.
- Changes: `supersede()` writes replacement before the atomic ledger transition.
- Changes: `delete_memory()` returns `False` for unknown/already-deleted IDs, `True` only for confirmed remote deletion, otherwise raises.
- Changes: `clear_user()` raises aggregate failure with `confirmed` and `failed` counts.

- [ ] **Step 1: Write failing supersession-order test**

Make `add_episode` raise and assert the old ledger record remains `active`, no
replacement is recorded, and the original exception propagates.

- [ ] **Step 2: Run and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 rtk pytest -p no:cacheprovider tests/test_memory/test_graphiti_backend.py::test_failed_replacement_keeps_old_episode_active -q`

Expected: FAIL because the current implementation marks the old episode first.

- [ ] **Step 3: Reorder supersession and verify GREEN**

Reserve the replacement without changing the old episode, write it through
Graphiti, then call the ledger's atomic `record_replacement`. If the final
transaction fails, retain `write_pending`, leave the old record visible, and
raise `GraphitiWriteRecoveryRequired`. Retry with the same replacement object
must reuse the UUID and complete the transition. Run Step 2 plus final-commit
failure/idempotency cases; expected PASS.

- [ ] **Step 4: Write failing safe-deletion and truthfulness tests**

Use the real provider method shape
`get_nodes_and_edges_by_episode([episode_id])` to cover: non-origin supporter
deletion; refusal when deleting an origin with an active supporter outside the
deletion set; success when every supporter belongs to the deletion set;
refusal when any supporter is unknown, foreign-scope, `write_pending`, or
`delete_pending`; safe disregard only for conclusively `deleted` or
`superseded` supporters;
successful `remove_episode`; remote exception; missing removal API; unknown and
foreign IDs; already deleted ID; remote success followed by ledger-finalization
failure; and retry after a prior failure. A remote failure must leave a visible
`delete_pending` record with `last_error` and raise `GraphitiDeletionError`.

- [ ] **Step 5: Run deletion cases and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 rtk pytest -p no:cacheprovider tests/test_memory/test_graphiti_backend.py -k 'delete_' -q`

Expected: shared-origin, remote-failure, finalization-failure, and unknown-ID
cases fail against the current adapter.

- [ ] **Step 6: Implement minimal truthful deletion and verify GREEN**

Acquire the non-expiring partition operation lock before preflight and hold it through
remote removal/finalization. Preflight with
`get_nodes_and_edges_by_episode`, inspect each edge's ordered `episodes`, and
refuse when the target is `episodes[0]` while any supporter outside the deletion
set is active or not conclusively resolved. Unknown, foreign-scope,
`write_pending`, and `delete_pending` provenance fails closed. Only `deleted` or
`superseded` supporters are safe to disregard. Call only `remove_episode`, the
supported API for the bounded Graphiti range. Record pending after successful preflight,
deleted after remote success, and the error on remote failure. If finalization
fails, retry treats Graphiti `NodeNotFoundError` as already remotely removed and
finishes the pending ledger transition. Do not capability-guess
`delete_episode`.

- [ ] **Step 7: Write failing partial-clear test**

Track a shared origin/supporter pair plus an independent episode. Assert clear
orders the supporter before the origin. Fail the independent remote deletion,
allow safe shared deletions to run, and assert aggregate confirmed/failed counts
with failed IDs retained for retry. Add a cross-scope supporter case that refuses
the unsafe origin deletion while continuing independent deletions.

Add a deterministic two-worker race: worker A acquires the partition lock and
preflights origin deletion; worker B attempts to add a supporter and blocks on
the same lock; after A releases, B proceeds. Add the inverse ordering where B
adds first and A's fresh under-lock preflight refuses origin removal. Assert
`remove_episode(origin)` is never called in the unsafe ordering.

- [ ] **Step 8: Implement aggregate clear and verify GREEN**

Acquire affected partition locks in sorted order to prevent deadlock. Preflight
the complete deletion set under those locks, topologically order non-origin supporters
before origins, include active/superseded/delete-pending records owned by the
user, attempt every independent safe deletion, collect failures, then raise
once. Run the partial clear test and all Task 4 tests.

- [ ] **Step 9: Commit Task 4**

Commit `fix(memory): make Graphiti lifecycle failure-safe`.

---

### Task 5: Conservative contradiction policy and public classifier injection

**Files:**
- Modify: `cutctx/memory/contradiction.py`
- Modify: `cutctx/memory/config.py`
- Modify: `cutctx/memory/core.py`
- Modify: `cutctx/memory/backends/local.py`
- Modify: `cutctx/memory/easy.py`
- Modify: `tests/test_memory/test_contradiction.py`
- Test existing: `tests/test_memory/test_easy.py`
- Test existing: `tests/test_memory/test_core_operations.py`

**Interfaces:**
- Produces: `ContradictionClassifier` public callable type.
- Changes: `Memory(..., contradiction_classifier_callable: ContradictionClassifier | None = None)`.
- Changes: `LocalBackendConfig` and `MemoryConfig` carry the optional callable.
- Changes: Graphiti-only connection options are `graphiti_neo4j_uri`, `graphiti_neo4j_user`, `graphiti_neo4j_password`, and `graphiti_ledger_path`; existing `neo4j_*` arguments retain qdrant defaults and meaning.
- Preserves: `contradiction_detection=False` default and all existing constructor arguments.
- Preserves: contradiction auto-supersession is local-backend-only; Graphiti does not consume the callable.

- [ ] **Step 1: Add failing non-exclusive predicate tests**

Parameterize `owns`, `likes`, `uses`, and `works on` pairs whose different
objects can coexist. Assert `INDEPENDENT`. Keep existing identical and strict
extension expectations.

- [ ] **Step 2: Run and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 rtk pytest -p no:cacheprovider tests/test_memory/test_contradiction.py -k 'nonexclusive' -q`

Expected: FAIL because current same-verb logic returns `CONTRADICT`.

- [ ] **Step 3: Implement conservative deterministic policy**

Remove broad same-verb contradiction. Define a small explicit exclusive
predicate table only when the subject and predicate are both unambiguous;
otherwise return `INDEPENDENT`. Do not add probabilistic heuristics.

- [ ] **Step 4: Verify classifier GREEN**

Run all deterministic classifier tests. Expected: PASS.

- [ ] **Step 5: Add failing public-facade classifier tests**

One test supplies a synchronous callable through `Memory` and observes it during
a local-backend conflict. Another constructs `Memory(contradiction_detection=True,
contradiction_classifier="llm")` without a callable and expects an immediate
`ValueError` before initialization or writes.

Add explicit compatibility tests asserting:

```python
memory = Memory(backend="qdrant-neo4j")
assert memory._neo4j_uri == "neo4j://localhost:7687"
assert memory._neo4j_user == "neo4j"
assert memory._neo4j_password
assert Memory().backend_type == "local"
```

Also assert explicit qdrant Neo4j arguments win without reading Graphiti
environment variables, while `graphiti_*` options override Graphiti environment
values only for `backend="graphiti"`.

- [ ] **Step 6: Run and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 rtk pytest -p no:cacheprovider tests/test_memory/test_contradiction.py -k 'easy_api_classifier' -q`

Expected: FAIL because the facade cannot accept or validate a callable.

- [ ] **Step 7: Wire the callable with backward-compatible defaults**

Restore `neo4j_uri="neo4j://localhost:7687"`, `neo4j_user="neo4j"`, and
`neo4j_password=""` defaults for the qdrant path. Add separate optional
`graphiti_*` parameters after existing parameters. Add the optional callable
after existing parameters, propagate it through
`LocalBackendConfig` and `MemoryConfig`, and initialize
`HierarchicalMemory._contradiction_classifier` from config. Validate allowed
mode strings and fail fast when `llm` lacks a callable. Reject contradiction
options with `backend="graphiti"` unless they remain at defaults, with an error
that directs users to Graphiti's temporal extraction rather than silently
ignoring configuration.

- [ ] **Step 8: Verify Task 5 and existing easy/local tests GREEN**

Run:

```text
PYTHONDONTWRITEBYTECODE=1 rtk pytest -p no:cacheprovider \
  tests/test_memory/test_contradiction.py \
  tests/test_memory/test_easy.py \
  tests/test_memory/test_core_operations.py -q
```

Expected: all selected tests pass.

- [ ] **Step 9: Commit Task 5**

Commit `fix(memory): make contradiction updates conservative`.

---

### Task 6: Documentation, branch reconciliation, and release verification

**Files:**
- Modify: `docs/content/docs/memory.mdx`
- Modify: `tests/test_docs_truthfulness.py`
- Modify: `tests/test_memory/test_graphiti_backend.py` only if a dependency-contract fixture is required
- Modify during reconciliation: files changed on `main` only when Git reports an actual conflict

**Interfaces:**
- Documents the exact public and operational contract produced by Tasks 1-5.
- Produces no new runtime behavior.

- [ ] **Step 1: Add failing documentation contract assertions**

Extend `tests/test_docs_truthfulness.py` with:

```python
def test_docs_site_documents_graphiti_memory_contract() -> None:
    text = (_PROJECT_ROOT / "docs/content/docs/memory.mdx").read_text()

    for expected in (
        "graphiti-core>=0.21,<0.23",
        "OPENAI_API_KEY",
        "opaque partition",
        "delete_pending",
        "Graphiti 0.23",
    ):
        assert expected in text
```

Run: `PYTHONDONTWRITEBYTECODE=1 rtk pytest -p no:cacheprovider tests/test_docs_truthfulness.py::test_docs_site_documents_graphiti_memory_contract -q`

Expected: FAIL because the Graphiti operational contract is not documented.

- [ ] **Step 2: Write operational documentation**

Add installation, environment, supported-version, scoping, failure, migration,
and cleanup examples. State explicitly that Graphiti 0.23+ database-per-scope
support is not provided by this adapter.

- [ ] **Step 3: Run focused feature verification**

Run:

```text
PYTHONDONTWRITEBYTECODE=1 rtk pytest -p no:cacheprovider \
  tests/test_memory/test_graphiti_backend.py \
  tests/test_memory/test_graphiti_ledger.py \
  tests/test_memory/test_graphiti_upstream_contract.py \
  tests/test_memory/test_contradiction.py -q
rtk proxy uvx ruff@0.9.4 check cutctx/memory tests/test_memory/test_graphiti_backend.py \
  tests/test_memory/test_graphiti_ledger.py tests/test_memory/test_contradiction.py
rtk proxy python3 -m mypy --follow-imports=skip \
  cutctx/memory/backends/graphiti.py \
  cutctx/memory/backends/graphiti_ledger.py \
  cutctx/memory/contradiction.py
```

Expected: zero failures/errors.

- [ ] **Step 4: Run memory regression verification**

Run the complete `tests/test_memory` suite. If the checkout still lacks
`cutctx._core`, build the Rust extension using the repository script before
retrying; do not permanently skip the collector. Expected: zero failures.

- [ ] **Step 5: Commit completed feature before integrating main**

After all feature-local gates pass, stage only the intended feature, tests, and
docs. Verify `rtk git diff --cached --check`, then commit
`feat(memory): complete Graphiti temporal backend`.

- [ ] **Step 6: Reconcile current main without rewriting user work**

Fetch no remote state. Merge local `main` into the feature branch with
`GIT_EDITOR=true rtk git merge --no-edit main`. Resolve only actual conflicts,
preserving the feature design and all newer main behavior.

- [ ] **Step 7: Run whole-repository gates fresh**

Run the repository's pinned CI commands from `.github/workflows/ci.yml`, at
minimum:

```text
PYTHONDONTWRITEBYTECODE=1 CI=true rtk pytest -p no:cacheprovider -q
rtk proxy uvx ruff@0.9.4 check .
rtk proxy uvx ruff@0.9.4 format --check .
CI=true rtk proxy python3 scripts/mypy_ratchet.py
rtk proxy python3 -m compileall -q cutctx cutctx_ee
rtk proxy python3 scripts/check_repo_hygiene.py
rtk proxy python3 scripts/check_secret_patterns.py
rtk git diff --check main...HEAD
```

Build and validate release artifacts exactly as CI does:

```text
rtk proxy maturin sdist --out dist
rtk proxy maturin build --release --out dist
rtk proxy twine check dist/*
rtk proxy python3 scripts/assert_oss_wheel_clean.py dist
```

Create a temporary virtual environment outside the repository, install the
built wheel with `[graphiti]`, and assert `import cutctx`, `import graphiti_core`,
and the installed Graphiti version is `>=0.21,<0.23`; delete only that explicit
temporary directory afterward. Expected: all commands exit zero. Record exact
pass/skip counts and treat unavailable live Neo4j credentials as an unverified
external smoke, not as a pass.

- [ ] **Step 8: Request independent final review**

Give the reviewer the accepted spec, this plan, base SHA, head SHA, and exact
verification evidence. Require review of privacy, lifecycle ordering,
concurrency, version boundary, compatibility, tests, and docs. Fix every
Critical or Important finding through a new red-green cycle.

- [ ] **Step 9: Final verification and completion commit**

Re-run all commands affected by review fixes, ensure the worktree is clean, and
commit any reviewed corrections as `fix(memory): address Graphiti completion review`.
