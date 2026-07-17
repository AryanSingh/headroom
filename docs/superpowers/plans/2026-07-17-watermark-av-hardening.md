# Watermark AV Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the AV-triggering runtime watermark behavior with a read-only, manifest-based traceability contract.

**Architecture:** `cutctx_ee.watermark` retains marker serialization and local SQLite verification, but exposes manifest helpers instead of editing package source or scanning arbitrary binaries. Tests define the safe public surface and prove legacy mutation/scanning entry points are absent.

**Tech Stack:** Python 3.12, dataclasses, JSON, SQLite, pytest, Ruff.

## Global Constraints

- Preserve compatibility with existing `CTXWM:` marker strings.
- The shipped module must not write source files or read arbitrary binaries.
- No network, subprocess, shell, dynamic execution, or new dependency.
- SQLite verification is explicit and read-only.

---

### Task 1: Define the read-only watermark contract

**Files:**
- Modify: `tests/test_software_protection.py`
- Modify: `tests/test_ship_it_coverage.py`
- Modify: `cutctx_ee/watermark.py`

**Interfaces:**
- Produces: `watermark_manifest(watermark: Watermark) -> dict[str, str | int]`
- Produces: `extract_watermark_from_manifest(manifest: Mapping[str, object]) -> Watermark | None`

- [ ] **Step 1: Write failing tests**

```python
def test_watermark_manifest_roundtrip() -> None:
    watermark = Watermark("lic", "customer", "build", canary_token="token", embedded_at=1)
    recovered = extract_watermark_from_manifest(watermark_manifest(watermark))
    assert recovered == watermark

def test_runtime_mutation_and_binary_scan_apis_are_absent() -> None:
    import cutctx_ee.watermark as module
    assert not hasattr(module, "embed_watermark_in_source")
    assert not hasattr(module, "extract_watermark_from_binary")
```

- [ ] **Step 2: Verify RED**

Run: `rtk proxy .venv/bin/pytest tests/test_software_protection.py -q -k 'manifest or mutation'`

Expected: import error because AV has quarantined the old module, or assertion failure because manifest helpers do not exist and legacy APIs remain.

- [ ] **Step 3: Implement the minimal read-only module**

```python
def watermark_manifest(watermark: Watermark) -> dict[str, str | int]:
    return {"schema_version": 1, "marker": watermark.to_marker()}

def extract_watermark_from_manifest(manifest: Mapping[str, object]) -> Watermark | None:
    marker = manifest.get("marker")
    return Watermark.from_marker(marker) if isinstance(marker, str) else None
```

Keep `verify_watermark_traceability` using a parameterized `SELECT 1` query.

- [ ] **Step 4: Verify GREEN**

Run: `rtk proxy .venv/bin/pytest tests/test_software_protection.py tests/test_ship_it_coverage.py -q -k watermark`

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```bash
rtk git add cutctx_ee/watermark.py tests/test_software_protection.py tests/test_ship_it_coverage.py
rtk git -c core.editor=true commit -m "fix(ee): harden watermark runtime surface"
```

### Task 2: Document migration and prove source safety

**Files:**
- Modify: `cutctx_ee/codemap.md`
- Modify: `docs/content/docs/proxy.mdx`

- [ ] **Step 1: Document release-tooling migration**

State that release engineering writes a signed marker manifest outside the package; the runtime module does not embed source or inspect binaries.

- [ ] **Step 2: Verify static safety**

Run: `rtk proxy rg -n 'write_text|read_bytes|subprocess|socket|httpx|requests|os\\.system' cutctx_ee/watermark.py`

Expected: no matches.

- [ ] **Step 3: Run validation and commit**

```bash
rtk proxy .venv/bin/pytest tests/test_software_protection.py tests/test_ship_it_coverage.py -q -k watermark
rtk ruff check cutctx_ee/watermark.py tests/test_software_protection.py tests/test_ship_it_coverage.py
rtk git add cutctx_ee/codemap.md docs/content/docs/proxy.mdx
rtk git -c core.editor=true commit -m "docs: document watermark release migration"
```
