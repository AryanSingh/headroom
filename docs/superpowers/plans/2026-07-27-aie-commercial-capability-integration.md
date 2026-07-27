# AIE Commercial Capability Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the approved AIE-aligned commercial program: honest ROI claims, skill/instruction preservation, harness/claw packaging, and receipts/skills GTM — without building eval/graph/security platforms.

**Architecture:** Verify commercial fail-closed foundations already in tree, then add a thin `skill_preserve` protection path in the compression pipeline, improve buyer-report honesty fields, package wrap/skill discovery, and update public docs/website narrative. Graph memory, full eval platforms, and security suites stay out of scope.

**Tech Stack:** Python 3.10+, pytest, Click CLI, FastAPI proxy, existing ContentRouter/SelectiveContextFilter/CacheAligner, MCP plugins, Vite/React dashboard only if a thin status surface is required, Markdown/MDX docs, website HTML.

## Global Constraints

- Dual-path rule: Builder/solo wrap + MCP compression must remain useful without a license.
- Raw `CUTCTX_ENTITLEMENT_TIER` must never independently unlock paid features.
- Public savings claims must distinguish eligible workloads from all-traffic averages and separate created vs observed savings.
- Do not implement Neo4j/context-graph core features in this plan.
- Do not build a general agent eval SaaS; only thin integrity checks.
- Prefer `rtk`-prefixed shell commands in this repository.
- Do not edit unrelated dirty worktree files.

## File structure

| File | Responsibility |
|---|---|
| `cutctx/transforms/skill_preserve.py` | Detect skill/instruction blocks; mark protected spans |
| `tests/test_skill_preserve.py` | Unit tests for detection + preservation |
| `cutctx/transforms/content_router.py` | Honor skill-preserve markers before aggressive transforms |
| `cutctx/transforms/selective_filter.py` | Never drop protected skill/instruction messages |
| `cutctx/cli/wrap.py` (or provider wrap helpers) | Discover skill dirs and enable preserve rules |
| `cutctx/cli/report.py` | Buyer-report honesty fields (eligible %, bypassed %) |
| `tests/test_buyer_report_honesty.py` | Report schema / copy invariants |
| `plugins/cutctx-plugin/skills/cutctx/SKILL.md` | Progressive-disclosure Cutctx skill |
| `README.md`, `artifacts/value-proposition.md`, `website/index.html`, docs MDX | GTM packaging |
| `cutctx/evals/` thin suite | Skill-survival + attribution invariant evals |

---

### Task 0: Verify commercial filter prerequisites

**Files:**
- Read/verify: `tests/test_entitlement_request_path.py`
- Read/verify: `cutctx/proxy/decision_receipt.py`
- Read/verify: `cutctx/cli/report.py`

**Interfaces:**
- Consumes: existing licensing enforcement and decision-receipt implementations
- Produces: a short verification note in the PR description (pass/fail); no new API

- [ ] **Step 1: Run entitlement fail-closed suite**

Run: `rtk pytest tests/test_entitlement_request_path.py tests/test_entitlement_boundaries.py -q`

Expected: PASS. If FAIL, stop this plan and finish `docs/superpowers/plans/2026-07-22-licensing-enforcement.md` first.

- [ ] **Step 2: Run decision-receipt suite**

Run: `rtk pytest tests/test_decision_receipt.py -q`

Expected: PASS (receipt contract already shipped).

- [ ] **Step 3: Spot-check buyer report CLI help**

Run: `rtk proxy cutctx report buyer --help`

Expected: help text mentions provider cache vs Cutctx compression separation.

- [ ] **Step 4: Commit only if you added a verification checklist file; otherwise proceed with no commit**

If documenting verification locally:

```bash
git add docs/superpowers/specs/2026-07-27-aie-commercial-capability-integration-design.md
git commit -m "$(cat <<'EOF'
docs: record AIE commercial integration design baseline

EOF
)"
```

---

### Task 1: Skill/instruction detection library

**Files:**
- Create: `cutctx/transforms/skill_preserve.py`
- Create: `tests/test_skill_preserve.py`

**Interfaces:**
- Produces: `SkillPreserveConfig(enabled: bool = True, markers: tuple[str, ...] = (...))`
- Produces: `is_skill_or_instruction_content(text: str, *, config: SkillPreserveConfig | None = None) -> bool`
- Produces: `annotate_messages_for_skill_preserve(messages: list[dict[str, Any]], *, config: SkillPreserveConfig | None = None) -> list[dict[str, Any]]`
- Produces: annotated messages may include `metadata.cutctx_skill_preserve: True` or content markers; must be JSON-serializable and safe to strip before upstream if needed

