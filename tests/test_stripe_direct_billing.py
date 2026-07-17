from __future__ import annotations

from cutctx.billing import get_checkout_url, get_portal_url


def test_checkout_ignores_legacy_direct_stripe_configuration(monkeypatch) -> None:
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_example")
    monkeypatch.setenv("CUTCTX_STRIPE_PRICE_TEAM_ANNUAL", "price_team_annual")

    assert get_checkout_url(
        "starter",
        email="buyer@example.com",
        billing="annual",
    ) == (
        "https://pitchtoship.com/billing?product=cutctx&plan=starter"
        "&billing=annual&email=buyer%40example.com"
    )


def test_portal_ignores_legacy_direct_stripe_configuration(monkeypatch) -> None:
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_example")

    assert get_portal_url("buyer@example.com") == (
        "https://pitchtoship.com/account?email=buyer%40example.com"
    )
