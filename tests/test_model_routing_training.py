from __future__ import annotations

import json

import pytest

from benchmarks.model_routing_train import train
from cutctx.proxy.model_router import (
    ModelRoute,
    ModelRouter,
    ModelRouterConfig,
    TaskComplexity,
    TaskComplexityAssessment,
)
from cutctx.proxy.model_routing_evals import (
    ModelRoutingEvalRecord,
    ModelRoutingEvalStore,
    extract_routing_features,
)
from cutctx.proxy.model_routing_training import (
    LinearCalibratedTaskComplexityScorer,
    LinearRoutingArtifact,
    train_linear_routing_artifact,
)


def _training_records() -> list[ModelRoutingEvalRecord]:
    records = []
    for index in range(24):
        messages = [{"role": "user", "content": f"What is item {index}?"}]
        records.append(
            ModelRoutingEvalRecord(
                request_id=f"safe-{index}",
                prompt_hash=str(index),
                source_model="gpt-strong",
                candidate_model="gpt-mini",
                scorer="heuristic",
                confidence=0.9,
                quality_score=0.96,
                source_cost_usd=0.01,
                candidate_cost_usd=0.002,
                features=extract_routing_features(messages),
                segments={"client": "codex", "task_type": "informational"},
            )
        )
    for index in range(16):
        messages = [
            {
                "role": "user",
                "content": f"Implement production security migration {index} across all modules.",
            }
        ]
        records.append(
            ModelRoutingEvalRecord(
                request_id=f"unsafe-{index}",
                prompt_hash=f"u{index}",
                source_model="gpt-strong",
                candidate_model="gpt-mini",
                scorer="heuristic",
                confidence=0.75,
                quality_score=0.3,
                source_cost_usd=0.01,
                candidate_cost_usd=0.002,
                features=extract_routing_features(messages),
                segments={"client": "codex", "task_type": "implementation"},
            )
        )
    return records


def test_feature_extraction_is_bounded_and_contains_no_text() -> None:
    features = extract_routing_features(
        [{"role": "user", "content": "Implement this production migration.\n```py\nx=1\n```"}]
    )

    assert all(0.0 <= value <= 1.0 for value in features.values())
    assert features["has_code"] == 1.0
    assert features["has_high_risk_intent"] == 1.0
    assert "production" not in json.dumps(features)


def test_training_produces_promotable_artifact_and_learns_risk_signal() -> None:
    artifact = train_linear_routing_artifact(
        _training_records(),
        minimum_samples=20,
        maximum_unsafe_rate=0.0,
        minimum_segment_samples=3,
    )

    safe = extract_routing_features([{"role": "user", "content": "What is a mutex?"}])
    risky = extract_routing_features(
        [{"role": "user", "content": "Implement a production security migration."}]
    )
    assert artifact.predict(safe) > artifact.predict(risky)
    assert artifact.metrics["selected_unsafe_rate"] == 0.0
    assert artifact.minimum_confidence > 0.0
    assert "client" in artifact.segment_thresholds


def test_artifact_round_trip_and_calibrated_scorer_preserve_high_safety_gate(tmp_path) -> None:
    path = tmp_path / "scorer.json"
    artifact = train_linear_routing_artifact(
        _training_records(), minimum_samples=20, maximum_unsafe_rate=0.0
    )
    artifact.save(path)
    loaded = LinearRoutingArtifact.load(path)
    scorer = LinearCalibratedTaskComplexityScorer(loaded)

    low = scorer.assess([{"role": "user", "content": "What is a mutex?"}])
    high = scorer.assess(
        [{"role": "user", "content": "Implement a production security migration."}]
    )

    assert low.complexity == TaskComplexity.LOW
    assert 0.0 <= low.confidence <= 1.0
    assert low.source == "linear-calibrated"
    assert high.complexity == TaskComplexity.HIGH
    assert high.source == "heuristic"


