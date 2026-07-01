# Implementation Plan: Close Remaining `audit/final-verdict.md` Items

**Date:** 2026-07-01
**Source:** `audit/final-verdict.md` (merged verdict 78/100, "PILOT RELEASE READY — defer marketing until P0 gaps close") plus a same-day, 3-agent verification pass and a Haiku-agent fix batch that closed most P0/P1 items. This plan closes what's left.
**Status:** 0/4 required phases complete. All facts below were re-verified directly against the current source tree on 2026-07-01 (not taken from memory) — file:line references are accurate as of that read.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Already Closed — Do Not Re-Implement](#2-already-closed--do-not-re-implement)
3. [Ground Rules for the Implementing Agent](#3-ground-rules-for-the-implementing-agent)
4. [Phase 1 (Required): `cutctx capabilities` visibility for the 3 moat features](#4-phase-1-required-cutctx-capabilities-visibility)
5. [Phase 2 (Required): Dashboard Feedback Loop panel](#5-phase-2-required-dashboard-feedback-loop-panel)
6. [Phase 3 (Required): Benchmark publication workflow](#6-phase-3-required-benchmark-publication-workflow)
7. [Phase 4 (Required): L-1 mitigation — bounded reachability cache](#7-phase-4-required-l-1-mitigation--bounded-reachability-cache)
8. [Phase 5 (Optional / stretch): top-level `cutctx benchmark` alias](#8-phase-5-optional--stretch-top-level-cutctx-benchmark-alias)
9. [Phase 6 (Not code — documented limitation only): opencode + Google routing](#9-phase-6-not-code--documented-limitation-only-opencode--google-routing)
10. [Dependency Map](#10-dependency-map)
11. [Risk Assessment](#11-risk-assessment)
12. [Full Verification Checklist](#12-full-verification-checklist)
13. [CHANGELOG Entries Required](#13-changelog-entries-required)
14. [Definition of Done](#14-definition-of-done)

---

## 1. Executive Summary

| # | Item | Audit source | Severity | Phase | Required? |
|---|------|--------------|----------|-------|-----------|
| 1 | `cutctx capabilities` doesn't list Feedback Loop / Stack Graphs / Benchmark CLI | Product Health §4, friction table | High | 1 | Yes |
| 2 | No dashboard panel for Feedback Loop | Product Health §4, friction table | Critical | 2 | Yes |
| 3 | No publication workflow for benchmark results | Product Health §4, friction table | High | 3 | Yes |
| 4 | L-1: `pre_compress_hook` synchronous O(symbols × files) BFS cost on request path | Security §2, L-1 | Low (perf) | 4 | Yes (mitigation, see caveat) |
| 5 | Benchmark CLI still nested under `evals` group, not a standalone top-level group | Product Health §4, P0 item 3 (alternate option) | High → mostly mitigated already | 5 | No, optional |
| 6 | opencode + Google model routing has no env-var fallback | Discovered this session, not in original audit | Low, single-user config | 6 | No — external, document only |

Everything else in the audit (H-1, H-2, H-3, M-1, L-2, L-3, L-4, `cutctx profile show`, README benchmark section, CHANGELOG entries, `cutctx stack-graph explain`, test-count verification) is **already closed and verified** — see §2. Re-verify, do not re-implement.

---

## 2. Already Closed — Do Not Re-Implement

Confirmed directly against source on 2026-07-01. If any of these checks fail when the implementing agent starts, stop and report — it means something regressed since this plan was written, which is a different problem from this plan's scope.

| Finding | Where it lives now | Verify with |
|---|---|---|
| H-1 (`extract_symbol_names` uncapped) | `cutctx/graph/reachability.py:65` — `return unique_symbols[:20]` | `grep -n "unique_symbols\[:20\]" cutctx/graph/reachability.py` |
| H-2 (`callers_of` O(N×E) regression risk) | `crates/cutctx-core/src/stack_graph/mod.rs:367-370` — early return if `node_count() > 5000` | `grep -n "node_count() > 5000" crates/cutctx-core/src/stack_graph/mod.rs` |
| H-3 (`set_protected_symbols` singleton leak) | `cutctx/transforms/code_compressor.py:951-963` — thread-local `_protected_symbols_local` | `grep -n "_protected_symbols_local" cutctx/transforms/code_compressor.py` |
| M-1 (`recommended_ratio` unbounded) | `cutctx/profiles.py:~117` — clamped via `_MAX_RECOMMENDED_RATIO` | `grep -n "_MAX_RECOMMENDED_RATIO" cutctx/profiles.py` |
| L-2 (`_strategy_to_content_type` silent fallback) | `cutctx/ccr/response_handler.py:28-46` — logs on `unknown` fallback | `grep -n "Unmapped compression strategy" cutctx/ccr/response_handler.py` |
| L-3 (hostname privacy) | `cutctx/telemetry/toin.py:~495` — documented, hash-only, already correct | `grep -n "machine_info" cutctx/telemetry/toin.py` |
| L-4 (`_anonymize_query_pattern` prose leak) | `cutctx/telemetry/toin.py:1010-1027` — `<prose>` fallback | `grep -n '"<prose>"' cutctx/telemetry/toin.py` |
| `cutctx profile show` (P0 item 1) | `cutctx/cli/profile.py` — top-level group via `cli/main.py` `_SIDE_EFFECT_COMMAND_MODULES["profile"]` | `.venv/bin/python3 -m cutctx.cli.main profile show --help` |
| `cutctx stack-graph explain` | `cutctx/cli/stack_graph.py:26-63` — already fully implemented | `.venv/bin/python3 -m cutctx.cli.main stack-graph explain --help` |
| README benchmark proof section (P0 item 2, 5) | `README.md` — real captured table + reproduce command using repeated `--dataset`/`--metrics` flags (not comma-separated) | `grep -n "Real output from the command above" README.md` |
| `evals` group relabel (P0 item 3, rename option) | `cutctx/cli/evals.py` group docstring | `.venv/bin/python3 -m cutctx.cli.main evals --help` |
| CHANGELOG `[Unreleased]` entries (P0 item 4) | `CHANGELOG.md:8-20` | `grep -n "Feedback Loop (Data Flywheel)" CHANGELOG.md` |
| `wiki/feedback-loop.md`, `wiki/benchmark-cli.md` | new wiki pages, spot-checked against source | `ls wiki/feedback-loop.md wiki/benchmark-cli.md` |
| `RELEASE_STATUS.md` accuracy | rewritten after catching a fabricated first draft | manual read — cross-check every named file path actually exists |
| `/stats` payload additions (`profile`, `content_router_overrides_count`) | `cutctx/proxy/server.py`, first `_build_stats_payload` (~line 3776) | `grep -n '"content_router_overrides_count"' cutctx/proxy/server.py` |
| Full test suite | 7608 passed, 0 failed, 244 skipped (316s) — this was a real run, not a claim | re-run per §12 |
| `cutctx wrap opencode` missing `ANTHROPIC_BASE_URL` | `cutctx/cli/wrap.py` (~line 3974) | `grep -n "ANTHROPIC_BASE_URL" cutctx/cli/wrap.py` |

---

## 3. Ground Rules for the Implementing Agent

These exist because a prior Haiku agent in this same remediation effort **fabricated fictional file paths, a fake SQLite backend, a fake BLEU metric, and a fake env var** while writing `RELEASE_STATUS.md`. It was caught only because the fabrication was cross-checked against independently-verified ground truth. Do not repeat that failure mode.

1. **Verify every fact before writing it down.** If you are about to claim a file, function, flag, or metric exists, `grep`/`Read` it first in *this* tree. Never extrapolate from a similar-sounding feature in a different file.
2. **Read before Edit.** Every file touched below must be read in full (or at minimum the exact region cited) immediately before editing it, even though this plan quotes line numbers — line numbers drift as the file changes across phases.
3. **No scope creep.** Do not "fix" adjacent things you notice while in a file (e.g. the pre-existing `install_hint` formatting quirk noted in Phase 1 — leave it, it is out of scope and not part of what was asked).
4. **No comments explaining what the code does.** Only comment on non-obvious *why* (e.g. why a cache key includes a generation counter). Match the existing terse style in each file.
5. **Run the exact verification command listed for each phase before moving to the next phase.** Do not batch all edits and verify once at the end — a failure in Phase 1 should not be discovered while debugging Phase 4.
6. **Do not auto-commit or auto-push from inside application code.** Phase 3 writes a docs file from a CLI command; it must not shell out to `git commit`. Committing the resulting diff is the developer's/agent's separate, explicit action after review — this matches this repo's existing git-safety norms.
7. **Python env is `.venv/bin/python3`**, not system `python3` (system python lacks pytest). Rust checks use `cargo check -p cutctx-core` from repo root.
8. **Click options declared `multiple=True` require repeated flags** (`--dataset a --dataset b`), not comma-separated values — this exact mistake was made twice already in this project's history. Any new CLI example you write must use repeated-flag syntax and must be tested by actually running it, not assumed correct.

---

## 4. Phase 1 (Required): `cutctx capabilities` visibility

**File:** `cutctx/cli/capabilities.py` (224 lines total, read in full first)

**Problem:** The `_FEATURES` list (lines 17-117) and `_check_feature` (lines 126-169) drive the `cutctx capabilities` table. None of the 3 moat features (Feedback Loop, Stack Graphs, Benchmark CLI) appear — confirmed by running `cutctx capabilities` and finding no matching rows. This is the audit's "High" severity Product-Health friction: a user running the showcase command sees 11 unrelated optional-dependency rows and nothing about the new features.

### 4.1 Generalize the `pass-through` branch to accept a custom reason

In `_check_feature` (around line 131-142), the `pass-through` branch currently hardcodes the reason string. Change it to allow a per-feature override, defaulting to the existing text so the current `audio` row is unaffected:

```python
if mode == "pass-through":
    return {
        "name": feature["name"],
        "label": feature["label"],
        "available": True,
        "missing_packages": [],
        "extra": feature["extra"],
        "critical": feature["critical"],
        "mode": "pass-through",
        "install_hint": None,
        "reason": feature.get("reason", "proxied unchanged; no token compression applied"),
    }
```

(Only the last line changes — `feature.get("reason", ...)` replaces the hardcoded literal.)

### 4.2 Add a `stack_graph` special case for accurate availability

`cutctx/graph/resolver.py:22-29` already exposes `stack_graph_available()`, which checks `from cutctx._core import StackGraphManager` specifically — more precise than a bare module-presence check (the `smart_crusher` row already checks `cutctx._core` for a *different* symbol, so reusing that generic check would be technically correct but less explicit). Add a special case next to the existing `knowledge_graph`/`llmlingua` special cases (currently lines 146-151):

```python
if str(feature.get("name")) == "stack_graph":
    from cutctx.graph.resolver import stack_graph_available
    main_ok = stack_graph_available()
```

### 4.3 Append 3 new entries to `_FEATURES`

Add after the existing `audio` entry (end of the list, before the closing `]` at line 117):

```python
    {
        "name": "feedback_loop",
        "label": "Feedback Loop (CompressionProfile)",
        "key_package": None,
        "extra": "built-in",
        "critical": False,
        "also_requires": [],
        "mode": "pass-through",
        "reason": "always on; run `cutctx profile show` to inspect the per-workspace profile",
    },
    {
        "name": "stack_graph",
        "label": "Stack Graphs (code reachability)",
        "key_package": "cutctx._core",
        "extra": "cutctx-ai (wheel)",
        "critical": False,
        "also_requires": [],
        "mode": "optional",
    },
    {
        "name": "benchmark_cli",
        "label": "Benchmark CLI (evals benchmark)",
        "key_package": None,
        "extra": "evals (only for --dataset longbench/squad/hotpotqa)",
        "critical": False,
        "also_requires": [],
        "mode": "pass-through",
        "reason": "run `cutctx evals benchmark --help`; tool_outputs dataset works with no extra installs",
    },
```

Do **not** try to fix the pre-existing `install_hint` formatting quirk where `smart_crusher`'s `extra="cutctx-ai (wheel)"` produces the nonsensical hint `pip install cutctx-ai[cutctx-ai (wheel)]` (line 167). The new `stack_graph` entry intentionally mirrors this exact existing pattern for consistency; fixing the underlying quirk is a separate, unrelated change and out of scope here.

### 4.4 Update the command docstring

`capabilities_cmd` docstring (lines 175-179) currently lists only the original 11 features. Extend the "Covers:" line to mention the 3 new ones, e.g. append `, feedback-loop, stack-graph, and benchmark-cli` — verify the final docstring text actually matches the final `_FEATURES` list content (no drift).

### 4.5 Verify

```bash
.venv/bin/python3 -m cutctx.cli.main capabilities | grep -E "Feedback Loop|Stack Graphs|Benchmark CLI"
```
Expect 3 rows. Then:
```bash
.venv/bin/python3 -m cutctx.cli.main capabilities --json | .venv/bin/python3 -c "import json,sys; rows=json.load(sys.stdin); assert {'feedback_loop','stack_graph','benchmark_cli'} <= {r['name'] for r in rows}"
```
No output / exit 0 means pass. Also run the full existing capabilities test file if one exists (`find tests -iname "*capabilit*"`) and the targeted pytest subset in §12.

---

## 5. Phase 2 (Required): Dashboard Feedback Loop panel

**File:** `cutctx/dashboard/templates/dashboard.html` (2556 lines, Alpine.js + Tailwind, no build step — this is the always-available fallback template served by `get_dashboard_html()` in `cutctx/dashboard/__init__.py` when the React bundle isn't mounted)

**Problem:** Audit friction table: "Dashboard → see feedback loop: No page: Critical." The `/stats` endpoint (`cutctx/proxy/server.py`, `_build_stats_payload`) already returns `stats.profile` (a `CompressionProfile.summary()` dict — see shape below) and `stats.content_router_overrides_count` (an int) as of this session's fix. Nothing in the dashboard renders them.

### 5.1 Exact shape of `stats.profile` (from `cutctx/profiles.py`, `CompressionProfile.summary()`)

```json
{
  "workspace_hash": "abc123...",
  "total_content_types": 4,
  "total_compressions": 812,
  "total_retrievals": 340,
  "overall_retrieval_rate": 0.4187,
  "stats_by_type": {
    "code": {
      "sessions_seen": 12,
      "total_compressions": 300,
      "retrieval_rate": 0.51,
      "avg_compression_ratio": 0.62,
      "recommended_ratio": 0.75
    }
  }
}
```
`stats.profile` is `null` if the profile hasn't loaded (e.g. proxy just started, no workspace history yet) — the panel must handle that.

### 5.2 Insertion point

Insert a new `<template x-if="...">` block immediately after the "Savings by Provider" block ends and immediately before the `<!-- Anthropic Subscription Window -->` comment. Read the file around that boundary first to confirm exact current line numbers (they will have shifted from the following reference, taken 2026-07-01): the "Savings by provider" block's closing `</template>` is followed by a blank line, then `<!-- Anthropic Subscription Window -->`.

### 5.3 New panel markup

Follow the exact same conventions already used by every other panel in this file (`bg-surface rounded-lg p-4 border border-border mb-6` wrapper, `text-sm font-medium text-gray-300 mb-3` section title, `tabular-nums` on numeric spans, `formatNumber`/`.toFixed()` helpers already defined elsewhere in this file's `<script>` — do not redefine them):

```html
<!-- Feedback Loop / Compression Profile -->
<template x-if="stats.profile">
    <div class="bg-surface rounded-lg p-4 border border-border mb-6">
        <div class="flex justify-between items-center mb-3">
            <div class="text-sm font-medium text-gray-300">Feedback Loop (Compression Profile)</div>
            <div class="text-xs text-gray-500" x-text="'workspace ' + (stats.profile.workspace_hash || '').slice(0, 8)"></div>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
            <div>
                <div class="text-xl font-light tabular-nums text-accent" x-text="formatNumber(stats.profile.total_compressions || 0)"></div>
                <div class="text-xs text-gray-500">Compressions</div>
            </div>
            <div>
                <div class="text-xl font-light tabular-nums text-emerald-400" x-text="formatNumber(stats.profile.total_retrievals || 0)"></div>
                <div class="text-xs text-gray-500">CCR Retrievals</div>
            </div>
            <div>
                <div class="text-xl font-light tabular-nums" x-text="((stats.profile.overall_retrieval_rate || 0) * 100).toFixed(1) + '%'"></div>
                <div class="text-xs text-gray-500">Retrieval Rate</div>
            </div>
            <div>
                <div class="text-xl font-light tabular-nums" x-text="formatNumber(stats.content_router_overrides_count || 0)"></div>
                <div class="text-xs text-gray-500">Router Overrides Active</div>
            </div>
        </div>
        <template x-if="stats.profile.stats_by_type && Object.keys(stats.profile.stats_by_type).length > 0">
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                <template x-for="(typeStat, typeName) in stats.profile.stats_by_type" :key="typeName">
                    <div class="border border-border rounded p-3">
                        <div class="text-sm font-medium text-gray-300 capitalize" x-text="typeName"></div>
                        <div class="text-xs text-gray-500 mt-1">
                            Recommended ratio: <span class="tabular-nums text-cyan-300" x-text="(typeStat.recommended_ratio || 0).toFixed(2)"></span>
                        </div>
                        <div class="text-xs text-gray-500">
                            Retrieval rate: <span class="tabular-nums" x-text="((typeStat.retrieval_rate || 0) * 100).toFixed(1) + '%'"></span>
                        </div>
                    </div>
                </template>
            </div>
        </template>
        <div class="mt-3 text-xs text-gray-500">
            Adapts per-content-type compression aggressiveness based on how often compressed content gets retrieved back via CCR. See `cutctx profile show` for the CLI view.
        </div>
    </div>
</template>
<template x-if="!stats.profile">
    <div class="bg-surface rounded-lg p-4 border border-border mb-6">
        <div class="text-sm font-medium text-gray-300 mb-1">Feedback Loop (Compression Profile)</div>
        <div class="text-xs text-gray-500">No profile data yet for this workspace — run a few compressions through the proxy, then refresh.</div>
    </div>
</template>
```

### 5.4 Verify

- No build step exists for this file (it's a static template read at request time), so verification is functional, not a compile step:
  1. Start the proxy locally (`.venv/bin/python3 -m cutctx.cli.main proxy` or the existing dev-server invocation used elsewhere in this repo).
  2. `curl localhost:<port>/stats | python3 -m json.tool | grep -A5 '"profile"'` — confirm the field is present in the live response (it was added earlier this session; confirm it survived).
  3. Open the dashboard in a real browser (or `curl` the HTML and grep for `Feedback Loop (Compression Profile)` to confirm the markup landed), and visually confirm the panel renders with either real numbers or the "no profile data yet" fallback — do not just grep the source, actually load it once as the CLAUDE.md UI-testing rule requires.
- Check for any existing dashboard HTML snapshot/lint tests (`grep -rl "dashboard.html" tests/`) and run them.

---

## 6. Phase 3 (Required): Benchmark publication workflow

**Files:** `cutctx/cli/evals.py` (benchmark command starts at `@evals.command("benchmark")`, currently ~line 718; core logic in `_run_benchmark`, currently ~line 826), `docs/benchmarks.md` (93 lines, pre-existing, unrelated older benchmark doc using a different `benchmarks/run_all.py` script — reuse its existing convention of dated `##` sections rather than inventing a new file).

**Problem:** Audit friction table: "Publish benchmark results: JSON/MD only, no workflow: High." Today `cutctx evals benchmark --markdown` writes a local `benchmark_results.md` (or `<output>.md`) and stops. There is no repeatable way to get a result into a durable, shareable location.

**Scope decision:** Do not build hosting/CI infrastructure that doesn't exist in this repo. The concrete, minimal fix: a `--publish` flag that appends a dated section to the existing `docs/benchmarks.md` (idempotent per calendar day — re-running `--publish` today replaces today's section rather than duplicating it). This gives a durable, versioned (via normal git history), reviewable publication trail without inventing a fake pipeline.

### 6.1 Add the CLI option

In the `@evals.command("benchmark")` decorator stack, add after the existing `--seed` option:

```python
@click.option(
    "--publish",
    is_flag=True,
    default=False,
    help="Append this run's results to docs/benchmarks.md (idempotent per day).",
)
```

Add `publish: bool` to the `benchmark(...)` function signature and thread it into the existing `_run_benchmark(...)` call (matching how `seed` is already threaded).

### 6.2 Thread through `_run_benchmark`

Add `publish: bool` to `_run_benchmark`'s signature. After the existing markdown-save block (currently):
```python
    # Save markdown
    if markdown or output:
        md_path = str(Path(output).with_suffix(".md")) if output else "benchmark_results.md"
        if markdown:
            md_content = _build_markdown_report(final, metrics)
            Path(md_path).write_text(md_content, encoding="utf-8")
            click.echo(f"Markdown saved to: {md_path}")
```
add:
```python
    # Publish: append a dated section to docs/benchmarks.md
    if publish:
        publish_content = md_content if markdown else _build_markdown_report(final, metrics)
        _publish_benchmark_results(
            publish_content,
            seed=seed,
            datasets=all_datasets,
            compressors=selected_compressors,
        )
```
(`md_content` is only defined inside the `if markdown:` branch above — the `if markdown else` fallback in the new block re-generates it via `_build_markdown_report` if the user passed `--publish` without `--markdown`, so `--publish` works standalone.)

### 6.3 New helper function

Add near the other module-level helpers in `evals.py` (next to `_build_markdown_report`):

```python
def _publish_benchmark_results(
    md_content: str,
    *,
    seed: int,
    datasets: list[str],
    compressors: list[str],
) -> None:
    """Append a dated cutctx evals benchmark run to docs/benchmarks.md.

    Idempotent per calendar day: re-running --publish the same day
    replaces that day's section instead of duplicating it.
    """
    from datetime import date

    docs_path = Path(__file__).resolve().parents[2] / "docs" / "benchmarks.md"
    today = date.today().isoformat()
    heading = f"## `cutctx evals benchmark` — {today}"
    section = (
        f"{heading}\n\n"
        f"Datasets: {', '.join(datasets)} · Compressors: {', '.join(compressors)} · Seed: {seed}\n\n"
        f"{md_content}\n"
    )
    existing = docs_path.read_text(encoding="utf-8") if docs_path.exists() else "# Cutctx Benchmarks\n"
    if heading in existing:
        before, _, after = existing.partition(heading)
        next_idx = after.find("\n## ", 1)
        rest = after[next_idx:] if next_idx != -1 else ""
        existing = before + section + rest
    else:
        existing = existing.rstrip("\n") + "\n\n" + section
    docs_path.write_text(existing, encoding="utf-8")
    click.echo(f"Published results to: {docs_path}")
```

Double-check `Path(__file__).resolve().parents[2]` actually resolves to the repo root from `cutctx/cli/evals.py` (parents[0]=`cli`, [1]=`cutctx`, [2]=repo root) — verify with a one-line `python3 -c` check before relying on it, since an off-by-one here silently writes the file to the wrong place.

Explicitly do **not** add any `git commit`/`git push`/`subprocess.run(["git", ...])` call inside this function — see Ground Rule 6. It only writes a file.

### 6.4 Verify

```bash
.venv/bin/python3 -m cutctx.cli.main evals benchmark --dataset tool_outputs --n 5 --publish
grep -n "cutctx evals benchmark" docs/benchmarks.md   # confirm the new section landed
git diff --stat docs/benchmarks.md                    # confirm only this file changed, no git actions were taken automatically
```
Then run it a second time on the same day and confirm `docs/benchmarks.md` gained no duplicate heading (`grep -c` for the exact heading string should stay at 1).

---

## 7. Phase 4 (Required): L-1 mitigation — bounded reachability cache

**Files:** `cutctx/graph/resolver.py` (`StackGraphResolver`, currently lines 40-161), `cutctx/graph/reachability.py` (`resolve_entry_points`, currently lines 68-127)

**Problem (audit L-1, exact text):** "`pre_compress_hook` runs synchronously in the request hot path; for 1000-file index, ~1000 BFS calls per request." Traced this session to `resolve_entry_points` (`cutctx/graph/reachability.py:99-122`): for every extracted symbol (capped at 20 by the already-fixed H-1), it linearly scans **every** indexed file and calls `resolver._inner.reachable_definitions(file, symbol, max_depth)` — a Rust BFS — once per file. Worst case is now bounded to `20 × file_count` per request (better than pre-H-1's unbounded symbol count, but still expensive on a cold cache, and every request re-does this from scratch even when the index hasn't changed and the same symbol was just queried moments ago).

**Honest scope statement (put this in the commit/PR description, do not overclaim):** This is a *mitigation*, not a full fix. It caches repeated `(resolver, symbol, max_depth)` lookups so that requests reusing the same context/query pay the BFS cost once instead of every request. It does **not** reduce the cold-cache, first-ever-query cost, which remains `O(symbols × files)`. A full fix would move the file scan into Rust as a symbol→file inverted index built at index time (`StackGraphManager`), which is a larger PyO3 + Rust change and is explicitly **out of scope** for this plan — leave it as a documented follow-up, do not attempt it here.

### 7.1 Add a generation counter to `StackGraphResolver`

In `__init__` (currently line 40-49), after `self._indexed_paths: set[str] = set()`:
```python
        self._generation: int = 0
```

In `index_file` (currently lines 51-78), immediately after the line `self._indexed_paths.add(path_str)` inside the `try` block (currently line 74):
```python
            self._indexed_paths.add(path_str)
            self._generation += 1
```

In `reindex_file` (currently lines 80-111), immediately after its own `self._indexed_paths.add(path_str)` (currently line 107):
```python
            self._indexed_paths.add(path_str)
            self._generation += 1
```

`index_project` calls `self.index_file(...)` internally per file, so it needs no separate change — the counter increments once per successfully indexed file, which is fine (an over-approximation of "did anything change" is safe; it only affects cache-hit rate, never correctness).

Add a property next to the existing `indexed_paths` property (currently lines 155-157):
```python
    @property
    def generation(self) -> int:
        """Monotonic counter bumped on every successful index/reindex.

        Used by cutctx.graph.reachability to invalidate its per-symbol
        BFS cache when the underlying index changes.
        """
        return self._generation
```

### 7.2 Add a bounded cache in `resolve_entry_points`

In `cutctx/graph/reachability.py`, add near the top of the file (after existing imports):
```python
from functools import lru_cache

_REACHABILITY_CACHE_SIZE = 512


@lru_cache(maxsize=_REACHABILITY_CACHE_SIZE)
def _cached_reachable_for_symbol(
    resolver: Any,
    generation: int,
    symbol: str,
    max_depth: int,
) -> tuple[dict[str, Any], ...]:
    reachable: list[dict[str, Any]] = []
    for file_path in getattr(resolver, "indexed_paths", set()):
        try:
            result = resolver._inner.reachable_definitions(str(file_path), symbol, max_depth)
            if result:
                reachable.extend(result)
        except Exception:
            continue
    return tuple(reachable)
```
(`resolver` is hashable by default identity — `StackGraphResolver` does not override `__hash__`/`__eq__` — so using it directly as an `lru_cache` key is safe. `generation` in the key means any successful re-index invalidates the cache for that resolver automatically, without needing explicit cache-clearing logic.)

Then rewrite the body of `resolve_entry_points`'s main loop (currently lines 99-122):

Before:
```python
    for symbol in symbols:
        reachable: list[dict[str, Any]] = []
        indexed_paths: set[str] = getattr(resolver, "indexed_paths", set())
        if not indexed_paths:
            continue
        for file_path in indexed_paths:
            try:
                result = resolver._inner.reachable_definitions(
                    str(file_path), symbol, max_depth
                )
                if result:
                    reachable.extend(result)
                    protected.add(symbol)
                    for ref in result:
                        name = ref.get("symbol_name", "")
                        if name:
                            protected.add(name)
            except Exception:
                continue
        report[symbol] = reachable
```

After:
```python
    generation = getattr(resolver, "generation", 0)
    for symbol in symbols:
        indexed_paths: set[str] = getattr(resolver, "indexed_paths", set())
        if not indexed_paths:
            continue
        reachable = list(_cached_reachable_for_symbol(resolver, generation, symbol, max_depth))
        if reachable:
            protected.add(symbol)
            for ref in reachable:
                name = ref.get("symbol_name", "")
                if name:
                    protected.add(name)
        report[symbol] = reachable
```

This preserves every existing behavior (including `test_resolve_exception_handled`'s expectation that a per-file exception is swallowed and contributes nothing — the `try/except` moved inside `_cached_reachable_for_symbol` but is otherwise identical).

### 7.3 New tests

Add to `tests/test_stack_graph_reachability.py`, inside `class TestResolveEntryPoints` (existing tests use `unittest.mock.MagicMock` for the resolver — follow that exact pattern):

```python
    def test_repeated_lookup_uses_cache(self) -> None:
        """A second call with the same resolver/generation/symbol hits the cache."""
        mock = MagicMock()
        mock._inner = MagicMock()
        mock.indexed_paths = {"/src/app.py"}
        mock.generation = 1
        mock._inner.reachable_definitions.return_value = [
            {"target_file": "/src/app.py", "symbol_name": "validate_input"},
        ]

        resolve_entry_points(mock, "debug `process_payment`", max_depth=5)
        resolve_entry_points(mock, "debug `process_payment`", max_depth=5)

        assert mock._inner.reachable_definitions.call_count == 1

    def test_reindex_invalidates_cache(self) -> None:
        """Bumping generation (simulating a re-index) forces a fresh lookup."""
        mock = MagicMock()
        mock._inner = MagicMock()
        mock.indexed_paths = {"/src/app.py"}
        mock.generation = 1
        mock._inner.reachable_definitions.return_value = [
            {"target_file": "/src/app.py", "symbol_name": "validate_input"},
        ]

        resolve_entry_points(mock, "debug `process_payment`", max_depth=5)
        mock.generation = 2
        resolve_entry_points(mock, "debug `process_payment`", max_depth=5)

        assert mock._inner.reachable_definitions.call_count == 2
```
Note: since `lru_cache` is process-global and persists across test functions, and each test creates a fresh `MagicMock()` instance (a distinct hashable identity every time), there is no cross-test pollution — but if flakiness is observed, add a `_cached_reachable_for_symbol.cache_clear()` call in a `setup_method`/fixture as a defensive measure.

### 7.4 Verify

```bash
cargo check -p cutctx-core   # unaffected by this phase, but confirms nothing else broke
.venv/bin/python3 -m pytest tests/test_stack_graph_reachability.py tests/test_initiative2_e2e.py -v
```
All existing tests plus the 2 new ones must pass. Then re-run the full suite per §12 to confirm no regression elsewhere (`resolver.generation` is a new attribute; grep for any other code that might iterate `vars(resolver)` or serialize the resolver and could be surprised by the new attribute — unlikely, but check).

---

## 8. Phase 5 (Optional / stretch): top-level `cutctx benchmark` alias

**Not required.** The audit's P0 item 3 offered two acceptable remedies: rename the `evals` group label (**already done**, confirmed via `cutctx evals --help`), *or* split benchmark into a separate top-level group. Only the first was done. If there's appetite to also close the friction-table row "`cutctx --help` → find benchmark CLI: Hidden under misleading group: High" more completely, do this — otherwise skip.

In `cutctx/cli/evals.py`, after the `benchmark` command function is fully defined, add:
```python
main.add_command(benchmark, name="benchmark")
```
(`main` is already imported via `from .main import main` at the top of the file.)

In `cutctx/cli/main.py`, add `"benchmark": "evals"` to `_SIDE_EFFECT_COMMAND_MODULES` (currently lines 16-38) so the lazy-loader knows importing the `evals` module registers a top-level `benchmark` command too.

Verify: `.venv/bin/python3 -m cutctx.cli.main benchmark --help` shows the same help as `.venv/bin/python3 -m cutctx.cli.main evals benchmark --help`, and the old form still works (backward compatible, purely additive alias).

---

## 9. Phase 6 (Not code — documented limitation only): opencode + Google routing

**Not part of this repo's fix surface.** Confirmed this session via source-level inspection of the installed `opencode` binary: its Google/Vertex provider factory only reads `X.baseURL` from `opencode.json` config, with no `environmentVariableName` fallback (unlike its OpenAI and Anthropic providers, both of which cutctx already routes correctly via `OPENAI_BASE_URL`/`ANTHROPIC_BASE_URL` after this session's fix to `cutctx/cli/wrap.py`).

If this needs closing, it requires a **user-machine-local** `opencode.json` edit (at `~/.config/opencode/opencode.json`) adding a `baseURL` override for the Google provider pointed at the local cutctx proxy port — not a change to this repository. Do not attempt to script an edit to a file outside this repo as part of implementing this plan; if the user wants that automated, that is a distinct, separate task requiring its own explicit approval (it would modify machine-local config outside version control).

---

## 10. Dependency Map

| Phase | Depends on | Blocks |
|---|---|---|
| 1 (capabilities) | none | none |
| 2 (dashboard) | Phase-independent; only depends on already-shipped `/stats` fields (`profile`, `content_router_overrides_count`) — verify those still exist before starting | none |
| 3 (publish) | none | none |
| 4 (L-1 cache) | none | none |
| 5 (optional alias) | Phase 3 not required, but touches the same `evals.py` file — do Phase 3 first to avoid a merge/diff conflict in the same file | none |
| 6 (opencode) | none (external) | none |

Phases 1-4 touch disjoint files (`capabilities.py`, `dashboard.html`, `evals.py`, `resolver.py`+`reachability.py`) and can be done in any order or in parallel by independent agents. Phase 5, if attempted, must come after Phase 3 since both edit `evals.py`.

---

## 11. Risk Assessment

| Risk | Phase | Mitigation |
|---|---|---|
| Fabricated facts in docs/help text (recurred once already this effort) | 1, 3 | Ground Rule 1 — grep/Read every claim before writing it |
| `lru_cache` holding a strong reference to `resolver`, preventing GC | 4 | Acceptable: `stack_graph_resolver` is already a long-lived singleton on the proxy instance; cache is bounded to 512 entries regardless |
| `--publish` writing to the wrong path due to `parents[2]` off-by-one | 3 | Verify path resolution with a standalone one-liner before relying on it (spec'd in §6.3) |
| Dashboard panel breaking Alpine.js rendering if `stats.profile` is `null` on a cold proxy | 2 | Both the `x-if="stats.profile"` and `x-if="!stats.profile"` branches are specified — test both states |
| New `_FEATURES` entries changing exit-code behavior of `cutctx capabilities --json` (used potentially by external health checks) | 1 | All 3 new entries use `"critical": False`, so they cannot flip the command's exit code from 0→1 |
| Editing `evals.py` twice (Phase 3 + optional Phase 5) causing a diff conflict if done out of order | 3, 5 | Dependency map above — do Phase 3 first |

---

## 12. Full Verification Checklist

Run after **all** required phases (1-4) are complete, in this order:

1. `cargo check -p cutctx-core` — exit 0 (confirms Phase 4 didn't touch Rust incorrectly; it shouldn't have touched Rust at all, but this is a cheap sanity check).
2. Targeted subset:
   ```bash
   .venv/bin/python3 -m pytest -q tests/test_stack_graph_reachability.py tests/test_initiative2_e2e.py tests/test_feedback_loop.py tests/test_evals_benchmark.py
   ```
   Expect all passing, including the 2 new tests from §7.3.
3. Any capabilities-specific test file found via `find tests -iname "*capabilit*"`.
4. Any dashboard-specific test file found via `grep -rl "dashboard.html\|get_dashboard_html" tests/`.
5. Full suite:
   ```bash
   .venv/bin/python3 -m pytest -q
   ```
   Baseline from this session was **7608 passed, 0 failed, 244 skipped**. The number of passed tests should increase by exactly the number of new tests added in §7.3 (and any added for Phases 1-3 if the agent chooses to add them — not strictly required by this plan but encouraged for Phase 1's `_check_feature` special case). Zero new failures, zero new skips introduced by these changes.
6. Manual CLI smoke test (do not just grep source — actually run each):
   ```bash
   .venv/bin/python3 -m cutctx.cli.main capabilities
   .venv/bin/python3 -m cutctx.cli.main evals benchmark --dataset tool_outputs --n 5 --markdown --publish
   .venv/bin/python3 -m cutctx.cli.main profile show
   .venv/bin/python3 -m cutctx.cli.main stack-graph explain "test query"
   ```
7. Dashboard: start the proxy, load the dashboard in a real browser (per CLAUDE.md's UI-testing rule — do not claim success without doing this), confirm the Feedback Loop panel renders in both the "has data" and "no data yet" states.
8. `git status` / `git diff --stat` — confirm only the files named in this plan changed, nothing unexpected (e.g. no accidental `docs/benchmarks.md` corruption from Phase 3's idempotency logic, no stray files).

---

## 13. CHANGELOG Entries Required

Add to `CHANGELOG.md`'s existing `[Unreleased]` → `### Added` section (do not create a new `[Unreleased]` heading, one already exists at line 8):

```markdown
- **Capabilities visibility for moat features** (`cutctx/cli/capabilities.py`) — `cutctx capabilities` now reports Feedback Loop, Stack Graphs, and Benchmark CLI availability alongside the existing optional-dependency checks.
- **Dashboard Feedback Loop panel** (`cutctx/dashboard/templates/dashboard.html`) — the fallback dashboard now surfaces per-workspace `CompressionProfile` stats (compressions, retrievals, retrieval rate, per-content-type recommended ratios) via the existing `/stats` `profile` field.
- **Benchmark result publication** (`cutctx evals benchmark --publish`) — appends a dated results section to `docs/benchmarks.md`, idempotent per calendar day.
- **Bounded reachability cache** (`cutctx/graph/reachability.py`, `cutctx/graph/resolver.py`) — mitigates L-1 (synchronous per-request BFS cost) by caching per-symbol stack-graph lookups, invalidated automatically on re-index via a new `StackGraphResolver.generation` counter.
```

If Phase 5 is also done, add:
```markdown
- **Top-level `cutctx benchmark` alias** — `cutctx evals benchmark` is now also reachable as `cutctx benchmark` for discoverability; both forms are equivalent.
```

---

## 14. Definition of Done

- [ ] Phase 1: `cutctx capabilities` lists all 3 moat features; `--json` output includes them; docstring matches; targeted + full test suite green.
- [ ] Phase 2: Dashboard renders the Feedback Loop panel in both data and no-data states, verified in an actual browser, not just by reading source.
- [ ] Phase 3: `--publish` flag exists, writes/updates `docs/benchmarks.md` idempotently per day, does not perform any git operations itself.
- [ ] Phase 4: `StackGraphResolver.generation` exists and increments correctly; `resolve_entry_points` caches repeated lookups; 2 new tests pass; full suite still 0 failures.
- [ ] §12 full verification checklist run end-to-end with a clean result.
- [ ] §13 CHANGELOG entries added.
- [ ] This plan's "Status" line at the top updated from "0/4 required phases complete" to reflect actual completion, and any deviations from the spec (e.g. a phase implemented differently than written here) noted inline with the reason.

