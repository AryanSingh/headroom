from __future__ import annotations

import json
from pathlib import Path

from scripts.generate_savings_reconciliation_smoke import generate_savings_reconciliation_smoke


def test_generate_savings_reconciliation_smoke_writes_consistent_artifacts(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    markdown_output = tmp_path / "reconciliation.md"
    json_output = tmp_path / "reconciliation.json"

    payload = generate_savings_reconciliation_smoke(
        workspace_dir=workspace,
        markdown_output=markdown_output,
        json_output=json_output,
    )

    assert markdown_output.exists()
    assert json_output.exists()

    saved_json = json.loads(json_output.read_text(encoding="utf-8"))
    saved_markdown = markdown_output.read_text(encoding="utf-8")

    validation = payload["validation"]
    assert all(validation.values())

    assert payload["lifetime"]["tokens_saved"] == 4150
    assert payload["lifetime"]["created_savings_usd"] == 0.39
    assert payload["lifetime"]["observed_provider_savings_usd"] == 0.09
    assert payload["lifetime"]["total_savings_usd"] == 0.48

    assert payload["history"]["tokens_saved_sum"] == 4150
    assert payload["history"]["created_savings_usd_sum"] == 0.39
    assert payload["history"]["observed_provider_savings_usd_sum"] == 0.09
    assert payload["history"]["usd_sum"] == 0.48

    assert saved_json["validation"]["created_plus_observed_equals_total"] is True
    assert "# Savings Reconciliation Smoke" in saved_markdown
    assert "- Created by Cutctx: $0.39" in saved_markdown
    assert "- Observed at provider: $0.09" in saved_markdown
