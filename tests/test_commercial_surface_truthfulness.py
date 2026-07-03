from __future__ import annotations

from pathlib import Path


def test_commercial_license_surfaces_use_consistent_entity_and_branding() -> None:
    root_license = Path("LICENSE-COMMERCIAL").read_text(encoding="utf-8")
    ee_license = Path("cutctx_ee/LICENSE").read_text(encoding="utf-8")

    expected_entity = "Payzli Inc. (operating as Cutctx Labs)"
    assert expected_entity in root_license
    assert expected_entity in ee_license
    assert '"CutCtx"' not in root_license

    public_brand_files = [
        Path("docs/pricing.html"),
        Path("docs/enterprise.html"),
        Path("artifacts/license-portal.html"),
        Path("marketing/roi-calculator/index.html"),
    ]
    for path in public_brand_files:
        text = path.read_text(encoding="utf-8")
        assert "CutCtx" not in text, f"{path} should use Cutctx branding"


def test_billing_docs_describe_current_hybrid_surface_truthfully() -> None:
    text = Path("docs/BILLING_INTEGRATION.md").read_text(encoding="utf-8")

    assert "Hosted checkout / portal helpers" in text
    assert "Enterprise subscription mapping" in text
    assert "not a single polished self-serve system" in text
    assert "Razorpay" not in text


def test_commercial_artifacts_do_not_present_dead_pitchtoship_checkout_as_live() -> None:
    checklist = Path("artifacts/IMPLEMENTATION_STATUS_CHECKLIST.md").read_text(
        encoding="utf-8"
    )
    portal = Path("artifacts/license-portal.html").read_text(encoding="utf-8")
    openapi = Path("artifacts/openapi-management.yaml").read_text(encoding="utf-8")

    assert "PitchToShip-backed" not in checklist
    assert "PitchToShip-managed" not in checklist
    assert (
        "Billing infrastructure works (PitchToShip checkout + license validation)"
        not in checklist
    )
    assert "https://pitchtoship.com/api/billing/checkout" not in portal
    assert "https://pitchtoship.com/api/billing/checkout" not in openapi


def test_install_docs_do_not_point_to_missing_powershell_installer() -> None:
    files = [
        Path("wiki/docker-install.md"),
        Path("docs/content/docs/docker-install.mdx"),
    ]

    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "scripts/install.ps1" in text
        assert (
            "https://raw.githubusercontent.com/cutctx/cutctx/main/scripts/install.ps1"
            not in text
        )


def test_soc2_and_licensing_docs_match_current_audit_chain_wording() -> None:
    roadmap = Path("gtm/soc2-roadmap.md").read_text(encoding="utf-8")
    migration = Path("docs/licensing-migration.md").read_text(encoding="utf-8")

    assert "secret-keyed SHA-256 hash chain" in roadmap
    assert "HMAC hash chain" not in roadmap
    assert "configured hosted license service" in migration
    assert "validated via portal" not in migration


def test_security_docs_do_not_assume_universal_customer_portal_flow() -> None:
    policy = Path("docs/security/SECURITY_POLICY.md").read_text(encoding="utf-8")
    questionnaire = Path("docs/security/VENDOR_SECURITY_QUESTIONNAIRE.md").read_text(
        encoding="utf-8"
    )

    assert "customer portal." not in policy
    assert "current commercial licensing workflow" in policy
    assert "customer billing portal" not in questionnaire
    assert "Cutctx account portal" not in questionnaire
    assert "operator-managed or management-API workflow" in questionnaire


def test_security_docs_do_not_overclaim_dr_or_pentest_artifacts() -> None:
    questionnaire = Path("docs/security/VENDOR_SECURITY_QUESTIONNAIRE.md").read_text(
        encoding="utf-8"
    )
    policy = Path("docs/security/SECURITY_POLICY.md").read_text(encoding="utf-8")

    assert "The DR plan is tested annually." not in questionnaire
    assert "conducts an annual third-party penetration test" not in questionnaire
    assert "The plan is reviewed and tested annually." not in questionnaire
    assert "When a current executive summary is available" in questionnaire
    assert "When a current third-party penetration test executive summary exists" in policy


def test_public_marketing_surfaces_do_not_link_dead_cutctx_sh_domain() -> None:
    public_files = [
        Path("blog/context-compression-101.md"),
        Path("blog/cutctx-vs-caching.md"),
    ]

    for path in public_files:
        text = path.read_text(encoding="utf-8")
        assert "https://cutctx.sh" not in text, (
            f"{path} should not point public CTAs at the dead cutctx.sh domain"
        )
        assert "https://cutctx.dev/docs/quickstart" in text
