# SPDX-License-Identifier: LicenseRef-Headroom-Commercial
# Copyright (c) 2025-2026 Headroom Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

"""Feature gating by license tier.

Defines which features are available at each tier (builder, team, business,
enterprise) and provides a checker that the proxy uses to enforce entitlements.

Usage:
    from headroom.entitlements import EntitlementChecker

    checker = EntitlementChecker(plan="team")
    if checker.is_entitled("audit_logs"):
        ...  # feature not available at team tier
"""

from __future__ import annotations

import enum
import logging

logger = logging.getLogger("headroom.entitlements")


class EntitlementTier(enum.IntEnum):
    """Tier order — higher value = more features."""

    BUILDER = 0  # Free / OSS
    TEAM = 1
    BUSINESS = 2
    ENTERPRISE = 3

    @classmethod
    def from_str(cls, s: str | None) -> EntitlementTier:
        """Parse a plan string from the license API into a tier."""
        if s is None:
            return cls.BUILDER
        mapping = {
            "builder": cls.BUILDER,
            "oss": cls.BUILDER,
            "free": cls.BUILDER,
            "team": cls.TEAM,
            "business": cls.BUSINESS,
            "enterprise": cls.ENTERPRISE,
            "enterprise_plus": cls.ENTERPRISE,
        }
        return mapping.get(s.lower().strip(), cls.BUILDER)


# ---------------------------------------------------------------------------
# Feature map — minimum tier required for each feature
# ---------------------------------------------------------------------------

FEATURE_TIERS: dict[str, EntitlementTier] = {
    # ── Core compression (always available) ──────────────────────────
    "smart_crusher": EntitlementTier.BUILDER,
    "code_compressor": EntitlementTier.BUILDER,
    "log_compressor": EntitlementTier.BUILDER,
    "diff_compressor": EntitlementTier.BUILDER,
    "search_compressor": EntitlementTier.BUILDER,
    "kompress": EntitlementTier.BUILDER,
    "image_compressor": EntitlementTier.BUILDER,
    "audio_compressor": EntitlementTier.BUILDER,
    "ccr": EntitlementTier.TEAM,
    "ccr_marker": EntitlementTier.TEAM,
    "episodic_memory": EntitlementTier.BUSINESS,
    "cross_agent_memory": EntitlementTier.BUSINESS,
    # ── Deployment modes (always available) ──────────────────────────
    "proxy_mode": EntitlementTier.BUILDER,
    "sdk_mode": EntitlementTier.BUILDER,
    "cli_wrap": EntitlementTier.BUILDER,
    "mcp_mode": EntitlementTier.BUILDER,
    "docker": EntitlementTier.BUILDER,
    # ── Provider support (always available) ──────────────────────────
    "anthropic": EntitlementTier.BUILDER,
    "openai": EntitlementTier.BUILDER,
    "google": EntitlementTier.BUILDER,
    "bedrock": EntitlementTier.BUILDER,
    "vertex": EntitlementTier.BUILDER,
    # ── Agent compatibility (always available) ───────────────────────
    "claude_code": EntitlementTier.BUILDER,
    "codex": EntitlementTier.BUILDER,
    "cursor": EntitlementTier.BUILDER,
    "copilot": EntitlementTier.BUILDER,
    "aider": EntitlementTier.BUILDER,
    # ── Observability (basic) ────────────────────────────────────────
    "dashboard": EntitlementTier.BUILDER,
    "metrics_prometheus": EntitlementTier.BUILDER,
    # ── Team features ────────────────────────────────────────────────
    "live_zone": EntitlementTier.TEAM,
    "org_analytics": EntitlementTier.TEAM,
    "team_analytics": EntitlementTier.TEAM,
    "policy_presets": EntitlementTier.TEAM,
    "usage_reports": EntitlementTier.TEAM,
    "savings_profiles": EntitlementTier.TEAM,
    "budget_controls": EntitlementTier.TEAM,
    # ── Business features ────────────────────────────────────────────
    "project_model": EntitlementTier.BUSINESS,
    "workspace_model": EntitlementTier.BUSINESS,
    "historical_reporting": EntitlementTier.BUSINESS,
    "exportable_reports": EntitlementTier.BUSINESS,
    "rate_limiting": EntitlementTier.BUSINESS,
    "request_logs": EntitlementTier.BUSINESS,
    "compression_hooks": EntitlementTier.BUSINESS,
    "custom_tool_profiles": EntitlementTier.BUSINESS,
    "code_graph": EntitlementTier.BUSINESS,
    "code_aware_compression": EntitlementTier.BUSINESS,
    "traffic_learning": EntitlementTier.BUSINESS,
    # ── Enterprise features ──────────────────────────────────────────
    "sso_saml": EntitlementTier.ENTERPRISE,
    "rbac": EntitlementTier.ENTERPRISE,
    "audit_logs": EntitlementTier.ENTERPRISE,
    "retention_controls": EntitlementTier.ENTERPRISE,
    "air_gap": EntitlementTier.ENTERPRISE,
    "kubernetes": EntitlementTier.ENTERPRISE,
    "helm": EntitlementTier.ENTERPRISE,
    "compliance": EntitlementTier.ENTERPRISE,
    "soc2_reports": EntitlementTier.ENTERPRISE,
    "hipaa_readiness": EntitlementTier.ENTERPRISE,
    "dedicated_support": EntitlementTier.ENTERPRISE,
    "premium_sla": EntitlementTier.ENTERPRISE,
    "onboarding_sessions": EntitlementTier.ENTERPRISE,
    "fleet_management": EntitlementTier.ENTERPRISE,
    "scim": EntitlementTier.ENTERPRISE,
}


