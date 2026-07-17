# Compression Routing Audit Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove and correct the compression size guard and detector precedence, then make the audit evidence-based.

**Architecture:** Tests define the replacement-size and timestamp-collision invariants. The code compressor changes only its local size comparison; Python and Rust detector order remains aligned. The audit records current verified evidence and scopes claims accurately.

**Tech Stack:** Python/pytest, Rust/cargo test, Markdown.

## Global Constraints

- Preserve existing user working-tree edits.
- Do not claim broad benchmark or competitor conclusions without reproducible evidence.
- Use test-first verification for behavior changes.

---

### Task 1: Prove replacement-size and timestamp precedence regressions

**Files:**
- Modify: `tests/test_transforms/test_code_compressor.py`
- Modify: `tests/test_transforms_content_detection.py`
- Modify: `crates/cutctx-core/src/transforms/content_detector.rs`

- [ ] Write a Python compressor test whose retained body prefix is longer than the omitted suffix and assert the compressed result is not longer than the original.
- [ ] Run the test before changing production code; it must expose the whole-body size comparison.
- [ ] Write Python and Rust timestamped-log tests with `2025-01-01T10:00:00Z [ERROR] ...` and assert `BUILD_OUTPUT` / `BuildOutput`.
- [ ] Run the detector tests before modifying production detection behavior; they must pass with the current log-first implementation.

### Task 2: Correct the size guard

**Files:**
- Modify: `cutctx/transforms/code_compressor.py:1679`
- Test: `tests/test_transforms/test_code_compressor.py`

- [ ] Compare the generated omitted-comment and placeholder text with the actual original omitted statement text, including the same newline boundary.
- [ ] Run the new regression test and relevant code-compressor suite.

### Task 3: Correct the audit evidence

**Files:**
- Modify: `docs/compression-routing-audit-2026-07-17.md`

- [ ] Replace the merged/final wording with current-state provenance.
- [ ] Replace the aggregate test table with exact, executed commands and outputs.
- [ ] Scope proxy routing confidence/shadow features separately from deterministic orchestration routing.
- [ ] Remove unsupported benchmark and competitor-superiority assertions or label them as unverified.
