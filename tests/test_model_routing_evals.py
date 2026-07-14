from __future__ import annotations

import json

import anyio
import pytest

from benchmarks.model_routing_calibrate import evaluate
from cutctx.proxy.model_routing_evals import (
    ModelRoutingEvalRecord,
    ModelRoutingEvalStore,
    build_model_routing_evidence_report,
    build_quality_cost_frontier,
    build_segmented_recommendations,
    maybe_run_model_routing_shadow,
    model_routing_shadow_enabled_from_env,
    model_routing_shadow_sample_rate_from_env,
    prompt_fingerprint,
    recommend_confidence_threshold,
    record_model_routing_comparison,
    sanitize_routing_segments,
    schedule_model_routing_shadow,
    should_sample_model_routing_shadow,
)


def _record(
    request_id: str,
    confidence: float,
    quality: float,
    savings: float,
) -> ModelRoutingEvalRecord:
    return ModelRoutingEvalRecord(
        request_id=request_id,
        prompt_hash="a" * 64,
        source_model="gpt-strong",
        candidate_model="gpt-mini",
        scorer="test",
        confidence=confidence,
        quality_score=quality,
        source_cost_usd=1.0,
        candidate_cost_usd=1.0 - savings,
    )


def test_shadow_sampling_is_stable_and_bounded() -> None:
    first = should_sample_model_routing_shadow("request-42", 0.37)
    assert should_sample_model_routing_shadow("request-42", 0.37) is first
    assert should_sample_model_routing_shadow("request-42", 0.0) is False
    assert should_sample_model_routing_shadow("request-42", 1.0) is True
    assert should_sample_model_routing_shadow("", 1.0) is False


def test_shadow_env_defaults_off_and_clamps_sample_rate(monkeypatch) -> None:
    monkeypatch.delenv("CUTCTX_MODEL_ROUTING_SHADOW_MODE", raising=False)
    monkeypatch.delenv("CUTCTX_MODEL_ROUTING_SHADOW_SAMPLE_RATE", raising=False)
    assert model_routing_shadow_enabled_from_env() is False
    assert model_routing_shadow_sample_rate_from_env() == 0.0

    monkeypatch.setenv("CUTCTX_MODEL_ROUTING_SHADOW_MODE", "true")
    monkeypatch.setenv("CUTCTX_MODEL_ROUTING_SHADOW_SAMPLE_RATE", "4")
    assert model_routing_shadow_enabled_from_env() is True
    assert model_routing_shadow_sample_rate_from_env() == 1.0


def test_shadow_scheduler_returns_before_background_work_completes() -> None:
    async def scenario() -> None:
        release = anyio.Event()
        started = anyio.Event()

        async def shadow_work() -> str:
            started.set()
            await release.wait()
            return "recorded"

        task = schedule_model_routing_shadow(shadow_work())

        await started.wait()
        assert task.done() is False
        release.set()
        assert await task == "recorded"

    anyio.run(scenario)


def test_shadow_scheduler_consumes_background_failures() -> None:
    async def scenario() -> None:
        async def shadow_work() -> None:
            raise RuntimeError("shadow provider unavailable")

        task = schedule_model_routing_shadow(shadow_work())
        await anyio.sleep(0)

        assert task.done() is True
        assert isinstance(task.exception(), RuntimeError)

    anyio.run(scenario)


def test_prompt_fingerprint_does_not_contain_prompt_text() -> None:
    messages = [{"role": "user", "content": "private customer secret"}]
    fingerprint = prompt_fingerprint(messages)

    assert len(fingerprint) == 64
    assert "private" not in fingerprint
    assert fingerprint == prompt_fingerprint(messages)


def test_eval_store_round_trips_sanitized_jsonl_and_skips_bad_rows(tmp_path) -> None:
    path = tmp_path / "routing.jsonl"
    store = ModelRoutingEvalStore(path)
    store.append(_record("req-1", 0.9, 0.95, 0.4))
    with path.open("a", encoding="utf-8") as handle:
        handle.write("not json\n")

    loaded = store.load()

    assert len(loaded) == 1
    assert loaded[0].request_id == "req-1"
    raw = json.loads(path.read_text().splitlines()[0])
    assert raw["savings_usd"] == pytest.approx(0.4)
    assert set(raw).isdisjoint({"messages", "prompt", "response", "baseline_response"})


