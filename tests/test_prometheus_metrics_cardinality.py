"""Cardinality bounds for PrometheusMetrics provider/model/path labels."""

from __future__ import annotations

import pytest

from cutctx.proxy.prometheus_metrics import PrometheusMetrics, bounded_label


async def _record_request(
    metrics: PrometheusMetrics,
    *,
    provider: str = "unknown",
    model: str = "unknown-model",
) -> None:
    await metrics.record_request(
        provider=provider,
        model=model,
        input_tokens=1,
        output_tokens=1,
        tokens_saved=0,
        latency_ms=1.0,
    )


@pytest.mark.parametrize(
    ("known", "seen", "limit", "value", "expected"),
    [
        ("anthropic", frozenset(), 0, "anthropic", "anthropic"),
        ("anthropic", frozenset(), 0, "new-provider", "other"),
        ("anthropic", frozenset({"seen-a"}), 1, "seen-a", "seen-a"),
        ("anthropic", frozenset({"seen-a"}), 1, "seen-b", "other"),
    ],
)
def test_bounded_label_routes_overflow_to_other(
    known: str,
    seen: frozenset[str],
    limit: int,
    value: str,
    expected: str,
) -> None:
    seen_mutable = set(seen)
    result = bounded_label(value, {known}, seen_mutable, limit)
    assert result == expected


@pytest.mark.asyncio
async def test_unrecognized_models_share_the_other_metric_bucket() -> None:
    metrics = PrometheusMetrics()

    for index in range(metrics.MAX_DISTINCT_MODELS):
        await _record_request(metrics, model=f"fill-{index}")

    for index in range(500):
        await _record_request(metrics, model=f"attacker-{index}")

    assert metrics.requests_by_model["other"] == 500
    assert len(metrics.requests_by_model) <= metrics.MAX_DISTINCT_MODELS + 1


@pytest.mark.asyncio
async def test_unrecognized_providers_share_the_other_metric_bucket() -> None:
    metrics = PrometheusMetrics()

    for index in range(metrics.MAX_DISTINCT_PROVIDERS):
        await _record_request(metrics, provider=f"fill-{index}")

    for index in range(500):
        await _record_request(metrics, provider=f"attacker-{index}")

    assert metrics.requests_by_provider["other"] == 500
    assert len(metrics.requests_by_provider) <= metrics.MAX_DISTINCT_PROVIDERS + 1


def test_unrecognized_paths_share_the_other_metric_bucket() -> None:
    metrics = PrometheusMetrics()

    for index in range(metrics.MAX_DISTINCT_PATHS):
        metrics.record_inbound_request(method="GET", path=f"/fill/{index}")

    for index in range(500):
        metrics.record_inbound_request(method="GET", path=f"/attacker/{index}")

    assert metrics.inbound_requests_by_path["other"] == 500
    assert len(metrics.inbound_requests_by_path) <= metrics.MAX_DISTINCT_PATHS + 1


@pytest.mark.asyncio
async def test_allowlisted_model_remains_distinct_under_overflow() -> None:
    metrics = PrometheusMetrics()
    allowlisted = "gpt-4o"

    for index in range(metrics.MAX_DISTINCT_MODELS):
        await _record_request(metrics, model=f"fill-{index}")

    await _record_request(metrics, provider="openai", model=allowlisted)

    for index in range(500):
        await _record_request(metrics, model=f"attacker-{index}")

    assert metrics.requests_by_model[allowlisted] == 1
    assert metrics.requests_by_model["other"] == 500
    assert allowlisted in metrics.requests_by_model


def test_allowlisted_path_remains_distinct_under_overflow() -> None:
    metrics = PrometheusMetrics()
    allowlisted = "/v1/responses"

    for index in range(metrics.MAX_DISTINCT_PATHS):
        metrics.record_inbound_request(method="GET", path=f"/fill/{index}")

    metrics.record_inbound_request(method="POST", path=allowlisted)

    for index in range(500):
        metrics.record_inbound_request(method="GET", path=f"/attacker/{index}")

    assert metrics.inbound_requests_by_path[allowlisted] == 1
    assert metrics.inbound_requests_by_path["other"] == 500
    assert allowlisted in metrics.inbound_requests_by_path
