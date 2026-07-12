from __future__ import annotations

from pathlib import Path


def test_customer_facing_identity_claims_do_not_advertise_unimplemented_saml() -> None:
    root = Path(__file__).resolve().parents[1]
    customer_facing_files = (
        root / "PRODUCT_GUIDE.md",
        root / "docs" / "enterprise.html",
        root / "docs" / "pricing.html",
        root / "dashboard" / "src" / "pages" / "Docs.jsx",
    )
    unsupported_claims = ("sso/saml", "saml / oidc", "saml integration", "oidc, saml")

    for path in customer_facing_files:
        text = path.read_text(encoding="utf-8").lower()
        assert not any(claim in text for claim in unsupported_claims), path
