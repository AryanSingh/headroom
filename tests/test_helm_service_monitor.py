from __future__ import annotations

from pathlib import Path


def test_helm_chart_offers_opt_in_service_monitor() -> None:
    root = Path(__file__).resolve().parents[1]
    values = (root / "helm" / "cutctx" / "values.yaml").read_text(encoding="utf-8")
    template = (root / "helm" / "cutctx" / "templates" / "servicemonitor.yaml").read_text(
        encoding="utf-8"
    )

    assert "serviceMonitor:" in values
    assert "enabled: false" in values
    assert "kind: ServiceMonitor" in template
    assert "path: /metrics" in template
