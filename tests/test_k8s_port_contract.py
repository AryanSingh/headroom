from __future__ import annotations

from pathlib import Path


def test_kubernetes_prometheus_port_matches_proxy_container_port() -> None:
    deployment = (Path(__file__).resolve().parents[1] / "k8s" / "deployment.yaml").read_text(
        encoding="utf-8"
    )

    assert 'prometheus.io/port: "8787"' in deployment
    assert "containerPort: 8787" in deployment
