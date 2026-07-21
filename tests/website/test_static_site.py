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


def test_static_delivery_contracts_are_present():
    headers = Path("website/_headers").read_text(encoding="utf-8")
    redirects = Path("website/_redirects").read_text(encoding="utf-8")
    assert "Strict-Transport-Security" in headers
    assert "Content-Security-Policy" in headers
    assert "X-Content-Type-Options: nosniff" in headers
    assert "www.cutctx.com/* https://cutctx.com/:splat 301" in redirects


def test_sitemap_uses_only_cutctx_canonical_urls():
    sitemap = Path("website/sitemap.xml").read_text(encoding="utf-8")
    assert "https://cutctx.com/" in sitemap
    assert "https://www.cutctx.com" not in sitemap
