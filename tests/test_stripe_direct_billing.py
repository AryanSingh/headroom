from __future__ import annotations

from unittest.mock import MagicMock

import httpx

from cutctx.billing import get_checkout_url


def test_checkout_uses_configured_direct_stripe_price(monkeypatch) -> None:
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_example")
    monkeypatch.setenv("CUTCTX_STRIPE_PRICE_TEAM_ANNUAL", "price_team_annual")
    captured = {}

    def fake_post(url, *, data, auth, timeout):  # noqa: ANN001
        captured.update(url=url, data=data, auth=auth, timeout=timeout)
        response = MagicMock()
        response.json.return_value = {"url": "https://checkout.stripe.com/c/pay_test"}
        return response

    monkeypatch.setattr(httpx, "post", fake_post)

    assert get_checkout_url("starter", email="buyer@example.com", billing="annual") == (
        "https://checkout.stripe.com/c/pay_test"
    )
    assert captured["url"] == "https://api.stripe.com/v1/checkout/sessions"
    assert captured["auth"] == ("sk_test_example", "")
    assert captured["data"]["line_items[0][price]"] == "price_team_annual"
    assert captured["data"]["customer_email"] == "buyer@example.com"
