from __future__ import annotations

from pathlib import Path


def test_safe_savings_docs_name_flag_status_command_and_authoritative_rollback() -> None:
    text = Path("docs/content/docs/model-routing-presets.mdx").read_text(encoding="utf-8")

    assert "CUTCTX_SAFE_SAVINGS_EXPERIENCE" in text
    assert "cutctx routing status" in text
    assert "/v1/orchestration/safe-savings/status" in text
    assert "orchestrator_mode" in text
    assert '"off"' in text
    assert "does not perform provider calls" in text
    assert "routing remains separately opt-in" in text
