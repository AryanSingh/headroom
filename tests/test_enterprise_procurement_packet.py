from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_enterprise_procurement_packet_has_fixed_checklist_and_evidence_links() -> None:
    packet = (ROOT / "artifacts" / "enterprise-procurement-packet.md").read_text()

    assert "## Fixed Checklist" in packet
    assert "| Area | Status | Evidence | Notes |" in packet
    assert "Available now" in packet
    assert "External legal review required" in packet
    assert "Not represented as completed" in packet
    assert "## Security Evidence Bundle" in packet
    assert "## Not Claimed In This Packet" in packet
    assert "docs/security-and-privacy.md" in packet
    assert "docs/security/SOC2_CONTROLS.md" in packet
    assert "artifacts/legal/DPA_TEMPLATE.md" in packet
    assert "artifacts/legal/MSA_TEMPLATE.md" in packet


def test_security_and_privacy_doc_separates_shipped_controls_from_external_work() -> None:
    doc = (ROOT / "docs" / "security-and-privacy.md").read_text()

    assert "## Procurement Review Split" in doc
    assert "### Available now in product" in doc
    assert "### External or planned workstreams" in doc
    assert "SOC 2 certification or audit completion" in doc
    assert "artifacts/enterprise-procurement-packet.md" in doc
