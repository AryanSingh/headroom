"""Release evidence must exercise the complete dashboard journey suite."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "product-release-evidence.yml"


def test_fixture_release_evidence_runs_full_dashboard_e2e_suite() -> None:
    content = WORKFLOW.read_text(encoding="utf-8")
    fixture_job = content.split("  staging-release-blocker:", maxsplit=1)[0]

    assert "npx playwright test --project=chromium" in fixture_job
    assert fixture_job.index("npx playwright test --project=chromium") < fixture_job.index(
        "npx playwright test dashboard-audit.spec.js"
    )
