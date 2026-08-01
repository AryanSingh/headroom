# Final review fix wave — 2026-08-01

Base reviewed: `029a8b0e`.

## TDD record

Focused RED was observed before the corresponding fixes for the qdrant facade,
completed supersession retry, cancellation-safe lock, scope-isolated
contradiction candidates, failed-delete visibility, and historical/
`include_superseded` provenance. The initial focused command reported six
failures (the qdrant mock was then tightened to enforce its real signature).
After the minimal fixes, the focused GREEN command reported all targeted cases
passing; the corrected focused backend/ledger/lock/facade/contradiction suite
reported `132 passed, 0 failed, 38 skipped`.

## Changes

- `easy.Memory.save` now sends `idempotency_key` only to Graphiti; qdrant keeps
  its existing adapter call contract and still receives `session_id`.
- Search treats `delete_pending` provenance as current, excludes
  `write_pending`/`deleted`, and admits superseded provenance only for
  `include_superseded` or a historical `valid_at`. Historical mapping now uses
  the durable provider reference time when an upstream edge omits `valid_at`.
- Preflight provider failures are wrapped in `GraphitiDeletionError` while the
  explicit unsafe-deletion error remains intact. Existing clear behavior
  continues independently safe partitions and aggregates failures.
- Partition lock acquisition/release is cancellation-safe; a late successful
  worker acquisition is released before cancellation propagates.
- Contradiction candidates now require exact session, agent, and turn scope.
- Exact completed supersession retries are idempotent.
- Removed the unused JSON `_EpisodeLedger`; Graphiti production uses the
  fail-closed SQLite ledger only.
- Documentation now describes provider credentials/cost for production Graphiti
  construction and exact session vs user-wide search scope. CI runs unmarked
  contract nodes and the marked live Neo4j contract separately for Graphiti
  0.21 and 0.22.

## Verification

Commands and fresh results:

```text
PYTHONDONTWRITEBYTECODE=1 rtk pytest -p no:cacheprovider tests/test_memory -q
505 passed, 0 failed, 146 skipped

uvx ruff@0.9.4 check --exclude .venv .
All checks passed

uvx ruff@0.9.4 format --check --exclude .venv .
1534 files already formatted

rtk git diff --check
exit 0
```

`rtk mypy` over the changed modules reaches three pre-existing errors in
`cutctx/memory/factory.py` (`VectorBackend.USEARCH` assignment/attribute/return
typing). No changed Graphiti/facade/lock/contradiction file was reported.

The live Neo4j contract is intentionally CI-only and was not run locally.

## Follow-up review fix wave

New RED cases covered: a mixed active/superseded edge queried between parent
reference times, repeated cancellation of a waiting partition lock, the exact
`DirectMem0Adapter.save_memory` keyword contract, and a direct provider
preflight failure in one partition while another can be deleted. The initial
focused RED command reported the mixed-parent historical failure (`IndexError`
from an empty result); the other follow-up cases exercised already-correct
facade/aggregation behavior and the original cancellation case did not model a
second cancellation during cleanup. The strengthened repeated-cancellation
case now does.

GREEN command after the fixes:

```text
PYTHONDONTWRITEBYTECODE=1 rtk pytest -p no:cacheprovider [four focused nodes] -q
3 passed, 0 failed, 1 skipped

PYTHONDONTWRITEBYTECODE=1 rtk pytest -p no:cacheprovider tests/test_memory -q
508 passed, 0 failed, 146 skipped

uvx ruff@0.9.4 check --exclude .venv .
All checks passed

uvx ruff@0.9.4 format --check --exclude .venv .
1534 files already formatted
```

Historical searches now evaluate every owned parent independently against its
provider reference and supersession time; normal superseded-inclusive searches
retain both current and superseded provenance. Cancellation compensation is a
detached task so repeated cancellation of the caller cannot strand a late
file-lock acquisition.