- [ ] **Step 1: Write the failing tests**

```python
from cutctx.transforms.skill_preserve import (
    SkillPreserveConfig,
    annotate_messages_for_skill_preserve,
    is_skill_or_instruction_content,
)


def test_detects_skill_frontmatter_and_body() -> None:
    text = "---\nname: cutctx\ndescription: compress bulky tool output\n---\n# Cutctx\nUse cutctx_compress on large logs."
    assert is_skill_or_instruction_content(text) is True


def test_detects_agents_md_style_instructions() -> None:
    text = "# AGENTS\n\nWhen running shell commands, always prefix with `rtk`."
    assert is_skill_or_instruction_content(text) is True


def test_ignores_ordinary_tool_log() -> None:
    text = "INFO starting\n" + ("error line\n" * 200)
    assert is_skill_or_instruction_content(text) is False


def test_annotate_marks_system_and_skill_messages() -> None:
    messages = [
        {"role": "system", "content": "You are a coding agent. Follow SKILL.md rules."},
        {"role": "user", "content": "---\nname: db-safety\ndescription: never drop tables\n---\nNever run DROP TABLE."},
        {"role": "user", "content": "please fix the flaky test"},
    ]
    out = annotate_messages_for_skill_preserve(messages, config=SkillPreserveConfig(enabled=True))
    assert out[0].get("metadata", {}).get("cutctx_skill_preserve") is True
    assert out[1].get("metadata", {}).get("cutctx_skill_preserve") is True
    assert out[2].get("metadata", {}).get("cutctx_skill_preserve") is not True


def test_disabled_config_is_noop() -> None:
    messages = [{"role": "system", "content": "Follow SKILL.md"}]
    out = annotate_messages_for_skill_preserve(messages, config=SkillPreserveConfig(enabled=False))
    assert out == messages
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `rtk pytest tests/test_skill_preserve.py -q`

Expected: FAIL with `ModuleNotFoundError` or import error for `cutctx.transforms.skill_preserve`.

- [ ] **Step 3: Implement minimal detection library**

```python
# cutctx/transforms/skill_preserve.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_DEFAULT_MARKERS = (
    "---\nname:",
    "SKILL.md",
    "# AGENTS",
    "# CLAUDE.md",
    "Always prefix with `rtk`",
    "cutctx_compress",
    "cutctx_retrieve",
)


@dataclass(frozen=True)
class SkillPreserveConfig:
    enabled: bool = True
    markers: tuple[str, ...] = field(default_factory=lambda: _DEFAULT_MARKERS)


def is_skill_or_instruction_content(
    text: str, *, config: SkillPreserveConfig | None = None
) -> bool:
    cfg = config or SkillPreserveConfig()
    if not text or not cfg.enabled:
        return False
    sample = text[:4000]
    lowered = sample.lower()
    if sample.lstrip().startswith("---") and "\nname:" in sample[:200].lower():
        return True
    return any(marker.lower() in lowered for marker in cfg.markers)


def annotate_messages_for_skill_preserve(
    messages: list[dict[str, Any]], *, config: SkillPreserveConfig | None = None
) -> list[dict[str, Any]]:
    cfg = config or SkillPreserveConfig()
    if not cfg.enabled:
        return messages
    annotated: list[dict[str, Any]] = []
    for msg in messages:
        item = dict(msg)
        content = item.get("content")
        text = content if isinstance(content, str) else ""
        role = item.get("role")
        protect = role == "system" or is_skill_or_instruction_content(text, config=cfg)
        if protect:
            metadata = dict(item.get("metadata") or {})
            metadata["cutctx_skill_preserve"] = True
            item["metadata"] = metadata
        annotated.append(item)
    return annotated
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `rtk pytest tests/test_skill_preserve.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cutctx/transforms/skill_preserve.py tests/test_skill_preserve.py
git commit -m "$(cat <<'EOF'
feat(compression): detect skill and instruction blocks for preservation

EOF
)"
```

---

### Task 2: Honor skill-preserve in SelectiveContextFilter

**Files:**
- Modify: `cutctx/transforms/selective_filter.py`
- Modify: `tests/test_skill_preserve.py` (integration cases) or create `tests/test_selective_filter_skill_preserve.py`

**Interfaces:**
- Consumes: `metadata.cutctx_skill_preserve`
- Produces: filter never drops messages marked for skill preserve

