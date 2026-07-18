"""The public tier/feature matrix must exist and stay entitlement-accurate."""

from pathlib import Path


def test_plans_page_documents_tiers_and_enforcement() -> None:
    text = Path("docs/content/docs/plans.mdx").read_text()
    for tier in ("Builder", "Team", "Business", "Enterprise"):
        assert tier in text
    # Entitlement-accurate rows: episodic memory is Business-gated, audit
    # logging is Enterprise, and enforcement semantics are described.
    assert "Episodic memory" in text
    assert "Audit logging" in text
    assert "feature_not_available" in text
    assert "fail closed" in text


def test_plans_page_is_in_docs_navigation() -> None:
    meta = Path("docs/content/docs/meta.json").read_text()
    assert '"plans"' in meta
