from __future__ import annotations

from pathlib import Path


def test_audit_store_source_describes_current_sha256_chain_honestly() -> None:
    text = Path("cutctx_ee/audit/store.py").read_text(encoding="utf-8")

    assert "secret-keyed SHA-256 chain value" in text
    assert "hashlib.sha256()" in text
    assert "HMAC SHA-256 hash for the event" not in text
    assert "hmac.new(" not in text


def test_audit_docs_match_current_source_contract() -> None:
    compliance = Path("docs/audit-compliance.md").read_text(encoding="utf-8")
    residency = Path("docs/data-residency.md").read_text(encoding="utf-8")
    roadmap = Path("gtm/soc2-roadmap.md").read_text(encoding="utf-8")

    assert "secret-keyed SHA-256 chain value" in compliance
    assert "SHA256(secret || prev_hash || payload)" in compliance
    assert "Current EE builds use this secret-prefixed SHA-256 chain directly" in residency
    assert "secret-keyed SHA-256 hash chain" in roadmap
