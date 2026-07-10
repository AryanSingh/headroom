from __future__ import annotations

import json
from pathlib import Path

from scripts.generate_agent_context_smoke import generate_agent_context_smoke


def test_generate_agent_context_smoke_writes_end_to_end_artifacts(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    markdown_output = tmp_path / "report.md"
    json_output = tmp_path / "report.json"

    payload = generate_agent_context_smoke(
        workspace_dir=workspace,
        request_count=6,
        markdown_output=markdown_output,
        json_output=json_output,
    )

    assert markdown_output.exists()
    assert json_output.exists()

    saved_json = json.loads(json_output.read_text(encoding="utf-8"))
    saved_markdown = markdown_output.read_text(encoding="utf-8")

    assert payload["summary"]["requests"] == 6
    assert payload["summary"]["tokens_saved"] > 0
    assert payload["telemetry"]["status"] == "observed"
    assert payload["telemetry"]["requests_observed"] >= 6
    assert saved_json["summary"]["requests"] == 6
    assert saved_json["telemetry"]["requests_observed"] >= 6
    assert "# Agent Context Report" in saved_markdown
    assert "## Telemetry Snapshot" in saved_markdown

    request_history = workspace / "logs" / "request_history.jsonl"
    assert request_history.exists()
    assert len(request_history.read_text(encoding="utf-8").splitlines()) >= 6
