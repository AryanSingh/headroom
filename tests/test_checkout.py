"""Tests for cutctx.checkout — checkout redirect and upgrade URLs."""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest

from cutctx.checkout import checkout_url, pricing_url, support_url, upgrade_url


class TestCheckoutUrl:
    def test_team_checkout(self):
        url = checkout_url("team")
        parsed = urlsplit(url)
        assert parsed.scheme == "https"
        assert parsed.netloc == "pitchtoship.com"
        assert parsed.path == "/billing"
        assert parse_qs(parsed.query) == {
            "product": ["cutctx"],
            "plan": ["starter"],
            "billing": ["annual"],
        }

    def test_business_checkout(self):
        url = checkout_url("business")
        assert "plan=studio" in url

    def test_enterprise_checkout(self):
        url = checkout_url("enterprise")
        assert "plan=portfolio" in url

    @pytest.mark.parametrize(
        ("tier", "plan"),
        [("team", "starter"), ("business", "studio"), ("enterprise", "portfolio")],
    )
    def test_checkout_with_org_id(self, tier: str, plan: str):
        url = checkout_url(tier, org_id="org_123")
        query = parse_qs(urlsplit(url).query)
        assert query["org"] == ["org_123"]
        assert query["plan"] == [plan]

    def test_unknown_tier_falls_back_to_pricing(self):
        url = checkout_url("unknown_tier")
        assert url == pricing_url()

    def test_case_insensitive(self):
        url = checkout_url("TEAM")
        assert "plan=starter" in url


class TestUpgradeUrl:
    def test_builder_upgrades_to_team(self):
        url = upgrade_url("builder")
        assert "plan=starter" in url

    def test_team_upgrades_to_business(self):
        url = upgrade_url("team")
        assert "plan=studio" in url

    def test_business_upgrades_to_enterprise(self):
        url = upgrade_url("business")
        assert "plan=portfolio" in url

    def test_enterprise_shows_pricing(self):
        url = upgrade_url("enterprise")
        assert url == pricing_url()

    def test_unknown_tier_suggests_team(self):
        url = upgrade_url("unknown")
        assert "plan=starter" in url

    def test_case_insensitive(self):
        url = upgrade_url("Builder")
        assert "plan=starter" in url


class TestSupportUrl:
    def test_support_email(self):
        url = support_url()
        assert url == "hello@aoexl.com"


class TestPricingUrl:
    def test_pricing_page(self):
        url = pricing_url()
        assert url == "https://cutctx.com/pricing/"
