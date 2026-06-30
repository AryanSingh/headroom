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

        enforcer = EgressEnforcer(
            EgressPolicy(policy_id="allow-all", allow_all=True)
        )
        d = enforcer.check("https://anywhere.example.com")
        assert d.allowed is True
        assert d.reason == "allow_all_policy"

    def test_substring_match(self):
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

    def test_regex_match(self):
        from cutctx.proxy.egress import EgressEnforcer, EgressPolicy

        enforcer = EgressEnforcer(
            EgressPolicy(
                policy_id="regex",
                allowed_patterns=(r".*\.anthropic\.com$",),
            )
        )
        d = enforcer.check("https://api.anthropic.com/v1/messages")
        assert d.allowed is True
        assert d.matched_pattern == r".*\.anthropic\.com$"

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
        # "not a url at all" has no parseable host, so denied.
        # Note: urlparse may extract "not" as the host, which is
        # then matched against the substring "anthropic" -> denied.
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

    def test_invalid_regex_pattern_is_skipped(self):
        from cutctx.proxy.egress import EgressEnforcer, EgressPolicy

        # [unclosed bracket is invalid regex
        enforcer = EgressEnforcer(
            EgressPolicy(
                policy_id="bad",
                allowed_patterns=("[unclosed", "api.openai.com"),
            )
        )
        d = enforcer.check("https://api.openai.com/v1/chat")
        # The first pattern is dropped at construction, but the
        # second still matches.
        assert d.allowed is True
        assert d.matched_pattern == "api.openai.com"


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
            '{"policy_id": "anthropic-only", '
            '"allowed_patterns": ["api.anthropic.com"]}',
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
        resp = client.post("/v1/airgap/check", json={"url": "https://api.anthropic.com/v1/messages"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["allowed"] is True
        assert body["matched_pattern"] == "api.anthropic.com"
        # Denied
        resp = client.post("/v1/airgap/check", json={"url": "https://example.com"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["allowed"] is False
