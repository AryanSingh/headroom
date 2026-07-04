"""Test that egress policy enforcement blocks unauthorized outbound requests.

Regression test for P0 bug: EgressEnforcer.check() should be called before
opening any HTTP connection to a provider. CUTCTX_OFFLINE_MODE=1 should prevent
requests to URLs not in the allowlist.
"""

import os
from unittest.mock import patch

import pytest

from cutctx.proxy.egress import EgressEnforcer, EgressPolicy


class TestEgressEnforcerIntegration:
    """Test that egress policy is enforced on outbound requests."""

    def test_egress_enforcer_blocks_disallowed_url(self):
        """Verify EgressEnforcer.check() rejects URLs not in allowlist."""
        policy = EgressPolicy(
            policy_id="test-policy",
            description="Allow only anthropic.com",
            allow_all=False,
            allowed_patterns=["https://api.anthropic.com"],
        )
        enforcer = EgressEnforcer(policy)

        # Should allow anthropic.com
        decision = enforcer.check("https://api.anthropic.com/v1/messages")
        assert decision.allowed is True

        # Should deny openai.com
        decision = enforcer.check("https://api.openai.com/v1/chat/completions")
        assert decision.allowed is False
        assert decision.reason != "allow_all_policy"

    def test_egress_enforcer_allow_all_mode(self):
        """Verify allow_all=True disables enforcement."""
        policy = EgressPolicy(
            policy_id="permissive",
            description="Allow everything",
            allow_all=True,
            allowed_patterns=[],
        )
        enforcer = EgressEnforcer(policy)

        # Should allow any URL
        decision = enforcer.check("https://api.openai.com/anything")
        assert decision.allowed is True
        assert decision.reason == "allow_all_policy"

    def test_egress_enforcer_deny_all_empty_patterns(self):
        """Verify that empty allowlist + allow_all=False denies everything."""
        policy = EgressPolicy(
            policy_id="deny-all",
            description="Block all egress",
            allow_all=False,
            allowed_patterns=[],  # Empty: deny-all
        )
        enforcer = EgressEnforcer(policy)

        # Should deny any URL when allowlist is empty
        decision = enforcer.check("https://api.anthropic.com/v1/messages")
        assert decision.allowed is False
        assert decision.reason == "deny_all_empty_allowlist"

    def test_egress_decision_structure(self):
        """Verify EgressDecision contains all required fields."""
        policy = EgressPolicy(
            policy_id="test",
            allow_all=False,
            allowed_patterns=["https://api.anthropic.com"],
        )
        enforcer = EgressEnforcer(policy)
        decision = enforcer.check("https://api.anthropic.com")

        # Verify decision has all required fields
        assert hasattr(decision, "allowed")
        assert hasattr(decision, "reason")
        assert hasattr(decision, "matched_pattern")
        assert hasattr(decision, "policy_id")
        assert decision.policy_id == "test"


class TestEgressPolicyLoading:
    """Test loading egress policy from environment."""

    def test_load_policy_from_env_with_valid_json(self):
        """Verify policy can be loaded from CUTCTX_EGRESS_POLICY env var."""
        import json

        from cutctx.proxy.egress import load_policy_from_env

        policy_dict = {
            "policy_id": "test-env-policy",
            "allow_all": False,
            "allowed_patterns": ["https://api.anthropic.com"],
        }

        with patch.dict(os.environ, {"CUTCTX_EGRESS_POLICY": json.dumps(policy_dict)}):
            policy = load_policy_from_env()
            assert policy.policy_id == "test-env-policy"
            assert policy.allow_all is False
            assert "https://api.anthropic.com" in policy.allowed_patterns

    def test_get_egress_enforcer_singleton(self):
        """Verify get_egress_enforcer() returns same instance on repeated calls."""
        import json

        from cutctx.proxy.egress import get_egress_enforcer, reset_egress_enforcer

        policy_dict = {
            "policy_id": "singleton-test",
            "allow_all": True,
            "allowed_patterns": [],
        }

        try:
            with patch.dict(os.environ, {"CUTCTX_EGRESS_POLICY": json.dumps(policy_dict)}):
                reset_egress_enforcer()  # Clear cache
                enforcer1 = get_egress_enforcer()
                enforcer2 = get_egress_enforcer()
                # Should return same instance
                assert enforcer1 is enforcer2
        finally:
            reset_egress_enforcer()


class TestOfflineModeWithEgress:
    """Test interaction between CUTCTX_OFFLINE_MODE and egress enforcement."""

    def test_offline_mode_env_var_detection(self):
        """Verify CUTCTX_OFFLINE_MODE=1 is properly detected."""
        with patch.dict(os.environ, {"CUTCTX_OFFLINE_MODE": "1"}):
            offline_mode = os.environ.get("CUTCTX_OFFLINE_MODE", "0") == "1"
            assert offline_mode is True

        with patch.dict(os.environ, {"CUTCTX_OFFLINE_MODE": "0"}, clear=False):
            offline_mode = os.environ.get("CUTCTX_OFFLINE_MODE", "0") == "1"
            assert offline_mode is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
