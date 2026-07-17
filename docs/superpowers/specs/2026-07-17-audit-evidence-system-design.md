# Audit Evidence System Design

## Objective

Turn the compression/routing audit's open evidence requirements into checked,
versioned artifacts that documentation can cite without overstating local test
or benchmark results.

## Components

1. A local inventory generator emits a schema-versioned JSON artifact with the
   Git revision/dirty state, catalogued orchestration providers, and revision-
   pinned source-line counts for named architecture areas.
2. An evidence index binds that inventory to the existing benchmark release
   manifest and release-evidence evaluator. It records whether a claim is
   locally reproducible, externally substantiated, or unavailable.
3. A competitor ledger stores dated claims with direct source URLs, source
   type, verification date, and an explicit status. Claims of a competitor's
   missing feature are forbidden unless a source directly establishes the
   absence; otherwise the ledger says `not_established`.
4. The compression/routing audit and relevant product docs cite those artifacts
   and distinguish local fixture evaluation from release and market evidence.

## Safety and verification

- Every generated artifact includes a schema version, timestamp, Git SHA, and
  dirty-worktree status.
- Provider counts represent built-in catalogued specs, never provider breadth
  mediated by optional dependencies.
- Source-line counts use tracked source files only and identify the exact path.
- Tests construct temporary repositories/fixtures, assert deterministic JSON
  shapes, and verify that dirty state and missing evidence lower claim status.
- Competitor research is documentation only; no external credentials or vendor
  APIs are invoked.

## Acceptance criteria

- A single command creates the local inventory and evidence-index artifacts.
- Its tests fail before implementation and pass after it.
- Existing benchmark and release tooling remains the source of benchmark and
  release truth; no duplicate benchmark runner is created.
- Documentation contains no unqualified performance, competitor-absence, or
  full-release claims without an artifact or primary source.
