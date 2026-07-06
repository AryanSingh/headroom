import pytest

from cutctx.proxy.compression_decision import CompressionDecision
from cutctx.proxy.prometheus_metrics import PrometheusMetrics


class MockConfig:
    def __init__(self, optimize: bool = True):
        self.optimize = optimize

class MockUsageReporter:
    def __init__(self, should_compress: bool = True):
        self.should_compress = should_compress


def test_compression_decline_telemetry() -> None:
    metrics = PrometheusMetrics()

    # Reason 1: bypass_header
    decision1 = CompressionDecision.decide(
        headers={"x-cutctx-bypass": "true"},
        config=MockConfig(),
        usage_reporter=MockUsageReporter(),
        messages=[{"role": "user", "content": "hi"}],
    )
    assert not decision1.should_compress
    assert decision1.passthrough_reason == "bypass_header"
    metrics.record_compression_declined(decision1.passthrough_reason or "unknown")

    # Reason 2: compression_disabled
    decision2 = CompressionDecision.decide(
        headers={},
        config=MockConfig(optimize=False),
        usage_reporter=MockUsageReporter(),
        messages=[{"role": "user", "content": "hi"}],
    )
    assert not decision2.should_compress
    assert decision2.passthrough_reason == "compression_disabled"
    metrics.record_compression_declined(decision2.passthrough_reason or "unknown")

    # Reason 3: no_messages
    decision3 = CompressionDecision.decide(
        headers={},
        config=MockConfig(),
        usage_reporter=MockUsageReporter(),
        messages=[],
    )
    assert not decision3.should_compress
    assert decision3.passthrough_reason == "no_messages"
    metrics.record_compression_declined(decision3.passthrough_reason or "unknown")

    # Reason 4: license_denied
    decision4 = CompressionDecision.decide(
        headers={},
        config=MockConfig(),
        usage_reporter=MockUsageReporter(should_compress=False),
        messages=[{"role": "user", "content": "hi"}],
    )
    assert not decision4.should_compress
    assert decision4.passthrough_reason == "license_denied"
    metrics.record_compression_declined(decision4.passthrough_reason or "unknown")

    # Verify metrics state
    assert metrics.compression_declined_total["bypass_header"] == 1
    assert metrics.compression_declined_total["compression_disabled"] == 1
    assert metrics.compression_declined_total["no_messages"] == 1
    assert metrics.compression_declined_total["license_denied"] == 1

    # Verify export output contains the new metric block
    import asyncio
    export_text = asyncio.run(metrics.export())
    
    assert "cutctx_compression_declined_total{reason=\"bypass_header\"} 1" in export_text
    assert "cutctx_compression_declined_total{reason=\"compression_disabled\"} 1" in export_text
    assert "cutctx_compression_declined_total{reason=\"no_messages\"} 1" in export_text
    assert "cutctx_compression_declined_total{reason=\"license_denied\"} 1" in export_text