def test_comparison_scores_and_persists_without_response_content(tmp_path) -> None:
    path = tmp_path / "routing.jsonl"
    store = ModelRoutingEvalStore(path)

    record = record_model_routing_comparison(
        store,
        request_id="req-compare",
        messages=[{"role": "user", "content": "What is idempotency?"}],
        source_model="gpt-strong",
        candidate_model="gpt-mini",
        scorer="heuristic",
        confidence=0.9,
        baseline_response="An operation that can be repeated safely.",
        candidate_response="An operation that can be repeated safely.",
        source_cost_usd=0.01,
        candidate_cost_usd=0.002,
    )

    assert record.quality_score == 1.0
    assert record.features["is_question"] == 1.0
    persisted = path.read_text()
    assert "repeated safely" not in persisted
    assert "What is idempotency" not in persisted
    assert store.load()[0].savings_usd == pytest.approx(0.008)


def test_legacy_evidence_without_features_remains_loadable(tmp_path) -> None:
    path = tmp_path / "legacy.jsonl"
    path.write_text(
        json.dumps(
            {
                "request_id": "legacy",
                "prompt_hash": "abc",
                "source_model": "strong",
                "candidate_model": "mini",
                "scorer": "heuristic",
                "confidence": 0.9,
                "quality_score": 1.0,
                "source_cost_usd": 1.0,
                "candidate_cost_usd": 0.2,
            }
        )
        + "\n"
    )

    record = ModelRoutingEvalStore(path).load()[0]
    assert record.request_id == "legacy"
    assert record.features == {}
    assert record.segments == {}


def test_segment_sanitization_hashes_workspace_and_repository() -> None:
    segments = sanitize_routing_segments(
        {
            "client": "Codex",
            "task_type": "Repository Lookup",
            "workspace": "/private/customer/workspace",
            "repository": "secret-repo",
        }
    )

    assert segments["client"] == "codex"
    assert segments["task_type"] == "repository lookup"
    assert len(segments["workspace_hash"]) == 64
    assert len(segments["repository_hash"]) == 64
    assert "customer" not in json.dumps(segments)


def test_segmented_recommendations_promote_dense_safe_segment_and_fallback_sparse() -> None:
    records = []
    for index in range(5):
        record = _record(f"codex-{index}", 0.9, 0.95, 0.1)
        records.append(
            ModelRoutingEvalRecord(**{**record.__dict__, "segments": {"client": "codex"}})
        )
    sparse = _record("claude-1", 0.9, 0.95, 0.1)
    records.append(ModelRoutingEvalRecord(**{**sparse.__dict__, "segments": {"client": "claude"}}))

    report = build_segmented_recommendations(
        records,
        minimum_samples=3,
        maximum_unsafe_rate=0.0,
    )

    assert report["dimensions"]["client"]["codex"]["status"] == "promoted"
    assert report["dimensions"]["client"]["claude"]["status"] == "global_fallback"
    assert (
        report["dimensions"]["client"]["claude"]["effective_minimum_confidence"]
        == report["global_recommendation"]["minimum_confidence"]
    )


def test_shadow_runner_executes_sampled_baseline_and_records_result(tmp_path) -> None:
    store = ModelRoutingEvalStore(tmp_path / "routing.jsonl")
    calls = 0

    async def baseline_call():
        nonlocal calls
        calls += 1
        return "same answer", 0.01

    record = anyio.run(
        lambda: maybe_run_model_routing_shadow(
            request_id="req-shadow",
            messages=[{"role": "user", "content": "hello"}],
            source_model="gpt-strong",
            candidate_model="gpt-mini",
            scorer="heuristic",
            confidence=0.9,
            candidate_response="same answer",
            candidate_cost_usd=0.002,
            baseline_call=baseline_call,
            store=store,
            enabled=True,
            sample_rate=1.0,
        )
    )

    assert calls == 1
    assert record is not None
    assert record.quality_score == 1.0
    assert store.load()[0].savings_usd == pytest.approx(0.008)


def test_shadow_runner_is_off_by_default_and_swallows_failures(tmp_path) -> None:
    store = ModelRoutingEvalStore(tmp_path / "routing.jsonl")
    calls = 0

    async def failing_call():
        nonlocal calls
        calls += 1
        raise RuntimeError("provider unavailable")

    disabled = anyio.run(
        lambda: maybe_run_model_routing_shadow(
            request_id="req-off",
            messages=[],
            source_model="strong",
            candidate_model="mini",
            scorer="test",
            confidence=0.9,
            candidate_response="answer",
            candidate_cost_usd=0.1,
            baseline_call=failing_call,
            store=store,
            enabled=False,
            sample_rate=1.0,
        )
    )
    failed = anyio.run(
        lambda: maybe_run_model_routing_shadow(
            request_id="req-fail",
            messages=[],
            source_model="strong",
            candidate_model="mini",
            scorer="test",
            confidence=0.9,
            candidate_response="answer",
            candidate_cost_usd=0.1,
            baseline_call=failing_call,
            store=store,
            enabled=True,
            sample_rate=1.0,
        )
    )

    assert disabled is None
    assert failed is None
    assert calls == 1
    assert store.load() == []


