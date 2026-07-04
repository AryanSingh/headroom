"""Tests for entitlement tier boundary enforcement.

Validates that every tier boundary correctly denies and allows features.
"""

from __future__ import annotations

import pytest

from cutctx.entitlements import (
    FEATURE_TIERS,
    EntitlementChecker,
    EntitlementError,
    EntitlementTier,
)

# ── Tier boundary matrix ────────────────────────────────────────────────
# For each feature, verify the exact tier boundary:
# - tier below required → denied
# - tier at required → allowed
# - tier above required → allowed


class TestTierBoundaryMatrix:
    """Exhaustive boundary tests for every feature in FEATURE_TIERS."""

    @pytest.mark.parametrize(
        "feature,required_tier",
        list(FEATURE_TIERS.items()),
        ids=[f"{f}-{t.name}" for f, t in FEATURE_TIERS.items()],
    )
    def test_entitled_at_required_tier(self, feature: str, required_tier: EntitlementTier):
        """Feature is allowed at exactly the required tier."""
        checker = EntitlementChecker(required_tier.name.lower())
        assert checker.is_entitled(feature), f"{feature} should be entitled at {required_tier.name}"

    @pytest.mark.parametrize(
        "feature,required_tier",
        [(f, t) for f, t in FEATURE_TIERS.items() if t != EntitlementTier.BUILDER],
        ids=[f"{f}-denied-below" for f, t in FEATURE_TIERS.items() if t != EntitlementTier.BUILDER],
    )
    def test_denied_below_required_tier(self, feature: str, required_tier: EntitlementTier):
        """Feature is denied one tier below the required tier."""
        # One tier below
        tiers = list(EntitlementTier)
        idx = tiers.index(required_tier)
        if idx > 0:
            lower_tier = tiers[idx - 1]
            checker = EntitlementChecker(lower_tier.name.lower())
            assert not checker.is_entitled(feature), (
                f"{feature} should NOT be entitled at {lower_tier.name} (needs {required_tier.name})"
            )


class TestBuilderDeniesAllPaid:
    """Builder tier should deny every paid feature."""

    def test_builder_denies_all_team_features(self):
        c = EntitlementChecker("builder")
        team_features = [f for f, t in FEATURE_TIERS.items() if t == EntitlementTier.TEAM]
        for f in team_features:
            assert not c.is_entitled(f), f"Builder should NOT have {f}"

    def test_builder_denies_all_business_features(self):
        c = EntitlementChecker("builder")
        biz_features = [f for f, t in FEATURE_TIERS.items() if t == EntitlementTier.BUSINESS]
        for f in biz_features:
            assert not c.is_entitled(f), f"Builder should NOT have {f}"

    def test_builder_denies_all_enterprise_features(self):
        c = EntitlementChecker("builder")
        ent_features = [f for f, t in FEATURE_TIERS.items() if t == EntitlementTier.ENTERPRISE]
        for f in ent_features:
            assert not c.is_entitled(f), f"Builder should NOT have {f}"


class TestTeamTier:
    """Team tier should have BUILDER + TEAM features, deny BUSINESS + ENTERPRISE."""

    def test_team_has_builder_plus_team(self):
        c = EntitlementChecker("team")
        for f, t in FEATURE_TIERS.items():
            if t in (EntitlementTier.BUILDER, EntitlementTier.TEAM):
                assert c.is_entitled(f), f"Team should have {f}"

    def test_team_denies_business(self):
        c = EntitlementChecker("team")
        for f, t in FEATURE_TIERS.items():
            if t == EntitlementTier.BUSINESS:
                assert not c.is_entitled(f), f"Team should NOT have {f}"

    def test_team_denies_enterprise(self):
        c = EntitlementChecker("team")
        for f, t in FEATURE_TIERS.items():
            if t == EntitlementTier.ENTERPRISE:
                assert not c.is_entitled(f), f"Team should NOT have {f}"


class TestBusinessTier:
    """Business tier should have BUILDER + TEAM + BUSINESS, deny ENTERPRISE."""

    def test_business_has_lower_tiers(self):
        c = EntitlementChecker("business")
        for f, t in FEATURE_TIERS.items():
            if t in (EntitlementTier.BUILDER, EntitlementTier.TEAM, EntitlementTier.BUSINESS):
                assert c.is_entitled(f), f"Business should have {f}"

    def test_business_denies_enterprise(self):
        c = EntitlementChecker("business")
        for f, t in FEATURE_TIERS.items():
            if t == EntitlementTier.ENTERPRISE:
                assert not c.is_entitled(f), f"Business should NOT have {f}"


