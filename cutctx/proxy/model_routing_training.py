"""Train and load a small calibrated model-routing confidence scorer."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from cutctx.proxy.model_routing_evals import (
    ROUTING_FEATURE_NAMES,
    ModelRoutingEvalRecord,
    build_quality_cost_frontier,
    build_segmented_recommendations,
    extract_routing_features,
    recommend_confidence_threshold,
)

ARTIFACT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class LinearRoutingArtifact:
    weights: dict[str, float]
    intercept: float
    quality_floor: float
    minimum_confidence: float
    training_samples: int
    metrics: dict[str, float]
    segment_thresholds: dict[str, dict[str, float]]
    schema_version: int = ARTIFACT_SCHEMA_VERSION

    def predict(self, features: dict[str, float]) -> float:
        logit = self.intercept + sum(
            self.weights.get(name, 0.0) * float(features.get(name, 0.0))
            for name in ROUTING_FEATURE_NAMES
        )
        return _sigmoid(logit)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "type": "linear_logistic",
            "feature_names": list(ROUTING_FEATURE_NAMES),
            "weights": self.weights,
            "intercept": self.intercept,
            "quality_floor": self.quality_floor,
            "minimum_confidence": self.minimum_confidence,
            "training_samples": self.training_samples,
            "metrics": self.metrics,
            "segment_thresholds": self.segment_thresholds,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> LinearRoutingArtifact:
        if int(payload.get("schema_version", 0)) != ARTIFACT_SCHEMA_VERSION:
            raise ValueError("Unsupported model-routing scorer artifact version")
        if payload.get("type") != "linear_logistic":
            raise ValueError("Unsupported model-routing scorer artifact type")
        weights = payload.get("weights")
        if not isinstance(weights, dict):
            raise ValueError("Model-routing scorer artifact has no weights")
        return cls(
            weights={name: float(weights.get(name, 0.0)) for name in ROUTING_FEATURE_NAMES},
            intercept=float(payload.get("intercept", 0.0)),
            quality_floor=float(payload.get("quality_floor", 0.8)),
            minimum_confidence=float(payload.get("minimum_confidence", 1.0)),
            training_samples=int(payload.get("training_samples", 0)),
            metrics={str(key): float(value) for key, value in payload.get("metrics", {}).items()},
            segment_thresholds={
                str(dimension): {
                    str(value): float(threshold) for value, threshold in thresholds.items()
                }
                for dimension, thresholds in payload.get("segment_thresholds", {}).items()
                if isinstance(thresholds, dict)
            },
        )

    @classmethod
    def load(cls, path: str | Path) -> LinearRoutingArtifact:
        payload = json.loads(Path(path).read_text())
        if not isinstance(payload, dict):
            raise ValueError("Model-routing scorer artifact must be a JSON object")
        return cls.from_dict(payload)

    def save(self, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n")


class LinearCalibratedTaskComplexityScorer:
    """Learned confidence layered beneath the deterministic safety tier."""

    def __init__(
        self, artifact: LinearRoutingArtifact, *, source: str = "linear-calibrated"
    ) -> None:
        self.artifact = artifact
        self.source = source

    def assess(self, messages):  # type: ignore[no-untyped-def]
        from cutctx.proxy.model_router import (
            HeuristicTaskComplexityScorer,
            TaskComplexity,
            TaskComplexityAssessment,
        )

        base = HeuristicTaskComplexityScorer().assess(messages)
        if base.complexity == TaskComplexity.HIGH:
            return base
        return TaskComplexityAssessment(
            complexity=base.complexity,
            confidence=self.artifact.predict(extract_routing_features(messages)),
            source=self.source,
        )


def train_linear_routing_artifact(
    records: list[ModelRoutingEvalRecord],
    *,
    quality_floor: float = 0.8,
    minimum_samples: int = 20,
    minimum_mean_quality: float = 0.9,
    maximum_unsafe_rate: float = 0.01,
    minimum_segment_samples: int = 20,
    minimum_holdout_samples: int = 20,
    minimum_selected_holdout_samples: int = 10,
    iterations: int = 600,
    learning_rate: float = 0.25,
    l2: float = 0.02,
) -> LinearRoutingArtifact:
    usable = [record for record in records if record.features]
    if len(usable) < minimum_samples:
        raise ValueError(
            f"At least {minimum_samples} feature-bearing shadow records are required; "
            f"found {len(usable)}"
        )
    training, validation = _deterministic_split(usable)
    if len(validation) < minimum_holdout_samples:
        raise ValueError(
            f"At least {minimum_holdout_samples} holdout records are required for scorer promotion; "
            f"found {len(validation)}"
        )
    weights = dict.fromkeys(ROUTING_FEATURE_NAMES, 0.0)
    positive_rate = sum(record.quality_score >= quality_floor for record in training) / len(
        training
    )
    clipped_rate = min(max(positive_rate, 1e-4), 1 - 1e-4)
    intercept = math.log(clipped_rate / (1 - clipped_rate))

    for _ in range(iterations):
        bias_gradient = 0.0
        gradients = dict.fromkeys(ROUTING_FEATURE_NAMES, 0.0)
        for record in training:
            prediction = _predict(weights, intercept, record.features)
            error = prediction - float(record.quality_score >= quality_floor)
            bias_gradient += error
            for name in ROUTING_FEATURE_NAMES:
                gradients[name] += error * record.features.get(name, 0.0)
        scale = 1.0 / len(training)
        intercept -= learning_rate * bias_gradient * scale
        for name in ROUTING_FEATURE_NAMES:
            weights[name] -= learning_rate * (gradients[name] * scale + l2 * weights[name])

    predictions = [_predict(weights, intercept, record.features) for record in validation]
    labels = [float(record.quality_score >= quality_floor) for record in validation]
    calibrated_records = [
        replace(record, confidence=prediction)
        for record, prediction in zip(validation, predictions, strict=True)
    ]
    recommendation = recommend_confidence_threshold(
        calibrated_records,
        minimum_mean_quality=minimum_mean_quality,
        maximum_unsafe_rate=maximum_unsafe_rate,
        quality_floor=quality_floor,
    )
    if recommendation is None:
        raise ValueError("No learned confidence threshold satisfies the configured quality limits")
    heuristic_recommendation = recommend_confidence_threshold(
        validation,
        minimum_mean_quality=minimum_mean_quality,
        maximum_unsafe_rate=maximum_unsafe_rate,
        quality_floor=quality_floor,
    )
    if heuristic_recommendation is not None and (
        float(recommendation["unsafe_rate"]) > float(heuristic_recommendation["unsafe_rate"])
        or float(recommendation["total_savings_usd"])
        < float(heuristic_recommendation["total_savings_usd"])
    ):
        raise ValueError(
            "Learned scorer did not match the heuristic policy's holdout safety and savings"
        )
    threshold = float(recommendation["minimum_confidence"])
    selected = [
        (record, prediction)
        for record, prediction in zip(validation, predictions, strict=True)
        if prediction >= threshold
    ]
    if len(selected) < minimum_selected_holdout_samples:
        raise ValueError(
            f"At least {minimum_selected_holdout_samples} selected holdout records are required "
            f"for scorer promotion; found {len(selected)}"
        )
    metrics = {
        "brier_score": sum(
            (prediction - label) ** 2 for prediction, label in zip(predictions, labels, strict=True)
        )
        / len(validation),
        "classification_accuracy": sum(
            (prediction >= 0.5) == bool(label)
            for prediction, label in zip(predictions, labels, strict=True)
        )
        / len(validation),
        "selected_samples": float(len(selected)),
        "selected_routing_rate": len(selected) / len(validation),
        "selected_mean_quality": sum(record.quality_score for record, _ in selected)
        / len(selected),
        "selected_unsafe_rate": sum(record.quality_score < quality_floor for record, _ in selected)
        / len(selected),
        "selected_total_savings_usd": sum(record.savings_usd for record, _ in selected),
        "frontier_points": float(
            len(build_quality_cost_frontier(calibrated_records, quality_floor=quality_floor))
        ),
        "fit_samples": float(len(training)),
        "holdout_samples": float(len(validation)),
        "heuristic_holdout_savings_usd": float(
            heuristic_recommendation["total_savings_usd"]
            if heuristic_recommendation is not None
            else 0.0
        ),
        "heuristic_holdout_unsafe_rate": float(
            heuristic_recommendation["unsafe_rate"] if heuristic_recommendation is not None else 1.0
        ),
    }
    segmented = build_segmented_recommendations(
        calibrated_records,
        minimum_samples=minimum_segment_samples,
        minimum_mean_quality=minimum_mean_quality,
        maximum_unsafe_rate=maximum_unsafe_rate,
        quality_floor=quality_floor,
    )
    segment_thresholds = {
        dimension: {
            value: float(row["recommendation"]["minimum_confidence"])
            for value, row in values.items()
            if row["status"] == "promoted" and row["recommendation"] is not None
        }
        for dimension, values in segmented["dimensions"].items()
    }
    return LinearRoutingArtifact(
        weights=weights,
        intercept=intercept,
        quality_floor=quality_floor,
        minimum_confidence=threshold,
        training_samples=len(usable),
        metrics=metrics,
        segment_thresholds=segment_thresholds,
    )


def _predict(weights: dict[str, float], intercept: float, features: dict[str, float]) -> float:
    return _sigmoid(
        intercept
        + sum(weights.get(name, 0.0) * features.get(name, 0.0) for name in ROUTING_FEATURE_NAMES)
    )


def _deterministic_split(
    records: list[ModelRoutingEvalRecord],
) -> tuple[list[ModelRoutingEvalRecord], list[ModelRoutingEvalRecord]]:
    training: list[ModelRoutingEvalRecord] = []
    validation: list[ModelRoutingEvalRecord] = []
    for record in records:
        identity = record.prompt_hash or record.request_id
        bucket = int.from_bytes(hashlib.sha256(identity.encode()).digest()[:2], "big") % 5
        (validation if bucket == 0 else training).append(record)
    if not validation:
        validation.append(training.pop())
    if not training:
        training.append(validation.pop())
    return training, validation


def _sigmoid(value: float) -> float:
    if value >= 0:
        exp = math.exp(-value)
        return 1.0 / (1.0 + exp)
    exp = math.exp(value)
    return exp / (1.0 + exp)


__all__ = [
    "ARTIFACT_SCHEMA_VERSION",
    "LinearCalibratedTaskComplexityScorer",
    "LinearRoutingArtifact",
    "train_linear_routing_artifact",
]
