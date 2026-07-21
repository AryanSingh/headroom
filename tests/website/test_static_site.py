from pathlib import Path


def test_public_legal_pages_do_not_contain_unapproved_legacy_identity():
    pages = [
        Path("website/terms/index.html"),
        Path("website/privacy/index.html"),
        Path("website/refunds/index.html"),
    ]
    assert all(page.exists() for page in pages)
    rendered = "\n".join(page.read_text(encoding="utf-8") for page in pages)
    assert "Cutctx Labs" not in rendered
    assert "sales@payzli.com" not in rendered
    assert "{{" not in rendered
