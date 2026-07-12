from __future__ import annotations

from benchmarks.model_routing_quality import evaluate


def test_routing_quality_benchmark_has_safe_and_balanced_decisions() -> None:
    result = evaluate()
    metrics = result["metrics"]
    matrix = result["confusion_matrix"]

    assert result["cases"] >= 28
    assert matrix["tp"] >= 8
    assert matrix["tn"] >= 12
    assert metrics["unsafe_downgrade_rate"] == 0.0
    assert metrics["balanced_accuracy"] >= 0.95
    assert metrics["luna_candidate_recall"] >= 0.95
    assert metrics["tier_accuracy"] >= 0.95
