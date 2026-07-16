# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Tests for the egress enforcer + airgap route.

Audit-Deep-2026-06-21 Blocker 3a: the previous airgap module was a
no-op; the route returned a hardcoded payload. These tests pin
the new behavior.
"""

from __future__ import annotations


class TestEgressEnforcer:
    def test_empty_policy_denies_all(self):
        from cutctx.proxy.egress import EgressEnforcer, EgressPolicy

        enforcer = EgressEnforcer(EgressPolicy(policy_id="empty"))
        d = enforcer.check("https://api.anthropic.com/v1/messages")
        assert d.allowed is False
        assert d.reason == "deny_all_empty_allowlist"
        assert d.policy_id == "empty"

    def test_allow_all_passes(self):
        from cutctx.proxy.egress import EgressEnforcer, EgressPolicy

        enforcer = EgressEnforcer(EgressPolicy(policy_id="allow-all", allow_all=True))
        d = enforcer.check("https://anywhere.example.com")
        assert d.allowed is True
        assert d.reason == "allow_all_policy"

    def test_exact_host_match(self):
        from cutctx.proxy.egress import EgressEnforcer, EgressPolicy

        enforcer = EgressEnforcer(
            EgressPolicy(
                policy_id="sub",
                allowed_patterns=("api.anthropic.com",),
            )
        )
        d = enforcer.check("https://api.anthropic.com/v1/messages")
        assert d.allowed is True
        assert d.matched_pattern == "api.anthropic.com"

    def test_path_cannot_impersonate_allowlisted_host(self):
        from cutctx.proxy.egress import EgressEnforcer, EgressPolicy

        enforcer = EgressEnforcer(
            EgressPolicy(
                policy_id="path-bypass",
                allowed_patterns=("api.anthropic.com",),
            )
        )
        d = enforcer.check("https://attacker.example/api.anthropic.com/v1/messages")
        assert d.allowed is False
        assert d.reason == "no_pattern_match"

    def test_exact_host_does_not_match_subdomain(self):
        from cutctx.proxy.egress import EgressEnforcer, EgressPolicy

        enforcer = EgressEnforcer(
            EgressPolicy(
                policy_id="exact",
                allowed_patterns=("api.anthropic.com",),
            )
        )
        d = enforcer.check("https://evil.api.anthropic.com/v1/messages")
        assert d.allowed is False

    def test_explicit_leading_wildcard_matches_subdomains_only(self):
        from cutctx.proxy.egress import EgressEnforcer, EgressPolicy

        enforcer = EgressEnforcer(
            EgressPolicy(
                policy_id="wildcard",
                allowed_patterns=("*.anthropic.com",),
            )
        )
        assert enforcer.check("https://api.anthropic.com/v1/messages").allowed is True
        assert enforcer.check("https://edge.api.anthropic.com/v1/messages").allowed is True
        assert enforcer.check("https://anthropic.com/v1/messages").allowed is False
        assert enforcer.check("https://notanthropic.com/v1/messages").allowed is False

    def test_legacy_origin_pattern_matches_its_host_only(self):
        from cutctx.proxy.egress import EgressEnforcer, EgressPolicy

        enforcer = EgressEnforcer(
            EgressPolicy(
                policy_id="legacy-origin",
                allowed_patterns=("https://api.anthropic.com",),
            )
        )
        assert enforcer.check("https://api.anthropic.com/v1/messages").allowed is True
        assert enforcer.check("https://attacker.example/https://api.anthropic.com").allowed is False

    def test_no_match_denies(self):
        from cutctx.proxy.egress import EgressEnforcer, EgressPolicy

        enforcer = EgressEnforcer(
            EgressPolicy(
                policy_id="narrow",
                allowed_patterns=("api.openai.com",),
            )
        )
        d = enforcer.check("https://api.anthropic.com/v1/messages")
        assert d.allowed is False
        assert d.reason == "no_pattern_match"

    def test_unparseable_url_denies(self):
        from cutctx.proxy.egress import EgressEnforcer, EgressPolicy

        enforcer = EgressEnforcer(
            EgressPolicy(
                policy_id="p",
                allowed_patterns=("anthropic",),
            )
        )
        d = enforcer.check("not a url at all")
        # The input has no URL hostname, so it cannot match an exact host rule.
        assert d.allowed is False

    def test_case_insensitive_match(self):
        from cutctx.proxy.egress import EgressEnforcer, EgressPolicy

        enforcer = EgressEnforcer(
            EgressPolicy(
                policy_id="ci",
                allowed_patterns=("api.anthropic.com",),
            )
        )
        d = enforcer.check("https://API.ANTHROPIC.COM/v1/messages")
        assert d.allowed is True

    def test_regex_pattern_is_not_interpreted(self):
        from cutctx.proxy.egress import EgressEnforcer, EgressPolicy

        enforcer = EgressEnforcer(
            EgressPolicy(
                policy_id="no-regex",
                allowed_patterns=(r".*\.anthropic\.com$", "api.openai.com"),
            )
        )
        assert enforcer.check("https://api.anthropic.com/v1/messages").allowed is False
        d = enforcer.check("https://api.openai.com/v1/chat")
        assert d.allowed is True
        assert d.matched_pattern == "api.openai.com"

    def test_host_normalization_is_case_insensitive_and_ignores_trailing_dot(self):
        from cutctx.proxy.egress import EgressEnforcer, EgressPolicy

        enforcer = EgressEnforcer(
            EgressPolicy(
                policy_id="normalized",
                allowed_patterns=("API.ANTHROPIC.COM.",),
            )
        )
        assert enforcer.check("https://api.anthropic.com./v1/messages").allowed is True


class TestLoadPolicyFromEnv:
    def test_unset_returns_connected_mode_by_default(self, monkeypatch):
        from cutctx.proxy.egress import load_policy_from_env

        monkeypatch.delenv("CUTCTX_EGRESS_POLICY", raising=False)
        p = load_policy_from_env()
        assert p.policy_id == "default-connected"
        assert p.allow_all is True

    def test_unset_returns_empty_in_offline_mode(self, monkeypatch):
        from cutctx.proxy.egress import load_policy_from_env

        monkeypatch.delenv("CUTCTX_EGRESS_POLICY", raising=False)
        monkeypatch.setenv("CUTCTX_OFFLINE_MODE", "1")
        p = load_policy_from_env()
        assert p.policy_id == "default-empty"
        assert p.allow_all is False
        assert p.allowed_patterns == ()

    def test_invalid_json_returns_invalid_marker(self, monkeypatch):
        from cutctx.proxy.egress import load_policy_from_env

        monkeypatch.setenv("CUTCTX_EGRESS_POLICY", "{not valid json")
        p = load_policy_from_env()
        assert p.policy_id == "default-invalid"

    def test_allow_all(self, monkeypatch):
        from cutctx.proxy.egress import load_policy_from_env

        monkeypatch.setenv("CUTCTX_EGRESS_POLICY", '{"allow_all": true}')
        p = load_policy_from_env()
        assert p.allow_all is True

    def test_patterns(self, monkeypatch):
        from cutctx.proxy.egress import load_policy_from_env

        monkeypatch.setenv(
            "CUTCTX_EGRESS_POLICY",
            '{"policy_id": "anthropic-only", "allowed_patterns": ["api.anthropic.com"]}',
        )
        p = load_policy_from_env()
        assert p.policy_id == "anthropic-only"
        assert p.allowed_patterns == ("api.anthropic.com",)


class TestAirgapStatusRoute:
    def test_status_returns_real_policy(self, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from cutctx.proxy.egress import reset_egress_enforcer
        from cutctx.proxy.routes.airgap import create_airgap_router

        reset_egress_enforcer()
        monkeypatch.setenv(
            "CUTCTX_EGRESS_POLICY",
            '{"policy_id": "test", "allowed_patterns": ["api.anthropic.com"]}',
        )
        monkeypatch.setenv("CUTCTX_OFFLINE_MODE", "1")
        reset_egress_enforcer()

        app = FastAPI()
        app.include_router(create_airgap_router())
        # No auth for this test — we just want to verify the
        # status payload reflects the policy.
        client = TestClient(app)
        resp = client.get("/v1/airgap/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["offline_mode"] is True
        assert body["policy_id"] == "test"
        assert body["allowed_patterns"] == ["api.anthropic.com"]
        assert body["is_empty"] is False
        assert body["limits_enforced"] is True

    def test_check_url_against_policy(self, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from cutctx.proxy.egress import reset_egress_enforcer
        from cutctx.proxy.routes.airgap import create_airgap_router

        reset_egress_enforcer()
        monkeypatch.setenv(
            "CUTCTX_EGRESS_POLICY",
            '{"policy_id": "p", "allowed_patterns": ["api.anthropic.com"]}',
        )
        reset_egress_enforcer()

        app = FastAPI()
        app.include_router(create_airgap_router())
        client = TestClient(app)
        # Allowed
        resp = client.post(
            "/v1/airgap/check", json={"url": "https://api.anthropic.com/v1/messages"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["allowed"] is True
        assert body["matched_pattern"] == "api.anthropic.com"
        # Denied
        resp = client.post("/v1/airgap/check", json={"url": "https://example.com"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["allowed"] is False
