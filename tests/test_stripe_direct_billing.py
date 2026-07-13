from __future__ import annotations

from unittest.mock import MagicMock

import httpx

from cutctx.billing import get_checkout_url, get_portal_url


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


def test_portal_uses_configured_direct_stripe_customer(monkeypatch) -> None:
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_example")
    calls = []

    def fake_get(url, *, params, auth, timeout):  # noqa: ANN001
        calls.append(("get", url, params, auth, timeout))
        response = MagicMock()
        response.json.return_value = {"data": [{"id": "cus_test"}]}
        return response

    def fake_post(url, *, data, auth, timeout):  # noqa: ANN001
        calls.append(("post", url, data, auth, timeout))
        response = MagicMock()
        response.json.return_value = {"url": "https://billing.stripe.com/p/session_test"}
        return response

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)

    assert get_portal_url("buyer@example.com") == "https://billing.stripe.com/p/session_test"
    assert calls[0][1] == "https://api.stripe.com/v1/customers"
    assert calls[1][1] == "https://api.stripe.com/v1/billing_portal/sessions"
    assert calls[1][2]["customer"] == "cus_test"
