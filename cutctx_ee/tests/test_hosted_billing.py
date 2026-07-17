from __future__ import annotations

from cutctx_ee import billing


def test_ee_checkout_is_a_pitchtoship_billing_deep_link(monkeypatch):
    monkeypatch.setattr(billing, "PITCHTOSHIP_BASE_URL", "https://billing.example")

    assert billing.get_checkout_url("studio", "buyer@example.com", "annual") == (
        "https://billing.example/billing?product=cutctx&plan=studio"
        "&billing=annual&email=buyer%40example.com"
    )


def test_ee_portal_is_the_pitchtoship_account_portal(monkeypatch):
    monkeypatch.setattr(billing, "PITCHTOSHIP_BASE_URL", "https://billing.example")

    assert billing.get_portal_url("buyer@example.com") == (
        "https://billing.example/account?email=buyer%40example.com"
    )
