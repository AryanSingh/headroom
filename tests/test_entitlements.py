"""Tests for headroom.entitlements — feature gating by license tier."""

from __future__ import annotations

import pytest

from headroom.entitlements import (
    FEATURE_TIERS,
    EntitlementChecker,
    EntitlementError,
    EntitlementTier,
)


class TestEntitlementTier:
    def test_from_str_none(self):
        assert EntitlementTier.from_str(None) == EntitlementTier.BUILDER

    def test_from_str_builder(self):
        assert EntitlementTier.from_str("builder") == EntitlementTier.BUILDER
        assert EntitlementTier.from_str("Builder") == EntitlementTier.BUILDER
        assert EntitlementTier.from_str("oss") == EntitlementTier.BUILDER
        assert EntitlementTier.from_str("free") == EntitlementTier.BUILDER

    def test_from_str_team(self):
        assert EntitlementTier.from_str("team") == EntitlementTier.TEAM

    def test_from_str_business(self):
        assert EntitlementTier.from_str("business") == EntitlementTier.BUSINESS

    def test_from_str_enterprise(self):
        assert EntitlementTier.from_str("enterprise") == EntitlementTier.ENTERPRISE
        assert EntitlementTier.from_str("enterprise_plus") == EntitlementTier.ENTERPRISE

    def test_from_str_unknown_defaults_to_builder(self):
        assert EntitlementTier.from_str("unknown_plan") == EntitlementTier.BUILDER

    def test_from_str_whitespace(self):
        assert EntitlementTier.from_str("  team  ") == EntitlementTier.TEAM

    def test_tier_ordering(self):
        assert EntitlementTier.BUILDER < EntitlementTier.TEAM
        assert EntitlementTier.TEAM < EntitlementTier.BUSINESS
        assert EntitlementTier.BUSINESS < EntitlementTier.ENTERPRISE


class TestFeatureTiers:
    def test_all_core_features_are_builder(self):
        core = [
            "smart_crusher", "code_compressor", "log_compressor",
            "diff_compressor", "search_compressor", "kompress",
            "image_compressor", "audio_compressor",
            "ccr", "ccr_marker", "episodic_memory", "cross_agent_memory",
        ]
        for f in core:
            assert FEATURE_TIERS[f] == EntitlementTier.BUILDER, f"{f} should be BUILDER tier"

    def test_team_features_exist(self):
        team_features = ["org_analytics", "team_analytics", "policy_presets"]
        for f in team_features:
            assert FEATURE_TIERS[f] == EntitlementTier.TEAM, f"{f} should be TEAM tier"

    def test_enterprise_features_exist(self):
        ent_features = [
            "sso_saml",
            "rbac",
            "audit_logs",
            "retention_controls",
            "fleet_management",
            "scim",
        ]
        for f in ent_features:
            assert FEATURE_TIERS[f] == EntitlementTier.ENTERPRISE, f"{f} should be ENTERPRISE tier"


class TestEntitlementChecker:
    def test_builder_entitled_to_core(self):
        c = EntitlementChecker("builder")
        assert c.is_entitled("smart_crusher")
        assert c.is_entitled("ccr")
        assert c.is_entitled("proxy_mode")

    def test_builder_not_entitled_to_team(self):
        c = EntitlementChecker("builder")
        assert not c.is_entitled("org_analytics")
        assert not c.is_entitled("policy_presets")

    def test_builder_not_entitled_to_enterprise(self):
        c = EntitlementChecker("builder")
        assert not c.is_entitled("sso_saml")
        assert not c.is_entitled("audit_logs")

    def test_team_entitled_to_team_features(self):
        c = EntitlementChecker("team")
        assert c.is_entitled("org_analytics")
        assert c.is_entitled("policy_presets")

    def test_team_not_entitled_to_enterprise(self):
        c = EntitlementChecker("team")
        assert not c.is_entitled("sso_saml")
        assert not c.is_entitled("rbac")

    def test_enterprise_entitled_to_everything(self):
        c = EntitlementChecker("enterprise")
        for feature in FEATURE_TIERS:
            assert c.is_entitled(feature), f"Enterprise should have {feature}"

    def test_unknown_feature_fail_open(self):
        c = EntitlementChecker("builder")
        assert c.is_entitled("totally_unknown_feature_xyz")

    def test_none_plan_defaults_to_builder(self):
        c = EntitlementChecker(None)
        assert c.tier == EntitlementTier.BUILDER
        assert c.is_entitled("smart_crusher")
        assert not c.is_entitled("org_analytics")

    def test_plan_name(self):
        assert EntitlementChecker("team").plan_name == "team"
        assert EntitlementChecker("enterprise").plan_name == "enterprise"
        assert EntitlementChecker(None).plan_name == "builder"


class TestRequireEntitled:
    def test_raises_when_not_entitled(self):
        c = EntitlementChecker("builder")
        with pytest.raises(EntitlementError) as exc_info:
            c.require_entitled("sso_saml")
        assert exc_info.value.feature == "sso_saml"
        assert exc_info.value.required_tier == EntitlementTier.ENTERPRISE
        assert exc_info.value.current_tier == EntitlementTier.BUILDER

    def test_no_raise_when_entitled(self):
        c = EntitlementChecker("enterprise")
        c.require_entitled("sso_saml")  # Should not raise


class TestListFeatures:
    def test_builder_list(self):
        c = EntitlementChecker("builder")
        features = c.list_features()
        assert "smart_crusher" in features
        assert "org_analytics" not in features
        assert "sso_saml" not in features

    def test_enterprise_list(self):
        c = EntitlementChecker("enterprise")
        features = c.list_features()
        assert "smart_crusher" in features
        assert "org_analytics" in features
        assert "sso_saml" in features

    def test_list_features_sorted(self):
        c = EntitlementChecker("builder")
        features = c.list_features()
        assert features == sorted(features)


class TestListMissing:
    def test_builder_missing_enterprise_features(self):
        c = EntitlementChecker("builder")
        missing = c.list_missing(EntitlementTier.ENTERPRISE)
        assert "sso_saml" in missing
        assert "org_analytics" in missing
        assert "smart_crusher" not in missing

    def test_enterprise_missing_nothing(self):
        c = EntitlementChecker("enterprise")
        missing = c.list_missing(EntitlementTier.ENTERPRISE)
        assert missing == []

    def test_team_missing_enterprise_features(self):
        c = EntitlementChecker("team")
        missing = c.list_missing(EntitlementTier.ENTERPRISE)
        assert "sso_saml" in missing
        assert "org_analytics" not in missing  # Already have it at team
