# Best-In-Class Release Plan

**Date:** 2026-06-29  
**Scope:** Remaining work after the latest dashboard/stats/Graphify hardening pass  
**Goal:** Turn Cutctx from "strong core with optional fallbacks" into a product that can honestly claim broad data-type coverage, reliable OSS-enhanced capabilities, and release readiness.

## Purpose

This document captures the remaining work in implementation-ready form:

- what is still blocking a "best in class" claim
- what is still blocking release readiness
- which issues are product/runtime defects vs packaging/environment defects
- the exact steps, acceptance criteria, and verification commands for each workstream

This is intentionally a **hold-implementation plan**. It should let a follow-on execution pass move fast without re-discovering the gaps.

## Current Verified State

Recent verification established:

- Dashboard savings math and attribution are materially improved.
- Graphify interceptor contract bug was fixed.
- Focused feature bundle passed:
  - `tests/test_graphify_index.py`
  - `tests/test_drain3_compressor.py`
  - `tests/test_difftastic_interceptor.py`
  - `tests/test_image_compression.py`
  - `tests/test_proxy_compress_endpoint.py`
  - `tests/test_product_capabilities.py`
- Broad result from the latest run:
  - `175 passed, 8 skipped`

Important interpretation:

- The **skips** are not noise. They show that some premium/OSS-derived capabilities still depend on optional extras or binaries that are not guaranteed present in a target environment.
- That is a release-readiness problem even when the fallback behavior is graceful.

## What Is Still Holding Us Back

## 1. Optional capability packaging is not yet "best-in-class ready"

### Problem

The codebase supports multiple advanced surfaces, but the current environment audit showed these missing:

- `graphifyy`
- `networkx`
- `drain3`
- `llmlingua`
- `PIL`

Meaning:

- Some "best" paths are not truly available by default.
- In practice, operators may think a feature is enabled because the UI/docs mention it, while runtime silently degrades or skips.

### Why this blocks release

- "Works with all kinds of data" is not defensible if advanced paths depend on extras that are not reliably installed.
- "Best in class" cannot mean "best when five optional packages are manually discovered and installed later."

### Remaining work

1. Decide the shipping model for advanced extras:
   - `core` only
   - `recommended`
   - `full best-in-class`
2. Define a supported default bundle for production:
   - knowledge graph
   - log ML
   - structural diff
   - multimodal image
   - optional llmlingua
3. Make install scripts and Docker images match the claim:
   - if a feature is advertised in enterprise/readiness docs, it must either:
     - be included in the default production image, or
     - be called out as optional and visibly unavailable at runtime
4. Add a release checklist that validates the image really contains:
   - Python extras
   - binary tools such as `difft`
5. Ensure docs name one canonical install command for the "full" feature set.

### Acceptance criteria

- A fresh "full production" environment has all premium extras available without ad hoc manual installs.
- `feature_availability` in `/stats` reports all targeted advanced features as available in the release image.
- The verification guide can be executed end to end on a fresh machine without undocumented dependency hunts.

## 2. Graphify is better, but not yet fully release-grade

### Problem

Graphify now has:

- better status exposure
- safer startup reasoning
- a repaired interceptor contract

But it still depends on optional packages and a build flow that can remain fragile across machines.

### Remaining risks

- `graphifyy` and `networkx` must both be available.
- Graph build correctness is still environment-sensitive.
- Index freshness/recovery is improved, but operator understanding still depends on reading low-level status.

### Remaining work

1. Package Graphify dependencies into the intended "full" environment.
2. Add a manual release test that proves:
   - the index builds from a non-trivial repo
   - `graph.json` is created
   - `/stats` reports `knowledge_graph.requested`, `available`, `active`, and `status` correctly
   - interceptor compression actually happens on large Read/Grep/Bash outputs
3. Add a dashboard/operator-facing visualization for Graphify availability:
   - requested
   - installed
   - building
   - ready
   - degraded
   - install/fix hint
4. Verify progressive disclosure behavior still works under repeated file reads.
5. Verify behavior on large but irrelevant outputs:
   - should pass through, not generate misleading graph summaries

### Acceptance criteria

- `tests/test_graphify_index.py` passes in the production image.
- A live proxy with `--knowledge-graph` produces a real graph and uses it in tool interception.
- Operators can diagnose Graphify availability from `/stats` or the dashboard without reading logs.

## 3. "All kinds of data" is still stronger for some data types than others

### Problem

Cutctx is strong on:

- logs
- diffs
- images
- generic tool output
- code-ish payloads

But the current repo signal is not equally strong for every claimed modality.

### Specific gap: audio

The product/docs claim audio compression, but the current audit did not find a similarly clear runtime/test surface for audio as exists for:

- image compression
- Graphify
- Drain3
- difftastic

This does **not** prove audio is absent everywhere, but it does prove the capability is not yet as operationally obvious or as easy to verify.

### Remaining work

1. Identify the canonical audio compression path in code.
2. If it exists:
   - add a focused test suite
   - add verification-guide steps
   - surface availability in runtime diagnostics
3. If it does not exist in a production-ready form:
   - either implement it
   - or soften docs/marketing until it is real
4. Build a modality matrix:
   - prose
   - code
   - logs
   - diffs
   - search output
   - JSON/tool schemas
   - images
   - audio
   - mixed multimodal request payloads
5. For each modality, define:
   - primary compressor
   - fallback path
   - required extra/binary
   - verification test

