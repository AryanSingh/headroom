from __future__ import annotations

import json
from pathlib import Path

from scripts.generate_buyer_report_smoke import generate_buyer_report_smoke


def test_generate_buyer_report_smoke_writes_reconciled_artifacts(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    markdown_output = tmp_path / "buyer-report.md"
    json_output = tmp_path / "buyer-report.json"

    payload = generate_buyer_report_smoke(
        workspace_dir=workspace,
        markdown_output=markdown_output,
        json_output=json_output,
    )

    assert markdown_output.exists()
    assert json_output.exists()

    saved_json = json.loads(json_output.read_text(encoding="utf-8"))
    saved_markdown = markdown_output.read_text(encoding="utf-8")

    assert payload["validation"]["tokens_match"] is True
    assert payload["validation"]["usd_match"] is True
    assert payload["validation"]["token_total"] == payload["validation"]["token_sum"]
    assert payload["validation"]["usd_total"] == payload["validation"]["usd_sum"]

    assert payload["savings_by_source"]["provider_prompt_cache"] == 1200
    assert payload["savings_by_source"]["cutctx_compression"] == 1000
    assert payload["savings_by_source"]["semantic_cache"] == 600
    assert payload["savings_by_source"]["model_routing"] == 900
    assert payload["savings_by_source"]["tool_schema_compaction"] == 300
    assert payload["savings_by_source"]["api_surface_slimming"] == 150

    assert saved_json["validation"]["tokens_match"] is True
    assert saved_json["validation"]["usd_match"] is True
    assert "# Cutctx ROI Report" in saved_markdown
    assert "| Source | Tokens |" in saved_markdown
    assert "| **Total** | **4,150** |" in saved_markdown