- [ ] **Step 1: Write failing integration test**

```python
from cutctx.transforms.selective_filter import SelectiveContextFilter, SelectiveFilterConfig
from cutctx.transforms.skill_preserve import annotate_messages_for_skill_preserve


def test_selective_filter_keeps_skill_messages_even_if_low_relevance() -> None:
    messages = annotate_messages_for_skill_preserve(
        [
            {"role": "system", "content": "You are helpful."},
            {
                "role": "user",
                "content": "---\nname: db-safety\ndescription: never drop tables\n---\nNever run DROP TABLE in production.",
            },
            {"role": "user", "content": "what is the weather in paris?"},
            {"role": "assistant", "content": "I cannot fetch weather."},
            {"role": "user", "content": "ok thanks"},
        ]
    )
    filt = SelectiveContextFilter(SelectiveFilterConfig(min_score=0.99, protect_recent=1))
    kept = filt.filter(messages, query="weather in paris")
    assert any(
        isinstance(m.get("content"), str) and "DROP TABLE" in m["content"] for m in kept
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk pytest tests/test_selective_filter_skill_preserve.py::test_selective_filter_keeps_skill_messages_even_if_low_relevance -q`

Expected: FAIL because skill message is dropped.

- [ ] **Step 3: Implement preserve check in filter**

In `SelectiveContextFilter.filter`, before dropping a message:

```python
metadata = msg.get("metadata") if isinstance(msg.get("metadata"), dict) else {}
if metadata.get("cutctx_skill_preserve") is True:
    keep = True
```

Also treat `role == "system"` as always retained when skill preserve is enabled via config flag on `SelectiveFilterConfig`:

```python
preserve_skills: bool = True
```

- [ ] **Step 4: Run tests**

Run: `rtk pytest tests/test_selective_filter_skill_preserve.py tests/test_skill_preserve.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cutctx/transforms/selective_filter.py tests/test_selective_filter_skill_preserve.py
git commit -m "$(cat <<'EOF'
feat(compression): never drop skill-preserved messages in selective filter

EOF
)"
```

---

### Task 3: Wire skill-preserve into ContentRouter hot path

**Files:**
- Modify: `cutctx/transforms/content_router.py` (`ContentRouterConfig` + route entry)
- Modify: `tests/test_skill_preserve.py` or `tests/test_content_router_skill_preserve.py`

**Interfaces:**
- Consumes: `SkillPreserveConfig`, `annotate_messages_for_skill_preserve`
- Produces: `ContentRouterConfig.skill_preserve: bool = True`
- Protected messages must not be routed through aggressive log/search crushers that rewrite instruction text

- [ ] **Step 1: Write failing router test**

```python
from cutctx.transforms.content_router import ContentRouter, ContentRouterConfig


def test_skill_body_not_aggressively_crushed() -> None:
    skill = (
        "---\nname: cutctx\ndescription: compress bulky outputs\n---\n"
        + ("Rule: always call cutctx_retrieve before quoting.\n" * 40)
    )
    messages = [
        {"role": "system", "content": "Follow installed skills."},
        {"role": "user", "content": skill},
        {"role": "user", "content": "Summarize the build log:\n" + ("ERROR boom\n" * 200)},
    ]
    router = ContentRouter(ContentRouterConfig(skill_preserve=True))
    out = router.transform(messages)
    joined = "\n".join(
        m["content"] for m in out if isinstance(m, dict) and isinstance(m.get("content"), str)
    )
    assert "always call cutctx_retrieve before quoting" in joined
    assert "name: cutctx" in joined
```

- [ ] **Step 2: Run test expecting failure or missing config**

Run: `rtk pytest tests/test_content_router_skill_preserve.py -q`

Expected: FAIL (`skill_preserve` missing or skill text crushed).

- [ ] **Step 3: Minimal wiring**

1. Add `skill_preserve: bool = True` to `ContentRouterConfig`.
2. At start of transform/route, if enabled, run `annotate_messages_for_skill_preserve`.
3. When selecting a compressor for a message with `cutctx_skill_preserve`, use passthrough or the lightest safe path (no LogCompressor / SearchCompressor on that message).

- [ ] **Step 4: Run focused suites**

Run: `rtk pytest tests/test_content_router_skill_preserve.py tests/test_skill_preserve.py tests/test_selective_filter_skill_preserve.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cutctx/transforms/content_router.py tests/test_content_router_skill_preserve.py
git commit -m "$(cat <<'EOF'
feat(compression): honor skill_preserve in content router

EOF
)"
```