def test_training_command_writes_artifact(tmp_path) -> None:
    evidence = tmp_path / "evidence.jsonl"
    output = tmp_path / "artifact.json"
    store = ModelRoutingEvalStore(evidence)
    for record in _training_records():
        store.append(record)

    payload = train(
        evidence,
        output,
        minimum_samples=20,
        maximum_unsafe_rate=0.0,
    )

    assert output.exists()
    assert payload["type"] == "linear_logistic"
    assert LinearRoutingArtifact.load(output).training_samples == 40


def test_router_loads_artifact_opt_in_and_falls_back_on_invalid_artifact(
    monkeypatch, tmp_path
) -> None:
    artifact_path = tmp_path / "artifact.json"
    train_linear_routing_artifact(
        _training_records(), minimum_samples=20, maximum_unsafe_rate=0.0
    ).save(artifact_path)
    monkeypatch.setenv("CUTCTX_MODEL_ROUTING_SCORER_ARTIFACT", str(artifact_path))
    cfg = ModelRouterConfig(
        enabled=True,
        downgrade_when="low_complexity",
        routes=[
            ModelRoute(
                source="gpt-strong",
                target="gpt-mini",
                source_cost_per_mtok=10,
                target_cost_per_mtok=1,
            )
        ],
    )

    router = ModelRouter(cfg)
    assert router.scorer.assess(
        [{"role": "user", "content": "What is a mutex?"}]
    ).source.startswith("linear-calibrated:")

    invalid = tmp_path / "invalid.json"
    invalid.write_text("{}")
    monkeypatch.setenv("CUTCTX_MODEL_ROUTING_SCORER_ARTIFACT", str(invalid))
    fallback = ModelRouter(cfg)
    assert fallback.scorer.assess([{"role": "user", "content": "hello"}]).source == "heuristic"


def test_training_rejects_insufficient_or_unpromotable_evidence() -> None:
    with pytest.raises(ValueError, match="At least 20"):
        train_linear_routing_artifact(_training_records()[:5], minimum_samples=20)

    bad = [
        ModelRoutingEvalRecord(
            request_id=f"bad-{index}",
            prompt_hash=str(index),
            source_model="strong",
            candidate_model="mini",
            scorer="heuristic",
            confidence=0.9,
            quality_score=0.1,
            source_cost_usd=1,
            candidate_cost_usd=0.1,
            features=extract_routing_features([{"role": "user", "content": "hello"}]),
        )
        for index in range(20)
    ]
    with pytest.raises(ValueError, match="No learned confidence threshold"):
        train_linear_routing_artifact(bad, minimum_samples=20, minimum_mean_quality=0.9)


def test_router_applies_model_pair_then_client_segment_thresholds() -> None:
    class SegmentedScorer:
        artifact = type(
            "Artifact",
            (),
            {
                "minimum_confidence": 0.5,
                "segment_thresholds": {
                    "client": {"codex": 0.8, "claude": 0.6},
                    "model_pair": {"gpt-strong->gpt-mini": 0.9},
                },
            },
        )()

        def assess(self, _messages):  # type: ignore[no-untyped-def]
            return TaskComplexityAssessment(TaskComplexity.LOW, 0.85, "segmented-test")

    cfg = ModelRouterConfig(
        enabled=True,
        downgrade_when="always",
        routes=[
            ModelRoute(
                source="gpt-strong",
                target="gpt-mini",
                source_cost_per_mtok=10,
                target_cost_per_mtok=1,
            ),
            ModelRoute(
                source="claude-strong",
                target="claude-mini",
                source_cost_per_mtok=10,
                target_cost_per_mtok=1,
            ),
        ],
    )
    router = ModelRouter(cfg, scorer=SegmentedScorer())
    assessment = router.scorer.assess([])

    pair_blocked = router.maybe_route("gpt-strong", task_assessment=assessment, client="claude")
    client_allowed = router.maybe_route(
        "claude-strong", task_assessment=assessment, client="claude"
    )

    assert pair_blocked.reason == "confidence_below_threshold"
    assert client_allowed.routing_applied is True
