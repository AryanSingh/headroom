from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_commercial_license_surfaces_use_consistent_entity_and_branding() -> None:
    root_license = (PROJECT_ROOT / "LICENSE-COMMERCIAL").read_text(encoding="utf-8")
    ee_license = (PROJECT_ROOT / "cutctx_ee/LICENSE").read_text(encoding="utf-8")

    expected_entity = "Payzli Inc. (operating as Cutctx Labs)"
    assert expected_entity in root_license
    assert expected_entity in ee_license
    assert '"CutCtx"' not in root_license

    expected_legal_entity = "Payzli Inc. (operating as Cutctx Labs)"
    for legal_template in [
        PROJECT_ROOT / "docs/legal/MSA_TEMPLATE.md",
        PROJECT_ROOT / "docs/legal/DPA_TEMPLATE.md",
    ]:
        text = legal_template.read_text(encoding="utf-8")
        assert "Cutctx, Inc." not in text
        assert expected_legal_entity in text

    public_brand_files = [
        PROJECT_ROOT / "docs/pricing.html",
        PROJECT_ROOT / "docs/enterprise.html",
        PROJECT_ROOT / "artifacts/license-portal.html",
        PROJECT_ROOT / "marketing/roi-calculator/index.html",
    ]
    for path in public_brand_files:
        text = path.read_text(encoding="utf-8")
        assert "CutCtx" not in text, f"{path} should use Cutctx branding"


def test_billing_docs_describe_pitchtoship_as_the_single_hosted_checkout_authority() -> None:
    text = (PROJECT_ROOT / "docs/BILLING_INTEGRATION.md").read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    assert "PitchToShip" in text
    assert "Razorpay Standard Checkout" in text
    assert "PITCHTOSHIP_URL" in text
    assert "does not create a Stripe Checkout Session" in normalized


def test_commercial_artifacts_do_not_present_dead_pitchtoship_checkout_as_live() -> None:
    checklist = (PROJECT_ROOT / "artifacts/IMPLEMENTATION_STATUS_CHECKLIST.md").read_text(
        encoding="utf-8"
    )
    portal = (PROJECT_ROOT / "artifacts/license-portal.html").read_text(encoding="utf-8")
    openapi = (PROJECT_ROOT / "artifacts/openapi-management.yaml").read_text(encoding="utf-8")

    assert "PitchToShip-backed" not in checklist
    assert "PitchToShip-managed" not in checklist
    assert (
        "Billing infrastructure works (PitchToShip checkout + license validation)" not in checklist
    )
    assert "https://pitchtoship.com/api/billing/checkout" not in portal
    assert "https://pitchtoship.com/api/billing/checkout" not in openapi


def test_install_docs_do_not_point_to_missing_powershell_installer() -> None:
    files = [
        PROJECT_ROOT / "wiki/docker-install.md",
        PROJECT_ROOT / "docs/content/docs/docker-install.mdx",
    ]

    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "scripts/install.ps1" in text
        assert (
            "https://raw.githubusercontent.com/cutctx/cutctx/main/scripts/install.ps1" not in text
        )


def test_soc2_and_licensing_docs_match_current_audit_chain_wording() -> None:
    roadmap = (PROJECT_ROOT / "gtm/soc2-roadmap.md").read_text(encoding="utf-8")
    migration = (PROJECT_ROOT / "docs/licensing-migration.md").read_text(encoding="utf-8")

    assert "HMAC-SHA256 hash chain" in roadmap
    assert "secret-keyed SHA-256 hash chain" not in roadmap
    assert "configured hosted license service" in migration
    assert "validated via portal" not in migration


def test_security_docs_do_not_assume_universal_customer_portal_flow() -> None:
    policy = (PROJECT_ROOT / "docs/security/SECURITY_POLICY.md").read_text(encoding="utf-8")
    questionnaire = (PROJECT_ROOT / "docs/security/VENDOR_SECURITY_QUESTIONNAIRE.md").read_text(
        encoding="utf-8"
    )

    assert "customer portal." not in policy
    assert "current commercial licensing workflow" in policy
    assert "customer billing portal" not in questionnaire
    assert "Cutctx account portal" not in questionnaire
    assert "operator-managed or management-API workflow" in questionnaire


def test_security_docs_do_not_overclaim_dr_or_pentest_artifacts() -> None:
    questionnaire = (PROJECT_ROOT / "docs/security/VENDOR_SECURITY_QUESTIONNAIRE.md").read_text(
        encoding="utf-8"
    )
    policy = (PROJECT_ROOT / "docs/security/SECURITY_POLICY.md").read_text(encoding="utf-8")

    assert "The DR plan is tested annually." not in questionnaire
    assert "conducts an annual third-party penetration test" not in questionnaire
    assert "The plan is reviewed and tested annually." not in questionnaire
    assert "When a current executive summary is available" in questionnaire
    assert "When a current third-party penetration test executive summary exists" in policy


def test_public_marketing_surfaces_do_not_link_dead_cutctx_sh_domain() -> None:
    public_files = [
        PROJECT_ROOT / "blog/context-compression-101.md",
        PROJECT_ROOT / "blog/cutctx-vs-caching.md",
    ]

    for path in public_files:
        text = path.read_text(encoding="utf-8")
        assert "https://cutctx.sh" not in text, (
            f"{path} should not point public CTAs at the dead cutctx.sh domain"
        )
        assert "https://cutctx.com/docs/quickstart" in text