class EntitlementChecker:
    """Checks whether a feature is available for the current license plan.

    Defaults to BUILDER (free tier) when no plan is set, ensuring all core
    compression features work out of the box.
    """

    def __init__(self, plan: str | None = None):
        self._tier = EntitlementTier.from_str(plan)
        logger.debug("Entitlement checker initialized: plan=%s tier=%s", plan, self._tier.name)

    @property
    def tier(self) -> EntitlementTier:
        return self._tier

    @property
    def plan_name(self) -> str:
        return self._tier.name.lower()

    def is_entitled(self, feature: str) -> bool:
        """Check if the current plan includes the given feature.

        Returns True if:
        - Feature exists in FEATURE_TIERS and current tier >= required tier
        - Feature does not exist in FEATURE_TIERS (unknown features allowed)

        Returns False if:
        - Feature exists but current tier is below the required tier
        """
        required = FEATURE_TIERS.get(feature)
        if required is None:
            # Unknown feature — deny by default (fail-closed).
            # Prevents accidental exposure of features added after this
            # proxy version was deployed. Operators who intentionally add
            # new features must register them in FEATURE_TIERS.
            logger.warning("Feature '%s' not in entitlement map, denying (fail-closed)", feature)
            return False
        entitled = self._tier >= required
        if not entitled:
            logger.info(
                "Feature '%s' requires tier %s, current tier is %s — denied",
                feature,
                required.name,
                self._tier.name,
            )
        return entitled

    def require_entitled(self, feature: str) -> None:
        """Raise if the feature is not available. Used for hard gates.

        For features not registered in FEATURE_TIERS (unknown features),
        raises EntitlementError with required_tier=ENTERPRISE so the error
        message guides the user to contact sales rather than exposing internals.
        Previously this would raise a bare KeyError — crash instead of a clean gate.
        """
        if not self.is_entitled(feature):
            required_tier = FEATURE_TIERS.get(feature, EntitlementTier.ENTERPRISE)
            raise EntitlementError(
                feature=feature,
                required_tier=required_tier,
                current_tier=self._tier,
            )

    def list_features(self, tier: EntitlementTier | None = None) -> list[str]:
        """List all features available at the given tier (or current tier)."""
        t = tier or self._tier
        return sorted(f for f, req in FEATURE_TIERS.items() if t >= req)

    def list_missing(self, target_tier: EntitlementTier) -> list[str]:
        """List features available at target_tier but not at current tier."""
        current = self.list_features()
        target_checker = EntitlementChecker(target_tier.name.lower())
        target = target_checker.list_features()
        return sorted(set(target) - set(current))


class EntitlementError(Exception):
    """Raised when a feature is not available at the current tier."""

    def __init__(self, feature: str, required_tier: EntitlementTier, current_tier: EntitlementTier):
        self.feature = feature
        self.required_tier = required_tier
        self.current_tier = current_tier
        # Use user-friendly tier names (avoid leaking internal enum names)
        _friendly = {
            EntitlementTier.BUILDER: "Free",
            EntitlementTier.TEAM: "Team",
            EntitlementTier.BUSINESS: "Business",
            EntitlementTier.ENTERPRISE: "Enterprise",
        }
        req_name = _friendly.get(required_tier, required_tier.name)
        cur_name = _friendly.get(current_tier, current_tier.name)
        super().__init__(
            f"Feature '{feature}' requires {req_name} plan "
            f"(current: {cur_name}). "
            f"Upgrade via the PitchToShip billing portal or contact hello@cutctx.dev"
        )