---

### Task 4: Wrap-time skill directory discovery

**Files:**
- Modify: provider wrap helpers under `cutctx/providers/` and/or `cutctx/cli/wrap.py`
- Create: `cutctx/transforms/skill_discovery.py`
- Create: `tests/test_skill_discovery.py`

**Interfaces:**
- Produces: `discover_skill_paths(home: Path | None = None) -> list[Path]`
- Produces: `load_skill_preserve_markers(paths: list[Path]) -> tuple[str, ...]`
- Wrap sets env `CUTCTX_SKILL_PRESERVE=1` and optional `CUTCTX_SKILL_MARKERS=...`

- [ ] **Step 1: Write failing discovery tests**

```python
from pathlib import Path

from cutctx.transforms.skill_discovery import discover_skill_paths, load_skill_preserve_markers


def test_discovers_claude_and_codex_skill_dirs(tmp_path: Path, monkeypatch) -> None:
    claude = tmp_path / ".claude" / "skills" / "db-safety"
    claude.mkdir(parents=True)
    (claude / "SKILL.md").write_text("---\nname: db-safety\ndescription: safe sql\n---\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path))
    paths = discover_skill_paths(home=tmp_path)
    assert any(p.name == "db-safety" for p in paths)
    markers = load_skill_preserve_markers(paths)
    assert any("db-safety" in m for m in markers)
```

- [ ] **Step 2: Run to verify fail**

Run: `rtk pytest tests/test_skill_discovery.py -q`

Expected: FAIL import/path missing.

- [ ] **Step 3: Implement discovery**

Search, in order, if present:

- `~/.claude/skills/*/SKILL.md`
- `~/.codex/skills/*/SKILL.md`
- project `.claude/skills/*/SKILL.md`
- project `.agents/skills/*/SKILL.md`

Return parent dirs; markers include skill `name:` values from front matter.

- [ ] **Step 4: Wire into wrap**

When `cutctx wrap <agent>` starts a session, call discovery and export:

```bash
CUTCTX_SKILL_PRESERVE=1
```

Proxy/config reads this to enable `ContentRouterConfig.skill_preserve`.

- [ ] **Step 5: Tests + commit**

Run: `rtk pytest tests/test_skill_discovery.py -q`

```bash
git add cutctx/transforms/skill_discovery.py cutctx/cli/wrap.py cutctx/providers tests/test_skill_discovery.py
git commit -m "$(cat <<'EOF'
feat(wrap): discover installed skills and enable skill_preserve

EOF
)"
```

---

### Task 5: Buyer-report honesty fields

**Files:**
- Modify: `cutctx/cli/report.py`
- Create: `tests/test_buyer_report_honesty.py`
- Modify: `README.md` (eligible-payload wording only)

**Interfaces:**
- Extends buyer JSON with:
  - `requests_total: int`
  - `requests_compressed: int`
  - `requests_bypassed_small: int`
  - `eligible_compression_rate: float`  # compressed / eligible
  - `all_traffic_compression_rate: float`  # compressed / total
  - `created_savings_tokens: int`
  - `observed_provider_cache_tokens: int`
- Text/markdown formats must print a one-line caveat:
  `Rates below are for eligible compressible payloads unless labeled all-traffic.`

- [ ] **Step 1: Write failing tests**

```python
from cutctx.cli.report import build_buyer_report_payload


def test_buyer_report_separates_eligible_and_all_traffic_rates() -> None:
    rows = [
        {"savings_by_source_tokens": {"cutctx_compression": 100}, "compressed": True, "bypassed_small": False},
        {"savings_by_source_tokens": {}, "compressed": False, "bypassed_small": True},
        {"savings_by_source_tokens": {"provider_prompt_cache": 50}, "compressed": False, "bypassed_small": False},
    ]
    payload = build_buyer_report_payload(rows)
    assert payload["requests_total"] == 3
    assert payload["requests_bypassed_small"] == 1
    assert payload["created_savings_tokens"] == 100
    assert payload["observed_provider_cache_tokens"] == 50
    assert "eligible" in payload["caveat"].lower()
```

If `build_buyer_report_payload` does not exist, extract it from `report_buyer` during implementation (YAGNI: only extract what the test needs).

- [ ] **Step 2: Run failing test**

Run: `rtk pytest tests/test_buyer_report_honesty.py -q`

Expected: FAIL missing helper/fields.

