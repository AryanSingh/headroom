"""Deterministic operator-surface contracts for release evidence."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_kubernetes_deployment_has_matching_readiness_and_liveness_contracts() -> None:
    deployment = (ROOT / "k8s" / "deployment.yaml").read_text(encoding="utf-8")
    readme = (ROOT / "k8s" / "README.md").read_text(encoding="utf-8")

    assert "readinessProbe:" in deployment
    assert "path: /readyz" in deployment
    assert "livenessProbe:" in deployment
    assert "path: /livez" in deployment
    assert "startupProbe:" in deployment
    assert "allowPrivilegeEscalation: false" in deployment
    assert "readOnlyRootFilesystem: true" in deployment
    assert "`/readyz` | Readiness" in readme
    assert "`/livez` | Liveness + startup" in readme


def test_docker_compose_keeps_local_first_proxy_configuration_explicit() -> None:
    compose = (ROOT / "docker" / "docker-compose.native.yml").read_text(encoding="utf-8")

    assert 'entrypoint: ["cutctx", "proxy"]' in compose
    assert "CUTCTX_HOST: 0.0.0.0" in compose
    assert '"${CUTCTX_PORT:-8787}:${CUTCTX_PORT:-8787}"' in compose
    assert "CUTCTX_WORKSPACE_DIR" in compose
    assert "CUTCTX_CONFIG_DIR" in compose