def test_frontier_reports_quality_safety_and_savings_at_each_threshold() -> None:
    records = [
        _record("high", 0.95, 0.98, 0.4),
        _record("middle", 0.85, 0.92, 0.3),
        _record("low", 0.70, 0.40, 0.2),
    ]

    frontier = build_quality_cost_frontier(records, quality_floor=0.8)

    assert [row["minimum_confidence"] for row in frontier] == [0.95, 0.85, 0.70]
    assert frontier[1]["routed_samples"] == 2
    assert frontier[1]["mean_quality"] == pytest.approx(0.95)
    assert frontier[1]["unsafe_rate"] == 0.0
    assert frontier[1]["total_savings_usd"] == pytest.approx(0.7)
    assert frontier[2]["unsafe_rate"] == pytest.approx(1 / 3)


def test_evidence_report_has_explicit_empty_and_collecting_states() -> None:
    empty = build_model_routing_evidence_report([], minimum_samples=2)
    collecting = build_model_routing_evidence_report(
        [_record("first", 0.9, 0.98, 0.4)],
        minimum_samples=2,
    )

    assert empty["schema_version"] == 1
    assert empty["status"] == "no_evidence"
    assert empty["recommendation"] is None
    assert empty["sample_progress"] == {"observed": 0, "required": 2, "fraction": 0.0}
    assert collecting["status"] == "collecting"
    assert collecting["recommendation"] is None
    assert collecting["sample_progress"]["fraction"] == 0.5
    assert collecting["segmented"]["global_recommendation"] is None
    assert (
        collecting["segmented"]["dimensions"]["model_pair"]["gpt-strong->gpt-mini"][
            "effective_minimum_confidence"
        ]
        is None
    )


def test_evidence_report_blocks_policy_that_misses_quality_limits() -> None:
    report = build_model_routing_evidence_report(
        [
            _record("unsafe-1", 0.95, 0.30, 0.4),
            _record("unsafe-2", 0.85, 0.40, 0.3),
        ],
        minimum_samples=2,
        minimum_mean_quality=0.9,
        maximum_unsafe_rate=0.0,
    )

    assert report["status"] == "quality_blocked"
    assert report["recommendation"] is None
    assert len(report["frontier"]) == 2


def test_evidence_report_promotes_highest_savings_safe_frontier_point() -> None:
    report = build_model_routing_evidence_report(
        [
            _record("high", 0.95, 0.98, 0.4),
            _record("middle", 0.85, 0.92, 0.3),
        ],
        minimum_samples=2,
        maximum_unsafe_rate=0.0,
    )

    assert report["status"] == "ready"
    assert report["recommendation"]["minimum_confidence"] == 0.85
    assert report["recommendation"]["mean_quality"] == pytest.approx(0.95)
    assert report["recommendation"]["unsafe_rate"] == 0.0
    assert report["recommendation"]["routing_rate"] == 1.0
    assert report["recommendation"]["total_savings_usd"] == pytest.approx(0.7)
    assert report["constraints"] == {
        "minimum_samples": 2,
        "minimum_mean_quality": 0.9,
        "maximum_unsafe_rate": 0.0,
        "quality_floor": 0.8,
    }
    serialized = json.dumps(report)
    assert "private customer prompt" not in serialized
    assert "/private/workspace" not in serialized


def test_recommendation_maximizes_savings_within_quality_limits() -> None:
    records = [
        _record("high", 0.95, 0.98, 0.4),
        _record("middle", 0.85, 0.92, 0.3),
        _record("low", 0.70, 0.40, 0.2),
    ]

    recommendation = recommend_confidence_threshold(
        records,
        minimum_mean_quality=0.9,
        maximum_unsafe_rate=0.0,
    )

    assert recommendation is not None
    assert recommendation["minimum_confidence"] == 0.85
    assert recommendation["total_savings_usd"] == pytest.approx(0.7)


def test_recommendation_abstains_when_no_policy_meets_quality_limits() -> None:
    records = [_record("bad", 0.9, 0.2, 0.4)]

    assert (
        recommend_confidence_threshold(
            records,
            minimum_mean_quality=0.95,
            maximum_unsafe_rate=0.0,
        )
        is None
    )


def test_offline_calibration_report_reads_persisted_evidence(tmp_path) -> None:
    path = tmp_path / "routing.jsonl"
    store = ModelRoutingEvalStore(path)
    store.append(_record("high", 0.95, 0.98, 0.4))
    store.append(_record("middle", 0.85, 0.92, 0.3))

    report = evaluate(path, maximum_unsafe_rate=0.0)

    assert report["samples"] == 2
    assert report["recommendation"] is not None
    assert report["recommendation"]["minimum_confidence"] == 0.85
    assert len(report["frontier"]) == 2
    assert "segmented" in report