- [ ] **Step 3: Implement payload builder + wire CLI formats**

Keep existing by-source tables. Add the honesty fields and caveat string to text, markdown, and JSON outputs.

- [ ] **Step 4: Align README claim**

Replace any unqualified “60–95% on everything” phrasing with eligible-payload wording that points to `cutctx report buyer`.

Example README line:

```markdown
**Per-workload savings on eligible payloads** (tool outputs, logs, long RAG/code dumps): see `cutctx report buyer` for created vs observed attribution. Short prompts are often bypassed and must not be averaged into headline claims.
```

- [ ] **Step 5: Tests + commit**

Run: `rtk pytest tests/test_buyer_report_honesty.py -q`

```bash
git add cutctx/cli/report.py tests/test_buyer_report_honesty.py README.md
git commit -m "$(cat <<'EOF'
fix(report): expose eligible vs all-traffic savings honesty fields

EOF
)"
```

---

### Task 6: Publish progressive Cutctx skill + docs

**Files:**
- Modify: `plugins/cutctx-plugin/skills/cutctx/SKILL.md`
- Create or update: `docs/content/docs/skills.mdx` (or extend `mcp.mdx` + `cutctx-learn.mdx`)
- Modify: `docs/content/docs/meta.json` to include the page if created

**Interfaces:**
- Skill front matter keeps short `description` (one line)
- Body teaches: when to compress, when to retrieve, never invent savings, use `cutctx_stats`

- [ ] **Step 1: Rewrite skill for progressive disclosure**

Front matter:

```yaml
---
name: cutctx
description: Compress bulky tool outputs and retrieve originals by hash when exact detail is needed.
---
```

Body sections: Automatic Mode, Compress, Retrieve, Verify, Do Not.

- [ ] **Step 2: Add docs page section “Skill-aware compression”**

Document:

- `CUTCTX_SKILL_PRESERVE`
- what gets protected
- that tool outputs remain aggressively compressible

- [ ] **Step 3: Manual sanity check**

Run: `rtk read plugins/cutctx-plugin/skills/cutctx/SKILL.md`

Confirm description ≤ ~160 chars and body has retrieve discipline.

- [ ] **Step 4: Commit**

```bash
git add plugins/cutctx-plugin/skills/cutctx/SKILL.md docs/content/docs/
git commit -m "$(cat <<'EOF'
docs: package Cutctx as a progressive skill with preserve semantics

EOF
)"
```

---

### Task 7: Harness / claw GTM packaging

**Files:**
- Modify: `artifacts/value-proposition.md`
- Modify: `docs/content/docs/global-routing.mdx`
- Modify: `website/index.html` (one section only)
- Modify: `README.md` agent compatibility blurb if needed

**Interfaces:**
- No new runtime API required
- Narrative sentence (exact):
  `Cutctx is the local-first context control plane under your agent harnesses.`

- [ ] **Step 1: Update value proposition pillars**

Map pillars to:

1. Systems of context (compress + CCR + memory + receipts)
2. Harness substrate (wrap / global routing)
3. Skills + MCP
4. Attributed ROI
5. Local-first governance

- [ ] **Step 2: Add global-routing doc callout**

```markdown
## Why this matters

Agent harnesses change every six months. Cutctx stays underneath them as the shared context plane — compression, memory, routing, and receipts — so switching Claude Code, Codex, Cursor, or OpenCode does not mean re-buying context infrastructure.
```

- [ ] **Step 3: Website one section**

Add a single section near existing product story (not a new page unless needed) with the narrative sentence and links to wrap + global routing docs.

- [ ] **Step 4: Commit**

```bash
git add artifacts/value-proposition.md docs/content/docs/global-routing.mdx website/index.html README.md
git commit -m "$(cat <<'EOF'
docs: position Cutctx as the context plane under agent harnesses

EOF
)"
```

---

### Task 8: Receipts + firewall commercial packaging (P1)

**Files:**
- Modify: `docs/content/docs/proxy.mdx` (receipts buyer section)
- Modify: `docs/content/docs/architecture.mdx` or security docs
- Modify: `artifacts/value-proposition.md` objection handling
- Optional: `website/security/` copy only

**Interfaces:**
- Product already has decision receipts + `cutctx_scan`
- This task is packaging + verify Builder can scan without license

- [ ] **Step 1: Write a regression test that Builder can call scan path without entitlement**

```python
def test_firewall_scan_available_without_license() -> None:
    from cutctx.security.firewall import FirewallScanner

    findings = FirewallScanner().scan_text("SSN 111-22-3333")
    assert findings  # local regex firewall works offline without EE
```

