# Audit Evidence System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make compression/routing audit claims reproducible through local inventory, release-evidence indexing, and sourced competitor records.

**Architecture:** Reuse `cutctx.evals.release_manifest`, `release_bundle`, and `release_evidence` as benchmark/release authorities. Add a small audit-evidence module and CLI script that records provider and architecture inventories. Documentation consumes generated artifacts and a hand-curated primary-source competitor ledger.

**Tech Stack:** Python 3.12, pytest, JSON, Markdown, Rust source inventory.

## Global Constraints

- Preserve unrelated dirty worktree edits.
- Every behavior change follows a red-green TDD cycle.
- Do not turn local evidence into market or release certification.

---

### Task 1: Local inventory artifact

**Files:**
- Create: `cutctx/evals/audit_evidence.py`
- Create: `scripts/generate_audit_evidence.py`
- Create: `tests/test_audit_evidence.py`

- [ ] Write failing tests for deterministic provider counts, tracked Rust source-line inventory, and dirty-worktree status.
- [ ] Implement the minimal inventory/evidence-index builder.
- [ ] Run the new tests and targeted release-evidence tests.

### Task 2: Competitor evidence ledger

**Files:**
- Create: `docs/evidence/competitor-routing-compression-2026-07-17.md`
- Modify: `docs/compression-routing-audit-2026-07-17.md`

- [ ] Collect dated primary-source URLs for each positive competitor claim.
- [ ] Mark every unsupported absence claim `not_established`.
- [ ] Update the audit to link the ledger and artifact commands.

### Task 3: Benchmark/release documentation

**Files:**
- Modify: `benchmarks/README.md`
- Modify: `docs/compression-routing-audit-2026-07-17.md`

- [ ] Document the existing benchmark-release manifest/bundle workflow and its scope limits.
- [ ] Document the clean-checkout requirement for release evidence.
- [ ] Run relevant tests, lint, formatting, and generated-artifact smoke checks.
