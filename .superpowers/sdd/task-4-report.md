# Task 4: Failure-safe supersession and truthful erasure

## Scope

Implemented only the Task 4 Graphiti lifecycle changes:

- `cutctx/memory/backends/graphiti.py`
- `cutctx/memory/backends/graphiti_ledger.py`
- `tests/test_memory/test_graphiti_backend.py`

The adapter now writes a superseding episode before atomically transitioning
the ledger; refuses unsafe origin erasure; holds sorted partition locks through
preflight, remote removal, and local finalization; records remote failures as
retryable `delete_pending`; and reports partial clear outcomes truthfully.

## RED / GREEN evidence

### Supersession ordering

Added `test_failed_replacement_keeps_old_episode_active`.

```text
PYTHONDONTWRITEBYTECODE=1 rtk pytest -p no:cacheprovider tests/test_memory/test_graphiti_backend.py::TestGraphitiSupersedeAndLedger::test_failed_replacement_keeps_old_episode_active -q
```

The test was green on the starting worktree: the existing implementation had
already reserved/written the replacement before `record_replacement`, leaving
the original record active when `add_episode` raises. This is recorded rather
than misrepresented as a RED result.

### Truthful deletion and partial clear

Added red cases for an active external supporter, remote removal failure,
unknown/already deleted IDs, finalization recovery, supporter-before-origin
clear ordering, and partial clear aggregation.

```text
PYTHONDONTWRITEBYTECODE=1 rtk pytest -p no:cacheprovider tests/test_memory/test_graphiti_backend.py -k 'delete_ or clear_user_reports_partial' -q
```

Observed RED before implementation: 3 deletion cases failed because
`GraphitiUnsafeDeletionError` and the truthful remote-deletion protocol did
not exist. (The initial run also exposed the optional `filelock` package being
absent in this environment; the test-local async lock shim isolates backend
semantics from that optional dependency.)

GREEN after implementation:

```text
PYTHONDONTWRITEBYTECODE=1 rtk pytest -p no:cacheprovider tests/test_memory/test_graphiti_backend.py -k 'delete_ or clear_user_reports_partial or clear_deletes_supporter or failed_replacement' -q
```

Result: `8 passed`.

## Final verification

```text
PYTHONDONTWRITEBYTECODE=1 rtk pytest -p no:cacheprovider tests/test_memory/test_graphiti_backend.py -q
rtk ruff check cutctx/memory/backends/graphiti.py cutctx/memory/backends/graphiti_ledger.py tests/test_memory/test_graphiti_backend.py
rtk mypy cutctx/memory/backends/graphiti.py cutctx/memory/backends/graphiti_ledger.py
rtk git diff --check
```

Results:

- Graphiti backend tests: `31 passed`.
- Ruff: clean.
- Diff check: clean.
- Mypy reports three pre-existing errors in unrelated
  `cutctx/memory/factory.py` (lines 339, 344, 345); neither Task 4 Graphiti
  file is reported.

## Design notes

- Only Graphiti's supported `remove_episode` mutation is called.
- Unknown, foreign-scope, `write_pending`, and `delete_pending` supporter
  provenance fails closed. Only `deleted` and `superseded` are disregarded.
- A finalization failure never claims success. A retry accepts only a
  `NodeNotFoundError` as confirmation of a prior remote removal and then
  finalizes the ledger.
- `GraphitiClearError` carries `confirmed`, `failed`, and per-ID failures;
  independent safe episodes continue after another deletion fails.

## Review-fix wave

RED observed with:

```text
PYTHONDONTWRITEBYTECODE=1 rtk pytest -p no:cacheprovider tests/test_memory/test_graphiti_backend.py -k 'clear_defers_origin or clear_continues_independent' -q
```

Result: `0 passed, 2 failed`. The old batch-membership preflight removed an
origin after its supporter failed and stopped an independent deletion when a
foreign supporter made the origin unsafe.

GREEN after changing clear to use a provenance-only ordering pass and a fresh,
singleton under-lock preflight immediately before every remote mutation:

```text
PYTHONDONTWRITEBYTECODE=1 rtk pytest -p no:cacheprovider tests/test_memory/test_graphiti_backend.py -k 'clear_defers_origin or clear_continues_independent or clear_deletes_supporter' -q
```

Result: `3 passed`.