- [ ] **Step 2: Run test**

Run: `rtk pytest tests/test_firewall_builder_available.py -q` (or existing firewall tests)

Expected: PASS after pointing at the real API.

- [ ] **Step 3: Docs copy**

Add buyer-facing mapping:

| AIE language | Cutctx surface |
|---|---|
| Agents need receipts | Decision receipts + `cutctx report buyer` |
| Permissions / provenance | Local firewall + audit (entitled) + CCR hashes |
| Verifiers are king | Thin compression/skill-survival evals (Task 9) |

- [ ] **Step 4: Commit**

```bash
git add docs/content/docs/ artifacts/value-proposition.md tests/
git commit -m "$(cat <<'EOF'
docs: map AIE receipts/security language to Cutctx surfaces

EOF
)"
```

---

### Task 9: Thin skill-survival + attribution evals (P1)

**Files:**
- Create: `cutctx/evals/skill_survival.py` (or under `tests/evals/`)
- Create: `tests/test_eval_skill_survival.py`
- Optional CLI hook in `cutctx/evals/` README only if a command already exists

**Interfaces:**
- Produces: `evaluate_skill_survival(compress_fn) -> dict` with `passed: bool`, `retained_rules: int`, `total_rules: int`
- Produces: attribution invariant check reusing buyer-report helper

- [ ] **Step 1: Failing eval test**

```python
from cutctx.evals.skill_survival import evaluate_skill_survival


def _identity_compress(messages):
    return messages


def test_skill_survival_eval_passes_on_identity() -> None:
    result = evaluate_skill_survival(_identity_compress)
    assert result["passed"] is True
    assert result["retained_rules"] == result["total_rules"]
```

- [ ] **Step 2: Run fail**

Run: `rtk pytest tests/test_eval_skill_survival.py -q`

Expected: FAIL missing module.

- [ ] **Step 3: Implement eval**

Build a fixture skill with N unique rule strings, pass through `compress_fn`, count how many rules remain. `passed` requires ≥ 95% retention when `skill_preserve` is on.

Add second function checking created vs observed tokens are not double-counted in a sample payload.

- [ ] **Step 4: Run + commit**

Run: `rtk pytest tests/test_eval_skill_survival.py tests/test_buyer_report_honesty.py -q`

```bash
git add cutctx/evals/skill_survival.py tests/test_eval_skill_survival.py
git commit -m "$(cat <<'EOF'
test: add thin skill-survival and attribution integrity evals

EOF
)"
```

---

### Task 10: End-to-end verification + scope freeze

**Files:**
- None new required
- Update this plan checkboxes as done

- [ ] **Step 1: Run the commercial integration suites**

Run:

```bash
rtk pytest \
  tests/test_skill_preserve.py \
  tests/test_selective_filter_skill_preserve.py \
  tests/test_content_router_skill_preserve.py \
  tests/test_skill_discovery.py \
  tests/test_buyer_report_honesty.py \
  tests/test_eval_skill_survival.py \
  tests/test_entitlement_request_path.py \
  -q
```

Expected: PASS

- [ ] **Step 2: Confirm out-of-scope not started**

Verify no new Neo4j core module, no Arize-like eval service, no new permission OS landed in the branch diff.

- [ ] **Step 3: Final commit if docs tweaks remain**

```bash
git status
git add docs/superpowers/plans/2026-07-27-aie-commercial-capability-integration.md
git commit -m "$(cat <<'EOF'
docs: add AIE commercial capability implementation plan

EOF
)"
```

---

## Spec coverage checklist

| Spec requirement | Task |
|---|---|
| Entitlement / commercial filter | Task 0 |
| Skill/instruction preservation | Tasks 1–3 |
| Wrap skill discovery | Task 4 |
| Honest ROI / eligible claims | Task 5 |
| Skills + MCP packaging | Task 6 |
| Harness / claw narrative | Task 7 |
| Security / receipts packaging | Task 8 |
| Thin evals | Task 9 |
| Graph / voice / RL out of scope | Task 10 freeze |
| Dual-path Builder UX | Tasks 0, 5, 8 |

## Suggested split if capacity is limited

1. **Plan A:** Tasks 0–5 (commercial honesty + skill preserve)  
2. **Plan B:** Tasks 6–7 (skills + harness GTM)  
3. **Plan C:** Tasks 8–9 (receipts packaging + thin evals)
