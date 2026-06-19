"""Tests for headroom.checkout — checkout redirect and upgrade URLs."""

from __future__ import annotations

from headroom.checkout import checkout_url, pricing_url, support_url, upgrade_url


class TestCheckoutUrl:
    def test_team_checkout(self):
        url = checkout_url("team")
        assert "headroom-team" in url
        assert "pitchtoship.com/checkout" in url

    def test_business_checkout(self):
        url = checkout_url("business")
        assert "headroom-business" in url

    def test_enterprise_checkout(self):
        url = checkout_url("enterprise")
        assert "headroom-enterprise" in url

    def test_checkout_with_org_id(self):
        url = checkout_url("team", org_id="org_123")
        assert "org=org_123" in url
        assert "headroom-team" in url

    def test_unknown_tier_falls_back_to_pricing(self):
        url = checkout_url("unknown_tier")
        assert url == pricing_url()

    def test_case_insensitive(self):
        url = checkout_url("TEAM")
        assert "headroom-team" in url


class TestUpgradeUrl:
    def test_builder_upgrades_to_team(self):
        url = upgrade_url("builder")
        assert "headroom-team" in url

    def test_team_upgrades_to_business(self):
        url = upgrade_url("team")
        assert "headroom-business" in url

    def test_business_upgrades_to_enterprise(self):
        url = upgrade_url("business")
        assert "headroom-enterprise" in url

    def test_enterprise_shows_pricing(self):
        url = upgrade_url("enterprise")
        assert url == pricing_url()

    def test_unknown_tier_suggests_team(self):
        url = upgrade_url("unknown")
        assert "headroom-team" in url

    def test_case_insensitive(self):
        url = upgrade_url("Builder")
        assert "headroom-team" in url


class TestSupportUrl:
    def test_support_email(self):
        url = support_url()
        assert url == "hello@cutctx.dev"


class TestPricingUrl:
    def test_pricing_page(self):
        url = pricing_url()
        assert url == "https://cutctx.dev/pricing"
