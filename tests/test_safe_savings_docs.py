"""Documentation assertions for the guided Safe Savings operator workflow."""

from pathlib import Path


def test_safe_savings_docs_name_flag_status_command_and_rollback() -> None:
    text = Path("docs/content/docs/model-routing-presets.mdx").read_text()
    assert "CUTCTX_SAFE_SAVINGS_EXPERIENCE" in text
    assert "cutctx routing status" in text
    assert "/v1/orchestration/safe-savings/status" in text
    assert "orchestrator_mode" in text
    assert '"off"' in text
