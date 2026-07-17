# Compression and Routing Verification Audit

**Date:** 2026-07-17  
**Scope:** Compression routing, code-body replacement safety, and model-routing capabilities visible in the current worktree.  
**Status:** Local verification record — not a release certification.

## Provenance and limits

The original remediation was committed in `c48fe63f`; this record is an
evidence-based audit, not a release certification. It does not attribute
unrelated worktree changes to the compression-routing remediation.

The previous version's aggregate test total, benchmark reductions/latencies, and competitor feature matrix had no commands, fixture definitions, revision identifiers, or primary-source citations. Those assertions are not retained as verified findings. They require a versioned benchmark harness and dated competitor research before use in product or sales material.

Run `python scripts/generate_audit_evidence.py` to produce the current local
inventory. The existing benchmark release workflow is documented in
[`benchmarks/README.md`](../benchmarks/README.md); it requires a clean checkout
and intentionally rejects stale fixture hashes. Competitor assertions are
governed by the [competitor evidence ledger](evidence/competitor-routing-compression-2026-07-17.md).

## Fresh verification

| Command | Result | What it establishes |
|---|---:|---|
| `uv run --no-sync python -m pytest tests/test_transforms/test_code_compressor.py::TestReplacementSizeGuard::test_short_omitted_suffix_does_not_expand_retained_function_body tests/test_transforms_content_detection.py::test_timestamped_logs_win_over_search_result_shape -q --tb=short` | 2 passed | The replacement-size and Python timestamp collision regressions pass. |
| `cargo test -p cutctx-core transforms::content_detector --lib --no-fail-fast` | 22 passed | Rust detector ordering, including the timestamp collision, passes. |
| `uv run --no-sync python -m pytest tests/test_model_router.py tests/test_model_routing_evals.py tests/test_model_routing_training.py tests/test_openai_responses_model_routing_shadow.py tests/test_anthropic_model_routing.py -q --tb=short` | 101 passed | Confidence gating, model-routing calibration, and sampled shadow evaluation have automated coverage. |
| `uv run --no-sync python -m pytest -q --tb=short` | 9,181 collected; completed successfully | Full Python suite, run serially. Python and Rust tests must not run concurrently because they share native-build state. |
| `cargo test --workspace --no-fail-fast` | completed successfully | Full Rust workspace suite, run serially after Python verification. |
| `python scripts/generate_benchmark_release_manifest.py` | completed for `c48fe63f` | The committed manifest binds fixture and environment metadata to the verified remediation revision. |

## Verified compression findings

### Fixed locally — replacement metadata can no longer expand a short omitted suffix

`CodeAwareCompressor` previously compared the explanatory replacement with the entire function body. A large retained prefix could therefore make a short omitted suffix appear profitable. Its omitted-statement collection also added the first over-budget statement twice, further overstating the source being replaced.

The implementation now builds the exact candidate replacement, compares it with the exact omitted statements rather than the whole function body, keeps the original omitted statements verbatim when the candidate is not shorter, and collects every omitted statement once.

The regression test uses a large retained assignment and two short omitted statements. It failed before the correction (`875 <= 874`) and passes now.

### Fixed locally — timestamped logs take precedence over grep-shaped text

An ISO timestamp such as `2025-01-01T10:00:00Z` includes the same colon-delimited prefix shape as a `file:line:` search result. Python and Rust detectors now check build/log output before search output. New tests assert the collision explicitly and classify it as `BUILD_OUTPUT` / `BuildOutput`.

## Verified routing capabilities and boundaries

The system has two different routing surfaces that must not be conflated.

| Surface | Verified capability | Boundary |
|---|---|---|
| Proxy model router | Confidence threshold gating, learned threshold artifacts, sampled provider shadow replays, persisted quality/cost evidence, and offline threshold recommendations. | Shadow mode is opt-in and evidence generation does not itself prove that an operator has promoted a policy to production. |
| Orchestration engine | Capability filtering, contract/policy governance, deterministic FASTEST/CHEAPEST/HIGHEST_QUALITY/BALANCED selection, fallbacks, and advisory quality-drift detection. | `BALANCED` remains a fixed reliability → latency → cost ordering; `OutcomeRecord` telemetry does not automatically change orchestration selection. |

Consequently, claims that the product has *no* confidence-based routing or *no* shadow-mode comparison are incorrect. A narrower claim is supported: the deterministic orchestration engine does not autonomously adapt its selected route from outcome telemetry.

## Evidence requirements before stronger product claims

The local mechanisms are complete: the benchmark manifest/bundle workflow,
audit inventory, dated competitor ledger, provider inventory, and architecture
inventory are all available and the remediation revision has a generated
manifest. For every future publishable claim, retain the resulting fixture
hashes, checkpoints, warmup/iteration/token-counter/quality-gate configuration,
and dated primary-source competitor evidence.

External evidence is intentionally still required before market claims: remote
hosted Python and TypeScript smoke runs, a staged gateway and dashboard, and
two valid partner snapshots. The evaluator reports this absence rather than
making an unsupported claim.

## Conclusion

The local fixes above have direct regression coverage. The compression and
routing subsystems have meaningful, verified capabilities, but industry-
leadership and market claims remain prohibited until the required external
evidence is collected.
