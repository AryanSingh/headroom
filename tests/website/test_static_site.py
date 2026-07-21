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


def test_homepage_has_product_and_merchant_disclosure():
    home = Path("website/index.html").read_text(encoding="utf-8")
    assert "Reduce LLM context overhead" in home
    assert "CutCtx is a product of PitchToShip" in home
    assert "OpenAI" in home and "Anthropic" in home and "Amazon Bedrock" in home
    assert "guaranteed" not in home.lower()


def test_pricing_routes_to_pitchtoship_without_payment_secrets():
    pricing = Path("website/pricing/index.html").read_text(encoding="utf-8")
    assert "https://pitchtoship.com/billing?product=cutctx&amp;plan=starter&amp;billing=monthly" in pricing
    assert "https://pitchtoship.com/billing?product=cutctx&amp;plan=studio&amp;billing=monthly" in pricing
    assert "Razorpay" not in pricing
    assert "RAZORPAY_" not in pricing


def test_docs_provides_a_fast_evaluation_path():
    docs = Path("website/docs/index.html").read_text(encoding="utf-8")
    assert "pip install" in docs
    assert "cutctx wrap" in docs
    assert "cutctx savings report" in docs


def test_security_page_makes_only_supported_claims():
    security = Path("website/security/index.html").read_text(encoding="utf-8")
    assert "local-first" in security.lower()
    assert "customer-managed local storage" in security.lower()
    assert "SOC 2" not in security
    assert "HIPAA compliant" not in security
