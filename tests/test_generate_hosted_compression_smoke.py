from __future__ import annotations

import json
from pathlib import Path

from scripts.generate_hosted_compression_smoke import (
    _hosted_server_python,
    generate_hosted_compression_smoke,
)


def test_hosted_smoke_prefers_project_virtualenv_runtime() -> None:
    project_root = Path(__file__).resolve().parents[1]
    project_python = project_root / ".venv" / "bin" / "python"

    if project_python.is_file():
        assert Path(_hosted_server_python()).resolve() == project_python.resolve()


def test_generate_hosted_compression_smoke_writes_live_http_artifacts(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    markdown_output = tmp_path / "hosted-smoke.md"
    json_output = tmp_path / "hosted-smoke.json"

    payload = generate_hosted_compression_smoke(
        workspace_dir=workspace,
        markdown_output=markdown_output,
        json_output=json_output,
    )

    assert markdown_output.exists()
    assert json_output.exists()

    saved_json = json.loads(json_output.read_text(encoding="utf-8"))
    saved_markdown = markdown_output.read_text(encoding="utf-8")

    assert payload["base_url"].startswith("http://127.0.0.1:")
    assert payload["input_kind"] == "text"
    assert payload["compatibility_mode"] == "tool_output"
    assert payload["tokens_saved"] > 0
    assert payload["tokens_before"] > payload["tokens_after"]

    assert saved_json["tokens_saved"] == payload["tokens_saved"]
    assert "# Hosted Compression Smoke" in saved_markdown
    assert "HostedCompressionClient" in saved_markdown
