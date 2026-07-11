from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_trust_release_checklist_keeps_external_claims_explicit() -> None:
    checklist = (ROOT / "artifacts" / "trust-release-checklist.md").read_text(encoding="utf-8")
    controls = (ROOT / "docs" / "security" / "SOC2_CONTROLS.md").read_text(encoding="utf-8")

    assert "Remote hosted proof | Pending external staging" in checklist
    assert "SOC 2 / penetration testing | Not represented as completed" in checklist
    assert "signed outbound webhook dispatcher" in controls
    assert "per-license-tier or per-user" in controls
    assert "Alert routing is a stub webhook" not in controls


def test_release_evidence_runbook_requires_real_staging_and_partner_validation() -> None:
    content = (ROOT / "docs" / "release-evidence-runbook.md").read_text(encoding="utf-8")

    assert "scripts/run_remote_hosted_smoke.py" in content
    assert "npm run smoke:hosted" in content
    assert "scripts/run_staged_gateway_smoke.py" in content
    assert "scripts/run_staging_dashboard_smoke.py" in content
    assert "validate_partner_telemetry_snapshot.py" in content
    assert "at least seven days" in content