### Acceptance criteria

- Every externally claimed data type maps to a discoverable implementation path and a reproducible verification path.
- There is no claimed modality whose status is ambiguous.

## 4. OSS-derived capabilities work in code, but not all are operationally proven

### Problem

The repo includes or absorbs ideas from:

- Graphify
- Drain3
- difftastic
- LLMLingua
- Ponytail-style minimal build guidance
- provider/self-hosted cache attribution
- tool schema compaction
- API surface slimming

The biggest remaining issue is not "do these names exist in code?" It is:

- are they installed?
- are they selected?
- are they measurable?
- are they operator-visible when missing?

### Remaining work

1. Build a capability truth table for each integrated OSS feature:
   - code path exists
   - unit tests exist
   - integration tests exist
   - runtime dependency present in release image
   - `/stats` exposes availability
   - dashboard exposes status
2. Prioritize fixes for any feature that is:
   - documented
   - optional at runtime
   - silent when absent
3. Ensure every advanced feature has:
   - install hint
   - fallback note
   - explicit status surface
4. Add a single "advanced capability doctor" flow:
   - either CLI or documented `/stats` inspection
   - should summarize what is available vs degraded

### Acceptance criteria

- No major advertised advanced capability is "best effort only" without operator-visible state.
- A support engineer can answer "why didn’t feature X activate?" from one status surface.

## 5. Best-in-class claim still lacks benchmark and corpus breadth

### Problem

Current benchmark evidence is useful but not broad enough for an absolute market claim.

The present evidence supports:

- strong structured-data savings
- good image/tool/log/diff behavior
- a compelling feature set

It does **not** yet support:

- universal best compression ratio
- superiority across all corpora
- superiority across all data shapes and operating environments

### Remaining work

1. Define a benchmark matrix that matches the claim:
   - code
   - logs
   - diffs
   - search output
   - long tool schemas
   - multimodal/image
   - mixed agent transcripts
2. Compare against named alternatives on each relevant corpus.
3. Record both:
   - savings quality
   - reliability/activation rate
4. Track "feature available but not installed" as a benchmark disqualifier for release images.
5. Publish only claims supported by that matrix.

### Acceptance criteria

- Marketing claims are backed by a versioned benchmark report.
- Benchmarks include both savings and activation/reliability.

## 6. Release readiness still has documented non-compression gaps

### Problem

Prior audits still call out security/enterprise/readiness items that are larger than pure compression quality.

Examples already called out elsewhere in the repo include:

- enterprise memory/auth/audit gaps
- documentation drift
- packaging drift
- optional dependency ambiguity
- stale running-process verification risk

### Remaining work

1. Reconcile this plan with the latest production audit docs.
2. Build a short release gate:
   - security gates
   - capability gates
   - packaging gates
   - benchmark gates
3. Require live runtime verification after restart, not only file-level/test-level verification.
4. Confirm the release image and local dev environment do not diverge materially.

### Acceptance criteria

- Release readiness is assessed from the shipped artifact, not only the repo checkout.
- A stale proxy process cannot be confused with current-code verification in the signoff procedure.

## Recommended Execution Order

## Phase 1: Truth and packaging

1. Finalize the "full production" dependency bundle.
2. Ensure release image/install path includes the intended advanced extras.
3. Keep `/stats.feature_availability` as the operator truth surface.

## Phase 2: Graphify and advanced compressors

1. Complete Graphify live verification.
2. Validate Drain3 and difftastic in the actual release image.
3. Decide whether LLMLingua is a supported production feature or an optional experiment.

## Phase 3: Data modality completeness

1. Audit audio specifically.
2. Build and validate the modality matrix.
3. Remove or soften any claims that cannot be verified.

## Phase 4: Benchmarks and claims

1. Expand corpora.
2. Compare against competitors.
3. Publish constrained claims.

## Phase 5: Release gate

1. Run full release checklist on the built artifact.
2. Sign off only when packaging, runtime, and benchmarks agree.

## Verification Commands To Reuse

### Focused OSS/data-type bundle

```bash
pytest -q \
  tests/test_graphify_index.py \
  tests/test_drain3_compressor.py \
  tests/test_difftastic_interceptor.py \
  tests/test_image_compression.py \
  tests/test_proxy_compress_endpoint.py \
  tests/test_product_capabilities.py
```

### Dashboard/stats sanity

```bash
pytest -q \
  tests/test_proxy_dashboard_stats_cache.py \
  tests/test_proxy_compress_endpoint.py
```

### Runtime availability inspection

```bash
curl -s -H "x-cutctx-admin-key: $CUTCTX_ADMIN_API_KEY" \
  http://127.0.0.1:8787/stats | jq '.feature_availability'
```

### Graphify live status

```bash
curl -s -H "x-cutctx-admin-key: $CUTCTX_ADMIN_API_KEY" \
  http://127.0.0.1:8787/stats | jq '.knowledge_graph'
```

## Definition Of Done

Cutctx is ready for a stronger "best in class" and "release ready" statement only when all are true:

1. The release image includes the advanced capabilities we claim.
2. Optional feature absence is visible and explainable at runtime.
3. Graphify, Drain3, difftastic, image, and any claimed audio path are all reproducibly verifiable.
4. The dashboard and `/stats` tell the truth even in degraded environments.
5. Benchmarks support the exact wording of the external claim.
6. The signoff process uses live runtime verification after restart, not just static code state.

