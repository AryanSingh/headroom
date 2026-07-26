from pathlib import Path

PUBLIC_PAGES = [
    Path("website/index.html"),
    Path("website/routing/index.html"),
    Path("website/integrations/index.html"),
    Path("website/pricing/index.html"),
    Path("website/docs/index.html"),
    Path("website/security/index.html"),
    Path("website/terms/index.html"),
    Path("website/privacy/index.html"),
    Path("website/refunds/index.html"),
]


def read_page(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_public_legal_pages_do_not_contain_unapproved_legacy_identity():
    pages = [
        Path("website/terms/index.html"),
        Path("website/privacy/index.html"),
        Path("website/refunds/index.html"),
    ]
    assert all(page.exists() for page in pages)
    rendered = "\n".join(page.read_text(encoding="utf-8") for page in pages)
    assert "PITCHTOSHIP (OPC) PRIVATE LIMITED" in rendered
    assert "Muzaffarpur, Bihar 842002, India" in rendered
    assert "hello@aoexl.com" in rendered
    assert "14 days" in rendered
    assert "laws of India" in rendered
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


def test_sitemap_includes_all_cutctx_public_destinations():
    sitemap = Path("website/sitemap.xml").read_text(encoding="utf-8")
    for path in ("/routing/", "/integrations/"):
        assert f"https://cutctx.com{path}" in sitemap


def test_homepage_has_product_and_merchant_disclosure():
    home = Path("website/index.html").read_text(encoding="utf-8")
    assert "Make every agent turn earn its context and its model" in home
    assert "CutCtx is a product of PitchToShip" in home
    assert "OpenAI" in home and "Anthropic" in home and "Amazon Bedrock" in home
    assert "guaranteed" not in home.lower()


def test_pricing_uses_database_backed_checkout_without_payment_secrets():
    pricing = Path("website/pricing/index.html").read_text(encoding="utf-8")
    assert 'src="/assets/pricing.js?v=20260723-inline-checkout"' in pricing
    assert 'data-plan-price="starter"' in pricing
    assert 'data-plan-price="studio"' in pricing
    assert 'data-plan-select="starter"' in pricing
    assert 'data-plan-select="studio"' in pricing
    assert "Razorpay" not in pricing
    assert "RAZORPAY_" not in pricing


def test_pricing_explains_checkout_and_license_management():
    pricing = read_page("website/pricing/index.html")
    assert ">Choose Team<" in pricing
    assert ">Choose Business<" in pricing
    assert "Secure CutCtx checkout" in pricing
    assert 'href="/licenses"' in pricing
    assert "Licenses" in pricing


def test_docs_explains_how_to_activate_and_recover_a_paid_license():
    docs = read_page("website/docs/index.html")
    assert "cutctx license activate &lt;license-key&gt;" in docs
    assert 'href="/licenses/"' in docs


def test_pricing_uses_the_verified_company_contact():
    pricing = Path("website/pricing/index.html").read_text(encoding="utf-8")
    assert "hello@aoexl.com" in pricing
    assert "hello@pitchtoship.com" not in pricing


def test_docs_provides_a_fast_evaluation_path():
    docs = Path("website/docs/index.html").read_text(encoding="utf-8")
    assert "pip install" in docs
    assert "cutctx wrap" in docs
    assert "cutctx savings report" in docs


def test_docs_include_the_verified_routing_status_evaluation():
    docs = read_page("website/docs/index.html")
    assert "cutctx routing status --proxy-url http://127.0.0.1:8787" in docs


def test_public_platform_navigation_and_routes_are_present():
    home = read_page("website/index.html")
    routing = read_page("website/routing/index.html")
    integrations = read_page("website/integrations/index.html")
    for page in (home, routing, integrations):
        assert 'href="/routing/"' in page
        assert 'href="/integrations/"' in page
        assert "CutCtx is a product of PitchToShip" in page


def test_routing_page_uses_only_verified_routing_language():
    routing = read_page("website/routing/index.html")
    assert "codex-gpt54mini-high" in routing
    assert "codex-opencode-slim" in routing
    assert "oh-my-opencode-slim" in routing
    assert "opt-in" in routing.lower()
    assert "capability" in routing.lower()
    assert "guaranteed" not in routing.lower()


def test_integrations_page_maps_verified_access_surfaces():
    integrations = read_page("website/integrations/index.html")
    for label in (
        "Python",
        "TypeScript",
        "Go",
        "MCP",
        "VS Code",
        "JetBrains",
        "OpenAI",
        "Anthropic",
        "Gemini",
    ):
        assert label in integrations
    assert "100+ providers" not in integrations


def test_public_pages_use_self_hosted_platform_fonts():
    css = read_page("website/assets/site.css")
    assert "@font-face" in css
    assert "/assets/fonts/" in css
    assert "fonts.googleapis.com" not in css


def test_platform_font_assets_are_local_and_present():
    for asset in (
        "website/assets/fonts/instrument-sans-latin.woff2",
        "website/assets/fonts/instrument-sans-latin-bold.woff2",
        "website/assets/fonts/jetbrains-mono-latin.woff2",
    ):
        assert Path(asset).exists()


def test_security_page_makes_only_supported_claims():
    security = Path("website/security/index.html").read_text(encoding="utf-8")
    assert "local-first" in security.lower()
    assert "customer-managed local storage" in security.lower()
    assert "SOC 2" not in security
    assert "HIPAA compliant" not in security


def test_public_navigation_reaches_platform_destinations():
    for page in PUBLIC_PAGES:
        html = page.read_text(encoding="utf-8")
        assert 'href="/routing/"' in html
        assert 'href="/integrations/"' in html


def test_public_navigation_exposes_purchase_and_license_management():
    home = read_page("website/index.html")
    pricing = read_page("website/pricing/index.html")
    assert 'href="/pricing/"' in home
    assert 'href="/licenses/' in home
    assert 'href="/licenses' in pricing


def test_pricing_does_not_invent_routing_entitlements():
    pricing = read_page("website/pricing/index.html")
    assert "unlimited routing" not in pricing.lower()
    assert "guaranteed savings" not in pricing.lower()


def test_security_explains_routing_safety_without_certification_claims():
    security = read_page("website/security/index.html")
    assert "capability" in security.lower()
    assert "transport" in security.lower()
    assert "SOC 2 certified" not in security


def test_homepage_uses_evolved_conversion_structure():
    home = read_page("website/index.html")
    assert 'class="hero hero-split"' in home
    assert "data-product-flow" in home
    assert 'id="how-it-works"' in home
    assert all(
        stage in home
        for stage in (
            "Observe",
            "Understand",
            "Compress / Recover",
            "Route or retain",
            "Forward",
            "Measure",
            "Govern",
        )
    )
    assert home.count('data-cta="start-free') >= 3
    assert 'href="/docs/#quick-start"' in home


def test_homepage_positions_routing_as_a_core_capability():
    home = read_page("website/index.html")
    assert "intelligent routing" in home.lower()
    assert 'href="/routing/"' in home
    assert "Route or retain" in home
    assert "codex-gpt54mini-high" in home


def test_homepage_exposes_the_verified_platform_layers():
    home = read_page("website/index.html")
    for label in (
        "Core runtime",
        "Intelligent optimization",
        "Operator layer",
        "Developer and agent access",
        "Optional enterprise controls",
    ):
        assert label in home


def test_homepage_visualization_avoids_unsupported_savings_claims():
    home = read_page("website/index.html")
    assert "Illustrative workflow" in home
    assert "guaranteed" not in home.lower()
    assert "typical savings" not in home.lower()
    assert "% saved" not in home.lower()


def test_homepage_exposes_verified_compatibility():
    home = read_page("website/index.html")
    for label in (
        "OpenAI",
        "Anthropic",
        "Gemini / Vertex",
        "Amazon Bedrock",
        "Claude Code",
        "Codex",
        "Cursor",
    ):
        assert label in home


def test_public_routes_share_the_evolved_shell():
    for page in PUBLIC_PAGES:
        html = page.read_text(encoding="utf-8")
        assert 'class="site-header"' in html
        assert "data-mobile-nav-toggle" in html
        assert 'href="/docs/#quick-start"' in html
        assert 'class="site-footer"' in html
        assert "CutCtx is a product of PitchToShip" in html


def test_public_pages_keep_local_assets_and_semantic_entry_points():
    for page in PUBLIC_PAGES:
        html = page.read_text(encoding="utf-8")
        assert (
            'href="/assets/site.css?v=20260721-platform"' in html
            or 'href="/assets/site.css?v=20260723-inline-checkout"' in html
        )
        assert 'href="/assets/favicon.svg?v=20260721-platform"' in html
        assert 'src="/assets/site.js?v=20260721-platform"' in html
        assert "fonts.googleapis.com" not in html
        assert "fonts.gstatic.com" not in html
        assert 'class="skip-link"' in html
        assert 'id="main-content"' in html


def test_local_favicon_is_present():
    favicon = Path("website/assets/favicon.svg")
    assert favicon.exists()
    assert "<svg" in favicon.read_text(encoding="utf-8")


def test_stylesheet_defines_responsive_accessible_contracts():
    css = read_page("website/assets/site.css")
    assert "prefers-reduced-motion: reduce" in css
    assert "min-height: 2.75rem" in css
    assert "min-height: 2.8rem" in css
    assert ".hero-split" in css
    assert ".product-flow" in css
    assert ".process-grid" in css


def test_pricing_preserves_commerce_and_adds_recommendation_hierarchy():
    pricing = read_page("website/pricing/index.html")
    assert 'class="price-card featured"' in pricing
    assert "Recommended for teams" in pricing
    assert "Start with a measured evaluation" in pricing
    assert 'data-plan-select="starter"' in pricing
    assert 'data-plan-select="studio"' in pricing


def test_pricing_uses_the_two_dollar_introductory_offer_for_paid_plans():
    pricing = read_page("website/pricing/index.html")
    assert pricing.count('data-plan-price=') == 2
    assert "$2 <small>/ month</small>" not in pricing
    assert "$1,500" not in pricing
    assert "$3,500" not in pricing


def test_docs_has_anchorable_install_to_report_flow():
    docs = read_page("website/docs/index.html")
    assert 'id="quick-start"' in docs
    assert 'id="install"' in docs
    assert 'id="wrap"' in docs
    assert 'id="measure"' in docs
    assert "pip install" in docs
    assert "cutctx wrap" in docs
    assert "cutctx savings report" in docs


def test_security_has_trust_flow_and_enterprise_path_without_certification_claims():
    security = read_page("website/security/index.html")
    assert 'class="trust-grid"' in security
    assert "Your environment" in security
    assert "Your provider" in security
    assert "Your retention" in security
    assert "mailto:hello@aoexl.com?subject=CutCtx%20Enterprise" in security
    assert "SOC 2 certified" not in security
    assert "HIPAA compliant" not in security
