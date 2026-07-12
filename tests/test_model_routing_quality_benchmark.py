from __future__ import annotations

from benchmarks.model_routing_quality import evaluate


def test_routing_quality_benchmark_has_safe_and_balanced_decisions() -> None:
    result = evaluate()
    metrics = result["metrics"]
    matrix = result["confusion_matrix"]

    assert result["schema_version"] == 2
    assert result["corpus_version"] == 2
    assert result["cases"] >= 50
    assert matrix["tp"] >= 8
    assert matrix["tn"] >= 12
    assert metrics["unsafe_downgrade_rate"] == 0.0
    assert metrics["balanced_accuracy"] >= 0.95
    assert metrics["luna_candidate_recall"] >= 0.95
    assert metrics["tier_accuracy"] >= 0.95
    for client in ("codex", "claude", "opencode"):
        client_metrics = result["per_client"][client]
        assert client_metrics["cases"] >= 8
        assert client_metrics["unsafe_downgrade_rate"] == 0.0
        assert client_metrics["tier_accuracy"] >= 0.95
    assert all(
        category["unsafe_downgrade_rate"] == 0.0 for category in result["per_category"].values()
    )
