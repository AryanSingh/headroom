from __future__ import annotations

import json
from pathlib import Path

from scripts.run_remote_hosted_smoke import (
    RemoteHostedNotConfigured,
    remote_hosted_config_from_env,
    run_remote_hosted_smoke,
)


def test_remote_hosted_config_requires_url_and_key(monkeypatch) -> None:
    monkeypatch.delenv("CUTCTX_HOSTED_BASE_URL", raising=False)
    monkeypatch.delenv("CUTCTX_HOSTED_API_KEY", raising=False)

    try:
        remote_hosted_config_from_env()
    except RemoteHostedNotConfigured as exc:
        assert "CUTCTX_HOSTED_BASE_URL" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected a not-configured error")


def test_remote_hosted_smoke_writes_redacted_latency_artifacts(tmp_path: Path, monkeypatch) -> None:
    class FakeClient:
        def __init__(self, base_url: str, *, api_key: str, timeout: float) -> None:
            assert base_url == "https://staging.example.test"
            assert api_key == "secret"
            assert timeout == 60.0

        def compress_text(self, text: str, **_kwargs):
            assert "remote hosted smoke payload" in text
            return type("Result", (), {"tokens_saved": 11})()

    monkeypatch.setattr("scripts.run_remote_hosted_smoke.HostedCompressionClient", FakeClient)
    json_output = tmp_path / "remote.json"
    markdown_output = tmp_path / "remote.md"

    payload = run_remote_hosted_smoke(
        base_url="https://staging.example.test",
        api_key="secret",
        samples_per_size=2,
        json_output=json_output,
        markdown_output=markdown_output,
    )

    assert payload["status"] == "passed"
    assert [case["size"] for case in payload["cases"]] == ["small", "medium", "large"]
    assert json.loads(json_output.read_text(encoding="utf-8"))["cases"][0]["tokens_saved"]["mean"] == 11
    markdown = markdown_output.read_text(encoding="utf-8")
    assert "secret" not in markdown
    assert "small" in markdown and "large" in markdown
