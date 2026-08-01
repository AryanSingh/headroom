<!-- markdownlint-disable MD013 -->

# Verified Code Review Report

**Date:** 2026-07-31
**Final verification:** 2026-08-01
**Method:** Source inspection, targeted tests, CI contract tests, Ruff 0.9.4, dashboard lint/build

## Outcome

The codebase is suitable for a controlled release. The generated report promoted maintainability observations to P1 defects and overstated silent exception handling. Verified reliability gaps were fixed.

## Actionable findings completed

| Finding | Resolution |
| --- | --- |
| Unbounded WebSocket lifecycle | Added pre-connect admission reservations, configured limit, cleanup, health fields, Prometheus counter, and alert. |
| Entry-count-only compression cache | Added value-byte and per-entry budgets, LRU eviction, stats, proxy config, health aggregation, and Prometheus gauges. |
| Stripe duplicate fulfillment | Added schema-enforced subscription identity plus a transactional delivery outbox with failed-hook retry. |
| Starlette legacy TestClient backend | Added `httpx2` and a 3.10–3.14 compatibility smoke job. |
| Missing visual regression contract | Added an inspected Playwright baseline for a stable dark overview shell. |
| Dependency audit findings | Updated dashboard transitive overrides for fixed `brace-expansion` and `postcss`; `npm audit` reports zero vulnerabilities. |

## Findings reclassified

| Generated finding | Verified disposition |
| --- | --- |
| `server.py` size | Maintainability backlog, not a release defect. Major route extraction already exists under `cutctx/proxy/routes/`; a large speculative split during an audit would increase regression risk. |
| 37 silent `except Exception` blocks | Count was stale. Current instances primarily log, re-raise, or intentionally degrade optional components. Health capability probes that return unavailable are diagnostic fallbacks, not swallowed request failures. |
| Savings tracker/model router size | Maintainability observations. No failing invariant or unsafe coupling was demonstrated. |
| F-string SQL | Fixed identifiers and placeholder construction; no attacker-controlled SQL identifiers found. |
| Missing per-request memory accounting | Body size is already bounded; retained cross-request cache memory was the actual gap and is now fixed. |
| No persistent cache | Product/performance choice, not correctness. |
| Dataclass/Pydantic split | Intentional boundary: internal runtime state versus request validation models. |

## Remaining engineering backlog

- Continue incremental extraction from `server.py` only when a feature change supplies a behavioral seam and dedicated tests.
- Standardize control-plane error envelopes without rewriting provider passthrough payloads.
- Add named diagnostic reason fields for optional health probes if operators need more detail than availability booleans.
- Externalize mutable state before enabling multiple replicas.

These are maintainability or platform-evolution items, not unremediated defects from this audit.

## Reproduction record

```bash
rtk pytest
rtk proxy uvx ruff@0.9.4 check .
rtk proxy uvx ruff@0.9.4 format --check .
rtk proxy .venv/bin/python scripts/mypy_ratchet.py
rtk git diff --check
```

Pytest passed 9,919 tests and skipped 271. Ruff checked and format-checked 1,513 files. The mypy ratchet reported no errors beyond its recorded baseline, and the diff whitespace check passed.
