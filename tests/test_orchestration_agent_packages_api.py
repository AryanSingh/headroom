from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app

PACKAGE_YAML = """\
apiVersion: cutctx.dev/agent/v1
id: implementer-codex
version: 1
harness: codex_cli
role: implementer
tools:
  - shell
policy_refs: []
"""


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    config_path = tmp_path / "orchestration.json"
    config_path.write_text(
        json.dumps({"version": 1, "providers": [], "roles": [], "models": [], "bindings": []}),
        encoding="utf-8",
    )
    monkeypatch.setenv("CUTCTX_ORCHESTRATION_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("CUTCTX_ORCHESTRATION_CONFIG", str(config_path))
    monkeypatch.setenv("CUTCTX_AGENT_PACKAGES_DIR", str(tmp_path / "agents"))
    app = create_app(
        ProxyConfig(
            backend="mock",
            cache_enabled=False,
            admin_api_key="admin_12345",
            prefix_freeze_db_path=str(tmp_path / "prefix-tracker.db"),
        )
    )
    return TestClient(app)


def test_agent_packages_put_and_list(tmp_path, monkeypatch) -> None:
    headers = {"Authorization": "Bearer admin_12345"}
    with _client(tmp_path, monkeypatch) as client:
        put = client.put(
            "/v1/orchestration/agent-packages/implementer-codex",
            headers=headers,
            json={"yaml": PACKAGE_YAML},
        )
        assert put.status_code == 200
        assert put.json()["package"]["harness"] == "codex_cli"
        listed = client.get("/v1/orchestration/agent-packages", headers=headers)
        assert listed.status_code == 200
        assert listed.json()["packages"][0]["id"] == "implementer-codex"