class TestEnterpriseTier:
    """Enterprise tier should have everything."""

    def test_enterprise_has_all_features(self):
        c = EntitlementChecker("enterprise")
        for f in FEATURE_TIERS:
            assert c.is_entitled(f), f"Enterprise should have {f}"


class TestRequireEntitledBoundary:
    """Test that require_entitled raises EntitlementError at boundaries."""

    def test_require_entitled_raises_for_builder_on_team_feature(self):
        c = EntitlementChecker("builder")
        with pytest.raises(EntitlementError) as exc_info:
            c.require_entitled("org_analytics")
        assert exc_info.value.feature == "org_analytics"
        assert exc_info.value.required_tier == EntitlementTier.TEAM
        assert exc_info.value.current_tier == EntitlementTier.BUILDER
        msg = str(exc_info.value)
        assert "Team" in msg  # friendly name
        assert "Free" in msg  # friendly name for builder
        assert "Upgrade" in msg

    def test_require_entitled_raises_for_builder_on_enterprise_feature(self):
        c = EntitlementChecker("builder")
        with pytest.raises(EntitlementError) as exc_info:
            c.require_entitled("sso_saml")
        assert exc_info.value.required_tier == EntitlementTier.ENTERPRISE

    def test_require_entitled_raises_for_team_on_enterprise_feature(self):
        c = EntitlementChecker("team")
        with pytest.raises(EntitlementError) as exc_info:
            c.require_entitled("audit_logs")
        assert exc_info.value.required_tier == EntitlementTier.ENTERPRISE
        assert exc_info.value.current_tier == EntitlementTier.TEAM

    def test_require_entitled_raises_for_business_on_enterprise_feature(self):
        c = EntitlementChecker("business")
        with pytest.raises(EntitlementError) as exc_info:
            c.require_entitled("retention_controls")
        assert exc_info.value.required_tier == EntitlementTier.ENTERPRISE
        assert exc_info.value.current_tier == EntitlementTier.BUSINESS

    def test_require_entitled_no_raise_for_correct_tier(self):
        # Team feature at team tier
        c = EntitlementChecker("team")
        c.require_entitled("org_analytics")  # Should not raise

    def test_require_entitled_no_raise_for_higher_tier(self):
        # Team feature at enterprise tier
        c = EntitlementChecker("enterprise")
        c.require_entitled("org_analytics")  # Should not raise


class TestListMissingBoundaries:
    """Test that list_missing correctly identifies gaps between tiers."""

    def test_builder_to_team_gap(self):
        c = EntitlementChecker("builder")
        missing = c.list_missing(EntitlementTier.TEAM)
        team_features = [f for f, t in FEATURE_TIERS.items() if t == EntitlementTier.TEAM]
        for f in team_features:
            assert f in missing, f"Builder missing {f} to reach Team"

    def test_builder_to_enterprise_gap(self):
        c = EntitlementChecker("builder")
        missing = c.list_missing(EntitlementTier.ENTERPRISE)
        # Should include all TEAM + BUSINESS + ENTERPRISE features
        assert len(missing) > 20

    def test_team_to_business_gap(self):
        c = EntitlementChecker("team")
        missing = c.list_missing(EntitlementTier.BUSINESS)
        biz_features = [f for f, t in FEATURE_TIERS.items() if t == EntitlementTier.BUSINESS]
        for f in biz_features:
            assert f in missing, f"Team missing {f} to reach Business"

    def test_team_to_enterprise_gap(self):
        c = EntitlementChecker("team")
        missing = c.list_missing(EntitlementTier.ENTERPRISE)
        ent_features = [f for f, t in FEATURE_TIERS.items() if t == EntitlementTier.ENTERPRISE]
        for f in ent_features:
            assert f in missing, f"Team missing {f} to reach Enterprise"

    def test_enterprise_gap_is_empty(self):
        c = EntitlementChecker("enterprise")
        assert c.list_missing(EntitlementTier.ENTERPRISE) == []


class TestFeatureCount:
    """Verify the total feature count is as expected."""

    def test_total_feature_count(self):
        assert len(FEATURE_TIERS) == 62

    def test_tier_distribution(self):
        counts = {}
        for t in FEATURE_TIERS.values():
            counts[t] = counts.get(t, 0) + 1
        assert counts[EntitlementTier.BUILDER] == 25
        assert counts[EntitlementTier.TEAM] == 9
        assert counts[EntitlementTier.BUSINESS] == 13
        assert counts[EntitlementTier.ENTERPRISE] == 15
